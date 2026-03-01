# build-installer.ps1
# Master build script for creating the LTX Desktop installer.
# Prepares the app (Python env, npm deps, frontend) then packages with electron-builder.

param(
    [switch]$SkipPython,
    [switch]$SkipNpm,
    [switch]$Clean,
    [switch]$Unpack,
    [string]$Publish = ""
)

$ErrorActionPreference = "Stop"

Write-Host @"

  _   _______  __  ____            _    _
 | | |_   _\ \/ / |  _ \  ___  ___| | _| |_ ___  _ __
 | |   | |  \  /  | | | |/ _ \/ __| |/ / __/ _ \| '_ \
 | |___| |  /  \  | |_| |  __/\__ \   <| || (_) | |_) |
 |_____|_| /_/\_\ |____/ \___||___/_|\_\\__\___/| .__/
                                                 |_|
  Installer Build Script

"@ -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Stage 1: Build app
$appParams = @{}
if ($SkipPython) { $appParams["SkipPython"] = $true }
if ($SkipNpm)    { $appParams["SkipNpm"] = $true }
if ($Clean)      { $appParams["Clean"] = $true }

& "$ScriptDir\build-app.ps1" @appParams
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Stage 2: Package installer
$pkgParams = @{}
if ($Unpack)        { $pkgParams["Unpack"] = $true }
if ($Publish -ne "") { $pkgParams["Publish"] = $Publish }

& "$ScriptDir\package-installer.ps1" @pkgParams
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
