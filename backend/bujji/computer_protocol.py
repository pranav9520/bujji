"""Typed desktop actions. The model cannot supply code, paths or permissions."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ControlError(Exception):pass

class Action(BaseModel):
    model_config=ConfigDict(extra='forbid')
    op: Literal['open_app','open_url','window','browser','type_text','click_control']
    app: str = Field(default='',max_length=100)
    window: str = Field(default='',max_length=100)
    command: str = Field(default='',max_length=30)
    control: str = Field(default='',max_length=100)
    text: str = Field(default='',max_length=1500)
    url: str = Field(default='',max_length=2000)

    @model_validator(mode='after')
    def check(self):
        allowed={'open_app':{'app'},'open_url':{'url'},'window':{'window','command'},'browser':{'window','command'},'type_text':{'window','control','text'},'click_control':{'window','control'}}[self.op]
        if any(value for key,value in self.model_dump().items() if key!='op' and key not in allowed):raise ValueError('Unexpected action fields')
        if self.op=='open_app' and not self.app:raise ValueError('Choose an installed app')
        if self.op=='open_url':safe_url(self.url)
        if self.op not in {'open_app','open_url'} and not self.window:raise ValueError('Choose a target window')
        if self.op=='window' and self.command not in {'focus','left','right','maximize','minimize','restore','close'}:raise ValueError('Unknown window command')
        if self.op=='browser' and self.command not in {'new_tab','close_tab','next_tab','previous_tab','reopen_tab','reload'}:raise ValueError('Unknown browser command')
        if self.op in {'type_text','click_control'} and not self.control:raise ValueError('Choose a currently inspected control')
        if self.op=='type_text' and (not self.text or any(ord(c)<32 for c in self.text)):raise ValueError('Unsupported typing text')
        return self

class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    summary: str = Field(max_length=500)
    actions: list[Action] = Field(default_factory=list,max_length=8)

class ComputerRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operation: Literal['status','plan','execute','stop','save_routine','delete_routine','diagnostics','info']
    message: str = Field(default='',max_length=2000)
    target: str = Field(default='',max_length=100)
    read_screen: bool = False
    direct: bool = False
    plan_id: str = Field(default='',max_length=100)
    confirmed: bool = False
    name: str = Field(default='',max_length=60)


def safe_url(url):
    try:
        p=urlsplit(url)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or any(ord(c)<33 for c in url):raise ValueError()
        p.port
    except ValueError:raise ValueError('Only ordinary HTTP/HTTPS URLs without credentials can be opened') from None
    return url


def requires_confirmation(action):
    return action.op in {'type_text','click_control'} or (action.op=='window' and action.command=='close') or (action.op=='browser' and action.command in {'close_tab','reopen_tab','reload'})
