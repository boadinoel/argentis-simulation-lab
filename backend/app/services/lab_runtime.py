"""Private Simulation Lab lifecycle safeguards. No paid work on page reads."""
import json
import re
import shutil
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import jsonify, request

_locks = {}
_guard = threading.Lock()


def run_options(sim_dir):
    root = Path(sim_dir)
    saved = root / 'run_options.json'
    if saved.exists():
        return json.loads(saved.read_text(encoding='utf-8'))
    state = json.loads((root / 'state.json').read_text(encoding='utf-8'))
    platforms = [p for p in ('twitter', 'reddit') if state.get('enable_' + p)]
    prior = root / 'run_state.json'
    previous = json.loads(prior.read_text(encoding='utf-8')) if prior.exists() else {}
    return {'platform': 'parallel' if len(platforms) == 2 else (platforms or ['reddit'])[0],
            'max_rounds': previous.get('total_rounds') or 10,
            'start_hour': 9, 'enable_graph_memory_update': False}


def validate_options(data, defaults):
    options = {k: data.get(k, v) for k, v in defaults.items()}
    if options['platform'] not in ('reddit', 'twitter', 'parallel'):
        raise ValueError('Choose Reddit, Twitter, or both platforms.')
    for key, low, high in [('max_rounds', 1, 1000), ('start_hour', 0, 23)]:
        value = options[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer between {low} and {high}.')
    if type(options['enable_graph_memory_update']) is not bool:
        raise ValueError('Graph memory must be a JSON boolean.')
    return options


def archive_attempt(root):
    """Copy all evidence before supported cleanup; never touch uploads/graph."""
    root = Path(root)
    dest = root / 'attempts' / datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')
    dest.mkdir(parents=True)
    for path in root.iterdir():
        if path.name == 'attempts':
            continue
        if path.is_dir():
            shutil.copytree(path, dest / path.name)
        else:
            shutil.copy2(path, dest / path.name)
    return dest


def guarded_start(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        from .simulation_runner import SimulationRunner, RunnerStatus
        data = request.get_json(silent=True) or {}
        for key in ('force', 'retry', 'enable_graph_memory_update'):
            if key in data and type(data[key]) is not bool:
                return jsonify(success=False, error=f'{key} must be a JSON boolean'), 400
        sid = data.get('simulation_id', '')
        if not isinstance(sid, str) or not re.fullmatch(r'sim_[A-Za-z0-9_-]{4,64}', sid):
            return jsonify(success=False, error='Invalid simulation ID'), 400
        with _guard:
            lock = _locks.setdefault(sid, threading.RLock())
        with lock:
            root = Path(SimulationRunner.RUN_STATE_DIR) / sid
            if not (root / 'simulation_config.json').exists():
                return jsonify(success=False, error='Prepare this simulation first.'), 400
            current = SimulationRunner.get_run_state(sid)
            if current and current.runner_status not in (RunnerStatus.IDLE, RunnerStatus.FAILED):
                return jsonify(success=True, data=current.to_dict(), already_running=True)
            if current and current.runner_status == RunnerStatus.FAILED and data.get('retry') is not True:
                return jsonify(success=False, error='This attempt failed. Use the explicit Retry button.'), 409
            try:
                options = validate_options(data, run_options(root))
                for platform in ('twitter', 'reddit'):
                    if options['platform'] in (platform, 'parallel'):
                        # Upstream uses CSV for Twitter and JSON for Reddit.
                        suffix = 'csv' if platform == 'twitter' else 'json'
                        if not (root / f'{platform}_profiles.{suffix}').exists():
                            raise ValueError(f'Prepare {platform} personas before selecting that platform.')
            except (ValueError, KeyError) as error:
                return jsonify(success=False, error=str(error)), 400
            if current and current.runner_status == RunnerStatus.FAILED:
                process = SimulationRunner._processes.get(sid)
                if process and process.poll() is None:
                    return jsonify(success=False, error='Stop the previous worker before retrying.'), 409
                archive_attempt(root)
                result = SimulationRunner.cleanup_simulation_logs(sid)
                if not result['success']:
                    return jsonify(success=False, error='Previous attempt cleanup failed; archive retained.'), 500
            (root / 'run_options.json').write_text(json.dumps(options), encoding='utf-8')
            config_file = root / 'simulation_config.json'
            config = json.loads(config_file.read_text(encoding='utf-8'))
            config.setdefault('time_config', {})['start_hour'] = options['start_hour']
            config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            data.update(options)
            data['force'] = False
            # Flask's cached request JSON is the same object read by the route.
            return fn(*args, **kwargs)
    return wrapped
