$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11+ from python.org, then reopen PowerShell.' }
python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or later required'"
if ($LASTEXITCODE -ne 0) { throw 'A working Python 3.11+ is required. Disable the Windows Store python alias if necessary.' }
if (-not (Test-Path .venv/Scripts/python.exe)) { python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
& ./.venv/Scripts/python.exe -m pip install -r requirements.lock -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Python installation failed; check internet access and retry.' }
& ./.venv/Scripts/python.exe scripts/init_config.py
if ($LASTEXITCODE -ne 0) { throw 'Local configuration initialization failed.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 LTS or newer, reopen PowerShell, and run setup again.' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Edit .env for model configuration, then run scripts/start.ps1.'
Write-Host 'View your private pairing token locally in .env. Do not share or commit it.'
