@echo off
setlocal
cd /d "%~dp0"

if not exist "explorer.db" (
  python server.py --build-only
  if errorlevel 1 exit /b 1
)

if not exist "dist\index.html" (
  call npm install
  if errorlevel 1 exit /b 1
  call npm run build
  if errorlevel 1 exit /b 1
)

start "" "http://127.0.0.1:4180"
python server.py --port 4180
endlocal
