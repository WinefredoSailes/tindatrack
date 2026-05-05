@echo off
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if not exist db.sqlite3 (
    echo Creating database...
    python manage.py migrate >nul 2>&1
    python setup.py >nul 2>&1
)

start /b python manage.py runserver > nul 2>&1

timeout /t 2 /nobreak > nul

start http://127.0.0.1:8000

echo TindaTrack is running! Opening browser...
echo.
echo If browser did not open, go to: http://127.0.0.1:8000

timeout /t 5 /nobreak > nul