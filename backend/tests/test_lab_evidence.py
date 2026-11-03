import json
from types import SimpleNamespace
import pytest
from flask import Flask
from app.utils.locale import get_locale, get_language_instruction, set_locale
from app.services.lab_evidence import bind_seed_posts, observed_context


@pytest.mark.parametrize('header', [None, 'en-US,en;q=0.9', 'en', 'unsupported'])
def test_english_default_and_browser_headers(header):
    app = Flask(__name__)
    with app.test_request_context(headers={'Accept-Language':header} if header else {}):
        assert get_locale() == 'en'
        assert 'English' in get_language_instruction()


def test_explicit_other_language_still_supported():
    app = Flask(__name__)
    with app.test_request_context(headers={'Accept-Language':'zh'}):
        assert get_locale() == 'zh'


def test_same_entity_type_cannot_assign_another_organization():
    agents = [SimpleNamespace(agent_id=0, entity_name='Buyer A', entity_type='Organization'), SimpleNamespace(agent_id=1, entity_name='Buyer B', entity_type='Organization')]
    with pytest.raises(ValueError):
        bind_seed_posts([{'poster_agent_id':0,'poster_name':'Buyer B','content':'I am B'}], agents)
    good={'poster_agent_id':1,'poster_name':'Buyer B','content':'I am B'}
    assert bind_seed_posts([good],agents)[0]['poster_agent_id']==1


def test_report_reads_real_actions_not_graph_size(tmp_path,monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config,'UPLOAD_FOLDER',str(tmp_path))
    root=tmp_path/'simulations'/'sim_test'
    (root/'reddit').mkdir(parents=True)
    (root/'run_state.json').write_text(json.dumps({'runner_status':'completed','current_round':2}))
    (root/'reddit'/'actions.jsonl').write_text('\n'.join(json.dumps(e) for e in [
        {'event_type':'round_start','round':1},
        {'round':1,'agent_id':0,'agent_name':'Buyer','action_type':'CREATE_POST','action_args':{'content':'I reject the unsupported claim.'}},
    ]))
    data=json.loads(observed_context('sim_test'))
    assert data['completed_rounds']==2
    assert data['action_counts']=={'CREATE_POST':1}
    assert data['observed_posts_sample'][0]['round']==1
