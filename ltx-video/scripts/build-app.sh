#!/usr/bin/env bash
# build-app.sh
# Prepares the application for packaging: Python environment, npm deps, frontend build.
#
# Usage:
#   bash scripts/build-app.sh [options]
#
# Options:
#   --platform mac|win   Target platform (auto-detected if omitted)
#   --skip-python        Use existing python-embed/ directory
#   --skip-npm           Skip npm install
#   --clean              Remove build artifacts before starting

set -euo pipefail

# ============================================================
# Parse arguments
# ============================================================
SKIP_PYTHON=false
SKIP_NPM=false
CLEAN=false
PLATFORM=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-python) SKIP_PYTHON=true ;;
    --skip-npm)    SKIP_NPM=true ;;
    --clean)       CLEAN=true ;;
    --platform)
      PLATFORM="$2"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--platform mac|win] [--skip-python] [--skip-npm] [--clean]"
      exit 1
      ;;
  esac
  shift
done

# Auto-detect platform if not specified
if [ -z "$PLATFORM" ]; then
  case "$(uname -s)" in
    Darwin)          PLATFORM="mac" ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM="win" ;;
    Linux)           PLATFORM="linux" ;;
    *)               echo "ERROR: Could not detect platform. Use --platform mac|win"; exit 1 ;;
  esac
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_EMBED_DIR="$PROJECT_DIR/python-embed"
RELEASE_DIR="$PROJECT_DIR/release"

cd "$PROJECT_DIR"

echo "Platform: $PLATFORM"
echo ""

# ============================================================
# Step 0: Clean if requested
# ============================================================
if [ "$CLEAN" = true ]; then
  echo "Cleaning previous build artifacts..."
  rm -rf "$PYTHON_EMBED_DIR" "$RELEASE_DIR" dist dist-electron
  echo "Clean complete."
  echo ""
fi

# ============================================================
# Step 1: Prepare Python environment
# ============================================================
if [ "$SKIP_PYTHON" = false ]; then
  echo "[1/3] Preparing Python environment..."

  if [ -d "$PYTHON_EMBED_DIR" ]; then
    echo "  Python environment already exists. Use --clean to rebuild."
  else
    case "$PLATFORM" in
      mac|linux)
        bash "$SCRIPT_DIR/prepare-python.sh"
        ;;
      win)
        powershell.exe -ExecutionPolicy Bypass -File "$SCRIPT_DIR/prepare-python.ps1"
        ;;
    esac
  fi
else
  echo "[1/3] Skipping Python preparation (using existing)..."
fi

# Verify Python environment exists
if [ ! -d "$PYTHON_EMBED_DIR" ]; then
  echo "ERROR: Python environment not found at $PYTHON_EMBED_DIR"
  echo "Run without --skip-python to create it."
  exit 1
fi
echo ""

# ============================================================
# Step 2: Install npm dependencies
# ============================================================
if [ "$SKIP_NPM" = false ]; then
  echo "[2/3] Installing npm dependencies..."
  npm install
else
  echo "[2/3] Skipping npm install..."
fi
echo ""

# ============================================================
# Step 3: Build frontend and Electron
# ============================================================
echo "[3/3] Building frontend and Electron app..."
npm run build:frontend
echo ""

echo "App build complete. Run package-installer.sh to create the installer."
