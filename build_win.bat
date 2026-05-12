@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Step: Detect Python ===
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo ERROR: Python not found. Install Python 3.11+ from https://www.python.org/downloads/ and re-run.
        exit /b 1
    )
)
echo Using: %PY%

echo === Step: Set up venv ===
if not exist ".venv\Scripts\activate.bat" (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv.
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate venv.
    exit /b 1
)

echo === Step: Install dependencies ===
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    exit /b 1
)
python -m pip install -r Frontend\requirements.txt pyinstaller
if errorlevel 1 (
    echo ERROR: dependency install failed.
    exit /b 1
)

echo === Step: Clean prior build artifacts ===
if exist build rmdir /s /q build

echo === Step: Run PyInstaller ===
pyinstaller ConflictChecker.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo === Step: Verify output ===
if not exist "dist\ConflictChecker.exe" (
    echo ERROR: dist\ConflictChecker.exe not found after build.
    exit /b 1
)

echo.
echo === Build complete ===
echo Output: %CD%\dist\ConflictChecker.exe
echo Note: This build is unsigned. Windows SmartScreen may warn on first run.
echo       Click "More info" then "Run anyway" to launch.
exit /b 0
