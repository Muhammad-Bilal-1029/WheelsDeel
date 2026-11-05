@echo off
REM ===== WheelDeal one-time setup: virtual environment + packages =====
cd /d "%~dp0backend"

set PY=python
where py >nul 2>nul && set PY=py -3

if not exist venv (
    echo Creating virtual environment...
    %PY% -m venv venv
    if errorlevel 1 (
        echo Python nahi mila. Python 3.10+ install karo: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Packages install nahi huay. Internet check karo.
    pause
    exit /b 1
)

if not exist .env copy .env.example .env >nul

echo.
echo Setup complete! Ab run.bat (testing) ya run_server.bat (server) chalao.
pause
