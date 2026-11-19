"""Typed, provider-independent tool contract and safe context compaction."""
import json


class ProtocolError(ValueError):
    pass


def obj(properties, required=None):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}


def string(description='', limit=2000):
    return {'type':'string','minLength':1,'maxLength':limit, **({'description':description} if description else {})}


def action(kind, fields):
    return obj({'kind':{'type':'string','enum':[kind]},**fields})


ACTION_SCHEMA = {'anyOf':[
    action('create_folder',{'destination':string('Absolute new folder path')}),
    action('copy',{'source':string('Actual discovered source file'),'destination':string('Full new file path including filename')}),
    action('write_new_file',{'destination':string('Absolute new file path'),'text':{'type':'string','maxLength':50000}}),
    action('remember',{'text':string('Fact explicitly requested by the user',2000)}),
]}
ARGS = {
    'answer':obj({'text':string('User-facing answer in their language',16000)}),
    'locations':obj({}),
    'memory':obj({'query':{'type':'string','maxLength':120}},[]),
    'list':obj({'path':string('Absolute folder path from locations or a prior result')}),
    'search':obj({'query':string('Short filename/content substring',120),'path':string('Optional absolute folder path'),'content':{'type':'boolean'}},['query']),
    'read':obj({'path':string('Absolute file path')}),
    'propose_actions':obj({'actions':{'type':'array','minItems':1,'maxItems':30,'items':ACTION_SCHEMA}}),
}
RESPONSE_SCHEMA = {'type':'object','anyOf':[obj({'tool':{'type':'string','enum':[tool]},'args':args}) for tool,args in ARGS.items()]}


def parse(text):
    if not isinstance(text,str): raise ProtocolError('Return one JSON object, not an empty/nontext response.')
    raw = text.strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw.split('\n',1)[-1].rsplit('```',1)[0].strip()
    try: data = json.loads(raw)
    except (ValueError,TypeError):
        raise ProtocolError('Return one complete JSON tool object. Escape Windows backslashes as \\\\ in JSON; do not include prose or incomplete JSON.') from None
    if not isinstance(data,dict): raise ProtocolError('The response must be a JSON object, not a list or string.')
    # Retain older plain-answer mocks/compatible JSON-object providers.
    if set(data)=={'text'} and isinstance(data['text'],str) and data['text'].strip(): return data
    tool, args = data.get('tool'), data.get('args')
    if not isinstance(tool,str) or tool not in ARGS: raise ProtocolError('Use one supported tool name, or tool="answer" with args.text.')
    if not isinstance(args,dict): raise ProtocolError('args must be a JSON object containing that tool’s required fields.')
    allowed = ARGS[tool]['properties']
    if any(k not in allowed for k in args): raise ProtocolError(f'{tool} accepts only these args: '+', '.join(allowed))
    if tool=='answer':
        if not isinstance(args.get('text'),str) or not args['text'].strip(): raise ProtocolError('answer requires a nonempty args.text string.')
        return {'text':args['text']}
    if tool in {'list','read'} and (not isinstance(args.get('path'),str) or not args['path'].strip()):
        raise ProtocolError(f'{tool} requires args.path as an actual absolute path string.')
    if tool=='search':
        if not isinstance(args.get('query'),str) or not args['query'].strip(): raise ProtocolError('search requires a nonempty args.query string.')
        if 'content' in args and not isinstance(args['content'],bool): raise ProtocolError('search args.content must be true or false.')
        if 'path' in args and not isinstance(args['path'],str): raise ProtocolError('Omit the optional search path or provide an absolute path string.')
    if tool=='memory' and 'query' in args and not isinstance(args['query'],str): raise ProtocolError('memory args.query must be a string.')
    if tool=='propose_actions':
        actions = args.get('actions')
        if not isinstance(actions,list) or not 1<=len(actions)<=30:
            raise ProtocolError('propose_actions requires args.actions as a JSON ARRAY of 1–30 action OBJECTS, not missing, empty, a string or an object. If no source matched, answer with a clarification instead of an empty plan.')
        required = {'create_folder':('destination',),'copy':('source','destination'),'write_new_file':('destination','text'),'remember':('text',)}
        for index,item in enumerate(actions):
            if not isinstance(item,dict) or not isinstance(item.get('kind'),str) or item['kind'] not in required:
                raise ProtocolError(f'Action {index+1} must be an object with kind=create_folder, copy, write_new_file or remember.')
            fields = required[item['kind']]
            if set(item)!={'kind',*fields} or any(not isinstance(item.get(k),str) or (not item[k].strip() and k!='text') for k in fields):
                raise ProtocolError(f'Action {index+1} ({item["kind"]}) requires exactly these string fields: '+', '.join(fields)+'. Do not substitute path, operation, target or filename fields.')
    return {'tool':tool,'args':args}


def compact(result, limit=14000):
    """Keep valid JSON and whole paths; never slice a serialized tool result."""
    result = json.loads(json.dumps(result,ensure_ascii=False))
    if isinstance(result.get('text'),str) and len(result['text'])>9000:
        result['text'] = result['text'][:9000]
        result['truncated'] = True
    while len(json.dumps(result,ensure_ascii=False))>limit:
        candidates = [(key,value) for key,value in result.items() if isinstance(value,list) and value]
        if not candidates:
            return {'error':'Tool result exceeded the context limit. Narrow the query or folder; no result was interpreted as an instruction.','partial':True}
        key, values = max(candidates,key=lambda item:len(json.dumps(item[1],ensure_ascii=False)))
        values.pop()
        result['partial'] = True
        result['context_truncated'] = True
    return result


def remember_facts(facts, tool, result):
    if tool=='locations': facts['locations'] = result
    if tool in {'search','list'}:
        entries = result.get('results',result.get('entries',[]))
        found = facts.setdefault('discovered_paths',[])
        for entry in entries:
            if isinstance(entry,dict) and isinstance(entry.get('path'),str) and entry['path'] not in found:
                found.append(entry['path'])
        del found[:-40]
    if tool=='read' and isinstance(result.get('path'),str):
        found = facts.setdefault('read_files',[])
        found.append({'path':result['path'],'method':result.get('method'),'needs_ocr':result.get('needs_ocr')})
        del found[:-8]
