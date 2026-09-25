@echo off
setlocal
cd /d "%~dp0"
title NEXGRAFT fine-tuning

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10-3.12 is required: https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
  pause
  exit /b 1
)
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo An NVIDIA GPU with a current driver is required ^(nvidia-smi was not found^).
  pause
  exit /b 1
)

if not exist ".venv-finetune\Scripts\python.exe" (
  echo [1/3] Creating the fine-tuning environment ^(.venv-finetune^)...
  python -m venv .venv-finetune || goto :fail
)
set "PY=.venv-finetune\Scripts\python.exe"

"%PY%" -c "import torch, sys; sys.exit(0 if torch.version.cuda else 1)" >nul 2>nul
if errorlevel 1 (
  echo [2/3] Installing PyTorch with CUDA ^(about 2.5 GB, first run only^)...
  "%PY%" -m pip install --disable-pip-version-check -q --upgrade pip
  "%PY%" -m pip install --disable-pip-version-check --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126 || goto :fail
)
echo [3/3] Checking fine-tuning packages...
"%PY%" -m pip install --disable-pip-version-check -q -r finetune\requirements.txt || goto :fail

"%PY%" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)"
if errorlevel 1 (
  echo PyTorch cannot see your NVIDIA GPU. Update the driver from nvidia.com, restart, and run this again.
  pause
  exit /b 1
)

"%PY%" -m finetune %*
if errorlevel 1 goto :fail
pause
exit /b 0

:fail
echo.
echo Fine-tuning stopped - see the messages above. Running finetune.bat again resumes after the last finished step.
pause
exit /b 1
