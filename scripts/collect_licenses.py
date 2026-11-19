"""Build-only dependency notices, without interpreter/user paths or environment data."""
import importlib.metadata as metadata
import json
from pathlib import Path

notices=[]
for distribution in metadata.distributions():
    info=distribution.metadata
    texts=[]
    for item in distribution.files or []:
        filename=str(item).lower()
        if any(part in filename for part in ('.dist-info/licenses/','.dist-info/license','.dist-info/copying')):
            p=distribution.locate_file(item)
            if p.is_file() and p.stat().st_size<1024*1024:
                texts.append({'file':item.name,'text':p.read_text(encoding='utf-8',errors='replace')})
    notices.append({'name':info.get('Name',''),'version':distribution.version,'license':info.get('License-Expression') or info.get('License',''),'notices':texts})
output=Path(__file__).resolve().parents[1]/'desktop/THIRD_PARTY_LICENSES.json'
output.write_text(json.dumps(sorted(notices,key=lambda v:v['name'].lower()),indent=2),encoding='utf-8')
print('Dependency notices generated; no configuration or environment values included.')
