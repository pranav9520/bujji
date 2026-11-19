"""One running scheduler per data directory, using an OS-owned process lock."""
import os
from contextlib import contextmanager


@contextmanager
def backend_lock(directory):
    path = directory / '.backend.lock'
    handle = open(path, 'a+b')
    try:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
                handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Bujji is already using this data directory. Quit the previous desktop app or stop the old backend with Ctrl+C, then retry.') from None
    try:
        yield
    finally:
        if os.name == 'nt':
            handle.seek(0)
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
