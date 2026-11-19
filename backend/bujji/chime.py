"""Fixed local reminder sound; no caller-supplied paths or shell execution."""
import os
from pathlib import Path


def play_chime():
    if os.name != 'nt':
        return {'ok':False,'reason':'unsupported'}
    try:
        import winsound
        path = Path(__file__).parent / 'assets' / 'reminder.wav'
        winsound.PlaySound(str(path),winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        # Acknowledges playback start, not whether the user's speakers were audible.
        return {'ok':True,'reason':'started'}
    except (OSError,RuntimeError,ImportError):
        return {'ok':False,'reason':'failed'}
