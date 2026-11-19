"""Routing, fixed provider contracts and no implicit fallback; all network calls mocked."""
import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from bujji import providers
from bujji.config import Settings
from bujji.main import create_app

@pytest.mark.parametrize('message,task',[
 ('Explain DBMS normalization','study'),('debug this python traceback','coding'),
 ('Find latest research with sources','research'),('draft an email','writing'),
 ('calculate my budget','analysis'),('hello Bujji','daily'),('explain the latest news','research'),
 ('I like chocolate','daily'),('dbms nerpinchu','study'),('find latest PDF in Downloads','daily'),
])
def test_local_auto_task_hints(message,task):
 assert providers.resolve_task('auto',message)==task
 assert providers.resolve_task('daily',message)=='daily'

@pytest.mark.parametrize('provider',['openai','anthropic','perplexity'])
def test_specialist_request_contracts(monkeypatch,provider):
 monkeypatch.setenv(provider.upper()+'_API_KEY','private-dummy-key')
 monkeypatch.setenv(provider.upper()+'_MODEL','test-model')
 real=httpx.AsyncClient;calls=[]
 def respond(request):
  calls.append(request);p=json.loads(request.content)
  assert p['model']=='test-model'
  if provider=='openai':
   assert str(request.url)=='https://api.openai.com/v1/chat/completions'
   assert p['store'] is False and p['max_completion_tokens']>0
   assert request.headers['authorization']=='Bearer private-dummy-key'
   return httpx.Response(200,json={'choices':[{'message':{'content':'Answer'}}]})
  if provider=='anthropic':
   assert str(request.url)=='https://api.anthropic.com/v1/messages'
   assert request.headers['x-api-key']=='private-dummy-key'
   assert request.headers['anthropic-version']=='2023-06-01'
   assert p['system'] and all(m['role']!='system' for m in p['messages'])
   return httpx.Response(200,json={'content':[{'type':'thinking','thinking':'private'},{'type':'text','text':'Answer'}]})
  assert str(request.url)=='https://api.perplexity.ai/v1/agent'
  assert p['tools']==[{'type':'web_search'}] and p['max_tool_calls']==3 and p['store'] is False
  return httpx.Response(200,json={'status':'completed','output':[{'type':'search_results','results':[{'url':'https://example.org/source'},{'url':'javascript:alert(1)'}]},{'type':'message','content':[{'type':'output_text','text':'Answer','annotations':[{'url':'https://example.org/source'}]}]}]})
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
 result=asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested=provider))
 assert result['provider']==provider and result['text'].startswith('Answer') and len(calls)==1
 assert 'private' not in result['text']
 if provider=='perplexity':assert result['text'].count('https://example.org/source')==1 and 'javascript:' not in result['text']

@pytest.mark.parametrize('provider',['openai','anthropic'])
def test_specialist_json_planner(monkeypatch,provider):
 monkeypatch.setenv(provider.upper()+'_API_KEY','private-dummy-key');monkeypatch.setenv(provider.upper()+'_MODEL','test-model')
 real=httpx.AsyncClient
 def respond(request):
  p=json.loads(request.content)
  if provider=='anthropic':
   assert 'schema' in p['system'] and 'JSON' in p['system']
   return httpx.Response(200,json={'stop_reason':'max_tokens','content':[{'type':'text','text':'{"tool":'}]})
  assert p['response_format']=={'type':'json_object'}
  return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{"tool":'}}]})
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
 result=asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested=provider,json_mode=True,json_schema={'type':'object'}))
 assert result['finish_reason']=='length'

@pytest.mark.parametrize('provider',['openai','anthropic','perplexity'])
def test_new_provider_quota_never_falls_back(monkeypatch,provider):
 monkeypatch.setenv(provider.upper()+'_API_KEY','private-dummy-key');monkeypatch.setenv(provider.upper()+'_MODEL','test-model')
 real=httpx.AsyncClient;calls=[]
 def respond(r):calls.append(r);return httpx.Response(429,text='private-dummy-key')
 monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
 with pytest.raises(providers.ProviderError,match='quota') as err:asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested=provider))
 assert len(calls)==1 and 'private-dummy-key' not in str(err.value)

def test_perplexity_cannot_be_used_for_local_json_tools(monkeypatch):
 monkeypatch.setenv('PERPLEXITY_API_KEY','private-dummy-key');monkeypatch.setenv('PERPLEXITY_MODEL','test-model')
 with pytest.raises(providers.ProviderError,match='not a local-action planner'):
  asyncio.run(providers.reply([{'role':'user','content':'Delete my files'}],[],requested='perplexity',json_mode=True))

def test_routes_persist_auth_validate_and_do_not_expose_keys(tmp_path,monkeypatch):
 token='route-test-token-'*3
 app=create_app(Settings(token=token,data=tmp_path/'data',files=tmp_path/'files'),background=False)
 with TestClient(app) as c:
  assert c.get('/api/ai/routes').status_code==401
  assert c.put('/api/ai/routes',json={'routes':providers.DEFAULT_ROUTES}).status_code==401
 with TestClient(app,headers={'Authorization':'Bearer '+token}) as c:
  assert c.put('/api/ai/routes',json={'routes':{'study':'notebooklm'}}).status_code==422
  assert c.put('/api/ai/routes',json={'routes':{**providers.DEFAULT_ROUTES,'daily':'perplexity'}}).status_code==422
  assert c.put('/api/ai/routes',json={'routes':providers.DEFAULT_ROUTES}).status_code==200
  assert c.get('/api/status').json()['routes']==providers.DEFAULT_ROUTES
  calls=[]
  async def reply(messages,memories,task,requested,focus):
   calls.append((task,requested));return {'text':'Hello','provider':requested,'model':'fake'}
  monkeypatch.setattr(providers,'reply',reply)
  assert c.post('/api/chat',json={'message':'explain DBMS','task':'auto'}).status_code==200
  assert calls[-1]==('study','openai')
  assert c.post('/api/chat',json={'message':'explain DBMS','task':'auto','provider':'groq'}).status_code==200
  assert calls[-1]==('study','groq')
 rebuilt=create_app(Settings(token=token,data=tmp_path/'data',files=tmp_path/'files'),background=False)
 with TestClient(rebuilt,headers={'Authorization':'Bearer '+token}) as c:assert c.get('/api/ai/routes').json()['routes']==providers.DEFAULT_ROUTES

def test_missing_key_stops_before_network(monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 with pytest.raises(providers.ProviderError,match='not configured'):
  asyncio.run(providers.reply([{'role':'user','content':'Study'}],[],task='study',requested='openai'))

def test_research_bypasses_local_action_loop(tmp_path,monkeypatch):
 token='research-test-token-'*3
 local=tmp_path/'User';local.mkdir()
 monkeypatch.setenv('BUJJI_LOCAL_FILE_ROOTS',json.dumps([str(local)]))
 app=create_app(Settings(token=token,data=tmp_path/'data',files=tmp_path/'files'),background=False)
 calls=[]
 async def reply(messages,memories,task,requested,focus):
  calls.append((messages,memories,task,requested));return {'text':'Research answer','provider':'perplexity','model':'fake'}
 monkeypatch.setattr(providers,'reply',reply)
 with TestClient(app,headers={'Authorization':'Bearer '+token}) as c:
  c.post('/api/assistant/access',json={'enabled':True})
  result=c.post('/api/assistant',json={'message':'latest research with sources','task':'auto','provider':'perplexity'})
  assert result.status_code==200,result.text
  event=json.loads(result.text.strip())
  assert event['type']=='result' and event['trace']==[] and event['pending']==[]
  assert calls[0][1:]==([], 'research','perplexity')
  assert len(c.get('/api/messages').json())==2


def test_role_overrides_survive_saved_task_routes(monkeypatch):
 from bujji import focus
 monkeypatch.setattr(providers,'available',lambda:{'openai':True,'anthropic':True})
 monkeypatch.setenv('BUJJI_FOCUS_REVIEW_PROVIDER','anthropic')
 routes=focus.routes('study','auto',route_provider='openai')
 assert routes['plan']=='openai' and routes['review']=='anthropic'
 assert set(focus.routes('study','openai',route_provider='openai').values())=={'openai'}
