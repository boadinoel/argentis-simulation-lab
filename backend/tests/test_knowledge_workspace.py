import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from werkzeug.datastructures import FileStorage
from app.models.project import ProjectManager,ProjectStatus
from app.services import knowledge_workspace as k


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    from app.api import graph
    monkeypatch.setattr(ProjectManager,'PROJECTS_DIR',str(tmp_path/'projects'))
    monkeypatch.setattr(graph,'_active_graph_consumers',lambda _:[])
    p=ProjectManager.create_project('Independent test')
    p.status=ProjectStatus.GRAPH_COMPLETED;p.graph_id='graph_owned';p.simulation_requirement='Original objective'
    p.files=[{'filename':'original.txt','size':8}]
    ProjectManager.save_project(p)
    ProjectManager.save_extracted_text(p.project_id,'ORIGINAL')
    (Path(ProjectManager._get_project_files_dir(p.project_id))/'original.txt').write_text('ORIGINAL')
    calls=[]
    class Builder:
        validate_batch_chunks=staticmethod(k.GraphBuilderService.validate_batch_chunks)
        fail=False
        def get_graph_data(self,gid):return {'nodes':[{'uuid':'old'}]+([{'uuid':'new'}] if calls else []),'edges':[]}
        def add_text_batches(self,gid,chunks,batch_created_callback):
            calls.append((gid,chunks));batch_created_callback('batch_saved','operation_saved')
            return SimpleNamespace(batch_id='batch_saved',operation_id='operation_saved')
        def _wait_for_batch(self,submission):
            if self.fail:raise TimeoutError('still processing')
        def get_batch_summary(self,bid):return SimpleNamespace(status='succeeded')
    monkeypatch.setattr(k,'GraphBuilderService',Builder)
    return p,calls,Builder


def upload(content=b'NEW research',name='new.txt'):
    return [FileStorage(stream=io.BytesIO(content),filename=name)]


def test_additive_update_preserves_graph_original_and_snapshots(workspace,tmp_path):
    p,calls,_=workspace
    sim=tmp_path/'simulation';sim.mkdir()
    k.pin_simulation(p,sim,'Different objective')
    u,reused=k.submit(p,upload(),'New evidence','2026-11-03','Correction is explicitly identified.')
    assert not reused and k.busy(p.project_id)
    k._worker(p.project_id,u['update_id'])
    assert calls[0][0]=='graph_owned'
    assert k.state(p.project_id)['revision']==2
    assert not k.busy(p.project_id)
    assert ProjectManager.get_project(p.project_id).graph_id=='graph_owned'
    text=ProjectManager.get_extracted_text(p.project_id)
    assert 'ORIGINAL' in text and 'NEW research' in text
    assert (k.project_root(p.project_id)/'knowledge/revisions/0001/text.txt').read_text()=='ORIGINAL'
    assert (sim/'source_text_snapshot.txt').read_text()=='ORIGINAL'
    with pytest.raises(ValueError,match='older knowledge'):k.verify_revision(p,sim)
    assert k.scenario_objective(p,sim)=='Different objective'
    assert ProjectManager.get_project(p.project_id).simulation_requirement=='Original objective'


def test_duplicate_upload_does_not_submit_again(workspace):
    p,calls,_=workspace
    first,_=k.submit(p,upload(),'first','','')
    second,reused=k.submit(p,upload(),'changed title','','')
    assert reused and first['update_id']==second['update_id']
    k._worker(p.project_id,first['update_id'])
    k._worker(p.project_id,first['update_id'])
    assert len(calls)==1 and k.state(p.project_id)['revision']==2


def test_original_document_duplicate_rejected(workspace):
    p,_,_=workspace
    with pytest.raises(ValueError,match='already present'):k.submit(p,upload(b'ORIGINAL'),'duplicate','','')


def test_failed_wait_resumes_saved_batch_without_replay(workspace):
    p,calls,builder=workspace
    u,_=k.submit(p,upload(),'first','','')
    builder.fail=True;k._worker(p.project_id,u['update_id'])
    assert k.busy(p.project_id)[0]['status']=='needs_review'
    with pytest.raises(ValueError):k.submit(p,upload(b'OTHER'),'second','','')
    builder.fail=False;k._worker(p.project_id,u['update_id'])
    assert len(calls)==1 and k.state(p.project_id)['revision']==2


def test_ambiguous_submission_never_replayed(workspace):
    p,calls,_=workspace
    u,_=k.submit(p,upload(),'first','','')
    k._patch(p.project_id,u['update_id'],status='submitting',batch_id=None)
    k._worker(p.project_id,u['update_id'])
    assert calls==[] and k.busy(p.project_id)[0]['status']=='needs_review'


def test_active_simulation_blocks_update(workspace,monkeypatch):
    from app.api import graph
    p,_,_=workspace
    monkeypatch.setattr(graph,'_active_graph_consumers',lambda _:['active_simulation'])
    with pytest.raises(ValueError,match='active simulations'):k.submit(p,upload(),'first','','')


def test_unrelated_project_is_unchanged(workspace):
    p,_,_=workspace
    other=ProjectManager.create_project('Unrelated');other.graph_id='graph_other';ProjectManager.save_project(other)
    ProjectManager.save_extracted_text(other.project_id,'UNRELATED')
    u,_=k.submit(p,upload(),'first','','');k._worker(p.project_id,u['update_id'])
    assert ProjectManager.get_extracted_text(other.project_id)=='UNRELATED'
    assert k.state(other.project_id)['revision']==1


@pytest.mark.parametrize('pid',['../escape','proj_a/../../escape'])
def test_invalid_project_path_rejected(pid):
    with pytest.raises(ValueError):k.project_root(pid)
