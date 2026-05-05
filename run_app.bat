@echo off
echo ========================================
echo TindaTrack - Sari-Sari Store System
echo ========================================
echo.

cd /d "%~dp0"

REM Check if database exists
if not exist db.sqlite3 (
    echo Creating database...
    python manage.py migrate
    python setup.py
    echo Database created successfully!
    echo.
)

echo Starting server...
echo Open your browser and go to: http://127.0.0.1:8000
echo.
python manage.py runserver

pause