$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) { throw 'Run scripts/setup.ps1 first.' }
if (-not (Test-Path frontend/dist/index.html)) { throw 'Frontend is not built. Run scripts/setup.ps1.' }
& ./.venv/Scripts/python.exe -m uvicorn bujji.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
