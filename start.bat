@echo off
setlocal
cd /d "%~dp0"
title NEXGRAFT AI

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required: https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python virtual environment...
  python -m venv .venv || goto :fail
)

echo [2/3] Checking Python packages...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r backend\requirements.txt || goto :fail

if not exist "frontend\dist\index.html" (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo Node.js 20.19+ or 22+ is required once, to build the interface: https://nodejs.org
    pause
    exit /b 1
  )
  echo [3/3] Building the web interface ^(first run only^)...
  pushd frontend
  call npm install || (popd & goto :fail)
  call npm run build || (popd & goto :fail)
  popd
)

if not exist ".env" copy ".env.example" ".env" >nul

".venv\Scripts\python.exe" run.py %*
exit /b 0

:fail
echo.
echo Setup failed - see the messages above.
pause
exit /b 1
