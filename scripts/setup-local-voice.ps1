param([switch]$AcceptModelLicense)
$ErrorActionPreference = 'Stop'
if (-not $AcceptModelLicense) { throw 'Review docs/VOICE.md and the upstream model terms first; rerun with -AcceptModelLicense only if you accept them.' }
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Run scripts/setup.ps1 first.' }
& ./.venv/Scripts/python.exe -m pip install -e '.[local-voice]'
if ($LASTEXITCODE -ne 0) { throw 'Local voice dependency installation failed.' }
& ./.venv/Scripts/python.exe -m bujji.local_voice_assets
if ($LASTEXITCODE -ne 0) { throw 'Pinned local voice download failed. Read the status above and retry; chat configuration was not changed.' }
Write-Host 'Optional local voice assets prepared. Rebuild/reopen the app to use the integrated local voice.'
