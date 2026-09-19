@echo off
setlocal
cd /d "%~dp0"

rem --- start backend in a separate window ---
start "verifier-backend" cmd /c "cd /d backend && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

rem --- resolve ngrok executable (project root or PATH) ---
if exist "%~dp0ngrok.exe" (set "NG=%~dp0ngrok.exe") else (set "NG=ngrok")

echo.
echo  ================================================
echo   Backend is starting (window "verifier-backend")
echo   The PUBLIC url will appear in ngrok below.
echo   Share that https://... address with others.
echo   Keep this window OPEN. Press Ctrl+C to stop.
echo  ================================================
echo.
"%NG%" start --config "%~dp0ngrok.yml" verifier
pause
