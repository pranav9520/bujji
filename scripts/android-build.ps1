param([switch]$Release)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'android')
$javaExe = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin/java.exe' } else { 'java.exe' }
$version = & $javaExe -version 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'version "17\.') { throw 'Use JDK 17. Set JAVA_HOME to its install folder; configure VS Code Gradle Java Home to the same JDK.' }
$task = if ($Release) { ':app:assembleRelease' } else { ':app:assembleDebug' }
& ./gradlew.bat $task :app:testDebugUnitTest :app:lintDebug --console=plain
if ($LASTEXITCODE -ne 0) { throw 'Android checks/build failed.' }
Write-Host 'APK output is under android/app/build/outputs/apk. Debug keys are local and never committed.'
