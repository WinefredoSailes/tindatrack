# TindaTrack - Sari-Sari Store POS & Inventory System

A simple inventory management and point-of-sale system for sari-sari stores.

## Requirements

- Python 3.8 or higher
- Windows (tested on Windows 10/11)

## Quick Start (First Time Setup)

### 1. Install Python (if not installed)
Download from: https://www.python.org/downloads/
- Make sure to check "Add Python to PATH" during installation

### 2. Install Dependencies
Open Command Prompt in this folder and run:
```
pip install -r requirements.txt
```

### 3. Setup Database
```
python manage.py migrate
```

### 4. Create Admin Account
```
python manage.py createsuperuser
```
Follow the prompts to create your admin username and password.

### 5. Run the App
```
python manage.py runserver
```

Then open your browser and go to: http://127.0.0.1:8000

## Using the App

1. Login with your admin account
2. First time: Add categories first, then products
3. Add stock via "Stock In" menu
4. Use "POS / Sale" for making sales
5. View reports under "Reports"

## User Roles

- **Owner** - Full access to all features
- **Teller** - Can only view products and make sales

## To Transfer to Another Computer

1. Copy the entire folder
2. On the new computer:
   - Install Python
   - Run `pip install -r requirements.txt`
   - Run `python manage.py migrate`
   - Run `python manage.py createsuperuser`
   - Run `python manage.py runserver`

## Default Login (after createsuperuser)
- Username: (what you created)
- Password: (what you created)

## Theme

Click the "Theme" button in the sidebar to switch between:
- Dark themes (Blue, Purple, Red, Green)
- Light themes (Blue, Pink, Purple, Green, Red, Orange)

The theme preference is saved automatically.

## Troubleshooting

**Port already in use error:**
- Another app is using port 8000
- Run: `python manage.py runserver 8001`

**Database error:**
- Delete `db.sqlite3` and run `python manage.py migrate` again

**Missing packages:**
- Run: `pip install -r requirements.txt`

## Launcher Scripts

This folder includes convenient shortcuts to run the app:

| File | Description |
|------|-------------|
| `run_app.bat` | Double-click to open app in browser (shows command window) |
| `Start TindaTrack.vbs` | Double-click, opens app in browser (no command window) |
| `Start TindaTrack Hidden.bat` | Runs app silently in background |

**How to use:**
1. First time: Follow steps 1-4 above (install Python, pip install, migrate, createsuperuser)
2. After setup, just double-click `run_app.bat` or `Start TindaTrack.vbs`
3. The app opens automatically in your browser

**Note:** The launchers assume you've already run the initial setup (migrate + createsuperuser). They just run the server for you.

## Files Included

```
├── manage.py               - Django management script
├── requirements.txt        - Python dependencies
├── README.md              - This file
├── run_app.bat            - Quick launcher (shows window)
├── Start TindaTrack.vbs    - Quick launcher (hidden)
├── Start TindaTrack Hidden.bat - Silent launcher
├── tindatrack/            - Django project settings
├── store/                 - Main application code
├── templates/             - HTML templates
└── db.sqlite3            - Database (created after migrate)
```