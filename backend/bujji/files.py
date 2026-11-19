import secrets
import time
from pathlib import Path
from fastapi import HTTPException
from .store import now

LIMIT = 10 * 1024 * 1024
DENIED = {".env", "credentials", "id_rsa", "id_ed25519"}


def safe_path(root, relative):
    root = root.resolve()
    candidate = root / relative
    if ':' in relative or '\\' in relative or Path(relative).is_absolute() or any(part.startswith('.') or part.lower() in DENIED for part in Path(relative).parts):
        raise HTTPException(403, "This path is not allowed.")
    # Refuse symlinks at every level, including dangling ones.
    cursor = candidate
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise HTTPException(403, "Symbolic links cannot be transferred.")
        cursor = cursor.parent
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise HTTPException(404, "File not found in the approved inbox.")
    if resolved.stat().st_size > LIMIT:
        raise HTTPException(413, "File exceeds the 10 MB transfer limit.")
    return resolved


def search(root, query):
    found = []
    for path in root.rglob('*'):
        if len(found) >= 50:
            break
        if query.lower() not in path.name.lower():
            continue
        try:
            relative = path.relative_to(root).as_posix()
            safe = safe_path(root, relative)
            found.append({"path": relative, "bytes": safe.stat().st_size})
        except (HTTPException, OSError):
            continue
    return found


def request_download(store, root, relative):
    safe_path(root, relative)
    action = secrets.token_urlsafe(24)
    store.execute("INSERT INTO approvals(id,path,expires) VALUES(?,?,?)", (action, relative, time.time() + 120))
    return {"action_id": action, "path": relative, "expires_in": 120, "requires_confirmation": True}


def consume(store, root, action):
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM approvals WHERE id=?", (action,)).fetchone()
        if not row or row["used"] or row["expires"] < time.time():
            raise HTTPException(409, "Approval expired, missing, or already used.")
        path = safe_path(root, row["path"])
        db.execute("UPDATE approvals SET used=1 WHERE id=?", (action,))
        db.execute("INSERT INTO audit(action,outcome,created) VALUES(?,?,?)", ("file-transfer", "approved", now()))
    return path
