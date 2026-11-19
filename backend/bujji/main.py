import asyncio
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, PrivateAttr
from .config import Settings
from .store import Store, now
from . import providers, files, focus, speech, tts, documents, workspace, agent, short_talk
from .deep_work import DeepWork, WorkAction
from .device_sync import DeviceSync, PairRequest, Exchange
from .remote_chat import FileChat, file_chat
from .remote_access import RemoteAccess, RemoteGrant, RemoteFiles, RemoteCommand
from .computer import Computer
from .computer_protocol import ComputerRequest, ControlError
from .reminders import due_utc, scheduler
from .telegram import poll
from .runtime_lock import backend_lock
from .middleware import SecurityHeaders

load_dotenv()


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session: str = Field(default='web', pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    task: Literal['auto', 'daily', 'study', 'research', 'coding', 'writing', 'analysis'] = 'daily'
    provider: Literal['auto', 'gemini', 'groq', 'ollama', 'openai', 'anthropic', 'perplexity'] = 'auto'
    focus: bool = False
    _auto_routed: bool = PrivateAttr(default=False)


class AIRoutes(BaseModel):
    routes: dict[Literal['daily','study','research','coding','writing','analysis'], Literal['gemini','groq','ollama','openai','anthropic','perplexity']]


class Profile(BaseModel):
    name: str = Field(min_length=1,max_length=40)


class AgentChat(Chat):
    cloud_ocr: bool = False
    collaborate: bool = False


class AgentConfirmation(BaseModel):
    session: str = Field(default="web", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    confirmed: bool


class FileAccess(BaseModel):
    enabled: bool


class ShortTurn(BaseModel):
    role: Literal['user','assistant']
    content: str = Field(min_length=1,max_length=1000)


class ShortTalk(BaseModel):
    message: str = Field(min_length=1,max_length=2000)
    history: list[ShortTurn] = Field(default_factory=list,max_length=8)
    provider: Literal['auto','gemini','groq','ollama','openai','anthropic','perplexity'] = 'auto'


class SpeechOutput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    ephemeral: bool = False


class Memory(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class Reminder(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due: str = Field(max_length=80)
    recurrence: Literal['none', 'daily', 'weekly'] = 'none'


class FolderGrant(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


class DocumentScan(BaseModel):
    grant_id: str = Field(min_length=1, max_length=100)
    cloud_ocr: bool = False


class DocumentCopy(BaseModel):
    plan_id: str = Field(min_length=1, max_length=100)
    selected: list[str] = Field(min_length=1, max_length=40)
    folder_name: str = Field(min_length=1, max_length=60)
    confirmed: bool


class FileAction(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class Confirmation(BaseModel):
    confirmed: bool


def create_app(settings=None, background=True):
    settings = settings or Settings()
    settings.validate()
    store = Store(settings.data / 'bujji.sqlite3')
    work_focus = DeepWork(store, settings.timezone)

    @asynccontextmanager
    async def lifespan(app):
        # Desktop launch opts out of Telegram regardless of old .env values.
        from contextlib import nullcontext
        with backend_lock(settings.data) if background else nullcontext():
            tasks = []
            if background:
                tasks.append(asyncio.create_task(scheduler(store, settings.timezone, work_focus)))
                if os.getenv('BUJJI_DISABLE_TELEGRAM') != '1':
                    tasks.append(asyncio.create_task(poll(store, settings.timezone)))
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                for task in tasks:
                    with suppress(asyncio.CancelledError):
                        await task

    app = FastAPI(title='Bujji', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    document_tasks = documents.DocumentTasks(os.getenv("BUJJI_DESKTOP_FOLDER"), store)
    app.state.documents = document_tasks
    try:
        file_roots = json.loads(os.getenv("BUJJI_LOCAL_FILE_ROOTS", "[]"))
        if not isinstance(file_roots,list) or not all(isinstance(p,str) for p in file_roots): file_roots = []
    except ValueError:
        file_roots = []
    file_workspace = workspace.Workspace(store,file_roots)
    app.state.workspace = file_workspace
    native_grant_token = os.getenv("BUJJI_FILE_GRANT_TOKEN", "")

    async def auth(authorization: str = Header(default='')):
        if not secrets.compare_digest(authorization.encode(), ('Bearer ' + settings.token).encode()):
            raise HTTPException(401, 'Enter your Bujji pairing token in Settings.')

    app.add_middleware(SecurityHeaders)

    protected = [Depends(auth)]
    devices = DeviceSync(store)
    app.state.devices = devices

    @app.post('/api/devices/pairing', dependencies=protected)
    async def device_pairing():
        return devices.pairing()

    @app.get('/api/devices', dependencies=protected)
    async def device_list():
        return [{**d, "remote":remote.permission(d["id"])} for d in devices.devices()]

    @app.delete('/api/devices/{device}', dependencies=protected)
    async def device_revoke(device: str):
        if remote.owner==device:remote.halt()
        devices.revoke(device)
        return {'revoked': True}

    @app.post('/api/devices/pair')
    async def device_pair(body: PairRequest):
        return devices.pair(body)

    @app.get('/api/devices/status')
    async def device_status(authorization: str = Header(default='')):
        devices.authenticate(authorization)
        return {'online': True, 'protocol': 1, 'scope': ['memories','reminders']}

    @app.post('/api/devices/sync')
    async def device_exchange(body: Exchange, authorization: str = Header(default='')):
        device = devices.authenticate(authorization)
        return await asyncio.to_thread(devices.exchange, device, body.changes)

    @app.get('/api/work-focus', dependencies=protected)
    async def work_focus_status():
        return await asyncio.to_thread(work_focus.snapshot)

    @app.post('/api/work-focus', dependencies=protected)
    async def work_focus_action(body: WorkAction):
        return await asyncio.to_thread(work_focus.action,body)

    active_focus = set()
    computer = Computer(store)
    app.state.computer = computer
    remote=RemoteAccess(store,devices,file_workspace,computer)
    app.state.remote=remote

    @app.put('/api/devices/{device}/access', dependencies=protected)
    async def grant_remote(device: str, body: RemoteGrant):
        return remote.grant(device,body)

    @app.post('/api/devices/remote/status')
    async def remote_status(authorization: str = Header(default='')):
        return remote.status(devices.authenticate(authorization))

    @app.post('/api/devices/remote/files')
    async def remote_files(body: RemoteFiles, authorization: str = Header(default='')):
        device=devices.authenticate(authorization)
        result=await asyncio.to_thread(remote.files,device,body)
        if body.operation=='download':
            data,name=result
            from urllib.parse import quote
            return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),'X-Bujji-Bytes':str(len(data))})
        return result

    @app.post('/api/devices/remote/chat')
    async def remote_file_chat(body: FileChat, request: Request, authorization: str = Header(default='')):
        device=devices.authenticate(authorization)
        task=asyncio.create_task(file_chat(remote,device,body))
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.2)
                if await request.is_disconnected():task.cancel();raise HTTPException(499,'File search stopped.')
            return await task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):await task

    @app.post('/api/devices/remote/control')
    async def remote_control(body: RemoteCommand, request: Request, authorization: str = Header(default='')):
        device=devices.authenticate(authorization)
        task=asyncio.create_task(remote.command(device,body))
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.2)
                if await request.is_disconnected():task.cancel();raise HTTPException(499,'Phone disconnected. Check the laptop before retrying an action.')
            return await task
        except asyncio.CancelledError:
            raise HTTPException(409,'Remote command stopped. Completed actions are not undone.') from None
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):await task


    @app.post('/api/computer', dependencies=protected)
    async def computer_request(body: ComputerRequest, request: Request, x_bujji_computer: str = Header(default='')):
        native=os.getenv('BUJJI_COMPUTER_TOKEN','')
        if not native or not secrets.compare_digest(native.encode(),x_bujji_computer.encode()):
            raise HTTPException(403,'Computer control requires the owned Windows desktop widget.')
        if body.operation=='stop':
            remote.halt()
            return computer.stop()
        if remote.lock.locked():raise HTTPException(409,'Computer control is active. Stop it or wait.')
        await remote.lock.acquire()
        task=asyncio.create_task(computer.request(body))
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.2)
                if await request.is_disconnected():
                    computer.stop();task.cancel();raise HTTPException(499,'Computer request stopped.')
            return Response(json.dumps(await task,ensure_ascii=False),media_type='application/json',headers={'Cache-Control':'no-store'})
        except (ControlError,providers.ProviderError) as exc:raise HTTPException(409,str(exc)) from None
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):await task
            remote.lock.release()


    def ai_routes():
        rows = store.rows("SELECT value FROM state WHERE key='ai_routes'")
        saved = json.loads(rows[0]['value']) if rows else {}
        return {task: saved[task] if task in saved else providers.choose(task) for task in providers.TASKS}

    def prepare_ai(body):
        body.task = providers.resolve_task(body.task, body.message)
        body._auto_routed = body.provider == 'auto'
        if body._auto_routed: body.provider = ai_routes()[body.task]

    @app.get('/api/ai/routes', dependencies=protected)
    async def get_ai_routes():
        return {'routes': ai_routes(), 'recommended': providers.DEFAULT_ROUTES, 'providers': providers.available()}

    @app.put('/api/ai/routes', dependencies=protected)
    async def save_ai_routes(body: AIRoutes):
        if set(body.routes) != set(providers.TASKS): raise HTTPException(422, 'Choose a provider for every category.')
        if body.routes.get('daily') == 'perplexity': raise HTTPException(422, 'Keep daily chat on a chat provider; Perplexity is for web research.')
        store.execute("INSERT INTO state(key,value) VALUES('ai_routes',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(body.routes),))
        return await get_ai_routes()

    def profile_value():
        return store.state('profile', {'name': os.getenv('BUJJI_USER_NAME','').strip()[:40]})

    @app.put('/api/profile', dependencies=protected)
    async def save_profile(body: Profile):
        name=body.name.strip()
        if not name or any(ord(c)<32 for c in name):raise HTTPException(422,'Enter a preferred name, up to 40 characters.')
        store.set_state('profile', {'name':name})
        return {'name':name}

    @app.get('/api/status', dependencies=protected)
    async def status():
        return {'profile':profile_value(),'online': True, 'timezone': settings.timezone, 'providers': providers.available(),
                'speech_voice':tts.voice_status(settings.data), 'routes': ai_routes(),
                'telegram_configured': os.getenv('BUJJI_DISABLE_TELEGRAM') != '1' and bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_ALLOWED_USERS')),
                'automation': 'approved-file-tools' if file_workspace.enabled else 'disabled', 'file_assistant':file_workspace.status(), 'version': '1.0.0'}

    @app.post('/api/assistant/access', dependencies=protected)
    async def assistant_access(body: FileAccess):
        return file_workspace.set_enabled(body.enabled)

    @app.get('/api/assistant/pending', dependencies=protected)
    async def assistant_pending(session: str = Query(default='web', pattern=r'^[a-zA-Z0-9_-]{1,80}$')):
        return file_workspace.pending(session)

    @app.post('/api/assistant/approvals/{approval}', dependencies=protected)
    async def assistant_confirm(approval: str, body: AgentConfirmation):
        return await asyncio.to_thread(file_workspace.confirm,body.session,approval,body.confirmed)

    @app.post('/api/assistant', dependencies=protected)
    async def assistant_chat(body: AgentChat, request: Request):
        prepare_ai(body)
        if not body.message.strip(): raise HTTPException(422,'Enter a message.')
        if not file_workspace.enabled: raise HTTPException(409,'File access is disabled.')
        async def stream():
            owner = asyncio.current_task()
            async def watch():
                while True:
                    await asyncio.sleep(.25)
                    if await request.is_disconnected():
                        owner.cancel()
                        return
            watcher = asyncio.create_task(watch())
            try:
                if body.provider == 'perplexity':
                    # Read-only research bypasses the local-action loop even when file tools are enabled.
                    result = await providers.reply([{'role':'user','content':body.message}], [], body.task, body.provider, body.focus)
                    store.message(body.session,'user',body.message)
                    store.message(body.session,'assistant',result['text'])
                    yield json.dumps({'type':'result', **result, 'trace':[], 'pending':[]},ensure_ascii=False)+'\n'
                else:
                    async for event in agent.run(file_workspace,body,store):
                        yield json.dumps(event,ensure_ascii=False)+'\n'
            except providers.ProviderError as exc:
                yield json.dumps({'type':'error','message':str(exc)})+'\n'
            finally:
                watcher.cancel()
                with suppress(asyncio.CancelledError): await watcher
        return StreamingResponse(stream(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

    @app.get('/api/messages', dependencies=protected)
    async def history(session: str = Query(default='web', pattern=r'^[a-zA-Z0-9_-]{1,80}$')):
        return store.messages(session)

    @app.post('/api/chat', dependencies=protected)
    async def chat(body: Chat):
        prepare_ai(body)
        if not body.message.strip():
            raise HTTPException(422, 'Enter a message.')
        try:
            result = await providers.reply(store.messages(body.session) + [{'role': 'user', 'content': body.message}], store.rows('SELECT * FROM memories ORDER BY updated DESC LIMIT 10'), body.task, body.provider, body.focus)
        except providers.ProviderError as exc:
            raise HTTPException(503, str(exc)) from None
        store.message(body.session, 'user', body.message)
        store.message(body.session, 'assistant', result['text'])
        return result

    @app.post('/api/focus', dependencies=protected)
    async def focus_chat(body: Chat, request: Request):
        prepare_ai(body)
        requested = 'auto' if body._auto_routed else body.provider
        if not body.message.strip():
            raise HTTPException(422, 'Enter a task.')
        if body.session in active_focus or len(active_focus) >= 2:
            raise HTTPException(409, 'A Focus run is already active for this session, or the two-run server limit was reached.')
        try:
            focus.routes(body.task, requested, body.provider)
        except providers.ProviderError as exc:
            raise HTTPException(503, str(exc)) from None
        active_focus.add(body.session)

        async def stream():
            owner = asyncio.current_task()
            async def watch_disconnect():
                while True:
                    await asyncio.sleep(0.25)
                    if await request.is_disconnected():
                        owner.cancel()
                        return
            watcher = asyncio.create_task(watch_disconnect())
            try:
                async for event in focus.run(body.message, store.messages(body.session), store.rows('SELECT * FROM memories ORDER BY updated DESC LIMIT 10'), body.task, requested, route_provider=body.provider):
                    if event['type'] == 'result':
                        text = event['text'] + '\n\nVerification: ' + event['verification']
                        # Save only a complete result, atomically with its user task.
                        with store.db() as db:
                            for role, content in [('user', body.message), ('assistant', text)]:
                                db.execute('INSERT INTO messages(session,role,content,created) VALUES(?,?,?,?)', (body.session,role,content,now()))
                        event['text'] = text
                    yield json.dumps(event, ensure_ascii=False) + '\n'
            except providers.ProviderError as exc:
                yield json.dumps({'type':'error', 'message':str(exc)}) + '\n'
            finally:
                watcher.cancel()
                with suppress(asyncio.CancelledError):
                    await watcher
                active_focus.discard(body.session)

        return StreamingResponse(stream(), media_type='application/x-ndjson', headers={'X-Accel-Buffering':'no'})

    active_short_talk=0

    @app.post('/api/short-talk', dependencies=protected)
    async def casual_reply(body: ShortTalk,request: Request):
        nonlocal active_short_talk
        if not body.message.strip():raise HTTPException(422,'Say a short message.')
        if active_short_talk>=2:raise HTTPException(409,'Two Short talk replies are already running. Wait or end another talk.')
        active_short_talk+=1
        task=asyncio.create_task(short_talk.reply(body.message,[turn.model_dump() for turn in body.history],ai_routes()['daily'] if body.provider == 'auto' else body.provider))
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.25)
                if await request.is_disconnected():
                    task.cancel();raise HTTPException(499,'Short talk ended.')
            result=await task
            return Response(json.dumps(result,ensure_ascii=False),media_type='application/json',headers={'Cache-Control':'no-store'})
        except providers.ProviderError as exc:
            raise HTTPException(503,str(exc)) from None
        finally:
            active_short_talk-=1
            if not task.done():task.cancel()
            with suppress(asyncio.CancelledError,providers.ProviderError):
                if not task.done() or task.cancelled():await task

    @app.post('/api/speech/synthesize', dependencies=protected)
    async def synthesize(body: SpeechOutput, request: Request):
        if not body.text.strip():
            raise HTTPException(422, 'Enter text to read aloud.')
        task=asyncio.create_task(tts.synthesize(body.text.strip(),settings.data,ephemeral=True) if body.ephemeral else tts.synthesize(body.text.strip(),settings.data))
        try:
            while not task.done():
                await asyncio.wait({task},timeout=0.25)
                if await request.is_disconnected():
                    task.cancel()
                    raise HTTPException(499, 'Voice request cancelled.')
            audio,model=await task
            return Response(audio,media_type='audio/wav',headers={'X-Bujji-Voice':'Bujji local voice' if model.startswith('hima-') else 'Aoede','X-Bujji-TTS-Model':'local-a-v2' if model.startswith('hima-') else model,'Cache-Control':'no-store'})
        except tts.TTSRateLimit as exc:
            raise HTTPException(429,str(exc),headers={"Retry-After":str(exc.seconds)}) from None
        except tts.TTSFailure as exc:
            raise HTTPException(503,str(exc)) from None
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError,tts.TTSFailure):
                if task.cancelled() or not task.done():
                    await task

    @app.post('/api/speech/transcribe', dependencies=protected)
    async def transcribe(request: Request, language: Literal['en-IN','te-IN'] = 'en-IN'):
        mime = request.headers.get('content-type','').split(';')[0].strip().lower()
        if mime not in speech.AUDIO_TYPES:
            raise HTTPException(415, 'Supported recording formats: WebM, Ogg, WAV, MP4.')
        length = request.headers.get('content-length')
        if length:
            try:
                size = int(length)
            except ValueError:
                raise HTTPException(400, 'Invalid recording length.') from None
            if size < 0 or size > speech.MAX_AUDIO_BYTES:
                raise HTTPException(413, 'Recording exceeds the 2 MB limit.')
        audio = bytearray()
        async for chunk in request.stream():
            if len(audio) + len(chunk) > speech.MAX_AUDIO_BYTES:
                raise HTTPException(413, 'Recording exceeds the 2 MB limit.')
            audio.extend(chunk)
        if not audio:
            raise HTTPException(422, 'No audio was recorded.')
        try:
            return await speech.transcribe(bytes(audio),mime,language)
        except providers.ProviderError as exc:
            raise HTTPException(503,str(exc)) from None

    @app.get('/api/memories', dependencies=protected)
    async def memories(q: str = Query(default='', max_length=100)):
        return store.rows('SELECT * FROM memories WHERE instr(lower(content),lower(?))>0 ORDER BY updated DESC LIMIT 100', (q,))

    @app.post('/api/memories', dependencies=protected)
    async def remember(body: Memory):
        if not body.content.strip():
            raise HTTPException(422, 'Memory cannot be blank.')
        return store.remember(body.content)

    @app.put('/api/memories/{item}', dependencies=protected)
    async def edit_memory(item: int, body: Memory):
        if not body.content.strip():
            raise HTTPException(422, 'Memory cannot be blank.')
        if not store.rows('SELECT id FROM memories WHERE id=?', (item,)):
            raise HTTPException(404, 'Memory not found.')
        try:
            store.execute('UPDATE memories SET content=?,updated=? WHERE id=?', (body.content.strip(), now(), item))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'That memory already exists.') from None
        return {'updated': True}

    @app.delete('/api/memories/{item}', dependencies=protected)
    async def forget(item: int):
        store.execute('DELETE FROM memories WHERE id=?', (item,))
        return {'deleted': True}

    def validate_reminder(body):
        try:
            due = due_utc(body.due, settings.timezone)
            if due <= datetime.now(timezone.utc) or not body.title.strip():
                raise ValueError()
            return due.isoformat()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Enter a valid future date and time.') from None

    @app.get('/api/reminders', dependencies=protected)
    async def reminders():
        return store.rows('SELECT * FROM reminders ORDER BY due DESC LIMIT 100')

    @app.post('/api/reminders', dependencies=protected)
    async def add_reminder(body: Reminder):
        due = validate_reminder(body)
        store.execute('INSERT OR IGNORE INTO reminders(title,due,recurrence,created) VALUES(?,?,?,?)', (body.title.strip(), due, body.recurrence, now()))
        return store.rows('SELECT * FROM reminders WHERE title=? AND due=? AND recurrence=?', (body.title.strip(), due, body.recurrence))[0]

    @app.put('/api/reminders/{item}', dependencies=protected)
    async def edit_reminder(item: int, body: Reminder):
        due = validate_reminder(body)
        if not store.rows('SELECT id FROM reminders WHERE id=?', (item,)):
            raise HTTPException(404, 'Reminder not found.')
        try:
            store.execute("UPDATE reminders SET title=?,due=?,recurrence=?,status='pending' WHERE id=?", (body.title.strip(), due, body.recurrence, item))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'That reminder already exists.') from None
        return {'updated': True}

    @app.delete('/api/reminders/{item}', dependencies=protected)
    async def cancel_reminder(item: int):
        store.execute("UPDATE reminders SET status='cancelled' WHERE id=?", (item,))
        return {'cancelled': True}

    @app.get('/api/notifications', dependencies=protected)
    async def notifications():
        rows=store.rows('SELECT * FROM notifications ORDER BY id DESC LIMIT 50')
        quiet=work_focus.quiet()
        return [{**row,'quiet':bool(row.get('quiet')) or (quiet and not row['content'].startswith(('Focus:', 'Break:')))} for row in rows]

    @app.post('/api/notifications/{item}/read', dependencies=protected)
    async def read_notification(item: int):
        store.execute('UPDATE notifications SET read=1 WHERE id=?', (item,))
        return {'read': True}

    @app.post('/api/documents/grant', dependencies=protected)
    async def grant_folder(body: FolderGrant, x_bujji_native: str = Header(default='')):
        if not native_grant_token or not secrets.compare_digest(x_bujji_native.encode(), native_grant_token.encode()):
            raise HTTPException(403, 'Choose a folder using the desktop folder picker.')
        return await asyncio.to_thread(document_tasks.grant, body.path)

    @app.post('/api/documents/scan', dependencies=protected)
    async def scan_documents(body: DocumentScan):
        return await document_tasks.scan(body.grant_id, body.cloud_ocr)

    @app.post('/api/documents/copy', dependencies=protected)
    async def copy_documents(body: DocumentCopy):
        return await asyncio.to_thread(document_tasks.copy, body.plan_id, body.selected, body.folder_name, body.confirmed)

    @app.delete('/api/documents/access', dependencies=protected)
    async def revoke_document_access():
        if document_tasks.scanning:
            raise HTTPException(409, 'Wait for the active scan to finish before revoking access.')
        with document_tasks.lock:
            document_tasks.grants.clear()
            document_tasks.plans.clear()
        return {'revoked':True}

    @app.get('/api/files', dependencies=protected)
    async def find_files(q: str = Query(min_length=1, max_length=100)):
        return files.search(settings.files, q)

    @app.post('/api/files/request', dependencies=protected)
    async def request_file(body: FileAction):
        return files.request_download(store, settings.files, body.path)

    @app.post('/api/files/{action}/confirm', dependencies=protected)
    async def download(action: str, body: Confirmation):
        if not body.confirmed:
            store.execute('UPDATE approvals SET used=1 WHERE id=?', (action,))
            return {'cancelled': True}
        path = files.consume(store, settings.files, action)
        return FileResponse(path, filename=path.name, media_type='application/octet-stream')

    dist = Path(os.environ['BUJJI_FRONTEND_DIR']) if os.getenv('BUJJI_FRONTEND_DIR') else Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app
