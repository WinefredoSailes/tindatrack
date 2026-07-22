# TindaTrack - Sari-Sari Store POS & Inventory System

A web-based POS, inventory, and subscription management system for sari-sari stores.
Built with Django, currently deployed for 1 client (semi-complete / single-tenant deployment).

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

#### 5. Setup Database & Seed Data
```
python manage.py migrate
python setup.py
```

#### 6. Run the App
```
python manage.py runserver
```

Then open your browser and go to: http://127.0.0.1:8000

## Default Login
- **Superuser:** Username: `admin`, Password: `admin123`
- **Owner:** Username: `owner`, Password: `owner123` (if created)
- **Teller:** Username: `teller`, Password: `teller123` (if created)

## User Roles

- **Superuser** — Full access including admin portal, client management, and subscription billing
- **Owner** — Full store access: Dashboard, POS, Products, Categories, Stock In, Reports, Users, Credit
- **Teller** — Limited access: Dashboard, POS, Products, Credit only

## Features

### Point of Sale
- Product grid with search, category filter, and pagination (25/page)
- Cash and Credit (utang) payment support
- Auto-deduct stock on sale

### Inventory Management
- Products with categories, SKU, pricing, reorder levels
- Stock batches with expiry tracking
- Low stock and near-expiry alerts on dashboard

### Credit / Utang Tracking
- Record credit sales per customer
- Track payments and remaining balance
- Status: unpaid / partial / paid

### Reports
- Daily sales, top products, low stock, near expiry
- Fast moving / slow moving items
- Credit summary

### Subscription Billing (Admin)
- **Plans:** Monthly (P299/30d) and Annual (P2,999/365d)
- Record payments with plan selector (auto-fills amount + covered-until date)
- Client detail with billing info (next due, amount due, payment history)
- **Flexible billing:** Any amount, any covered-until date — no restrictions

### Client-Side Subscription
- `/my-subscription/` page: view plan, rate, paid until, next due, payment history
- Warning banners on every page when expiring or expired
- GCash payment instructions displayed

### Subscription States
- **Trial** — Countdown based on `trial_end_date`
- **Active** — Unlimited validity
- **Expired** — Checks `paid_until_date` (can be extended via payment)
- **Locked** — Manually locked by admin

### Theme
- 10 themes: Dark (Blue, Purple, Red, Green) and Light (Blue, Pink, Purple, Green, Red, Orange)

## Multi-Tenant Architecture

The system is built with multi-tenant support (single database, client FK on all models).
Currently deployed for **1 client** (Default Store). Adding more clients is supported via the admin portal.

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
   - Run `python setup.py`
   - Run `python manage.py runserver`

**Important:** Delete `db.sqlite3` if copying to a new computer to start fresh, or keep it to preserve all data.

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
├── setup.py              - Database seeder (plans, categories, admin)
├── tindatrack/            - Django project settings
├── store/                - Main application code
├── templates/            - HTML templates
└── db.sqlite3           - Database (created after migrate)
```

## Quick Start
1. Double-click `run_app.bat`
2. Open browser to http://127.0.0.1:8000
3. Login with admin / admin123
4. See **USER_GUIDE.md** for detailed instructions

## Engineered by
TindaTrack - WSS @2026
