@echo off
REM ===== Admin banao / hatao.  Istemal:  make_admin.bat <username ya email> [--remove]   ya   make_admin.bat --list =====
cd /d "%~dp0backend"
if not exist venv\Scripts\activate.bat (
    echo Pehle setup.bat chalao.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python make_admin.py %*
pause
