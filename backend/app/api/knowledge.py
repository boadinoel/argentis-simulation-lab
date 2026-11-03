from flask import jsonify,request
from . import graph_bp
from ..models.project import ProjectManager
from ..services import knowledge_workspace as knowledge
from ..utils.zep_lifecycle import graph_lifecycle_lock


@graph_bp.route('/project/<pid>/knowledge',methods=['GET','POST'])
def project_knowledge(pid):
    try:
        knowledge.project_root(pid)
        project=ProjectManager.get_project(pid)
        if not project:return jsonify(success=False,error='Project not found'),404
        if request.method=='GET':return jsonify(success=True,data=knowledge.public_state(pid))
        if not project.graph_id:return jsonify(success=False,error='Build this graph first.'),409
        with graph_lifecycle_lock(project.graph_id):
            update,reused=knowledge.submit(project,request.files.getlist('files'),request.form.get('title',''),request.form.get('source_date',''),request.form.get('note',''))
        if not reused:knowledge.launch(pid,update['update_id'])
        return jsonify(success=True,data={'update_id':update['update_id'],'reused':reused,**knowledge.public_state(pid)})
    except ValueError as error:return jsonify(success=False,error=str(error)),409


@graph_bp.route('/project/<pid>/knowledge/<uid>/resume',methods=['POST'])
def resume_knowledge(pid,uid):
    try:
        if not any(u['update_id']==uid for u in knowledge.state(pid)['updates']):
            return jsonify(success=False,error='Update not found'),404
        knowledge.launch(pid,uid)
        return jsonify(success=True,data=knowledge.public_state(pid))
    except ValueError as error:return jsonify(success=False,error=str(error)),400
