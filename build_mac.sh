#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: build_mac.sh must be run on macOS. For Windows, use build_win.bat." >&2
    exit 1
fi

echo "==> Step: Set up venv"
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Step: Install dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "==> Step: Clean prior build artifacts"
rm -rf build
rm -rf dist/ConflictChecker
rm -rf dist/ConflictChecker.app
rm -f dist/ConflictChecker.dmg
# Intentionally preserve any other files in dist/ (e.g., a prior ConflictChecker.exe).

echo "==> Step: Run PyInstaller"
pyinstaller ConflictChecker.spec --clean --noconfirm

if [[ ! -d "dist/ConflictChecker.app" ]]; then
    echo "ERROR: dist/ConflictChecker.app was not produced by PyInstaller." >&2
    exit 1
fi

echo "==> Step: Package .dmg"
if command -v create-dmg >/dev/null 2>&1; then
    set +e
    create-dmg \
        --volname "ConflictChecker" \
        --window-size 600 400 \
        --icon-size 100 \
        --app-drop-link 450 200 \
        --no-internet-enable \
        dist/ConflictChecker.dmg \
        dist/ConflictChecker.app
    cdmg_status=$?
    set -e
    if [[ ! -f "dist/ConflictChecker.dmg" ]]; then
        echo "ERROR: create-dmg failed (exit $cdmg_status) and no DMG was produced." >&2
        exit 1
    fi
else
    echo "    (create-dmg not installed; falling back to hdiutil.)"
    echo "    Tip: 'brew install create-dmg' for a nicer DMG layout."
    hdiutil create -volname "ConflictChecker" \
        -srcfolder dist/ConflictChecker.app \
        -ov -format UDZO \
        dist/ConflictChecker.dmg
fi

if [[ ! -f "dist/ConflictChecker.dmg" ]]; then
    echo "ERROR: dist/ConflictChecker.dmg was not produced." >&2
    exit 1
fi

echo
echo "==> Build complete"
echo "    App: $(pwd)/dist/ConflictChecker.app  ($(du -sh dist/ConflictChecker.app | cut -f1))"
echo "    DMG: $(pwd)/dist/ConflictChecker.dmg  ($(du -sh dist/ConflictChecker.dmg | cut -f1))"
echo
echo "    Note: This build is unsigned and not notarized."
echo "          On first launch, right-click the app and choose Open to bypass Gatekeeper."
