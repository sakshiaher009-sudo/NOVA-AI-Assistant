@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"

if not exist "%PROJECT_DIR%\backend\.venv\Scripts\uvicorn.exe" (
  echo [ERROR] Backend environment is missing. Run scripts\setup_windows.bat first.
  exit /b 1
)
if not exist "%PROJECT_DIR%\frontend\node_modules" (
  echo [ERROR] Frontend dependencies are missing. Run scripts\setup_windows.bat first.
  exit /b 1
)
where ollama >nul 2>&1
if errorlevel 1 (echo [ERROR] Ollama was not found on PATH. Install Ollama and reopen this terminal.& exit /b 1)
where ffmpeg >nul 2>&1
if errorlevel 1 (echo [ERROR] FFmpeg was not found on PATH. Install FFmpeg for voice support.& exit /b 1)

if not exist "%PROJECT_DIR%\data\documents" mkdir "%PROJECT_DIR%\data\documents"
if not exist "%PROJECT_DIR%\data\audio" mkdir "%PROJECT_DIR%\data\audio"
if not exist "%PROJECT_DIR%\data\chroma" mkdir "%PROJECT_DIR%\data\chroma"
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"
if errorlevel 1 (echo [ERROR] Could not create NOVA data directories.& exit /b 1)

REM Start Ollama's installed local service if it is not already responding.
curl.exe -fsS http://127.0.0.1:11434/ >nul 2>&1
if errorlevel 1 (
  where ollama >nul 2>&1
  start "NOVA Ollama" ollama serve
  timeout /t 3 /nobreak >nul
  curl.exe -fsS http://127.0.0.1:11434/ >nul 2>&1
  if errorlevel 1 (echo [ERROR] Ollama did not start at 127.0.0.1:11434. Start Ollama and check its installation.& exit /b 1)
)

set "OLLAMA_MODEL=llama3.2:1b"
if exist "%PROJECT_DIR%\.env" (
  for /f "tokens=1,* delims==" %%A in ('findstr /B /I "OLLAMA_MODEL=" "%PROJECT_DIR%\.env"') do set "OLLAMA_MODEL=%%B"
)
if not defined OLLAMA_MODEL set "OLLAMA_MODEL=llama3.2:1b"
ollama list | findstr /B /I /C:"%OLLAMA_MODEL%" >nul
if errorlevel 1 (
  echo [ERROR] Ollama model "%OLLAMA_MODEL%" is not installed.
  echo Install it with: ollama pull %OLLAMA_MODEL%
  exit /b 1
)

start "NOVA Backend" /D "%PROJECT_DIR%\backend" cmd.exe /k ".venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload"
if errorlevel 1 (echo [ERROR] Could not launch the backend.& exit /b 1)
start "NOVA Frontend" /D "%PROJECT_DIR%\frontend" cmd.exe /k "npm run dev"
if errorlevel 1 (echo [ERROR] Could not launch the frontend.& exit /b 1)

echo.
echo NOVA launch commands were sent to separate windows.
echo Frontend: http://127.0.0.1:3000
echo Backend:  http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo Close the NOVA Backend and NOVA Frontend windows to stop those services.
