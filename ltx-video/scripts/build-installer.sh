#!/usr/bin/env bash
# build-installer.sh
# Master build script for creating the LTX Desktop installer.
# Prepares the app (Python env, npm deps, frontend) then packages with electron-builder.
#
# Usage:
#   bash scripts/build-installer.sh [options]
#
# Options:
#   --platform mac|win   Target platform (auto-detected if omitted)
#   --skip-python        Use existing python-embed/ directory
#   --skip-npm           Skip npm install
#   --clean              Remove build artifacts before starting
#   --unpack             Build unpacked app only (faster, no installer/dmg)
#   --publish <mode>     Publish mode for electron-builder (always|never|onTag)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat << 'BANNER'

  _   _______  __  ____            _    _
 | | |_   _\ \/ / |  _ \  ___  ___| | _| |_ ___  _ __
 | |   | |  \  /  | | | |/ _ \/ __| |/ / __/ _ \| '_ \
 | |___| |  /  \  | |_| |  __/\__ \   <| || (_) | |_) |
 |_____|_| /_/\_\ |____/ \___||___/_|\_\\__\___/| .__/
                                                 |_|
  Installer Build Script

BANNER

# Separate flags for each stage
APP_ARGS=()
PKG_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-python|--skip-npm|--clean)
      APP_ARGS+=("$1")
      ;;
    --unpack)
      PKG_ARGS+=("$1")
      ;;
    --platform)
      APP_ARGS+=("$1" "$2")
      PKG_ARGS+=("$1" "$2")
      shift
      ;;
    --publish)
      PKG_ARGS+=("$1" "$2")
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--platform mac|win] [--skip-python] [--skip-npm] [--clean] [--unpack] [--publish always|never|onTag]"
      exit 1
      ;;
  esac
  shift
done

bash "$SCRIPT_DIR/build-app.sh" "${APP_ARGS[@]+"${APP_ARGS[@]}"}"
bash "$SCRIPT_DIR/package-installer.sh" "${PKG_ARGS[@]+"${PKG_ARGS[@]}"}"
