import asyncio
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji.remote_access import RemoteCommand, MAX_DOWNLOAD

MASTER='remote-owner-token-'*3
@pytest.fixture
def setup(tmp_path,monkeypatch):
 root=tmp_path/'User';root.mkdir();(root/'Downloads').mkdir();(root/'Downloads'/'assignment.txt').write_text('My assignment notes')
 (root/'.env').write_text('private');(root/'passwords.txt').write_text('private')
 monkeypatch.setenv('BUJJI_LOCAL_FILE_ROOTS',json.dumps([str(root)]))
 app=create_app(Settings(token=MASTER,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
 with TestClient(app) as c:
  owner={'Authorization':'Bearer '+MASTER}
  code=c.post('/api/devices/pairing',headers=owner).json()['code']
  phone=c.post('/api/devices/pair',json={'code':code,'name':'Test phone'}).json()
  h={'Authorization':'Bearer '+phone['token']}
  yield app,c,root,owner,phone['id'],h

def grant(c,owner,device,**kwargs):
 r=c.put('/api/devices/'+device+'/access',headers=owner,json=kwargs);assert r.status_code==200,r.text

def test_existing_pairings_start_without_remote_grants(setup):
 app,c,root,owner,device,h=setup
 r=c.post('/api/devices/remote/status',headers=h).json();assert r['permissions']=={'control':False,'files':False} and r['roots']==[]
 for endpoint,payload in [('files',{'path':str(root)}),('control',{'operation':'status'})]:
  assert c.post('/api/devices/remote/'+endpoint,headers=h,json=payload).status_code==403
 assert c.put('/api/devices/'+device+'/access',headers=h,json={'files':True}).status_code==401
 assert c.post('/api/devices/remote/status').status_code==401
 assert c.get('/api/messages',headers=h).status_code==401
 assert c.post('/api/computer',headers=h,json={'operation':'status'}).status_code==401

def test_read_browse_and_download_do_not_modify_sources(setup):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 status=c.post('/api/devices/remote/status',headers=h).json();assert str(root) in status['roots']
 r=c.post('/api/devices/remote/files',headers=h,json={'path':str(root)}).json();assert [e['name'] for e in r['entries']]==['Downloads']
 path=str(root/'Downloads'/'assignment.txt')
 r=c.post('/api/devices/remote/files',headers=h,json={'operation':'read','path':path});assert r.status_code==200 and r.json()['text']=='My assignment notes'
 r=c.post('/api/devices/remote/files',headers=h,json={'operation':'download','path':path});assert r.status_code==200 and r.content==b'My assignment notes'
 assert 'attachment' in r.headers['content-disposition']
 assert (root/'Downloads'/'assignment.txt').read_text()=='My assignment notes'
 assert c.post('/api/devices/remote/control',headers=h,json={'operation':'status'}).status_code==403

def test_file_boundaries_symlinks_disabled_and_download_limit(setup,tmp_path):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 outside=tmp_path/'outside';outside.write_text('outside');(root/'linked').symlink_to(outside)
 for path in [root/'.env',root/'passwords.txt',root/'linked',outside,root/'Downloads'/'..'/'.env']:
  r=c.post('/api/devices/remote/files',headers=h,json={'operation':'download','path':str(path)})
  assert r.status_code==409,r.text
 huge=root/'large.bin'
 with huge.open('wb') as f:f.truncate(MAX_DOWNLOAD+1)
 assert c.post('/api/devices/remote/files',headers=h,json={'operation':'download','path':str(huge)}).status_code==409
 app.state.workspace.set_enabled(False)
 assert c.post('/api/devices/remote/files',headers=h,json={'path':str(root)}).status_code==409

def test_folder_pagination_reaches_more_than_eighty_entries(setup):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True)
 for i in range(190):(root/'Downloads'/f'file-{i}.txt').write_text('x')
 offset=0;found=[]
 for _ in range(6):
  r=c.post('/api/devices/remote/files',headers=h,json={'path':str(root/'Downloads'),'offset':offset}).json()
  found.extend(e['name'] for e in r['entries'])
  offset=r['next_offset']
  if offset is None:break
 assert len(found)==191 and len(set(found))==191

def test_grants_persist_and_revoke_blocks_every_remote_endpoint(setup):
 app,c,root,owner,device,h=setup;grant(c,owner,device,files=True,control=True)
 assert c.get('/api/devices',headers=owner).json()[0]['remote']=={'files':True,'control':True}
 rebuilt=create_app(Settings(token=MASTER,data=root.parent/'data',files=root.parent/'inbox'),background=False)
 assert rebuilt.state.remote.permission(device)['files']
 c.delete('/api/devices/'+device,headers=owner)
 for path,payload in [('status',{}),('files',{'path':str(root)}),('control',{'operation':'stop'})]:
  assert c.post('/api/devices/remote/'+path,headers=h,json=payload).status_code==401

def test_control_uses_native_plan_and_same_id_is_not_executed_twice(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True);calls=[]
 async def native(body):
  calls.append(body);return {'detail':'Opened YouTube'}
 monkeypatch.setattr(app.state.remote.computer,'native',native)
 payload={'request_id':str(uuid.uuid4()),'message':'open youtube'}
 for _ in range(2):
  r=c.post('/api/devices/remote/control',headers=h,json=payload);assert r.status_code==200,r.text;assert r.json()['completed']
 assert len(calls)==1 and calls[0]['op']=='act'
 assert c.post('/api/devices/remote/control',headers=h,json={**payload,'message':'open github'}).status_code==409

def test_control_rechecks_grants_after_planning(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True);calls=[]
 async def request(body):
  calls.append(body.operation)
  app.state.store.set_state('remote_access_'+device,{'control':False,'files':False})
  return {'plan_id':'test','summary':'Open app'}
 monkeypatch.setattr(app.state.remote.computer,'request',request)
 r=c.post('/api/devices/remote/control',headers=h,json={'request_id':str(uuid.uuid4()),'message':'open youtube'})
 assert r.status_code==403 and calls==['plan']

def test_stop_and_cross_controller_busy_checks(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True)
 app.state.computer.busy=True
 assert c.post('/api/devices/remote/control',headers=h,json={'operation':'status'}).status_code==409
 assert c.post('/api/devices/remote/control',headers=h,json={'operation':'stop'}).json()['stopped']
 app.state.computer.busy=False
 code=c.post('/api/devices/pairing',headers=owner).json()['code'];other=c.post('/api/devices/pair',json={'code':code,'name':'Other phone'}).json()['id']
 app.state.remote.owner=other
 assert c.post('/api/devices/remote/control',headers=h,json={'operation':'stop'}).status_code==409
 app.state.remote.owner=None

def test_no_remote_write_shell_or_routine_management(setup):
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True,files=True)
 assert c.post('/api/devices/remote/control',headers=h,json={'operation':'execute','plan_id':'anything'}).status_code==422
 assert c.post('/api/devices/remote/files',headers=h,json={'operation':'write','path':str(root/'new.txt')}).status_code==422
 assert c.put('/api/devices/'+device+'/access',headers=owner,json={'files':True,'shell':True}).status_code==422

def test_revocation_between_native_steps_stops_remaining_actions(setup,monkeypatch):
 from bujji import providers
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True);calls=[]
 async def native(body):
  app.state.remote.guard()
  if body['op']=='act':
   calls.append(body)
   app.state.store.set_state('remote_access_'+device,{'control':False,'files':False})
   return {'detail':'First step completed'}
  return {'apps':[],'windows':[],'controls':[]}
 async def reply(*args,**kwargs):
  return {'text':json.dumps({'summary':'Two steps','actions':[{'op':'open_url','url':'https://example.org/a'},{'op':'open_url','url':'https://example.org/b'}]})}
 monkeypatch.setattr(app.state.remote.computer,'native',native);monkeypatch.setattr(providers,'reply',reply)
 r=c.post('/api/devices/remote/control',headers=h,json={'request_id':str(uuid.uuid4()),'message':'perform my setup'})
 assert r.status_code==200,r.text
 assert r.json()['completed'] is False and len(calls)==1
 assert 'revoked' in r.json()['results'][-1]['detail']

def test_stop_cancels_waiting_native_request_and_releases_control(setup,monkeypatch):
 app,c,root,owner,device,h=setup;grant(c,owner,device,control=True)
 async def check():
  entered=asyncio.Event()
  async def native(body):entered.set();await asyncio.Event().wait()
  monkeypatch.setattr(app.state.remote.computer,'native',native)
  task=asyncio.create_task(app.state.remote.command(device,RemoteCommand(operation='status')))
  await entered.wait()
  assert app.state.remote.stop(device)['stopped']
  with pytest.raises(asyncio.CancelledError):await task
  assert not app.state.remote.lock.locked() and app.state.remote.active_task is None
 asyncio.run(check())
