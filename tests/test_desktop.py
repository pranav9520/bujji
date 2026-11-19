import os
import json
import queue
import socket
import subprocess
import sys
import threading
import time
import httpx
import pytest
from bujji.runtime_lock import backend_lock


def test_backend_lock_refuses_second_owner_and_releases(tmp_path):
    with backend_lock(tmp_path):
        with pytest.raises(RuntimeError,match='already using'):
            with backend_lock(tmp_path):
                pass
    with backend_lock(tmp_path):
        pass


def test_desktop_owned_child_readiness_auth_and_stdin_shutdown(tmp_path):
    # Reserve a free address only to select the test port, then let the child bind.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    token='desktop-test-pairing-token-'*3
    env={**os.environ,'BUJJI_TOKEN':token,'BUJJI_DATA_DIR':str(tmp_path/'data'),'BUJJI_FILE_ROOT':str(tmp_path/'inbox'),'BUJJI_DISABLE_TELEGRAM':'1','PYTHONUNBUFFERED':'1'}
    process=subprocess.Popen([sys.executable,'-m','bujji.desktop_backend','--port',str(port)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    lines=queue.Queue()
    def read():
        for line in process.stdout:
            lines.put(line)
    threading.Thread(target=read,daemon=True).start()
    try:
        ready=lines.get(timeout=10)
        assert ready.startswith('BUJJI_READY:') and token not in ready
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=1,trust_env=False) as client:
            deadline=time.monotonic()+10
            while True:
                try:
                    response=client.get('/api/status',headers={'Authorization':'Bearer '+token})
                    if response.status_code==200:
                        break
                except httpx.HTTPError:
                    pass
                assert time.monotonic()<deadline
                time.sleep(0.05)
            assert response.json()['online'] and not response.json()['telegram_configured']
            assert client.get('/api/status').status_code==401
        process.stdin.write(json.dumps({'command':'chime','id':'integration-test'})+'\n');process.stdin.flush()
        sound=lines.get(timeout=5)
        assert sound.startswith('BUJJI_SOUND:')
        result=json.loads(sound.split(':',1)[1])
        assert result['id']=='integration-test' and result['reason'] in {'unsupported','started','failed'}
        process.stdin.write('quit\n');process.stdin.flush()
        assert process.wait(timeout=10)==0
        with backend_lock(tmp_path/'data'):
            pass
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=5)
        process.stdout.close();process.stdin.close()
