"""On-demand Windows worker. No arbitrary shell, scripts, model paths or hotkeys.
Design informed by Atticus Windows' ctypes/UI Automation helpers; independently
implemented for Bujji's typed, target-bound contract (see docs/COMPUTER_CONTROL.md).
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from .computer_protocol import Action, ControlError, safe_url
from .computer_wire import encode, diagnostic
from .computer_targets import choose

BROWSERS={'chrome.exe','msedge.exe','firefox.exe','brave.exe','opera.exe','vivaldi.exe'}
TERMINALS={'cmd.exe','powershell.exe','pwsh.exe','windowsterminal.exe','wt.exe','conhost.exe','mintty.exe','bash.exe','python.exe','pythonw.exe','wscript.exe','cscript.exe','regedit.exe','mmc.exe','taskmgr.exe'}
SENSITIVE=re.compile(r'password|passcode|secret|api.?key|credit.?card|payment|one.?time|verification.?code|otp',re.I)
DANGEROUS=re.compile(r'\b(send|delete|remove|buy|purchase|pay|submit|transfer|install|uninstall|allow|grant|authorize|enable|disable|security|sign.?in|log.?in|confirm|accept)\b',re.I)

def fingerprint(value):return hashlib.sha256(value.encode()).hexdigest()[:24]

def app_catalog():
    result=[]
    root=Path(os.environ.get('SYSTEMROOT',r'C:\Windows'))
    for name,file in [('Notepad',root/'system32/notepad.exe'),('Calculator',root/'system32/calc.exe'),('File Explorer',root/'explorer.exe')]:
        if file.is_file():result.append({'id':fingerprint(str(file)),'name':name,'path':str(file)})
    roots=[Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs',Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Microsoft/Windows/Start Menu/Programs']
    seen={a['name'].casefold() for a in result};deadline=time.monotonic()+2;visited=0
    stack=[(folder,0) for folder in roots]
    while stack and len(result)<180 and visited<1200 and time.monotonic()<deadline:
        folder,depth=stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited+=1
                    if visited>1200 or len(result)>=180 or time.monotonic()>=deadline:break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Don't descend junctions/cloud redirects/other reparse folders.
                            if depth<6 and not getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:stack.append((Path(entry.path),depth+1))
                            continue
                        if not entry.name.lower().endswith('.lnk') or not entry.is_file(follow_symlinks=False):continue
                    except OSError:continue
                    name=Path(entry.name).stem
                    if name.casefold() in seen or re.search(r'uninstall|powershell|terminal|command prompt|registry|script|administrat|python|node.js|git bash',name,re.I):continue
                    result.append({'id':fingerprint(entry.path),'name':name,'path':entry.path});seen.add(name.casefold())
        except OSError:continue

    return result

def launch(item):
    action=Action.model_validate(item['action'])
    if action.op=='open_app':
        found=next((a for a in app_catalog() if a['id']==action.app and a['name']==item['app']['name']),None)
        if not found:raise ControlError('The installed app shortcut changed or was not found. Ask again.')
        os.startfile(found['path']);return {'detail':'Windows accepted the request to launch '+found['name']+'. App readiness is not verified.'}
    if action.op=='open_url':
        os.startfile(safe_url(action.url));return {'detail':'Windows accepted the website-open request. Page loading is not verified.'}
    raise ControlError('That action needs a window target.')

class Windows:
    def __init__(self):
        if sys.platform!='win32':raise ControlError('Computer control is available only in the Windows desktop app.')
        import ctypes as c
        from ctypes import wintypes as W
        self.c=c;self.W=W;self.u=c.WinDLL('user32',use_last_error=True);self.k=c.WinDLL('kernel32',use_last_error=True)
        self.u.GetForegroundWindow.restype=W.HWND
        for name,args,result in [('GetWindowTextLengthW',[W.HWND],c.c_int),('GetWindowTextW',[W.HWND,W.LPWSTR,c.c_int],c.c_int),('IsWindowVisible',[W.HWND],W.BOOL),('IsWindow',[W.HWND],W.BOOL),('IsIconic',[W.HWND],W.BOOL),('IsZoomed',[W.HWND],W.BOOL),('GetWindowThreadProcessId',[W.HWND,c.POINTER(W.DWORD)],W.DWORD),('SetForegroundWindow',[W.HWND],W.BOOL),('ShowWindow',[W.HWND,c.c_int],W.BOOL),('GetWindowRect',[W.HWND,c.POINTER(W.RECT)],W.BOOL),('MoveWindow',[W.HWND,c.c_int,c.c_int,c.c_int,c.c_int,W.BOOL],W.BOOL),('PostMessageW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],W.BOOL)]:
            fn=getattr(self.u,name);fn.argtypes=args;fn.restype=result
        self.k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];self.k.OpenProcess.restype=W.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,c.POINTER(W.DWORD)];self.k.QueryFullProcessImageNameW.restype=W.BOOL
        self.k.CloseHandle.argtypes=[W.HANDLE];self.k.CloseHandle.restype=W.BOOL
        try:self.u.SetProcessDpiAwarenessContext(c.c_void_p(-4))
        except (AttributeError,OSError):pass

    def describe(self,hwnd):
        c,W=self.c,self.W
        if not self.u.IsWindow(hwnd) or not self.u.IsWindowVisible(hwnd):return None
        pid=W.DWORD();self.u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        if pid.value in {os.getpid(),int(os.getenv('BUJJI_DESKTOP_PID','0'))}:return None
        name=c.create_unicode_buffer(min(600,self.u.GetWindowTextLengthW(hwnd)+1));self.u.GetWindowTextW(hwnd,name,len(name))
        if not name.value:return None
        process=self.k.OpenProcess(0x1000,False,pid.value)
        if not process:return None
        try:
            path=c.create_unicode_buffer(32768);length=W.DWORD(len(path))
            if not self.k.QueryFullProcessImageNameW(process,0,path,c.byref(length)):return None
            exe=Path(path.value).name.lower()
        finally:self.k.CloseHandle(process)
        if exe in {'bujji.exe','electron.exe','bujji-backend.exe'}:return None
        return {'id':str(int(hwnd)),'pid':pid.value,'exe':exe,'title':name.value[:180]}

    def windows(self):
        result=[];c,W=self.c,self.W
        callback=c.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        deadline=time.monotonic()+2
        def visit(hwnd,_):
            if len(result)>=30 or time.monotonic()>=deadline:return False
            try:
                item=self.describe(hwnd)
                if item and len(result)<30:result.append(item)
            except (OSError,ValueError):pass
            return True
        fn=callback(visit);self.u.EnumWindows.argtypes=[callback,W.LPARAM];self.u.EnumWindows(fn,0)
        return result

    def check(self,bound,strict_title=False):
        try:current=self.describe(int(bound['id']))
        except (ValueError,TypeError,KeyError):current=None
        if not current or any(current[k]!=bound.get(k) for k in ('id','pid','exe')):raise ControlError('The target app changed or closed. Ask again; no input was sent.')
        if strict_title and current.get('title')!=bound.get('title'):raise ControlError('The selected tab/document changed since approval. Ask again before closing or reloading it.')
        if current['exe'] in TERMINALS:raise ControlError('Terminal, administration and script windows are excluded from computer control.')
        return int(current['id'])

    def focus(self,bound):
        hwnd=self.check(bound)
        if self.u.IsIconic(hwnd):self.u.ShowWindow(hwnd,9)
        # Join the foreground input queue only for this focus request, then detach.
        foreground=self.u.GetForegroundWindow()
        self.k.GetCurrentThreadId.restype=self.W.DWORD
        thread=self.k.GetCurrentThreadId();foreground_thread=self.u.GetWindowThreadProcessId(foreground,None) if foreground else 0
        self.u.AttachThreadInput.argtypes=[self.W.DWORD,self.W.DWORD,self.W.BOOL];self.u.AttachThreadInput.restype=self.W.BOOL
        attached=bool(foreground_thread and foreground_thread!=thread and self.u.AttachThreadInput(thread,foreground_thread,True))
        try:self.u.SetForegroundWindow(hwnd)
        finally:
            if attached:self.u.AttachThreadInput(thread,foreground_thread,False)
        time.sleep(.15)
        if self.u.GetForegroundWindow()!=hwnd:raise ControlError('Windows did not allow the target app to take focus. Select it manually and retry.')
        return hwnd

    def send(self,bound,keys=None,text=None,field_guard=None):
        c,W=self.c,self.W;hwnd=self.check(bound)
        if self.u.GetForegroundWindow()!=hwnd:raise ControlError('Focus changed. Input was stopped to avoid typing into another app.')
        class KEY(c.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',c.c_size_t)]
        class MOUSE(c.Structure):_fields_=[('x',W.LONG),('y',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',c.c_size_t)]
        class UNION(c.Union):_fields_=[('key',KEY),('mouse',MOUSE)]
        class INPUT(c.Structure):_anonymous_=('value',);_fields_=[('type',W.DWORD),('value',UNION)]
        self.u.SendInput.argtypes=[W.UINT,c.POINTER(INPUT),c.c_int];self.u.SendInput.restype=W.UINT
        def emit(vk=0,scan=0,flags=0):
            value=INPUT(type=1,key=KEY(vk,scan,flags,0,0))
            if self.u.SendInput(1,c.byref(value),c.sizeof(INPUT))!=1:raise ControlError('Windows blocked input, possibly because the app is elevated.')
        if keys:
            pressed=[]
            try:
                for vk in keys:emit(vk=vk);pressed.append(vk)
            finally:
                for vk in reversed(pressed):emit(vk=vk,flags=2)
        else:
            raw=text.encode('utf-16-le')
            for index in range(0,len(raw),2):
                if field_guard:field_guard()
                if self.u.GetForegroundWindow()!=hwnd:raise ControlError('Focus changed during typing; stopped remaining text.')
                code=int.from_bytes(raw[index:index+2],'little');emit(scan=code,flags=4);emit(scan=code,flags=6)

    def controls(self,bound,include_text=False):
        hwnd=self.check(bound)
        import uiautomation as auto
        auto.Logger.SetLogFile('')
        root=auto.ControlFromHandle(hwnd);result=[];end=time.monotonic()+2;remaining=4000
        for index,(control,depth) in enumerate(auto.WalkControl(root,maxDepth=16)):
            if index>900 or time.monotonic()>end or len(result)>=70:break
            try:
                if control.IsOffscreen or not control.IsEnabled or control.IsPassword:continue
                name=' '.join((control.Name or '').split())[:160]
                if SENSITIVE.search(name):continue
                kind=control.ControlTypeName
                if kind not in {'EditControl','DocumentControl','TextControl','ButtonControl','HyperlinkControl','TabItemControl','MenuItemControl','CheckBoxControl','ComboBoxControl'}:continue
                rid=list(control.GetRuntimeId())
                if not name and kind not in {'EditControl','DocumentControl'}:continue
                # Never read ValuePattern: password widgets sometimes mislabel themselves.
                item={'id':fingerprint(json.dumps(rid)),'rid':rid,'name':name,'kind':kind,'editable':kind in {'EditControl','DocumentControl'},'_control':control}
                if include_text and remaining>0 and kind in {'EditControl','DocumentControl'}:
                    try:
                        pattern=control.GetTextPattern()
                        if pattern:
                            excerpt=pattern.DocumentRange.GetText(min(1200,remaining))
                            item['text']=excerpt[:min(1200,remaining)];remaining-=len(item['text'])
                    except Exception:pass
                result.append(item)
            except Exception:continue
        return result

    def current_control(self,bound,saved):
        current=next((x for x in self.controls(bound) if x['rid']==saved.get('rid') and x['name']==saved.get('name') and x['kind']==saved.get('kind')),None)
        if not current:raise ControlError('That screen control changed. Read the app again before acting.')
        if DANGEROUS.search(current['name']) or SENSITIVE.search(current['name']):raise ControlError('Sending, deleting, payments, authentication and security controls are not supported here. Complete that step yourself.')
        return current

    def snapshot(self,target,read,catalog=True,message=""):
        wins=self.windows();active=str(int(self.u.GetForegroundWindow() or 0))
        # An explicit selected target never silently falls back to a different app.
        chosen=choose(wins,active,target,message)
        result={'windows':wins,'apps':[{k:v for k,v in a.items() if k!='path'} for a in app_catalog()] if catalog else [],'target':chosen['id'] if chosen else '', 'controls':[]}
        if read and chosen:
            diagnostic(sys.stderr,'screen_text')
            try:result['controls']=[{k:v for k,v in x.items() if k!='_control'} for x in self.controls(chosen,include_text=True)]
            except ImportError:raise ControlError('Install the desktop-control dependencies with the full build first.') from None
            except ControlError:raise
            except Exception:raise ControlError('This app does not expose readable Windows controls. Try another app; no screenshot was taken.') from None
        return result

    def act(self,item):
        action=Action.model_validate(item['action'])
        if action.op in {'open_app','open_url'}:return launch(item)
        bound=item['window'];hwnd=self.check(bound)
        if action.op=='window':
            command=action.command
            if command=='focus':self.focus(bound)
            elif command=='close':
                self.check(bound,strict_title=True)
                if not self.u.PostMessageW(hwnd,0x112,0xF060,0):raise ControlError('Windows rejected the close request.')
                time.sleep(.2)
                return {'detail':'Window closed.' if not self.u.IsWindow(hwnd) else 'Close requested; the app may require an unsaved-work response. Nothing was force-killed.'}
            elif command in {'maximize','minimize','restore'}:
                self.u.ShowWindow(hwnd,{'maximize':3,'minimize':6,'restore':9}[command]);time.sleep(.15)
                success=bool(self.u.IsIconic(hwnd)) if command=='minimize' else bool(self.u.IsZoomed(hwnd)) if command=='maximize' else not self.u.IsIconic(hwnd) and not self.u.IsZoomed(hwnd)
                if not success:raise ControlError('The app did not reach the requested window state.')
            else:
                c,W=self.c,self.W
                self.u.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];self.u.MonitorFromWindow.restype=W.HANDLE
                class INFO(c.Structure):_fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
                info=INFO();info.size=c.sizeof(info);self.u.GetMonitorInfoW.argtypes=[W.HANDLE,c.POINTER(INFO)]
                if not self.u.GetMonitorInfoW(self.u.MonitorFromWindow(hwnd,2),c.byref(info)):raise ControlError('Could not read the target monitor.')
                r=info.work;width=(r.right-r.left)//2;x=r.left if command=='left' else r.left+width
                self.u.ShowWindow(hwnd,9)
                if not self.u.MoveWindow(hwnd,x,r.top,width,r.bottom-r.top,True):raise ControlError('Windows rejected window placement.')
                rect=W.RECT();self.u.GetWindowRect(hwnd,c.byref(rect))
                if abs(rect.left-x)>25 or abs(rect.top-r.top)>25:raise ControlError('The app did not accept the requested placement.')
            return {'detail':'Observed window action: '+command+'.'}
        if action.op=='browser':
            if bound['exe'] not in BROWSERS:raise ControlError('Select a supported browser window for tab commands.')
            self.focus(bound)
            combos={'new_tab':[0x11,0x54],'close_tab':[0x11,0x57],'next_tab':[0x11,0x09],'previous_tab':[0x11,0x10,0x09],'reopen_tab':[0x11,0x10,0x54],'reload':[0x11,0x52]}
            if action.command in {'close_tab','reload','reopen_tab'}:self.check(bound,strict_title=True)
            self.send(bound,keys=combos[action.command]);return {'detail':'Sent '+action.command.replace('_',' ')+' shortcut to '+bound['exe']+'. Tab/page outcome is not independently verified.'}
        current=self.current_control(bound,item['control']);self.focus(bound);control=current['_control']
        if action.op=='type_text':
            if not current['editable']:raise ControlError('The selected control is not editable.')
            control.SetFocus()
            if self.u.GetForegroundWindow()!=hwnd:raise ControlError('Focus changed before typing.')
            # Only send literal Unicode, never Enter/submit or a model-provided hotkey.
            import uiautomation as auto
            def guard():
                focused=auto.GetFocusedControl()
                if focused.IsPassword or list(focused.GetRuntimeId())!=current['rid']:raise ControlError('The focused field changed. Stopped remaining text.')
            guard()
            self.send(bound,text=action.text,field_guard=guard);return {'detail':'Literal text input sent to the selected field. Nothing was submitted.'}
        if action.op=='click_control':
            if current['kind'] not in {'ButtonControl','HyperlinkControl','TabItemControl','CheckBoxControl','MenuItemControl'}:raise ControlError('This control does not support the permitted click actions.')
            if self.u.GetForegroundWindow()!=hwnd:raise ControlError('Focus changed before clicking.')
            for method,operation in [('GetInvokePattern','Invoke'),('GetSelectionItemPattern','Select'),('GetTogglePattern','Toggle')]:
                try:pattern=getattr(control,method)()
                except Exception:continue
                if pattern:
                    getattr(pattern,operation)();return {'detail':'Requested accessibility action on '+current['name']+'. Application outcome is not independently verified.'}
            raise ControlError('This control has no supported accessibility action. No coordinate click was attempted.')
        raise ControlError('Unsupported control action')

def main():
    try:
        diagnostic(sys.stderr,'request')
        raw=sys.stdin.buffer.read(30001)
        if len(raw)>30000:raise ControlError('Computer request too large.')
        from contextlib import redirect_stdout
        body=json.loads(raw)
        with redirect_stdout(sys.stderr):
            if sys.platform!='win32':raise ControlError('Computer control is available only in the Windows desktop app.')
            if body.get('op')=='catalog':
                diagnostic(sys.stderr,'catalog')
                result={'apps':[{k:v for k,v in item.items() if k!='path'} for item in app_catalog()]}
            elif body.get('op')=='act' and body.get('item',{}).get('action',{}).get('op') in {'open_app','open_url'}:
                diagnostic(sys.stderr,'action');result=launch(body['item'])
            else:
                diagnostic(sys.stderr,'initializing');native=Windows()
                if body.get('op')=='snapshot':
                    diagnostic(sys.stderr,'windows')
                    result=native.snapshot(body.get('target',''),bool(body.get('read')),bool(body.get('catalog',True)),body.get('message',''))
                elif body.get('op')=='act':
                    diagnostic(sys.stderr,'action');result=native.act(body['item'])
                else:raise ControlError('Unknown desktop helper operation.')
        diagnostic(sys.stderr,'complete')
    except ControlError as exc:
        diagnostic(sys.stderr,'error',type(exc).__name__);result={'error':str(exc)}
    except Exception as exc:
        diagnostic(sys.stderr,'error',type(exc).__name__)
        result={'error':'Windows could not complete this control request ('+type(exc).__name__+'). No further steps ran.'}
    sys.stdout.buffer.write(encode(result));sys.stdout.buffer.flush();return 0

if __name__=='__main__':raise SystemExit(main())
