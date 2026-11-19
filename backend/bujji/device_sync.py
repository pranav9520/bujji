"""Scoped device pairing and revision-checked memory/reminder exchange.

No shell, file, message-history, provider-key or computer-control capability.
The existing laptop tables stay authoritative; changes by old clients/scheduler
are captured transactionally before each exchange.
"""
import hashlib
import json
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class PairRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=16, max_length=16, pattern='^[a-fA-F0-9]{16}$')
    name: str = Field(min_length=1, max_length=40)


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: uuid.UUID
    kind: Literal['memory', 'reminder']
    revision: int = Field(ge=0)
    body: str = Field(default='', max_length=2000)
    deleted: bool = False
    title: str = Field(default='', max_length=200)
    due: int = Field(default=0, ge=0, le=253402300799000)
    repeat: Literal['none', 'daily', 'weekly'] = 'none'
    status: Literal['pending', 'done', 'cancelled'] = 'pending'


class Exchange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    changes: list[Change] = Field(default_factory=list, max_length=500)


def encode(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


class DeviceSync:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.pending = None
        with store.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS mobile_devices(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,created REAL NOT NULL,seen REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS mobile_records(id TEXT PRIMARY KEY,kind TEXT NOT NULL,local_id INTEGER,payload TEXT NOT NULL,revision INTEGER NOT NULL,UNIQUE(kind,local_id));
            CREATE TABLE IF NOT EXISTS mobile_clock(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL);
            INSERT OR IGNORE INTO mobile_clock VALUES(1,0);
            ''')

    def pairing(self):
        with self.lock:
            code = secrets.token_hex(8)
            self.pending = {'hash': digest(code), 'expires': time.time()+600, 'attempts': 0}
            return {'code': code, 'expires_in': 600, 'scope': ['memories', 'reminders']}

    def pair(self, request):
        with self.lock:
            p = self.pending
            if not p or p['expires'] < time.time() or p['attempts'] >= 5:
                raise HTTPException(403, 'Pairing code expired or locked. Generate another on the laptop.')
            p['attempts'] += 1
            if not secrets.compare_digest(digest(request.code.lower()), p['hash']):
                raise HTTPException(403, 'Pairing code did not match.')
            if len(self.devices()) >= 10:
                raise HTTPException(409, 'Revoke an old device before pairing another.')
            token = secrets.token_urlsafe(32)
            device = str(uuid.uuid4())
            self.store.execute('INSERT INTO mobile_devices(id,name,token_hash,created,seen) VALUES(?,?,?,?,?)', (device, request.name.strip() or 'Android phone', digest(token), time.time(), time.time()))
            self.pending = None
            return {'id': device, 'token': token, 'scope': ['memories', 'reminders'], 'protocol': 1}

    def devices(self):
        return self.store.rows('SELECT id,name,created,seen FROM mobile_devices WHERE revoked=0 ORDER BY created')

    def revoke(self, device):
        with self.lock:
            self.store.execute('UPDATE mobile_devices SET revoked=1 WHERE id=?', (device,))

    def authenticate(self, authorization):
        token = authorization.removeprefix('Bearer ')
        if not authorization.startswith('Bearer ') or len(token) < 32 or len(token) > 200:
            raise HTTPException(401, 'Pair this phone with the laptop again.')
        rows = self.store.rows('SELECT id FROM mobile_devices WHERE token_hash=? AND revoked=0', (digest(token),))
        if not rows:
            raise HTTPException(401, 'Device connection revoked or invalid. Pair again on the laptop.')
        return rows[0]['id']

    @staticmethod
    def payload(kind, row):
        if kind == 'memory':
            # A pre-existing desktop memory may exceed the phone's limit; do not truncate it.
            if len(row['content']) > 2000:
                raise HTTPException(409, 'A laptop memory exceeds the phone limit. Shorten it before syncing.')
            return {'body': row['content'], 'deleted': False}
        if len(row['title']) > 200:
            raise HTTPException(409, 'A laptop reminder title exceeds the phone limit. Shorten it before syncing.')
        return {'title': row['title'], 'due': int(datetime.fromisoformat(row['due']).timestamp()*1000), 'repeat': row['recurrence'], 'status': 'done' if row['status']=='delivered' else row['status']}

    @staticmethod
    def put(db, record_id, kind, local_id, payload):
        db.execute('UPDATE mobile_clock SET revision=revision+1 WHERE id=1')
        rev = db.execute('SELECT revision FROM mobile_clock WHERE id=1').fetchone()[0]
        db.execute('INSERT INTO mobile_records VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET local_id=excluded.local_id,payload=excluded.payload,revision=excluded.revision', (record_id, kind, local_id, encode(payload), rev))

    def capture(self, db):
        for kind, table in [('memory', 'memories'), ('reminder', 'reminders')]:
            rows = db.execute('SELECT * FROM '+table+' LIMIT 1001').fetchall()
            if len(rows)>1000:
                raise HTTPException(409, 'This preview supports up to 1000 memories/reminders per type.')
            live = set()
            for row in rows:
                live.add(row['id'])
                payload = self.payload(kind, row)
                record = db.execute('SELECT * FROM mobile_records WHERE kind=? AND local_id=?', (kind, row['id'])).fetchone()
                if record is None or record['payload'] != encode(payload):
                    self.put(db, record['id'] if record else str(uuid.uuid4()), kind, row['id'], payload)
            for old in db.execute('SELECT * FROM mobile_records WHERE kind=? AND local_id IS NOT NULL', (kind,)).fetchall():
                if old['local_id'] not in live:
                    payload = json.loads(old['payload'])
                    payload['deleted' if kind=='memory' else 'status'] = True if kind=='memory' else 'cancelled'
                    self.put(db, old['id'], kind, None, payload)

    def exchange(self, device, changes):
        with self.lock, self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM mobile_devices WHERE id=? AND revoked=0', (device,)).fetchone():
                raise HTTPException(401, 'Device connection revoked.')
            self.capture(db)
            results = []
            seen = set()
            for change in changes:
                key = str(change.id)
                if key in seen:
                    raise HTTPException(422, 'Duplicate change ID.')
                seen.add(key)
                current = db.execute('SELECT * FROM mobile_records WHERE id=?', (key,)).fetchone()
                if current and current['kind'] != change.kind:
                    raise HTTPException(409, 'Record type mismatch.')
                if (current['revision'] if current else 0) != change.revision:
                    results.append({'id': key, 'status': 'conflict'})
                    continue
                local = current['local_id'] if current else None
                if change.kind == 'memory':
                    payload = {'body': change.body.strip(), 'deleted': change.deleted}
                    if not payload['body']:
                        raise HTTPException(422, 'Memory cannot be blank.')
                    if change.deleted:
                        if local is not None: db.execute('DELETE FROM memories WHERE id=?', (local,))
                        local = None
                    else:
                        duplicate = db.execute('SELECT id FROM memories WHERE content=? COLLATE NOCASE AND id!=?', (payload['body'], local or -1)).fetchone()
                        if duplicate:
                            match = db.execute('SELECT id FROM mobile_records WHERE kind=? AND local_id=?', (change.kind, duplicate['id'])).fetchone()
                            results.append({'id': key, 'status': 'duplicate', 'remote_id': match['id']})
                            continue
                        stamp = datetime.now(timezone.utc).isoformat()
                        if local is None:
                            local = db.execute('INSERT INTO memories(content,source,updated) VALUES(?,?,?)', (payload['body'], 'paired-phone', stamp)).lastrowid
                        else: db.execute('UPDATE memories SET content=?,updated=? WHERE id=?', (payload['body'], stamp, local))
                else:
                    if not change.title.strip(): raise HTTPException(422, 'Reminder title cannot be blank.')
                    payload = {'title': change.title.strip(), 'due': change.due, 'repeat': change.repeat, 'status': change.status}
                    due = datetime.fromtimestamp(change.due/1000, timezone.utc).isoformat()
                    duplicate = db.execute('SELECT id FROM reminders WHERE title=? AND due=? AND recurrence=? AND id!=?', (payload['title'], due, change.repeat, local or -1)).fetchone()
                    if duplicate:
                        match = db.execute('SELECT id FROM mobile_records WHERE kind=? AND local_id=?', (change.kind, duplicate['id'])).fetchone()
                        results.append({'id': key, 'status': 'duplicate', 'remote_id': match['id']})
                        continue
                    values = (payload['title'], due, change.repeat, 'delivered' if change.status=='done' else change.status)
                    if local is None:
                        local = db.execute('INSERT INTO reminders(title,due,recurrence,status,created) VALUES(?,?,?,?,?)', (*values, datetime.now(timezone.utc).isoformat())).lastrowid
                    else: db.execute('UPDATE reminders SET title=?,due=?,recurrence=?,status=? WHERE id=?', (*values, local))
                self.put(db, key, change.kind, local, payload)
                results.append({'id': key, 'status': 'applied'})
            records = [dict(row) for row in db.execute('SELECT id,kind,payload,revision FROM mobile_records ORDER BY revision LIMIT 2501')]
            if len(records)>2500:
                raise HTTPException(409, 'Sync history limit reached. No changes from this exchange were committed.')
            for row in records: row['payload'] = json.loads(row['payload'])
            db.execute('UPDATE mobile_devices SET seen=? WHERE id=?', (time.time(), device))
            return {'protocol': 1, 'records': records, 'results': results, 'server_time': time.time(), 'scope': ['memories','reminders']}
