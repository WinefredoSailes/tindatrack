@echo off
echo ========================================
echo TindaTrack - Sari-Sari Store System
echo ========================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created!
    echo.
    echo Installing requirements...
    call venv\Scripts\pip.exe install -r requirements.txt
    echo Requirements installed!
    echo.
)

REM Check if database exists
if not exist db.sqlite3 (
    echo Creating database...
    call venv\Scripts\python.exe manage.py migrate
    call venv\Scripts\python.exe setup.py
    echo Database created successfully!
    echo.
)

echo Starting server...
echo Open your browser and go to: http://127.0.0.1:8000
echo.
call venv\Scripts\python.exe manage.py runserver

pause