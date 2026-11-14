"""Responses bridge for modern OpenAI models, preserving Camel's wire contract.

No automatic model fallback. Receipts contain model/usage metadata, never prompts,
image payloads, credentials or reasoning. Reasoning continuation is private to
the exact tool call IDs present in an agent's own supplied history.
"""
import json
import threading
from pathlib import Path
from openai.types.chat import ChatCompletion

DEFAULT_LAB_MODEL = 'gpt-6-astra'


def is_modern(model):
    return str(model).strip().lower().startswith('gpt-6')


def validate_lab_model(model):
    if str(model).strip().lower().startswith(('gpt-4', 'gpt-3.5')):
        raise ValueError('Legacy GPT-4/3.5 models are disabled in this Lab. Select a current verified model; no automatic downgrade is permitted.')
    return model


class ResponsesBridge:
    def __init__(self, receipt_path=None):
        self._continuations = {}
        self._lock = threading.Lock()
        self.receipt_path = Path(receipt_path) if receipt_path else None

    def request(self, model, messages, config=None, tools=None, response_format=None):
        config = dict(config or {})
        if config.get('stream'):
            raise ValueError('Lab GPT-6 bridge requires non-streaming responses')
        items = []
        for message in messages:
            role = message['role']
            if role == 'tool':
                items.append({'type':'function_call_output','call_id':message['tool_call_id'],'output':message.get('content') or ''})
                continue
            content = message.get('content')
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part['type'] == 'text':
                        parts.append({'type':'output_text' if role=='assistant' else 'input_text','text':part['text']})
                    elif part['type'] == 'image_url' and role != 'assistant':
                        image = part['image_url']
                        parts.append({'type':'input_image','image_url':image['url'],'detail':image.get('detail','auto')})
                    else:
                        raise ValueError('Unsupported content part in GPT-6 bridge: '+part['type'])
                content = parts
            if content:
                items.append({'role':role,'content':content})
            emitted = set()
            for call in message.get('tool_calls') or []:
                with self._lock:
                    cached = self._continuations.get(call['id'])
                if cached:
                    for item in cached:
                        identity = item.get('id') or item.get('call_id')
                        if identity not in emitted:
                            items.append(item); emitted.add(identity)
                else:
                    items.append({'type':'function_call','call_id':call['id'],'name':call['function']['name'],'arguments':call['function']['arguments']})
        req = {'model':str(model),'input':items,'store':False,'include':['reasoning.encrypted_content'],
               'reasoning':{'effort':'medium'},'max_output_tokens':config.get('max_tokens',8192)}
        functions = tools if tools is not None else config.get('tools')
        if functions:
            req['tools'] = []
            for tool in functions:
                if tool['type'] != 'function':
                    raise ValueError('Only function tools are supported by the Camel bridge')
                function = dict(tool['function']); function.setdefault('strict',False)
                req['tools'].append({'type':'function',**function})
        choice = config.get('tool_choice')
        if choice is not None:
            req['tool_choice'] = ({'type':'function','name':choice['function']['name']} if isinstance(choice,dict) else choice)
        fmt = response_format or config.get('response_format')
        if fmt:
            if isinstance(fmt,type):
                fmt = {'type':'json_schema','name':fmt.__name__,'schema':fmt.model_json_schema(),'strict':False}
            elif fmt.get('type')=='json_schema' and 'json_schema' in fmt:
                fmt = {'type':'json_schema',**fmt['json_schema']}
            req['text'] = {'format':fmt}
        return req

    def completion(self, response, requested_model):
        d = response.model_dump(exclude_none=True)
        receipt = {'requested_model':str(requested_model),'returned_model':d.get('model'),
                   'response_id':d.get('id'),'status':d.get('status'),'usage':d.get('usage'),
                   'endpoint':'responses','reasoning_effort':'medium'}
        if self.receipt_path:
            with self._lock:
                self.receipt_path.parent.mkdir(parents=True,exist_ok=True)
                with self.receipt_path.open('a',encoding='utf-8') as f:
                    f.write(json.dumps(receipt)+'\n')
        if d.get('status') != 'completed':
            raise RuntimeError('Model response did not complete: '+str(d.get('status')))
        if not str(d.get('model','')).startswith(str(requested_model)):
            raise RuntimeError('Provider returned an unexpected model; refusing silent fallback')
        output = d.get('output',[]); text=[];calls=[]
        reasoning = [x for x in output if x['type']=='reasoning']
        for item in output:
            if item['type']=='message':
                for part in item.get('content',[]):
                    if part['type']=='output_text':text.append(part['text'])
                    elif part['type']=='refusal':raise RuntimeError('Provider refused this request')
            elif item['type']=='function_call':
                calls.append({'id':item['call_id'],'type':'function','function':{'name':item['name'],'arguments':item['arguments']}})
                with self._lock:self._continuations[item['call_id']]=reasoning+[item]
        usage=d.get('usage',{});message={'role':'assistant','content':'\n'.join(text) or None}
        if calls:message['tool_calls']=calls
        if not text and not calls:raise RuntimeError('Provider returned no answer or tool calls')
        return ChatCompletion.model_validate({'id':d['id'],'object':'chat.completion','created':int(d.get('created_at',0)),
          'model':d['model'],'choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if calls else 'stop'}],
          'usage':{'prompt_tokens':usage.get('input_tokens',0),'completion_tokens':usage.get('output_tokens',0),
                   'total_tokens':usage.get('total_tokens',0)}})
