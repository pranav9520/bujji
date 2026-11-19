"""Conservative target selection: explicit override, named app, then last active."""
import re

ALIASES={'chrome.exe':('chrome','google chrome'),'msedge.exe':('edge','microsoft edge'),'notepad.exe':('notepad',),'code.exe':('vs code','vscode','visual studio code'),'firefox.exe':('firefox',),'brave.exe':('brave',),'winword.exe':('word','microsoft word'),'excel.exe':('excel',),'spotify.exe':('spotify',),'explorer.exe':('file explorer','explorer')}

def choose(windows,foreground,manual='',message=''):
    if manual:return next((w for w in windows if w['id']==manual),None)
    text=' '.join(message.lower().split())
    named=[w for w in windows if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text) for alias in ALIASES.get(w['exe'],()))]
    if len(named)==1:return named[0]
    return next((w for w in windows if w['id']==foreground),windows[0] if windows else None)
