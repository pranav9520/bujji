import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, content TEXT NOT NULL COLLATE NOCASE UNIQUE,
                source TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, title TEXT NOT NULL, due TEXT NOT NULL,
                recurrence TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL,
                UNIQUE(title,due,recurrence));
            CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, reminder_id INTEGER,
                content TEXT NOT NULL, created TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0, quiet INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, path TEXT NOT NULL, expires REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL, outcome TEXT NOT NULL,
                created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS messages_session_id ON messages(session,id);
            CREATE INDEX IF NOT EXISTS reminders_status_due ON reminders(status,due);
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            if 'quiet' not in {r['name'] for r in db.execute('PRAGMA table_info(notifications)')}:
                try:
                    db.execute('ALTER TABLE notifications ADD COLUMN quiet INTEGER NOT NULL DEFAULT 0')
                except sqlite3.OperationalError:
                    if 'quiet' not in {r['name'] for r in db.execute('PRAGMA table_info(notifications)')}:
                        raise

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.db() as db:
            return [dict(r) for r in db.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.db() as db:
            cursor = db.execute(sql, args)
            return cursor.lastrowid

    def audit(self, action, outcome):
        self.execute("INSERT INTO audit(action,outcome,created) VALUES(?,?,?)", (action, outcome, now()))

    def remember(self, content, source="explicit"):
        self.execute("INSERT INTO memories(content,source,updated) VALUES(?,?,?) ON CONFLICT(content) DO UPDATE SET updated=excluded.updated",
                     (content.strip(), source, now()))
        return self.rows("SELECT * FROM memories WHERE content=? COLLATE NOCASE", (content.strip(),))[0]

    def messages(self, session):
        return list(reversed(self.rows("SELECT role,content FROM messages WHERE session=? ORDER BY id DESC LIMIT 12", (session,))))

    def message(self, session, role, content):
        self.execute("INSERT INTO messages(session,role,content,created) VALUES(?,?,?,?)", (session, role, content, now()))

    def state(self, key, default=None):
        rows = self.rows("SELECT value FROM state WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_state(self, key, value):
        self.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, json.dumps(value)))
