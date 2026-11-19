param([switch]$IncludeLocalVoice)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows app on Windows.' }
if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Run scripts/setup.ps1 first.' }
& ./.venv/Scripts/python.exe -m pip install 'pyinstaller==6.16.0' -e '.[desktop-control]'
if ($LASTEXITCODE -ne 0) { throw 'Backend build dependencies failed to install.' }
if ($IncludeLocalVoice) {
    & ./.venv/Scripts/python.exe -m pip install -e '.[local-voice]'
    if ($LASTEXITCODE -ne 0) { throw 'Optional voice dependencies failed.' }
}
& ./.venv/Scripts/python.exe -c "from pathlib import Path; import comtypes, comtypes.client; comtypes.client.gen_dir=str(Path(comtypes.__file__).parent/'gen'); comtypes.client.GetModule('UIAutomationCore.dll')"
if ($LASTEXITCODE -ne 0) { throw 'Windows UI Automation interface preparation failed.' }
& npm.cmd --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
& npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
& npm.cmd --prefix desktop ci
if ($LASTEXITCODE -ne 0) { throw 'Electron dependencies failed.' }
$collect = @('--collect-all','bujji','--collect-all','uvicorn','--collect-all','tzdata','--collect-all','certifi','--collect-all','uiautomation','--collect-all','comtypes','--hidden-import','comtypes.gen.UIAutomationClient')
if ($IncludeLocalVoice) { $collect += @('--collect-all','onnxruntime','--collect-all','numpy','--collect-all','safetensors','--collect-all','sentencepiece','--collect-all','yaml') }
& ./.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onedir --console --name bujji-backend --paths backend @collect --distpath desktop/backend-dist --workpath desktop/backend-build --specpath desktop/backend-build desktop/backend_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }
& ./.venv/Scripts/python.exe scripts/collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'Dependency notice generation failed.' }
& npm.cmd --prefix desktop run pack:win
if ($LASTEXITCODE -ne 0) { throw 'Windows ZIP packaging failed.' }
Write-Host 'Build complete in desktop/release. Extract ALL files, then run Bujji.exe.'
Write-Host 'Packaged builds create their own private workspace and random owner token on first launch.'
