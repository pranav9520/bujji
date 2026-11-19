$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Run scripts/setup.ps1 first.' }
if (-not (Test-Path .env)) { throw 'Run setup to create your local .env first.' }
if (-not (Test-Path frontend/dist/index.html)) { throw 'Build the interface: npm.cmd --prefix frontend run build' }
if (-not (Test-Path desktop/node_modules/electron/dist/electron.exe)) {
    & npm.cmd --prefix desktop ci
    if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed. Check internet access and retry.' }
}
Write-Host 'Starting Bujji desktop. Close hides it in the tray; use tray > Quit Bujji to stop it.'
& npm.cmd --prefix desktop start
if ($LASTEXITCODE -ne 0) { throw 'Desktop launch failed. Check the error dialog and stop previous Bujji backends.' }
