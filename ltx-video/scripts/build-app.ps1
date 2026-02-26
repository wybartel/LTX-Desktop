# build-app.ps1
# Prepares the application for packaging: Python environment, npm deps, frontend build.

param(
    [switch]$SkipPython,
    [switch]$SkipNpm,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonEmbedDir = Join-Path $ProjectDir "python-embed"
$ReleaseDir = Join-Path $ProjectDir "release"

Set-Location $ProjectDir

# Clean build if requested
if ($Clean) {
    Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow

    if (Test-Path $PythonEmbedDir) {
        Remove-Item -Recurse -Force $PythonEmbedDir
    }
    if (Test-Path $ReleaseDir) {
        Remove-Item -Recurse -Force $ReleaseDir
    }
    if (Test-Path "dist") {
        Remove-Item -Recurse -Force "dist"
    }
    if (Test-Path "dist-electron") {
        Remove-Item -Recurse -Force "dist-electron"
    }

    Write-Host "Clean complete." -ForegroundColor Green
}

# Step 1: Prepare Python environment
if (-not $SkipPython) {
    Write-Host "`n[1/3] Preparing Python environment..." -ForegroundColor Yellow

    if (Test-Path $PythonEmbedDir) {
        Write-Host "Python environment already exists. Use -Clean to rebuild." -ForegroundColor DarkYellow
    } else {
        & "$ScriptDir\prepare-python.ps1"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to prepare Python environment!" -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "`n[1/3] Skipping Python preparation (using existing)..." -ForegroundColor DarkYellow
}

# Verify Python environment exists
if (-not (Test-Path $PythonEmbedDir)) {
    Write-Host "ERROR: Python environment not found at $PythonEmbedDir" -ForegroundColor Red
    Write-Host "Run without -SkipPython to create it." -ForegroundColor Red
    exit 1
}

# Step 2: Install npm dependencies
if (-not $SkipNpm) {
    Write-Host "`n[2/3] Installing npm dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install npm dependencies!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n[2/3] Skipping npm install..." -ForegroundColor DarkYellow
}

# Step 3: Build frontend and electron
Write-Host "`n[3/3] Building frontend and Electron app..." -ForegroundColor Yellow

npm run build:frontend
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build frontend!" -ForegroundColor Red
    exit 1
}

Write-Host "`nApp build complete. Run package-installer.ps1 to create the installer." -ForegroundColor Green
