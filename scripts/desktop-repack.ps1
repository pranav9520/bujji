# Reuse a previously built backend/UI to bypass the NSIS installer path.
# This is suitable for packaging-only changes; use desktop-build.ps1 after backend/UI edits.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Get-Process -Name 'Bujji','bujji-backend' -ErrorAction SilentlyContinue) {
    throw 'Quit Bujji from its tray menu before repacking. No processes were stopped automatically.'
}
if (-not (Test-Path desktop/backend-dist/bujji-backend/bujji-backend.exe)) { throw 'No Windows backend build found. Run scripts/desktop-build.ps1 instead.' }
if (-not (Test-Path frontend/dist/index.html)) { throw 'No interface build found. Run scripts/desktop-build.ps1 instead.' }
if (-not (Test-Path desktop/node_modules/.bin/electron-builder.cmd)) { throw 'Desktop build tools are missing. Run scripts/desktop-build.ps1 instead.' }
& npm.cmd --prefix desktop run pack:win
if ($LASTEXITCODE -ne 0) { throw 'ZIP repack failed. Send the final non-secret error lines.' }
$desktopVersion = (Get-Content desktop/package.json -Raw | ConvertFrom-Json).version
Write-Host "Created desktop/release/Bujji-$desktopVersion-x64.zip."
Write-Host 'Extract ALL files to a permanent new folder, then run Bujji.exe. No setup/uninstaller is involved.'
Write-Host 'Packaged app settings and data stay in your private BujjiCommunity workspace.'
