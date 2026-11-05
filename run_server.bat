@echo off
REM ===== Server mode: network par sab devices ke liye (0.0.0.0) =====
cd /d "%~dp0backend"
if not exist venv\Scripts\python.exe (
    echo Pehle setup.bat chalao.
    pause
    exit /b 1
)
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo Port 8000 pehle se use ho raha hai. Agar WheelDeal pehle se chal raha hai,
    echo browser mai http://localhost:8000 kholain. Warna port 8000 use karne wali app band karein.
    pause
    exit /b 1
)
echo Server chal raha hai: http://0.0.0.0:8000  (dusre device se: http://YOUR-PC-IP:8000)
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
if errorlevel 1 (
    echo WheelDeal server start nahi ho saka. Python environment ya port check karein.
    pause
    exit /b 1
)
pause
