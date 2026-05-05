# TindaTrack MVP — Sari-Sari Store POS & Inventory System

**Project Type:** Django Monolith (Django Templates + HTMX + PostgreSQL)
**Target Users:** Small sari-sari store owners, mini grocery operators
**Design Philosophy:** Simple, fast, practical, web-first, scalable

---

## 1. Project Overview

The goal is to build a web-first POS and Inventory Management System that a sari-sari store owner can use on a laptop or tablet at the counter. It replaces manual notebook tracking with a fast, reliable system that tracks stock, records sales, manages restocking, and shows daily profit — without the complexity of a full ERP.

---

## 2. Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Frontend** | Django Templates + HTMX | Server-rendered pages with HTMX for dynamic interactions |
| **Backend** | Django 5.x (Python) | Built-in auth, ORM, admin, forms |
| **Database** | PostgreSQL | Reliable, production-ready, handles growth |
| **CSS** | Tailwind CSS (via django-tailwind) | Fast styling, responsive, clean UI |
| **Caching** | Browser Session + Django Cache | Cache product list for fast search |

**Why this stack is scalable:**
- Django monolith → easy to extract API later for mobile app
- PostgreSQL → handles thousands of products and transactions
- HTMX → no JS framework to maintain, simple architecture
- Can evolve to multi-store SaaS by extracting API layer later

---

## 3. Core Features (MVP)

### Feature 1 — User Authentication & Roles

- Owner login with username/password
- Simple session-based auth
- Logout button on every page
- 2 roles: **Teller** and **Owner (Admin)**

| Role | Permissions |
|------|-------------|
| **Owner (Admin)** | Full access: all CRUD, reports, settings, user management |
| **Teller** | View products, make sales, view today's sales summary only |

### Feature 2 — Dashboard
- Today's total sales amount
- Number of transactions today
- Low-stock count (items at or below reorder level)
- Near-expiry count (within 7 days)
- Quick action buttons: "New Sale", "Add Stock", "View Products"

### Feature 3 — Products / Inventory Management
- Add, edit, archive/unarchive products (flag-based)
- Fields: name, SKU (optional), category, selling price, cost price, reorder level, track expiry
- Categories: Drinks, Snacks, Toiletries, Home Essentials, Other (customizable)
- Search and filter by name, category, stock status
- Toggle product active/inactive via `is_active` flag

### Feature 4 — Stock Batches & Expiry Tracking
- Each stock "IN" creates a batch record
- Batch fields: product, quantity, unit cost, expiry date, purchase date
- FIFO deduction (sell oldest batch first)
- Expiry status: Fresh, Near-Expiry (7 days), Expired
- Near-expiry items flagged in dashboard and inventory list
- Expired items blocked from sale

### Feature 5 — POS / Sales
- Product search (auto-suggest - cached in session for speed)
- Quantity input (+/- buttons and direct number entry)
- Add to cart, remove items
- Payment type: Cash, GCash/Transfer (record only, no integration)
- Calculate total, show change due
- On confirm: deduct stock (FIFO per batch), create sale record
- Show low-stock or expiry warnings but don't block

### Feature 6 — Purchase / Restock (Stock In)
- Select product (or add new on-the-fly)
- Enter: quantity, unit cost, supplier name, purchase date, expiry date
- Creates new stock batch, updates product's current stock

### Feature 7 — Sales History & Daily Summary
- List of today's transactions (time, items, total, payment type)
- Daily totals: total sales, total purchases, net profit
- Filter by date range (Owner only)

### Feature 8 — Reports
- Daily sales summary
- Monthly sales overview (total sales, profit, top products)
- Inventory summary (current stock levels, low-stock items, near-expiry items)
- Export to CSV option

---

## 4. Database Schema (MVP)

```
User (Django's built-in)
├── role (owner, teller)

Category
├── name
├── description
├── is_active (BooleanField)

Product
├── name
├── sku (unique, optional)
├── category (FK → Category)
├── selling_price (Decimal)
├── cost_price (Decimal)
├── reorder_level (IntegerField)
├── track_expiry (BooleanField)
├── is_active (BooleanField) — flag for archive/unarchive
├── created_at, updated_at

StockBatch
├── product (FK → Product)
├── quantity (IntegerField)
├── remaining_quantity (IntegerField)
├── unit_cost (Decimal)
├── expiry_date (DateField, nullable)
├── purchase_date (DateField)
├── created_at

Sale
├── sale_date (DateTimeField)
├── total_amount (Decimal)
├── payment_type (cash, gcash, other)
├── created_by (FK → User)
├── created_at

SaleItem
├── sale (FK → Sale)
├── product (FK → Product)
├── quantity (IntegerField)
├── unit_price (Decimal)
├── subtotal (Decimal)

Purchase (Stock In)
├── product (FK → Product)
├── supplier_name
├── quantity (IntegerField)
├── unit_cost (Decimal)
├── purchase_date
├── expiry_date (nullable)
├── created_by (FK → User)
```

**Stock Calculation:** `current_stock` computed on-the-fly from `StockBatch.remaining_quantity` sum. Use Django signals to cache if needed later.

---

## 5. Screen Structure (7 Screens)

All screens follow the same layout: sidebar navigation + main content area.

### Screen 1 — Login
- Simple centered card: username, password, login button
- "TindaTrack" logo/branding at top
- Error message on failed login

### Screen 2 — Dashboard (Home)
- 4 stat cards: Today's Sales, Transactions Today, Low Stock Items, Near Expiry
- "Quick Actions" row: New Sale (prominent), Add Stock, View Products
- Low-stock table, Near-expiry table

### Screen 3 — POS / New Sale
- Search bar with product autocomplete (cached for speed)
- Product grid/list below — shows name, price, stock
- Click product → adds to cart with default qty 1
- Cart panel (right): item list, quantity +/-, remove, subtotal, total
- Payment type dropdown (Cash, GCash/Transfer)
- "Complete Sale" button

### Screen 4 — Products List
- Search bar
- Filter: category dropdown, stock status
- Table: Name, SKU, Category, Price, Stock, Status, Actions
- "Add Product" button
- Row actions: Edit, Archive/Unarchive

### Screen 5 — Product Detail / Edit
- All product fields
- Stock batches table with expiry dates
- "Add Stock" quick action

### Screen 6 — Purchase / Stock In
- Form: Product, Supplier, Quantity, Unit Cost, Purchase Date, Expiry Date
- "Save & Add Stock" button

### Screen 7 — Reports
- Tabs: Daily Summary, Monthly Summary, Inventory
- Export CSV buttons

### Additional — User Management (Owner Only)
- User list table
- Add user form (username, password, role: Owner/Teller)
- Edit/Deactivate actions

---

## 6. Role-Based Access Control

| Screen/Action | Owner | Teller |
|--------------|-------|--------|
| Login/Logout | ✅ | ✅ |
| Dashboard | ✅ | ✅ (limited) |
| POS / New Sale | ✅ | ✅ |
| View Products | ✅ | ✅ (read-only) |
| Add/Edit Product | ✅ | ❌ |
| Archive Product | ✅ | ❌ |
| Purchase / Stock In | ✅ | ❌ |
| View Sales History | ✅ | ❌ (today only) |
| Reports | ✅ | ❌ |
| User Management | ✅ | ❌ |
| Settings | ✅ | ❌ |

---

## 7. Browser Session Caching Strategy

**What's cached (in browser session/localStorage):**
- Product list (name, price, stock) — for fast autocomplete search
- Dashboard stats (updated on page load)

**What's NOT cached (always from server):**
- Sales (must be online to process)
- Stock batches
- Reports
- User management

**Why this works:**
- Product search is instant (no server roundtrip)
- Sales still require internet (acceptable for MVP)
- Simple to implement, no complex offline sync logic

---

## 8. UI/UX Guidelines

- **Color Theme:** White background, blue primary, green for sales, red for alerts, gray sidebar
- **Typography:** System fonts (Inter/Roboto) — readable
- **Buttons:** Large, touch-friendly for tablet use
- **Forms:** Clear labels, inline validation
- **Tables:** Pagination if > 50 items
- **Responsive:** Works on 1024px+ tablets and laptops

---

## 9. Development Phases

### Phase 1 — Foundation
- Django project + PostgreSQL + Tailwind
- Auth with 2 roles (Owner/Teller)
- Product CRUD with `is_active` flag
- Category CRUD

### Phase 2 — Core Operations
- Stock batch management
- Purchase / stock in flow
- POS page with cart and sale processing

### Phase 3 — Expiry & Alerts
- Expiry status logic (fresh/near/expired)
- FIFO stock deduction
- Dashboard alerts

### Phase 4 — Reports & Polish
- Daily/Monthly summaries
- CSV export
- Basic testing
- Deploy

---

## 10. Success Criteria

- New sale completes in under 30 seconds
- Stock levels accurate after each sale
- Near-expiry items show on dashboard (7 days warning)
- Expired items blocked from sale
- Daily profit visible automatically
- Owner can add a product in under a minute
- Tellers have restricted access
- Product search is fast via session caching
- Scalable: can later extract API for mobile app or multi-store