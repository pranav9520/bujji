import asyncio
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .store import now


def due_utc(value, tz):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(tz))
    return parsed.astimezone(timezone.utc)


def tick(store, tz, instant=None):
    instant = instant or datetime.now(timezone.utc)
    # Each due occurrence is moved and its notification recorded in one transaction.
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("SELECT * FROM reminders WHERE status='pending' AND due<=?", (instant.isoformat(),)).fetchall()
        stored=db.execute("SELECT value FROM state WHERE key='deep_focus'").fetchone()
        focus=json.loads(stored[0]) if stored else {}
        quiet=bool(focus.get('status')=='running' and focus.get('phase')=='work' and focus.get('quiet') and instant.timestamp()*1000<focus.get('deadline',0))
        for row in rows:
            late = (instant - datetime.fromisoformat(row["due"])).total_seconds() > 60
            label = "Missed while offline: " if late else "Reminder: "
            db.execute("INSERT INTO notifications(reminder_id,content,created,quiet) VALUES(?,?,?,?)", (row["id"], label + row["title"], now(),int(quiet)))
            if row["recurrence"] == "none":
                db.execute("UPDATE reminders SET status='delivered' WHERE id=?", (row["id"],))
            else:
                step = timedelta(days=1 if row["recurrence"] == "daily" else 7)
                next_due = datetime.fromisoformat(row["due"]).astimezone(ZoneInfo(tz))
                while next_due <= instant:
                    next_due += step
                db.execute("UPDATE reminders SET due=? WHERE id=?", (next_due.astimezone(timezone.utc).isoformat(), row["id"]))


async def scheduler(store, tz, work_focus=None):
    while True:
        try:
            if work_focus: work_focus.advance()
            tick(store, tz)
        except Exception:
            store.audit("scheduler", "failed; retry next tick")
        await asyncio.sleep(15)
