"""Explicit per-phone grants. Read-only files and bounded native commands over pairing HTTPS."""
import asyncio
import os
from collections import OrderedDict
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from fastapi import HTTPException
from .computer import Computer
from .computer_protocol import ComputerRequest, ControlError
from . import providers

MAX_DOWNLOAD = 25 * 1024 * 1024

class RemoteGrant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    control: bool = False
    files: bool = False

class RemoteFiles(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['list','search','read','download'] = 'list'
    path: str = Field(default='',max_length=2000)
    query: str = Field(default='',max_length=120)
    offset: int = Field(default=0,ge=0,le=1000000)

class RemoteCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['command','status','stop'] = 'command'
    request_id: str = Field(default='',pattern=r'^[a-zA-Z0-9_-]{0,80}$')
    message: str = Field(default='',max_length=2000)
    target: str = Field(default='',max_length=100)
    read_screen: bool = False

class RemoteAccess:
    def __init__(self,store,devices,workspace,local):
        self.store,self.devices,self.workspace,self.local = store,devices,workspace,local
        self.computer=Computer(store)
        self.lock=asyncio.Lock()
        self.owner=None
        self.active_task=None
        self.results=OrderedDict()
        self.computer.guard=self.guard

    def permission(self,device):
        active=self.store.rows('SELECT id FROM mobile_devices WHERE id=? AND revoked=0',(device,))
        if not active: raise HTTPException(401,'Phone connection revoked. Pair again.')
        return self.store.state('remote_access_'+device,{'control':False,'files':False})

    def require(self,device,capability):
        if not self.permission(device).get(capability):
            raise HTTPException(403,'Enable '+capability+' for this phone in laptop Devices first.')

    def grant(self,device,body):
        self.permission(device)
        self.store.set_state('remote_access_'+device,body.model_dump())
        if not body.control and self.owner==device:self.halt()
        self.store.audit('phone_remote_grant','control='+str(body.control)+', files='+str(body.files))
        return body.model_dump()

    def guard(self):
        try:self.require(self.owner,'control')
        except HTTPException:raise ControlError('Phone control permission was revoked. Remaining steps stopped.') from None

    def halt(self):
        result=self.computer.stop()
        if self.active_task is not None:self.active_task.cancel()
        return result

    def stop(self,device):
        self.require(device,'control')
        if self.lock.locked() and self.owner is None:raise HTTPException(409,'The local widget is active. Use its Stop button.')
        if self.owner not in (None,device):raise HTTPException(409,'Another phone is controlling the laptop.')
        return self.halt()

    def status(self,device):
        permission=self.permission(device)
        return {'online':True,'protocol':2,'permissions':permission,
                'roots':self.workspace.status()['locations'] if permission.get('files') and self.workspace.enabled else [],
                'files_enabled':self.workspace.enabled,'download_limit':MAX_DOWNLOAD,
                'control_busy':self.lock.locked() or self.local.busy,'live_video':False}

    def files(self,device,body):
        self.require(device,'files')
        try:
            if body.operation in {'search','read'}:
                result=self.workspace.search(body.query,body.path or None,False) if body.operation=='search' else self.workspace.read_local(body.path)
                self.require(device,'files')
                return result
            path=self.workspace.checked(body.path)
            if body.operation=='download':
                if not path.is_file():raise ValueError('Choose a regular file.')
                initial=path.stat()
                if initial.st_size>MAX_DOWNLOAD:raise ValueError('Download files up to 25 MB. Choose a smaller file.')
                fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
                with os.fdopen(fd,'rb') as stream:
                    current=os.fstat(stream.fileno())
                    if (current.st_dev,current.st_ino)!=(initial.st_dev,initial.st_ino):raise ValueError('File changed. Refresh and select it again.')
                    data=stream.read(MAX_DOWNLOAD+1)
                if len(data)>MAX_DOWNLOAD:raise ValueError('File exceeds 25 MB.')
                self.require(device,'files')
                return data,path.name
            if not path.is_dir():raise ValueError('Choose a folder.')
            entries=[];next_offset=None
            with os.scandir(path) as iterator:
                for index,entry in enumerate(iterator):
                    if index<body.offset:continue
                    if index>=body.offset+500 or len(entries)>=80:
                        next_offset=index;break
                    try:
                        item=self.workspace.checked(entry.path)
                        if not item.is_file() and not item.is_dir():continue
                        entries.append({'path':str(item),'name':item.name,'kind':'folder' if item.is_dir() else 'file','bytes':item.stat().st_size if item.is_file() else None})
                    except (OSError,ValueError):continue
            self.require(device,'files')
            return {'path':str(path),'entries':entries,'next_offset':next_offset,'partial':next_offset is not None}
        except (ValueError,OSError) as exc:
            raise HTTPException(409,str(exc) if isinstance(exc,ValueError) else 'File unavailable. Refresh the folder and retry.') from None

    async def command(self,device,body):
        self.require(device,'control')
        if body.operation=='stop':return self.stop(device)
        key=(device,body.request_id)
        fingerprint=(body.operation,body.message,body.target,body.read_screen)
        if body.operation=='command':
            if not body.request_id or not body.message.strip():raise HTTPException(422,'Provide a request ID and command.')
            if key in self.results:
                old=self.results[key]
                if old[0]!=fingerprint:raise HTTPException(409,'That request ID belongs to another command.')
                if old[1] is None:raise HTTPException(409,'That command was interrupted or is still running. Check the laptop before issuing it again.')
                return old[1]
        if self.lock.locked() or self.local.busy:raise HTTPException(409,'Laptop control is busy. Wait or stop your command.')
        async with self.lock:
            self.owner=device
            self.active_task=asyncio.current_task()
            if body.operation=='command':
                self.results[key]=(fingerprint,None)
                while len(self.results)>100:self.results.popitem(last=False)
            try:
                if body.operation=='status':return await self.computer.request(ComputerRequest(operation='status',target=body.target))
                plan=await self.computer.request(ComputerRequest(operation='plan',message=body.message,target=body.target,read_screen=body.read_screen,direct=True))
                self.require(device,'control')
                result=plan
                if plan.get('plan_id'):
                    result=await self.computer.request(ComputerRequest(operation='execute',plan_id=plan['plan_id'],confirmed=True))
                self.results[key]=(fingerprint,result)
                self.store.audit('phone_remote_command','completed' if result.get('completed') else 'answered_or_partial')
                return result
            except (ControlError,providers.ProviderError) as exc:
                self.computer.stop()
                raise HTTPException(409,str(exc)) from None
            except asyncio.CancelledError:
                self.computer.stop();raise
            finally:self.owner=None;self.active_task=None
