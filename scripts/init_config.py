"""Create a local .env once. Never prints tokens or overwrites configuration."""
from pathlib import Path
import secrets


def initialize(root):
    root=Path(root)
    target=root/'.env'
    if target.exists():
        return False
    template=(root/'.env.example').read_text(encoding='utf-8')
    token=secrets.token_urlsafe(48)
    lines=[('BUJJI_TOKEN='+token) if line.startswith('BUJJI_TOKEN=') else line for line in template.splitlines()]
    with target.open('x',encoding='utf-8') as output:
        output.write('\n'.join(lines)+'\n')
    try:target.chmod(0o600)
    except OSError:pass
    return True

if __name__=='__main__':
    created=initialize(Path(__file__).resolve().parents[1])
    print('Created private .env. Configure provider keys locally.' if created else 'Existing .env retained.')
