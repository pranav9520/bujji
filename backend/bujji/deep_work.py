"""Persistent timer sessions; elapsed timer time is not measured attention."""
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class WorkAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['start','pause','resume','end','reset','skip_break','settings','task_add','task_toggle','task_delete','task_select']
    title: str = Field(default='Deep work',max_length=200)
    work_minutes: int = Field(default=45,ge=1,le=180)
    break_minutes: int = Field(default=10,ge=0,le=60)
    rounds: int = Field(default=3,ge=1,le=12)
    quiet: bool = False
    auto_break: bool = True
    task_id: str = Field(default='',max_length=36)
    done: bool = False

class DeepWork:
    def __init__(self,store,tz='Asia/Kolkata'):
        self.store=store;self.tz=ZoneInfo(tz);self.lock=threading.RLock()
        with store.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS focus_history(id TEXT PRIMARY KEY,title TEXT,status TEXT,planned INTEGER,ended INTEGER,segments TEXT,task TEXT);
            CREATE TABLE IF NOT EXISTS focus_tasks(id TEXT PRIMARY KEY,title TEXT,done INTEGER,created INTEGER);''')

    @staticmethod
    def stamp():return int(time.time()*1000)
    def read(self,db,key,default):
        row=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone();return json.loads(row[0]) if row else default
    def write(self,db,key,value):db.execute('INSERT OR REPLACE INTO state(key,value) VALUES(?,?)',(key,json.dumps(value)))
    def save_round(self,db,s,status,at):
        if s['phase']!='work':return
        if s['status']=='running' and s.get('anchor',0):
            end=min(at,s['deadline']);
            if end>s['anchor']:s['segments'].append([s['anchor'],end])
        s['anchor']=0
        if s['segments'] or status=='completed':
            db.execute('INSERT OR IGNORE INTO focus_history VALUES(?,?,?,?,?,?,?)',(s['id'],s['title'],status,s['work_ms'],at,json.dumps(s['segments']),s.get('task_id','')))
    def notify(self,db,text):
        db.execute('INSERT INTO notifications(content,created) VALUES(?,?)',(text,datetime.now(self.tz).isoformat()))
    def next_work(self,s):
        s.update(id=str(uuid.uuid4()),round=s['round']+1,phase='work',status='ready',remaining=s['work_ms'],deadline=0,anchor=0,segments=[])
    def advance_in(self,db,s,at):
        if not s or s['status']!='running' or at<s['deadline']:return
        end=s['deadline']
        if s['phase']=='work':
            self.save_round(db,s,'completed',end)
            self.notify(db,'Focus: '+s['title']+' completed.')
            if s['round']>=s['rounds']:s.update(status='finished',remaining=0,deadline=0)
            elif s['break_ms']>0:s.update(phase='break',status='running' if s['auto_break'] else 'ready',remaining=s['break_ms'],deadline=end+s['break_ms'] if s['auto_break'] else 0,anchor=0,segments=[])
            else:self.next_work(s)
        if s['phase']=='break' and s['status']=='running' and at>=s['deadline']:
            self.notify(db,'Break: finished. Start your next focus session when ready.');self.next_work(s)
        self.write(db,'deep_focus',s)
    def advance(self,at=None):
        with self.lock,self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');s=self.read(db,'deep_focus',{});self.advance_in(db,s,at if at is not None else self.stamp())
    def quiet(self):
        s=self.store.state('deep_focus',{});return bool(s and s['status']=='running' and s['phase']=='work' and s.get('quiet') and self.stamp()<s['deadline'])
    def action(self,body,at=None):
        at=self.stamp() if at is None else at
        with self.lock,self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');s=self.read(db,'deep_focus',{});self.advance_in(db,s,at);a=body.action
            if a=='task_add':
                title=body.title.strip()
                if not title:raise HTTPException(422,'Enter a task title.')
                if db.execute('SELECT count(*) FROM focus_tasks').fetchone()[0]>=200:raise HTTPException(409,'Remove an old task first (200 maximum).')
                db.execute('INSERT INTO focus_tasks VALUES(?,?,0,?)',(str(uuid.uuid4()),title,at))
            elif a in {'task_toggle','task_delete','task_select'}:
                task=db.execute('SELECT * FROM focus_tasks WHERE id=?',(body.task_id,)).fetchone()
                if not task:raise HTTPException(404,'Task not found.')
                if a=='task_toggle':db.execute('UPDATE focus_tasks SET done=? WHERE id=?',(int(body.done),body.task_id))
                elif a=='task_delete':
                    db.execute('DELETE FROM focus_tasks WHERE id=?',(body.task_id,))
                    if self.read(db,'focus_choice',{}).get('task_id')==body.task_id:self.write(db,'focus_choice',{})
                else:
                    if s and s['status'] in {'running','paused'}:raise HTTPException(409,'End the current session before choosing a different task.')
                    self.write(db,'focus_choice',{'title':task['title'],'task_id':task['id']})
            elif a=='start':
                if s and s['status'] in {'running','paused','ready'}:raise HTTPException(409,'End the current session first.')
                title=body.title.strip()
                if not title:raise HTTPException(422,'Enter a focus title.')
                if body.task_id and not db.execute('SELECT id FROM focus_tasks WHERE id=?',(body.task_id,)).fetchone():raise HTTPException(404,'Task not found.')
                s=dict(id=str(uuid.uuid4()),title=title,task_id=body.task_id,work_ms=body.work_minutes*60000,break_ms=body.break_minutes*60000,rounds=body.rounds,round=1,phase='work',status='running',remaining=body.work_minutes*60000,deadline=at+body.work_minutes*60000,anchor=at,segments=[],quiet=body.quiet,auto_break=body.auto_break)
                self.write(db,'focus_defaults',dict(work_minutes=body.work_minutes,break_minutes=body.break_minutes,rounds=body.rounds,quiet=body.quiet,auto_break=body.auto_break))
            elif a=='settings':
                if s:s.update(quiet=body.quiet,auto_break=body.auto_break)
                cfg=self.read(db,'focus_defaults',dict(work_minutes=45,break_minutes=10,rounds=3));cfg.update(quiet=body.quiet,auto_break=body.auto_break);self.write(db,'focus_defaults',cfg)
            else:
                if not s:raise HTTPException(409,'Start a focus session first.')
                if a=='pause':
                    if s['status']=='running':
                        if s['phase']=='work' and at>s['anchor']:s['segments'].append([s['anchor'],min(at,s['deadline'])])
                        s.update(status='paused',remaining=max(0,s['deadline']-at),deadline=0,anchor=0)
                elif a=='resume':
                    if s['status']!='running':
                        if s['status'] not in {'ready','paused'}:raise HTTPException(409,'The timer is not ready to resume.')
                        s.update(status='running',deadline=at+s['remaining'],anchor=at if s['phase']=='work' else 0)
                elif a=='end':
                    self.save_round(db,s,'ended',at);s.update(status='finished',remaining=0,deadline=0,anchor=0)
                elif a=='reset':
                    self.save_round(db,s,'reset',at);s.update(id=str(uuid.uuid4()),phase='work',status='ready',remaining=s['work_ms'],deadline=0,anchor=0,segments=[])
                elif a=='skip_break':
                    if s['phase']!='break':raise HTTPException(409,'No break to skip.')
                    self.next_work(s)
            self.write(db,'deep_focus',s)
        return self.snapshot(at)
    def snapshot(self,at=None):
        with self.lock:
            at=self.stamp() if at is None else at
            self.advance(at)
            with self.store.db() as db:
                s=self.read(db,'deep_focus',{})
                day=datetime.fromtimestamp(at/1000,self.tz).replace(hour=0,minute=0,second=0,microsecond=0);lo=int(day.timestamp()*1000);hi=int((day+timedelta(days=1)).timestamp()*1000)
                rows=db.execute('SELECT * FROM focus_history ORDER BY ended DESC LIMIT 10000').fetchall();total=0;completed=0;ended=0
                for row in rows:
                    for start,end in json.loads(row['segments']):total+=max(0,min(end,hi)-max(start,lo))
                    if lo<=row['ended']<hi:
                        completed+=row['status']=='completed';ended+=1
                if s and s['phase']=='work' and s['status']!='finished':
                    for start,end in s['segments']:total+=max(0,min(end,hi)-max(start,lo))
                    if s['status']=='running':total+=max(0,min(at,s['deadline'],hi)-max(s['anchor'],lo))
                if s:s={**s,'remaining':max(0,s['deadline']-at) if s['status']=='running' else s['remaining']}
                recent=[{'title':r['title'],'status':r['status'],'ended':r['ended'],'focused_ms':sum(max(0,b-a) for a,b in json.loads(r['segments']))} for r in rows[:10]]
                return dict(active=s,recent=recent,tasks=[dict(r) for r in db.execute('SELECT * FROM focus_tasks ORDER BY done,created DESC LIMIT 200')],stats={'focused_ms':total,'completed':completed,'completion':int(completed/ended*100+.5) if ended else None},defaults=self.read(db,'focus_defaults',{'work_minutes':45,'break_minutes':10,'rounds':3,'quiet':False,'auto_break':True}),choice=self.read(db,'focus_choice',{}))
