import asyncio
import base64
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from visual_study import image_parts, stage_prompt, run_round


def study(tmp_path):
    Image.new('RGB', (8, 8), 'blue').save(tmp_path / 'portrait.png')
    return {'version': 1, 'images': ['portrait.png'], 'rounds': [
        {'prompt': 'Evaluate only these images.'},
        {'prompt': 'DELAYED_DISCLOSURE_5FT8: reconsider only your own answer.'}]}


def test_image_parts_are_real_bytes_with_hashes(tmp_path):
    cfg = study(tmp_path)
    parts, receipts = image_parts(tmp_path, cfg['images'])
    assert parts[0]['type'] == 'image_url'
    assert base64.b64decode(parts[0]['image_url']['url'].split(',')[1]) == (tmp_path / 'portrait.png').read_bytes()
    assert len(receipts[0]['sha256']) == 64


@pytest.mark.parametrize('names', [[], ['../outside.png'], ['/etc/passwd'], ['https://example.com/a.jpg']])
def test_images_cannot_escape_private_directory(tmp_path, names):
    with pytest.raises((ValueError, FileNotFoundError)):
        image_parts(tmp_path, names)


def test_first_prompt_cannot_read_future_disclosure(tmp_path):
    cfg = study(tmp_path)
    assert 'DELAYED_DISCLOSURE' not in stage_prompt(cfg, 0, [])
    assert 'DELAYED_DISCLOSURE' in stage_prompt(cfg, 1, [{'response': 'my own answer'}])
    with pytest.raises(ValueError):
        stage_prompt(cfg, 2, [])


def test_native_round_has_images_own_history_only_and_textual_saved_history(tmp_path, monkeypatch):
    cfg = study(tmp_path)
    db = tmp_path / 'reddit_simulation.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE trace (user_id INTEGER, action TEXT, info TEXT)')
    class Action:
        def __init__(self, action_type, action_args):
            self.action_type, self.action_args = action_type, action_args
    monkeypatch.setitem(sys.modules, 'oasis', SimpleNamespace(ManualAction=Action, ActionType=SimpleNamespace(INTERVIEW='interview')))
    captured = []
    class Env:
        async def step(self, actions):
            with sqlite3.connect(db) as conn:
                for uid, action in actions.items():
                    content = action.action_args['prompt']
                    assert content[1]['type'] == 'image_url'
                    captured.append((uid, content[0]['text']))
                    conn.execute('INSERT INTO trace VALUES (?,?,?)', (uid, 'interview', json.dumps({'prompt': content, 'response': f'OWN_RESPONSE_{uid}'})))
    graph = SimpleNamespace(get_agents=lambda: [(0, 0), (1, 1)])
    config = {'visual_study': cfg}
    asyncio.run(run_round(Env(), graph, config, 0, tmp_path, 'reddit'))
    assert all('DELAYED_DISCLOSURE' not in prompt for _, prompt in captured)
    captured.clear()
    asyncio.run(run_round(Env(), graph, config, 1, tmp_path, 'reddit'))
    for uid, prompt in captured:
        assert f'OWN_RESPONSE_{uid}' in prompt
        assert f'OWN_RESPONSE_{1-uid}' not in prompt
        assert 'DELAYED_DISCLOSURE' in prompt
    with sqlite3.connect(db) as conn:
        rows = conn.execute('SELECT info FROM trace').fetchall()
    assert len(rows) == 4
    for (info,) in rows:
        saved = json.loads(info)
        assert isinstance(saved['prompt'], str)
        assert 'base64,' not in saved['prompt']
        assert saved['visual_input'][0]['sha256']
    assert len((tmp_path / 'visual_requests.jsonl').read_text().splitlines()) == 4


def test_installed_oasis_interview_preserves_multimodal_content(tmp_path):
    pytest.importorskip('oasis')
    from oasis.social_agent.agent import SocialAgent
    images, _ = image_parts(tmp_path, study(tmp_path)['images'])
    content = [{'type': 'text', 'text': 'Only these pixels.'}, *images]
    captured = {}
    async def model_reply(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_messages=[SimpleNamespace(content='A blue square.')])
    async def perform_action(data, kind):
        assert data['prompt'] == content
        return {'success': True}
    agent = SimpleNamespace(interview_record=False, social_agent_id=0,
        system_message=SimpleNamespace(role_name='system', content='Fictional observer.'),
        memory=SimpleNamespace(get_context=lambda: ([], 10)),
        _aget_model_response=model_reply,
        env=SimpleNamespace(action=SimpleNamespace(perform_action=perform_action)))
    result = asyncio.run(SocialAgent.perform_interview(agent, content))
    assert captured['openai_messages'][-1]['content'] == content
    assert result['success']


def test_interview_timeline_keeps_answer_not_image_payload(tmp_path):
    pytest.importorskip('oasis')
    from run_parallel_simulation import fetch_new_actions_from_db
    db = tmp_path / 'trace.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE trace (user_id INTEGER, action TEXT, info TEXT)')
        conn.execute('INSERT INTO trace VALUES (?,?,?)', (0, 'interview', json.dumps({
            'response': 'Saved answer', 'prompt': [{'type': 'image_url', 'image_url': {'url': 'secret-image-bytes'}}]})))
    actions, marker = fetch_new_actions_from_db(str(db), 0, {0: 'Observer'})
    assert marker == 1
    assert actions[0]['action_args']['content'] == 'Saved answer'
    assert 'secret-image-bytes' not in json.dumps(actions)
