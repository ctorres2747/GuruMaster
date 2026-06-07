@echo off
echo Liberando puerto 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
cd /d "%~dp0backend"
echo Iniciando GuruMaster en http://localhost:8000
timeout /t 2 >nul
start "" "http://localhost:8000"
uvicorn main:app --port 8000
pause
