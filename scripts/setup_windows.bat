@echo off
setlocal EnableExtensions

REM NOVA Windows setup. Run from any directory.
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%" || (echo [ERROR] Cannot enter project directory.& exit /b 1)

echo.
echo ========================================
echo   NOVA - Windows Setup
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer was not found on PATH.
  echo Install 64-bit Python from https://www.python.org/downloads/ and enable "Add Python to PATH".
  exit /b 1
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer is required.
  python --version
  exit /b 1
)
python --version || exit /b 1

where node >nul 2>&1
if errorlevel 1 (echo [ERROR] Node.js 18 or newer is required. Install from https://nodejs.org/.& exit /b 1)
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 18 ? 0 : 1)"
if errorlevel 1 (echo [ERROR] Node.js 18 or newer is required.& node --version& exit /b 1)
node --version || exit /b 1
where npm >nul 2>&1
if errorlevel 1 (echo [ERROR] npm was not found. Repair the Node.js installation.& exit /b 1)
npm --version || exit /b 1

where ollama >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Ollama is required. Install it from https://ollama.com/download/windows and reopen this terminal.
  exit /b 1
)
echo [OK] Ollama command found.

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [ERROR] FFmpeg is required for voice audio conversion and must be on PATH.
  echo Install with: winget install --id Gyan.FFmpeg --exact
  echo Then reopen this terminal and run this setup script again.
  exit /b 1
)
ffmpeg -version >nul 2>&1
if errorlevel 1 (echo [ERROR] FFmpeg was found but could not run. Check its installation and PATH.& exit /b 1)
echo [OK] FFmpeg found.

if not exist "backend\.venv\Scripts\python.exe" (
  echo [INFO] Creating backend virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 (echo [ERROR] Could not create backend virtual environment.& exit /b 1)
)

echo [INFO] Installing Python backend dependencies...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (echo [ERROR] Failed to upgrade pip.& exit /b 1)
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (echo [ERROR] Backend dependency installation failed.& exit /b 1)

if not exist "frontend\package.json" (echo [ERROR] frontend\package.json is missing.& exit /b 1)
echo [INFO] Installing frontend dependencies with npm ci...
pushd "frontend"
if errorlevel 1 (echo [ERROR] Could not enter the frontend directory.& exit /b 1)
call npm ci
if errorlevel 1 (
  popd
  echo [ERROR] Frontend dependency installation failed.
  exit /b 1
)
popd

if not exist ".env" (
  if not exist ".env.example" (echo [ERROR] .env.example is missing; cannot create local configuration.& exit /b 1)
  copy /y ".env.example" ".env" >nul
  if errorlevel 1 (echo [ERROR] Could not create .env from .env.example.& exit /b 1)
  python -c "from pathlib import Path; p=Path('.env'); s=p.read_text(encoding='utf-8'); assert 'TTS_ENGINE=' in s; p.write_text(s.replace('TTS_ENGINE=macos', 'TTS_ENGINE=windows'), encoding='utf-8')"
  if errorlevel 1 (echo [ERROR] Could not configure Windows SAPI5 in .env.& exit /b 1)
  echo [OK] Created local .env. It is ignored by Git.
  echo [OK] Configured Windows SAPI5 speech output.
)

for %%D in ("data\documents" "data\audio" "data\chroma" "logs") do if not exist "%%~D" mkdir "%%~D"
if errorlevel 1 (echo [ERROR] Could not create NOVA data directories.& exit /b 1)

echo.
echo [OK] Setup complete.
echo Pull a local model in Command Prompt: ollama pull llama3.2:1b
echo Then launch NOVA with: scripts\start_nova_windows.bat
exit /b 0
