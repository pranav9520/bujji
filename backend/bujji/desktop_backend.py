"""Owned desktop child process. stdin EOF/quit stops only this server."""
import argparse
import json
import multiprocessing
import re
import socket
import sys
import threading
import uvicorn
from .main import create_app
from .chime import play_chime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit('Invalid desktop port.')
    app = create_app()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Do not reuse occupied ports or attach to an unknown local service.
    try:
        listener.bind(('127.0.0.1', args.port))
        listener.listen(128)
    except OSError:
        listener.close()
        raise SystemExit('The desktop port is occupied. Quit the previous Bujji instance or choose another BUJJI_DESKTOP_PORT in .env.') from None
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning', timeout_graceful_shutdown=5))
    def parent_control():
        # Parent exit closes the pipe too, preventing an orphan reminder process.
        try:
            for line in sys.stdin:
                if line.strip() == 'quit':
                    break
                try:
                    command=json.loads(line)
                except (ValueError,TypeError):
                    continue
                if isinstance(command,dict) and command.get('command') == 'chime' and isinstance(command.get('id'),str) and re.fullmatch(r'[a-zA-Z0-9-]{1,64}',command['id']):
                    result=play_chime()
                    print('BUJJI_SOUND:'+json.dumps({'id':command['id'],**result}),flush=True)
        finally:
            server.should_exit = True
    threading.Thread(target=parent_control, daemon=True).start()
    print('BUJJI_READY:' + json.dumps({'port':args.port}), flush=True)
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
