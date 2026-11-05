@echo off
REM ===== Development mode: auto-reload, sirf is PC par =====
cd /d "%~dp0backend"
if not exist venv\Scripts\activate.bat (
    echo Pehle setup.bat chalao.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
echo Open: http://127.0.0.1:8000
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
