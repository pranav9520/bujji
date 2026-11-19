import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if '--voice-worker' in sys.argv:
        from bujji.local_voice_worker import main
    elif '--computer-worker' in sys.argv:
        from bujji.computer_wire import diagnostic
        diagnostic(sys.stderr,'dispatch')
        from bujji.computer_native import main
    else:
        from bujji.desktop_backend import main
    raise SystemExit(main())
