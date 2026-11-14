import json
from types import SimpleNamespace
import pytest
from modern_openai import ResponsesBridge, validate_lab_model

def response(output, status='completed', model='gpt-6-astra'):
    d={'id':'resp_test','created_at':1,'model':model,'status':status,'output':output,'usage':{'input_tokens':20,'output_tokens':10,'total_tokens':30}}
    return SimpleNamespace(model_dump=lambda **kwargs:d)

def test_text_images_and_parameter_contract():
    b=ResponsesBridge();messages=[{'role':'system','content':'English'}, {'role':'user','content':[{'type':'text','text':'Inspect'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AA','detail':'low'}}]}]
    req=b.request('gpt-6-astra',messages,{'max_tokens':8192,'temperature':0.5,'top_p':1},response_format={'type':'json_object'})
    assert req['store'] is False and req['reasoning']=={'effort':'medium'}
    assert req['max_output_tokens']==8192 and 'temperature' not in req and 'top_p' not in req
    assert req['input'][1]['content'][1]=={'type':'input_image','image_url':'data:image/png;base64,AA','detail':'low'}
    assert req['text']['format']=={'type':'json_object'}
    assert messages[1]['content'][1]['type']=='image_url'

def test_tool_roundtrip_preserves_reasoning_without_cross_agent_leak(tmp_path):
    b=ResponsesBridge(tmp_path/'receipts.jsonl')
    reasoning={'id':'rs_private','type':'reasoning','encrypted_content':'opaque','summary':[]}
    call={'id':'fc_1','type':'function_call','call_id':'call_1','name':'lookup','arguments':'{"q":"food"}'}
    c=b.completion(response([reasoning,call]),'gpt-6-astra')
    assistant=c.choices[0].message.model_dump(exclude_none=True)
    history=[{'role':'user','content':'Look up food'},assistant,{'role':'tool','tool_call_id':'call_1','content':'done'}]
    req=b.request('gpt-6-astra',history,tools=[{'type':'function','function':{'name':'lookup','parameters':{'type':'object','properties':{}}}}])
    assert req['tools'][0]['name']=='lookup' and req['tools'][0]['strict'] is False
    assert reasoning in req['input'] and call in req['input']
    assert req['input'][-1]=={'type':'function_call_output','call_id':'call_1','output':'done'}
    other=b.request('gpt-6-astra',[{'role':'user','content':'Independent user'}])
    assert reasoning not in other['input'] and call not in other['input']
    receipt=json.loads((tmp_path/'receipts.jsonl').read_text())
    assert receipt['returned_model']=='gpt-6-astra' and 'opaque' not in json.dumps(receipt)

def test_text_conversion_and_no_silent_partial_or_downgrade():
    b=ResponsesBridge();output=[{'type':'message','content':[{'type':'output_text','text':'Answer'}]}]
    c=b.completion(response(output),'gpt-6-astra');assert c.choices[0].message.content=='Answer' and c.usage.total_tokens==30
    with pytest.raises(RuntimeError,match='did not complete'):b.completion(response(output,status='incomplete'),'gpt-6-astra')
    with pytest.raises(RuntimeError,match='unexpected model'):b.completion(response(output,model='gpt-4.1-mini'),'gpt-6-astra')
    with pytest.raises(ValueError,match='Legacy'):validate_lab_model('gpt-4.1-mini')
    with pytest.raises(ValueError,match='non-streaming'):b.request('gpt-6-astra',[],{'stream':True})
