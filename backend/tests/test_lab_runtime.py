import json
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request
import pytest

from app.services.lab_runtime import guarded_start, archive_attempt, validate_options, run_options
from app.services.simulation_runner import SimulationRunner, SimulationRunState, RunnerStatus


@pytest.fixture
def lab(tmp_path, monkeypatch):
    sid = 'sim_labtest'
    root = tmp_path / sid
    root.mkdir()
    (root / 'state.json').write_text(json.dumps({'enable_reddit': True, 'enable_twitter': False}))
    (root / 'simulation_config.json').write_text('{"time_config":{}}')
    (root / 'reddit_profiles.json').write_text('[]')
    monkeypatch.setattr(SimulationRunner, 'RUN_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(SimulationRunner, '_run_states', {})
    monkeypatch.setattr(SimulationRunner, '_sync_simulation_status', classmethod(lambda *a: None))
    app = Flask(__name__)
    calls = []

    @app.post('/start')
    @guarded_start
    def start():
        calls.append(dict(request.get_json()))
        state = SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.RUNNING)
        SimulationRunner._save_run_state(state)
        return jsonify(success=True, data=state.to_dict())

    return app, sid, root, calls


def test_concurrent_start_launches_once_and_preserves_settings(lab):
    app, sid, root, calls = lab
    def send(_):
        with app.test_client() as client:
            return client.post('/start', json={'simulation_id': sid, 'max_rounds': 4}).status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        assert list(pool.map(send, range(5))) == [200] * 5
    assert len(calls) == 1
    assert calls[0]['platform'] == 'reddit'
    assert calls[0]['force'] is False
    assert calls[0]['enable_graph_memory_update'] is False
    assert run_options(root)['max_rounds'] == 4


def test_completed_start_is_read_only(lab):
    app, sid, root, calls = lab
    state = SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.COMPLETED)
    SimulationRunner._save_run_state(state)
    with app.test_client() as client:
        assert client.post('/start', json={'simulation_id': sid, 'force': True}).status_code == 200
    assert not calls


def test_stale_running_becomes_failed_and_retry_archives(lab):
    app, sid, root, calls = lab
    SimulationRunner._save_run_state(SimulationRunState(simulation_id=sid, runner_status=RunnerStatus.RUNNING))
    SimulationRunner._run_states.clear()
    assert SimulationRunner.get_run_state(sid).runner_status == RunnerStatus.FAILED
    (root / 'simulation.log').write_text('original evidence')
    with app.test_client() as client:
        assert client.post('/start', json={'simulation_id': sid}).status_code == 409
        assert client.post('/start', json={'simulation_id': sid, 'retry': True}).status_code == 200
    archived = list((root / 'attempts').glob('*/simulation.log'))
    assert len(archived) == 1
    assert archived[0].read_text() == 'original evidence'


@pytest.mark.parametrize('bad', [{'max_rounds': True}, {'max_rounds': 0}, {'start_hour': 24}, {'enable_graph_memory_update': 'false'}])
def test_invalid_options_fail_visibly(lab, bad):
    _, _, root, _ = lab
    with pytest.raises(ValueError):
        validate_options(bad, run_options(root))


def test_parallel_completion_waits_for_other_platform(lab):
    _, sid, root, _ = lab
    (root / 'reddit').mkdir()
    (root / 'reddit' / 'actions.jsonl').write_text('')
    state = SimulationRunState(simulation_id=sid, reddit_completed=True, twitter_running=True)
    assert not SimulationRunner._check_all_platforms_completed(state)


def test_single_platform_is_already_prepared(lab, monkeypatch):
    from app.api import simulation as api
    _, sid, root, _ = lab
    monkeypatch.setattr(api.Config, 'OASIS_SIMULATION_DATA_DIR', str(root.parent))
    (root / 'state.json').write_text(json.dumps({'enable_reddit': True, 'enable_twitter': False, 'status': 'failed', 'config_generated': True}))
    prepared, _ = api._check_simulation_prepared(sid)
    assert prepared


def test_foreign_graph_is_rejected(monkeypatch):
    from types import SimpleNamespace
    from app.api import simulation as api
    monkeypatch.setattr(api.ProjectManager, 'get_project', lambda _: SimpleNamespace(graph_id='graph_owned'))
    app = Flask(__name__)
    with app.test_request_context(json={'project_id': 'proj_test', 'graph_id': 'graph_unrelated'}):
        response, status = api.create_simulation()
        assert status == 400
        assert 'selected project' in response.get_json()['error']
