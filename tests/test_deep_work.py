from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from bujji.deep_work import DeepWork, WorkAction
from bujji.store import Store
from bujji.main import create_app
from bujji.config import Settings

T=int(datetime(2026,11,18,10,0,tzinfo=timezone.utc).timestamp()*1000)
@pytest.fixture
def work(tmp_path):return DeepWork(Store(tmp_path/'work.sqlite3'))
def action(work,a,at=T,**kw):return work.action(WorkAction(action=a,**kw),at)
def test_pause_resume_counts_only_running_intervals(work):
    action(work,'start',work_minutes=1,rounds=1)
    d=action(work,'pause',T+20000);assert d['active']['remaining']==40000
    assert work.snapshot(T+300000)['stats']['focused_ms']==20000
    action(work,'resume',T+300000)
    d=work.snapshot(T+340000);assert d['active']['status']=='finished';assert d['stats']['focused_ms']==60000;assert d['stats']['completed']==1

def test_restart_and_offline_gap_do_not_credit_unstarted_rounds(work):
    action(work,'start',work_minutes=1,break_minutes=1,rounds=3)
    restored=DeepWork(Store(Path(work.store.path)))
    d=restored.snapshot(T+600000)
    assert d['active']['phase']=='work' and d['active']['status']=='ready' and d['active']['round']==2
    assert d['stats']['completed']==1 and d['stats']['focused_ms']==60000
    assert len(work.store.rows('SELECT * FROM notifications'))==2
    restored.snapshot(T+700000);assert len(work.store.rows('SELECT * FROM notifications'))==2

def test_manual_break_waits_for_user(work):
    action(work,'start',work_minutes=1,break_minutes=2,rounds=2,auto_break=False)
    d=work.snapshot(T+60000);assert d['active']['phase']=='break' and d['active']['status']=='ready'
    d=action(work,'resume',T+300000);assert d['active']['deadline']==T+420000
    d=work.snapshot(T+420000);assert d['active']['phase']=='work' and d['active']['status']=='ready'

def test_end_and_reset_preserve_actual_time(work):
    action(work,'start',work_minutes=1)
    d=action(work,'reset',T+10000);assert d['active']['status']=='ready';assert d['stats']['focused_ms']==10000
    action(work,'resume',T+20000)
    d=action(work,'end',T+30000);assert d['stats']['focused_ms']==20000;assert d['stats']['completed']==0;assert d['stats']['completion']==0

def test_cross_midnight_stats_allocate_intervals(work):
    start=int(datetime(2026,11,18,18,25,tzinfo=timezone.utc).timestamp()*1000) # 23:55 IST
    action(work,'start',start,work_minutes=10,rounds=1)
    d=work.snapshot(start+600000);assert d['stats']['focused_ms']==300000;assert d['stats']['completed']==1

def test_tasks_are_explicit_and_persist(work):
    d=action(work,'task_add',title='Revise DBMS');task=d['tasks'][0]['id']
    d=action(work,'task_select',task_id=task);assert d['choice']['title']=='Revise DBMS'
    d=action(work,'task_toggle',task_id=task,done=True);assert d['tasks'][0]['done']==1
    d=action(work,'task_delete',task_id=task);assert d['tasks']==[]

def test_new_start_does_not_destroy_active_session(work):
    action(work,'start',title='Existing')
    with pytest.raises(HTTPException):action(work,'start',title='Replacement')
    assert work.snapshot(T)['active']['title']=='Existing'

def test_focus_api_auth_and_no_fake_attention_score(tmp_path):
    token='focus-owner-test-token-'*3
    app=create_app(Settings(token=token,data=tmp_path/'data',files=tmp_path/'files'),background=False)
    with TestClient(app) as c:
        assert c.get('/api/work-focus').status_code==401
        h={'Authorization':'Bearer '+token}
        assert c.get('/api/work-focus',headers=h).json()['stats']['completion'] is None
        assert c.post('/api/work-focus',headers=h,json={'action':'start','work_minutes':0}).status_code==422
        assert c.post('/api/work-focus',headers=h,json={'action':'start','title':'Study','work_minutes':1,'quiet':True}).status_code==200
        app.state.store.execute("INSERT INTO notifications(content,created) VALUES(?,?)",('Reminder: test',datetime.now(timezone.utc).isoformat()))
        assert c.get('/api/notifications',headers=h).json()[0]['quiet'] is True
        assert c.post('/api/work-focus',headers=h,json={'action':'pause'}).json()['active']['status']=='paused'
        assert c.get('/api/notifications',headers=h).json()[0]['quiet'] is False


def test_quiet_suppression_is_persistent_even_after_focus_ends(work):
    from bujji.reminders import tick
    from bujji.store import now
    action(work,'start',T,work_minutes=10,quiet=True)
    work.store.execute("INSERT INTO reminders(title,due,recurrence,created) VALUES(?,?,?,?)",('Muted test',datetime.fromtimestamp((T+1000)/1000,timezone.utc).isoformat(),'none',now()))
    tick(work.store,'Asia/Kolkata',datetime.fromtimestamp((T+2000)/1000,timezone.utc))
    action(work,'end',T+3000)
    assert work.store.rows('SELECT quiet FROM notifications')[0]['quiet']==1

def test_old_notification_schema_upgrades_without_losing_rows(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE notifications(id INTEGER PRIMARY KEY,reminder_id INTEGER,content TEXT,created TEXT,read INTEGER DEFAULT 0)')
        db.execute('INSERT INTO notifications(content,created) VALUES(?,?)',('Previously saved reminder','2026-11-18T10:00:00+00:00'))
    upgraded=Store(path)
    row=upgraded.rows('SELECT * FROM notifications')[0]
    assert row['content']=='Previously saved reminder' and row['quiet']==0
