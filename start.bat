@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found.
    echo Please run these commands first:
    echo   cd backend
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   Multimodal Verifier is starting...
echo   Open:  http://localhost:8000
echo   LAN :  http://YOUR-PC-IP:8000
echo   Stop :  press Ctrl+C
echo  ================================================
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
