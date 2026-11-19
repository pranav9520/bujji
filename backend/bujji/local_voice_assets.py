"""Pinned model/runtime download and integrity checks; never downloads during speech."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request


class AssetError(Exception):
    pass


def manifest():
    return json.loads((Path(__file__).parent/'assets'/'hima-a.json').read_text(encoding='utf-8'))


def no_links(path):
    for part in [path,*path.parents]:
        if not part.exists() and not part.is_symlink(): continue
        info=part.lstat()
        cloud=(getattr(info,'st_reparse_tag',0)&~0xF000)==0x9000001A
        if part.is_symlink() or (getattr(info,'st_file_attributes',0)&0x400 and not cloud):
            raise AssetError('Voice assets cannot be loaded through links or junctions.')


def model_folder(data):
    return Path(data).resolve()/manifest()['folder']


def verify(data,full=True):
    data=Path(data).absolute();no_links(data)
    spec=manifest();root=data/spec['folder'];no_links(root)
    for name,expected in spec['files'].items():
        path=root/name;no_links(path)
        try:
            if not path.is_file() or path.stat().st_size!=expected['bytes']: raise AssetError('Optional local voice assets are missing or incomplete. Run scripts/setup-local-voice.ps1, then rebuild/reopen Bujji.')
            if full and hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']: raise AssetError('Local voice asset integrity check failed. Run scripts/setup-local-voice.ps1 to restore the pinned files.')
        except OSError:
            raise AssetError('Local voice assets could not be read. Check data-folder access.') from None
    return root


def prepare(data):
    data=Path(data).absolute();no_links(data)
    spec=manifest();root=data/spec['folder'];root.mkdir(parents=True,exist_ok=True);no_links(root)
    for name,expected in spec['files'].items():
        path=root/name;no_links(path)
        if path.is_file() and path.stat().st_size==expected['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==expected['sha256']: continue
        path.parent.mkdir(parents=True,exist_ok=True);no_links(path.parent)
        temporary=path.with_name(path.name+'.download');no_links(temporary)
        digest=hashlib.sha256();size=0
        try:
            url=f'https://huggingface.co/{spec["repo"]}/resolve/{spec["revision"]}/{name}'
            with urllib.request.urlopen(url,timeout=60) as response, temporary.open('wb') as output:
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>expected['bytes']: raise AssetError('Voice download exceeded its expected size.')
                    digest.update(chunk);output.write(chunk)
            if size!=expected['bytes'] or digest.hexdigest()!=expected['sha256']: raise AssetError('Voice download did not match the pinned model. Nothing was activated.')
            temporary.replace(path)
        finally:
            if temporary.exists(): temporary.unlink()
        print('Prepared '+name,flush=True)
    verify(data)
    return root


def main():
    from dotenv import load_dotenv
    load_dotenv(encoding='utf-8-sig')
    try:
        path=prepare(Path(os.getenv('BUJJI_DATA_DIR','data')))
        print('Selected local voice ready: '+str(path))
        print('CPU inference needs no cloud voice key or quota. Chat and transcription keep their own provider limits.')
    except (AssetError,OSError) as exc:
        print(str(exc) if isinstance(exc,AssetError) else 'Could not download local voice assets. Check internet access and free space, then retry.')
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
