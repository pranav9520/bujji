import json
import pytest
from bujji import providers
from test_remote_access import setup, grant


def test_literal_filename_search_needs_no_model_or_path(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 async def forbidden(*a,**k):raise AssertionError('Literal filename must not call a model')
 monkeypatch.setattr(providers,'reply',forbidden)
 r=c.post('/api/devices/remote/chat',headers=h,json={'message':'send assignment.txt to my phone'})
 assert r.status_code==200,r.text
 assert r.json()['files'][0]['path']==str(root/'Downloads'/'assignment.txt')
 assert r.json()['auto_save'] is True
 assert (root/'Downloads'/'assignment.txt').exists()

def test_discovered_model_results_only_and_autosave(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 app.state.store.set_state('ai_routes',{'daily':'groq'})
 answers=iter([{'tool':'search','args':{'query':'assignment'}},{'tool':'answer','args':{'text':'Found your assignment.','files':[str(root/'Downloads'/'assignment.txt')]}}])
 async def reply(*args,**kwargs):
  assert kwargs['json_mode'] and 'untrusted' in kwargs['system_override']
  assert kwargs['requested']=='groq'
  return {'text':json.dumps(next(answers)),'provider':'gemini'}
 monkeypatch.setattr(providers,'reply',reply)
 r=c.post('/api/devices/remote/chat',headers=h,json={'message':'send my assignment to phone'})
 assert r.status_code==200 and r.json()['auto_save'] and len(r.json()['files'])==1

def test_guessed_attachment_rejected(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 async def reply(*a,**k):return {'text':json.dumps({'tool':'answer','args':{'text':'Found it','files':[str(root/'Downloads'/'assignment.txt')]}})}
 monkeypatch.setattr(providers,'reply',reply)
 assert c.post('/api/devices/remote/chat',headers=h,json={'message':'send assignment'}).status_code==409

def test_remote_chat_requires_file_grant_and_refuses_write_tools(setup,monkeypatch):
 app,c,root,owner,device,h=setup
 assert c.post('/api/devices/remote/chat',headers=h,json={'message':'send my assignment'}).status_code==403
 grant(c,owner,device,files=True)
 async def reply(*a,**k):return {'text':json.dumps({'tool':'write','args':{'path':str(root/'new.txt')}})}
 monkeypatch.setattr(providers,'reply',reply)
 assert c.post('/api/devices/remote/chat',headers=h,json={'message':'send my assignment'}).status_code==409
 assert not (root/'new.txt').exists()
 assert app.state.remote.file_chats==set()

def test_ambiguous_literal_matches_are_not_auto_saved(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 (root/'assignment.txt').write_text('Other copy')
 r=c.post('/api/devices/remote/chat',headers=h,json={'message':'send assignment.txt'})
 assert r.status_code==200 and len(r.json()['files'])==2 and not r.json()['auto_save']

def test_reading_one_candidate_does_not_clear_partial_search_warning(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 path=str(root/'Downloads'/'assignment.txt')
 monkeypatch.setattr(app.state.workspace,'search',lambda *a:{'results':[{'path':path,'kind':'file'}],'partial':True})
 answers=iter([{'tool':'search','args':{'query':'assignment'}},{'tool':'read','args':{'path':path}},{'tool':'answer','args':{'text':'Found the file','files':[path]}}])
 async def reply(*a,**k):return {'text':json.dumps(next(answers))}
 monkeypatch.setattr(providers,'reply',reply)
 r=c.post('/api/devices/remote/chat',headers=h,json={'message':'send my assignment'})
 assert r.status_code==200,r.text
 assert r.json()['files'] and not r.json()['auto_save']

def test_transfer_receipt_is_not_taken_from_model_claims(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 async def reply(*a,**k):return {'text':json.dumps({'tool':'answer','args':{'text':'I sent it successfully','files':[]}})}
 monkeypatch.setattr(providers,'reply',reply)
 r=c.post('/api/devices/remote/chat',headers=h,json={'message':'send my assignment'})
 assert r.status_code==200 and not r.json()['auto_save']
 assert r.json()['reply'].startswith('No verified')
