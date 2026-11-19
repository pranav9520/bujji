import sqlite3
import pytest
from bujji.store import Store


def test_connections_close_after_commit_and_rollback(tmp_path):
    store = Store(tmp_path/'test.sqlite')
    with store.db() as committed:
        committed.execute("INSERT INTO state VALUES ('key','saved')")
    with pytest.raises(sqlite3.ProgrammingError):
        committed.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with store.db() as rolled_back:
            rolled_back.execute("UPDATE state SET value='unsaved'")
            raise RuntimeError('rollback')
    with pytest.raises(sqlite3.ProgrammingError):
        rolled_back.execute('SELECT 1')
    assert store.rows('SELECT value FROM state') == [{'value':'saved'}]
