# TindaTrack - Sari-Sari Store POS & Inventory System

A simple inventory management and point-of-sale system for sari-sari stores.

## Requirements

- Python 3.8 or higher
- Windows (tested on Windows 10/11)

## Quick Start (First Time Setup)

### Option A: Using Launcher Scripts (Recommended)

1. Install Python from: https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. Double-click `run_app.bat` in this folder
   - It will automatically create the virtual environment
   - Install all requirements
   - Create the database
   - Start the server

3. Open your browser and go to: http://127.0.0.1:8000

### Option B: Manual Setup

#### 1. Install Python (if not installed)
Download from: https://www.python.org/downloads/
- Make sure to check "Add Python to PATH" during installation

#### 2. Create Virtual Environment
```
python -m venv venv
```

#### 3. Activate Virtual Environment
```
venv\Scripts\activate
```

#### 4. Install Dependencies
```
pip install -r requirements.txt
```

#### 5. Setup Database
```
python manage.py migrate
```

#### 6. Create Admin Account
```
python manage.py createsuperuser
```
Follow the prompts to create your admin username and password.

#### 7. Run the App
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

### Method 1: Copy Folder with venv (Recommended for same Python version)
1. Copy the entire folder to the new computer
2. Double-click `run_app.bat`
3. Done!

### Method 2: Fresh Install (If Python version differs)
1. Copy the entire folder (or just the files, not venv/)
2. On the new computer:
   - Install Python
   - Run `python -m venv venv`
   - Run `venv\Scripts\activate`
   - Run `pip install -r requirements.txt`
   - Run `python manage.py migrate`
   - Run `python manage.py createsuperuser`
   - Run `python manage.py runserver`

**Important:** Delete `db.sqlite3` if copying to a new computer to start fresh, or keep it to preserve all data.

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

**venv activation issues:**
- On Windows, make sure to run: `venv\Scripts\activate`
- If you get security error, run PowerShell as Administrator and run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Launcher Scripts

This folder includes convenient shortcuts to run the app:

| File | Description |
|------|-------------|
| `run_app.bat` | Double-click to open app (auto-creates venv if missing, shows window) |
| `Start TindaTrack.vbs` | Double-click, opens app in browser (no command window) |
| `launcher.vbs` | Alternative launcher (hidden) |

**How to use:**
1. First time: Double-click `run_app.bat` - it handles everything automatically
2. After setup, just double-click any launcher to start the app
3. The app opens automatically in your browser

## Files Included

```
├── manage.py               - Django management script
├── requirements.txt       - Python dependencies
├── venv/                  - Virtual environment (created automatically)
├── README.md             - This file
├── USER_GUIDE.md         - User manual (how to use the system)
├── run_app.bat           - Quick launcher (auto-setup)
├── Start TindaTrack.vbs  - Quick launcher (hidden)
├── launcher.vbs          - Alternative launcher (hidden)
├── tindatrack/            - Django project settings
├── store/                - Main application code
├── templates/            - HTML templates
└── db.sqlite3           - Database (created after migrate)
```

## Quick Start
1. Double-click `run_app.bat`
2. Open browser to http://127.0.0.1:8000
3. Login with your admin account
4. See **USER_GUIDE.md** for detailed instructions

## Engineered by
TindaTrack - WSS @2026