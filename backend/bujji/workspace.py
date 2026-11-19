"""General, chat-driven filesystem tools. Models propose; confirmed plans execute."""
import asyncio
from collections import deque, OrderedDict
from datetime import datetime, timezone
from itertools import islice
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
import zipfile
from xml.etree import ElementTree
from fastapi import HTTPException
from .documents import plain_path, read_file, ocr
from pypdf import PdfReader

SKIP = {'windows','program files','program files (x86)','programdata','appdata','$recycle.bin','system volume information','recovery','node_modules','__pycache__','venv','dist','build','backend-dist','backend-build','site-packages'}
TEXT = {'.txt','.md','.csv','.json','.yaml','.yml','.toml','.py','.js','.ts','.tsx','.jsx','.html','.css','.rst','.log'}
READABLE = TEXT | {'.pdf','.docx','.png','.jpg','.jpeg'}
DENIED = re.compile(r'credential|password|passwd|secret|token|private.?key|id_rsa|id_ed25519', re.I)


def modified(entry):
    try: return entry.stat(follow_symlinks=False).st_mtime
    except OSError: return 0


def modified_at(path):
    return datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()


class Workspace:
    def __init__(self, store, roots):
        self.store = store
        self.roots = [Path(p).absolute() for p in roots]
        self.resolved_roots = [p.resolve() for p in self.roots]
        try:
            self.known_folders = json.loads(os.getenv("BUJJI_KNOWN_FOLDERS", "{}"))
            if not isinstance(self.known_folders,dict): self.known_folders = {}
        except ValueError:
            self.known_folders = {}
        saved = store.rows("SELECT value FROM state WHERE key='file_assistant_enabled'")
        self._enabled = not saved or saved[0]["value"] == "true"
        self.plans = OrderedDict()
        self.lock = threading.Lock()
        self.active = set()

    @property
    def enabled(self):
        return bool(self.roots) and self._enabled

    def set_enabled(self, enabled):
        self.store.execute("INSERT INTO state(key,value) VALUES('file_assistant_enabled',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(enabled),))
        self._enabled = enabled
        if not enabled:
            with self.lock: self.plans.clear()
        return self.status()

    def status(self):
        return {'available':bool(self.roots), 'enabled':self.enabled, 'locations':[str(p) for p in self.roots], 'desktop':os.getenv('BUJJI_DESKTOP_FOLDER'), 'known_folders':self.known_folders, 'operations':['list','search','read','create_folder','copy','write_new_file','remember']}

    def checked(self, raw, new=False):
        if not self.enabled: raise ValueError('File access is off. Enable it in Conversation to use local file tools.')
        if not isinstance(raw,str) or not raw or len(raw)>2000: raise ValueError('Supply a complete file path.')
        path = Path(raw)
        if not path.is_absolute(): raise ValueError('Use an absolute path from locations/list/search, not a guessed relative path.')
        candidates = [root for root in self.roots if path.is_relative_to(root)]
        if not candidates: raise ValueError('That path is outside this desktop’s available local locations.')
        closest_root = max(candidates,key=lambda p:len(p.parts))
        relative_parts = path.relative_to(closest_root).parts
        if any(part.startswith('.') or part.lower() in SKIP or DENIED.search(part) for part in relative_parts):
            raise ValueError('Hidden, system, dependency and credential paths are excluded.')
        if any(':' in part for part in path.parts[1:]): raise ValueError('Alternate data stream paths are excluded.')
        resolved = path.resolve()
        if not any(resolved.is_relative_to(root) for root in self.resolved_roots):
            raise ValueError('That path is outside this desktop’s available local locations.')
        existing = path
        while new and not existing.exists() and not existing.is_symlink():
            if existing == existing.parent: break
            existing = existing.parent
        plain_path(existing)
        if not new: plain_path(path)
        return path

    def memory(self, query=""):
        if not isinstance(query,str) or len(query)>120: raise ValueError("Use a short memory query.")
        return {"memories":self.store.rows("SELECT id,content FROM memories WHERE content LIKE ? ORDER BY updated DESC LIMIT 20", ("%"+query+"%",))}

    def listing(self, path):
        folder = self.checked(path)
        if not folder.is_dir(): raise ValueError('Choose a directory to list.')
        entries, count = [], 0
        with os.scandir(folder) as iterator:
            for entry in iterator:
                count += 1
                if count > 500: break
                try:
                    item = self.checked(entry.path)
                    entries.append({'path':str(item), 'kind':'folder' if item.is_dir() else 'file', 'bytes':item.stat().st_size if item.is_file() else None, 'modified_at':modified_at(item)})
                except (OSError,ValueError): continue
                if len(entries)>=80: break
        return {'path':str(folder),'entries':entries,'partial':len(entries)>=80 or count>500}

    def read_local(self, raw):
        path = self.checked(raw)
        suffix = path.suffix.lower()
        if suffix not in READABLE: raise ValueError('This file type is not readable yet. Supported: PDF, DOCX, text/code, PNG and JPEG.')
        data = read_file(path.parent,path.name)
        if suffix in TEXT:
            text = data.decode('utf-8-sig')
            method = 'local text'
        elif suffix == '.pdf':
            reader = PdfReader(io.BytesIO(data),strict=False)
            if reader.is_encrypted: raise ValueError('Encrypted PDF; contents were not read.')
            if len(reader.pages)>10: raise ValueError('PDF exceeds ten pages; inspect a smaller document.')
            text = '\n'.join((page.extract_text() or '')[:12000] for page in reader.pages)
            method = 'local PDF'
        elif suffix == '.docx':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                member = archive.getinfo('word/document.xml')
                if member.file_size>5*1024*1024: raise ValueError('DOCX text exceeds the extraction limit.')
                xml = ElementTree.fromstring(archive.read(member))
                text = '\n'.join(''.join(p.itertext()) for p in xml.iter() if p.tag.endswith('}p'))
            method = 'local DOCX'
        else: text, method = '', 'image needs OCR'
        return {'path':str(path),'text':text[:12000], 'method':method, 'truncated':len(text)>12000,'needs_ocr':not text.strip(), 'sha256':hashlib.sha256(data).hexdigest()}

    async def read(self, path, allow_ocr):
        result = await asyncio.to_thread(self.read_local,path)
        if result['needs_ocr'] and allow_ocr:
            checked = self.checked(path)
            if checked.suffix.lower() not in {'.pdf','.png','.jpg','.jpeg'}: return result
            data = await asyncio.to_thread(read_file,checked.parent,checked.name)
            if len(data)>3*1024*1024: raise ValueError('OCR input exceeds 3 MB.')
            extracted = (await ocr(data,checked.suffix.lower()))[:12000]
            result.update(text=extracted,method='Gemini OCR',needs_ocr=not extracted.strip())
        result.pop('sha256',None)
        return result

    def search(self, query, start=None, content=False):
        if not isinstance(query,str) or not query.strip() or len(query)>120: raise ValueError('Supply a short search query.')
        starts = [self.checked(start)] if start else [self.checked(str(p)) for p in self.roots]
        queue = deque((p,0) for p in starts)
        seen, results, inspected, reads, errors = set(), [], 0, 0, 0
        query = query.casefold()
        while queue and inspected<3000 and len(results)<40:
            folder, depth = queue.popleft()
            if str(folder.resolve()).casefold() in seen: continue
            seen.add(str(folder.resolve()).casefold())
            try:
                with os.scandir(folder) as entries:
                    snapshot = list(islice(entries,max(0,3000-inspected)))
                    for entry in sorted(snapshot,key=modified,reverse=True):
                        inspected += 1
                        if inspected>3000: break
                        try:
                            path = self.checked(entry.path)
                            if path.is_dir():
                                if depth<7: queue.append((path,depth+1))
                                if query in path.name.casefold(): results.append({'path':str(path),'kind':'folder','matched':'name','modified_at':modified_at(path)})
                            elif path.is_file():
                                if query in path.name.casefold(): results.append({'path':str(path),'kind':'file','matched':'name','modified_at':modified_at(path)})
                                elif content and reads<30 and path.suffix.lower() in (TEXT|{'.pdf','.docx'}):
                                    reads += 1
                                    document = self.read_local(str(path))
                                    index = document['text'].casefold().find(query)
                                    if index>=0: results.append({'path':str(path),'kind':'file','matched':'contents','modified_at':modified_at(path),'excerpt':document['text'][max(0,index-100):index+350]})
                        except Exception: errors += 1
                        if len(results)>=40: break
            except OSError: errors += 1
        return {'results':results, 'entries_checked':min(inspected,3000), 'documents_read':reads, 'unreadable_or_excluded':errors, 'partial':bool(queue) or inspected>=3000 or len(results)>=40 or (content and reads>=30), 'note':'Bounded search; absence is not proof a file does not exist. Narrow the location or query if needed.'}

    def preview(self, session, actions):
        if not self.enabled: raise ValueError("Local file access is off; no approval was prepared.")
        if not isinstance(actions,list) or not 1<=len(actions)<=30: raise ValueError('args.actions must be a nonempty JSON array of 1–30 action objects; no actions were prepared.')
        normalized, created, destinations = [], set(), set()
        for action in actions:
            kind = action.get('kind')
            if kind == 'remember':
                text = action.get('text','').strip()
                if not 1<=len(text)<=2000: raise ValueError('Memory must be a short nonempty string.')
                normalized.append({'kind':kind,'text':text}); continue
            if kind not in {'create_folder','copy','write_new_file'}: raise ValueError('Only create_folder, copy, write_new_file and remember are supported for approval. No shell, deletion or overwrites.')
            target = self.checked(action.get('destination'),new=True)
            if target.exists() or target.is_symlink() or str(target).casefold() in destinations:
                raise ValueError(f'Destination already exists or is duplicated: {target}. Nothing was changed.')
            if not target.parent.is_dir() and str(target.parent) not in created:
                raise ValueError('Create the parent folder in an earlier action first.')
            if not re.fullmatch(r'[^<>:"/\\|?*\x00-\x1f]{1,160}',target.name) or target.name.endswith((' ','.')) or target.stem.upper() in {'CON','PRN','AUX','NUL', *('COM'+str(n) for n in range(1,10)), *('LPT'+str(n) for n in range(1,10))}:
                raise ValueError('Destination has an invalid Windows filename.')
            item = {'kind':kind,'destination':str(target)}
            if kind == 'copy':
                source = self.checked(action.get('source'))
                if source.suffix.lower() not in READABLE: raise ValueError('Only supported document/code/image files can be copied in this version.')
                data = read_file(source.parent,source.name)
                item.update(source=str(source),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
            elif kind == 'write_new_file':
                text = action.get('text')
                if target.suffix.lower() not in TEXT or not isinstance(text,str) or len(text)>50000:
                    raise ValueError('New files must contain at most 50,000 characters in a supported text/code format.')
                item['text'] = text
            else: created.add(str(target))
            destinations.add(str(target).casefold()); normalized.append(item)
        with self.lock:
            if not self.enabled: raise ValueError("Local file access was disabled; no approval was prepared.")
            token = secrets.token_urlsafe(24)
            self.plans[token] = {'id':token,'session':session,'actions':normalized,'expires':time.monotonic()+600}
            while len(self.plans)>10: self.plans.popitem(last=False)
        return self.pending(session)[-1]

    def pending(self, session):
        with self.lock:
            for key, plan in list(self.plans.items()):
                if plan['expires']<time.monotonic(): del self.plans[key]
            return [{'id':p['id'],'expires_in':max(0,int(p['expires']-time.monotonic())), 'actions':[{k:v for k,v in a.items() if k!='sha256'} for a in p['actions']]} for p in self.plans.values() if p['session']==session]

    def confirm(self, session, token, confirmed):
        if not self.enabled: raise HTTPException(409,'File access is off; this approval cannot run.')
        with self.lock:
            plan = self.plans.get(token)
            if not plan or plan['session']!=session or plan['expires']<time.monotonic(): raise HTTPException(409,'Approval expired, missing or already used.')
            del self.plans[token]
        if not confirmed:
            text = 'Cancelled. No file or memory actions were performed.'
            self.store.message(session,'assistant',text)
            return {'text':text,'results':[]}
        results = []
        failed = False
        for action in plan['actions']:
            if failed:
                results.append({'kind':action['kind'],'ok':False,'reason':'Not attempted after an earlier failure.'}); continue
            try:
                if not self.enabled: raise ValueError('File access was disabled before this action.')
                kind = action['kind']
                if kind=='remember': self.store.remember(action['text'],'chat-approved')
                else:
                    destination = self.checked(action['destination'],new=True)
                    plain_path(destination.parent)
                    if kind=='create_folder': destination.mkdir()
                    else:
                        if kind=='copy':
                            source = self.checked(action['source'])
                            data = read_file(source.parent,source.name)
                            if hashlib.sha256(data).hexdigest()!=action['sha256']: raise ValueError('Source changed since preview; not copied.')
                        else: data = action['text'].encode('utf-8')
                        with destination.open('xb') as output: output.write(data)
                results.append({'kind':kind,'ok':True, **({'destination':action['destination']} if 'destination' in action else {'memory':action['text']})})
            except Exception as exc:
                failed = True
                results.append({'kind':action['kind'],'ok':False,'reason':str(exc) if isinstance(exc,ValueError) else 'Action failed; check the path, access and disk space. A partial new file may remain.'})
        done = sum(r['ok'] for r in results)
        text = f'Completed {done} of {len(results)} approved actions. '+('Some actions failed or were not attempted; see the results.' if failed else 'Verified by the local file tools.')
        self.store.audit('chat-file-actions',f'{done}/{len(results)} succeeded')
        text += '\n'+'\n'.join(('Done: ' if r['ok'] else 'Not done: ')+r['kind']+' — '+r.get('destination',r.get('memory',r.get('reason',''))) for r in results)
        self.store.message(session,'assistant',text)
        return {'text':text,'results':results}
