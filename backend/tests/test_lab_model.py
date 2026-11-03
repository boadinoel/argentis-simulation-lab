import sys
from pathlib import Path

def test_memory_limit_is_independent_of_reply_cap():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from lab_model import LabOpenAIModel
    model=LabOpenAIModel(model_type='gpt-4.1-mini',api_key='test-no-network',model_config_dict={'max_tokens':1024})
    assert model.token_limit==32768
    assert model.model_config_dict['max_tokens']==1024
