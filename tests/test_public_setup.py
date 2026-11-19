import importlib.util
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from bujji.main import create_app
from bujji.config import Settings

TOKEN='public-test-owner-token-'*3

def test_profile_has_no_personal_default_and_persists(tmp_path,monkeypatch):
    monkeypatch.delenv('BUJJI_USER_NAME',raising=False)
    settings=Settings(token=TOKEN,data=tmp_path/'data',files=tmp_path/'files')
    app=create_app(settings,background=False)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
        assert c.get('/api/status').json()['profile']=={'name':''}
        for name in ['', ' '*4, 'a'*41, 'User\nName']:
            assert c.put('/api/profile',json={'name':name}).status_code==422
        assert c.put('/api/profile',json={'name':'  Maya  '}).json()=={'name':'Maya'}
    rebuilt=create_app(settings,background=False)
    with TestClient(rebuilt,headers={'Authorization':'Bearer '+TOKEN}) as c:
        assert c.get('/api/status').json()['profile']['name']=='Maya'
    with TestClient(rebuilt) as c:assert c.put('/api/profile',json={'name':'Other'}).status_code==401

def test_config_generation_is_random_and_never_overwrites(tmp_path):
    spec=importlib.util.spec_from_file_location('config_init',Path(__file__).resolve().parents[1]/'scripts/init_config.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'.env.example').write_text('BUJJI_TOKEN=\nGEMINI_API_KEY=\n')
    assert module.initialize(tmp_path)
    text=(tmp_path/'.env').read_text()
    assert len(text.splitlines()[0].split('=',1)[1])>=48
    assert not module.initialize(tmp_path)
    assert (tmp_path/'.env').read_text()==text
