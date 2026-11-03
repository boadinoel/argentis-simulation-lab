"""Additive, journaled research updates to a project's existing Zep graph."""
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..models.project import ProjectManager, ProjectStatus
from ..utils.file_parser import FileParser
from ..utils.zep_lifecycle import graph_lifecycle_lock
from .graph_builder import GraphBuilderService, BatchSubmission
from .text_processor import TextProcessor


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def project_root(pid):
    if not re.fullmatch(r'proj_[A-Za-z0-9_-]{4,64}', pid):
        raise ValueError('Invalid project ID')
    return Path(ProjectManager.PROJECTS_DIR) / pid


def state(pid):
    path = project_root(pid) / 'knowledge/state.json'
    return json.loads(path.read_text()) if path.exists() else {'revision': 1, 'revisions': [], 'updates': []}


def busy(pid):
    return [u for u in state(pid)['updates'] if u['status'] != 'completed']


def assert_available(pid):
    if busy(pid):
        raise ValueError('This project has an unfinished knowledge update. Check its update history before preparing another run or report.')


def public_state(pid):
    s = state(pid)
    return {'revision': s['revision'], 'revisions': s['revisions'],
            'updates': [{k: u.get(k) for k in ('update_id','title','source_date','created_at','status','message','revision','files','batch_id')} for u in s['updates']]}


def _save(pid, s):
    atomic_json(project_root(pid) / 'knowledge/state.json', s)


def _patch(pid, uid, **values):
    project = ProjectManager.get_project(pid)
    with graph_lifecycle_lock(project.graph_id):
        s = state(pid)
        u = next(u for u in s['updates'] if u['update_id'] == uid)
        u.update(values)
        _save(pid, s)
        return dict(u)


def pin_simulation(project, simulation_dir, objective=None):
    """Record the knowledge used for preparation without rewriting old runs."""
    assert_available(project.project_id)
    root = Path(simulation_dir)
    s = state(project.project_id)
    text = ProjectManager.get_extracted_text(project.project_id) or ''
    if objective is not None and (not isinstance(objective,str) or not objective.strip() or len(objective)>20000):
        raise ValueError('Scenario objective must contain 1–20,000 characters.')
    manifest = {'project_id': project.project_id, 'graph_id': project.graph_id,
                'knowledge_revision': s['revision'], 'document_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'captured_at': now(), 'source_policy': 'Uploaded research; simulation outputs are not source facts.'}
    atomic_json(root / 'source_manifest.json', manifest)
    (root / 'source_text_snapshot.txt').write_text(text, encoding='utf-8')
    atomic_json(root / 'scenario.json', {'objective': objective or project.simulation_requirement, 'knowledge_revision': s['revision']})
    return manifest


def verify_revision(project, simulation_dir):
    assert_available(project.project_id)
    path = Path(simulation_dir) / 'source_manifest.json'
    if path.exists():
        revision = json.loads(path.read_text()).get('knowledge_revision', 1)
        if revision != state(project.project_id)['revision']:
            raise ValueError('This run uses an older knowledge revision. Its saved results remain available; create a new scenario to prepare or report against the updated graph.')


def scenario_objective(project, simulation_dir):
    path=Path(simulation_dir)/'scenario.json'
    return (json.loads(path.read_text()).get('objective') if path.exists() else None) or project.simulation_requirement


def guard_preparation(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args,**kwargs):
        from flask import request,jsonify
        from .simulation_manager import SimulationManager
        simulation=SimulationManager().get_simulation((request.get_json(silent=True) or {}).get('simulation_id',''))
        if not simulation:return fn(*args,**kwargs)
        with graph_lifecycle_lock(simulation.graph_id):
            try:assert_available(simulation.project_id)
            except ValueError as error:return jsonify(success=False,error=str(error)),409
            return fn(*args,**kwargs)
    return wrapped


def _initialize(project, s):
    root = project_root(project.project_id) / 'knowledge'
    baseline = root / 'revisions/0001'
    if not baseline.exists():
        baseline.mkdir(parents=True)
        text = ProjectManager.get_extracted_text(project.project_id) or ''
        (baseline / 'text.txt').write_text(text, encoding='utf-8')
        atomic_json(baseline / 'files.json', project.files)
    if not s['revisions']:
        text = (baseline / 'text.txt').read_text(encoding='utf-8')
        s['revisions'] = [{'revision':1,'title':'Original research','created_at':project.created_at,'graph_id':project.graph_id,'document_sha256':hashlib.sha256(text.encode()).hexdigest()}]


def submit(project, uploaded, title, source_date, note):
    """Called under the graph lock. Validate and journal before any cloud mutation."""
    from ..api.graph import _active_graph_consumers
    if project.status != ProjectStatus.GRAPH_COMPLETED or not project.graph_id:
        raise ValueError('Build this project graph before adding research.')
    if not title.strip() or len(title) > 200:
        raise ValueError('Provide an update title of 1–200 characters.')
    if source_date:
        from datetime import date
        date.fromisoformat(source_date)
    if len(note) > 5000 or not 1 <= len(uploaded) <= 10:
        raise ValueError('Upload 1–10 documents and keep notes under 5,000 characters.')
    blobs = []
    for file in uploaded:
        name = Path(file.filename or '').name
        ext = Path(name).suffix.lower()
        if ext not in ('.pdf','.md','.txt','.markdown'):
            raise ValueError('Research documents must be PDF, Markdown or text.')
        data = file.read()
        if not data:
            raise ValueError('Empty document: ' + name)
        blobs.append((name, ext, data, hashlib.sha256(data).hexdigest()))
    digest = hashlib.sha256('|'.join(sorted(b[3] for b in blobs)).encode()).hexdigest()
    uid = 'upd_' + digest[:20]
    s = state(project.project_id)
    existing = next((u for u in s['updates'] if u['update_id'] == uid), None)
    if existing:
        return existing, True
    if busy(project.project_id) or _active_graph_consumers(project.graph_id):
        raise ValueError('Wait for active simulations/reports or finish the previous knowledge update first.')
    existing_hashes = {hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ProjectManager.get_project_files(project.project_id)}
    existing_hashes.update(f['sha256'] for u in s['updates'] for f in u.get('files', []))
    if len({b[3] for b in blobs}) != len(blobs) or any(b[3] in existing_hashes for b in blobs):
        raise ValueError('A document is already present in this project or repeated in this upload. Upload only new research.')
    _initialize(project, s)
    folder = project_root(project.project_id) / 'knowledge/updates' / uid
    folder.mkdir(parents=True, exist_ok=True)
    texts, files = [], []
    for name, ext, data, sha in blobs:
        path = folder / (sha + ext)
        path.write_bytes(data)
        text = TextProcessor.preprocess_text(FileParser.extract_text(str(path)))
        if not text.strip():
            raise ValueError('No readable text in ' + name)
        texts.append(f'SOURCE: {name}\nSOURCE DATE: {source_date or "not specified"}\n{text}')
        files.append({'filename':name,'size':len(data),'sha256':sha,'stored_name':path.name})
    text = '\n\n'.join(texts)
    (folder / 'text.txt').write_text(f'RESEARCH UPDATE: {title}\nINGESTED: {now()}\nOPERATOR NOTE (not independently verified): {note}\n\n'+text, encoding='utf-8')
    chunks = _chunks(folder)
    GraphBuilderService.validate_batch_chunks(chunks)
    u = {'update_id':uid,'title':title,'source_date':source_date,'created_at':now(),'files':files,'status':'queued','message':'Research update queued.','batch_id':None,'item_count':len(chunks)}
    s['updates'].append(u)
    _save(project.project_id,s)
    return u, False


def _chunks(folder):
    # Source metadata travels with every chunk, not just the first one.
    text = (folder/'text.txt').read_text(encoding='utf-8')
    return [f'Research update {folder.name}. Source provenance is recorded in the project update history.\n{c}' for c in TextProcessor.split_text(text,chunk_size=1200,overlap=80)]


def _finish(project, u, graph):
    pid = project.project_id
    with graph_lifecycle_lock(project.graph_id):
        s = state(pid)
        u = next(x for x in s['updates'] if x['update_id']==u['update_id'])
        if u['status']=='completed': return
        revision = s['revision'] + 1
        folder=project_root(pid)/'knowledge'
        base=(folder/'revisions/0001/text.txt').read_text(encoding='utf-8')
        included=[x for x in s['updates'] if x['status']=='completed' or x['update_id']==u['update_id']]
        text=base+'\n\n'+'\n\n'.join((folder/'updates'/x['update_id']/'text.txt').read_text(encoding='utf-8') for x in included)
        files=json.loads((folder/'revisions/0001/files.json').read_text())
        files += [{**f,'knowledge_update_id':x['update_id']} for x in included for f in x['files']]
        target=folder/'revisions'/f'{revision:04d}'
        target.mkdir(parents=True,exist_ok=True)
        (target/'text.txt').write_text(text,encoding='utf-8')
        atomic_json(target/'graph.json',graph)
        # Rebuilding the cumulative local text from immutable inputs is idempotent.
        ProjectManager.save_extracted_text(pid,text)
        project=ProjectManager.get_project(pid)
        project.files=files;project.total_text_length=len(text)
        ProjectManager.save_project(project)
        u.update(status='completed',message='Research added to the existing graph.',revision=revision)
        s['revision']=revision
        s['revisions'].append({'revision':revision,'title':u['title'],'created_at':now(),'update_id':u['update_id'],'graph_id':project.graph_id,'document_sha256':hashlib.sha256(text.encode()).hexdigest(),'nodes':len(graph.get('nodes',[])),'edges':len(graph.get('edges',[]))})
        _save(pid,s)


_workers=set()
_workers_lock=threading.Lock()


def launch(pid, uid):
    with _workers_lock:
        if (pid,uid) in _workers: return
        _workers.add((pid,uid))
    threading.Thread(target=_worker,args=(pid,uid),daemon=True).start()


def _worker(pid, uid):
    try:
        project=ProjectManager.get_project(pid)
        u=next(x for x in state(pid)['updates'] if x['update_id']==uid)
        if u['status']=='completed': return
        builder=GraphBuilderService()
        folder=project_root(pid)/'knowledge/updates'/uid
        chunks=_chunks(folder)
        if u['status'] in ('queued','preparing'):
            _patch(pid,uid,status='preparing',message='Saving the previous graph revision.')
            previous=project_root(pid)/'knowledge/revisions'/f'{state(pid)["revision"]:04d}'/'graph.json'
            if not previous.exists():atomic_json(previous,builder.get_graph_data(project.graph_id))
            _patch(pid,uid,status='submitting',message='Submitting new research; existing graph is retained.')
            def remember(batch_id,operation_id):
                _patch(pid,uid,batch_id=batch_id,operation_id=operation_id)
            submission=builder.add_text_batches(project.graph_id,chunks,batch_created_callback=remember)
            u=_patch(pid,uid,status='processing',batch_id=submission.batch_id,operation_id=submission.operation_id,message='Zep is processing the research update.')
        else:
            # Recovery is read-only: never blindly replay add/process mutations.
            if not u.get('batch_id'):
                raise RuntimeError('Submission state is uncertain. No mutation was replayed; operator reconciliation is required.')
            summary=builder.get_batch_summary(u['batch_id'])
            if getattr(summary,'status',None)=='draft':
                raise RuntimeError('The recorded batch is still a draft. No mutation was replayed; operator reconciliation is required.')
            submission=BatchSubmission(batch_id=u['batch_id'],operation_id=u.get('operation_id',''),episode_uuids=[],item_count=u['item_count'])
        builder._wait_for_batch(submission)
        _finish(project,u,builder.get_graph_data(project.graph_id))
    except Exception as error:
        _patch(pid,uid,status='needs_review',message='Update is incomplete; graph may contain partial new research. '+str(error))
    finally:
        with _workers_lock:_workers.discard((pid,uid))
