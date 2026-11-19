"""Check tracked files for accidental secrets, private data and generated artifacts."""
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BANNED_SUFFIXES={'.keystore','.jks','.sqlite3','.db','.apk','.exe','.onnx','.safetensors','.pyc','.mp3'}
PATTERNS=[
    re.compile(r'AIza[0-9A-Za-z_-]{30,}'),
    re.compile(r'\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{24,}'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(r'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----$'),
]

def check():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    failures=[]
    for name in filter(None,names):
        p=ROOT/name
        if p.is_symlink():failures.append((name,'symlink'));continue
        if p.suffix.lower() in BANNED_SUFFIXES or (p.name.startswith('.env') and p.name!='.env.example'):
            failures.append((name,'private/generated file'));continue
        if any(part in {'node_modules','.gradle','.local','__pycache__','release','backend-dist','backend-build'} for part in p.parts):
            failures.append((name,'generated directory'));continue
        raw=p.read_bytes()
        try:text=raw.decode('utf-8')
        except UnicodeError:continue
        if any(pattern.search(text) for pattern in PATTERNS):failures.append((name,'possible credential'))
    template=(ROOT/'.env.example').read_text()
    for line in template.splitlines():
        if re.match(r'^(?:BUJJI_TOKEN|\w+_API_KEY)=.+',line):failures.append(('.env.example','nonempty token/key'))
    if failures:
        for name,reason in failures:print(f'{name}: {reason}')
        return 1
    print(f'Public-tree audit passed: {len(list(filter(None,names)))} tracked files; no detected secrets/generated/private data.')
    return 0

if __name__=='__main__':sys.exit(check())
