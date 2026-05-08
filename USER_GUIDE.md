# TindaTrack User Guide

## Table of Contents
1. [Login](#login)
2. [Dashboard](#dashboard)
3. [Categories & Products](#categories--products)
4. [Stock In](#stock-in)
5. [POS / New Sale](#pos--new-sale)
6. [Credit / Utang](#credit--utang)
7. [Reports](#reports)
8. [User Management](#user-management)
9. [Theme](#theme)
10. [Tips](#tips)

---

## Login

1. Open browser to: http://127.0.0.1:8000
2. Enter username and password
3. Click "Login"

**Default Roles:**
- **Owner** - Full access to all features
- **Teller** - Can only view products, make sales, and process credit payments

---

## Dashboard

Shows quick stats:
- Today's Sales - Total sales amount today
- Transactions - Number of sales today
- Low Stock - Products with low inventory
- Near Expiry - Items expiring within 7 days
- Credit Received Today - Payments collected today
- Total Outstanding - Total unpaid credit balance

---

## Categories & Products

### Adding Categories (Owner only)
1. Click **Categories** in sidebar
2. Click **Add Category** button
3. Enter category name
4. Click **Save**

### Adding Products (Owner only)
1. Click **Products** in sidebar
2. Click **Add Product** button
3. Fill in details:
   - Name - Product name
   - SKU - Optional stock keeping unit
   - Category - Select from dropdown
   - Selling Price - Retail price
   - Unit - Piece, pack, etc.
   - Reorder Level - Alert when stock runs low
4. Click **Save**

### Viewing Products
- All users can view products
- Shows: Name, Price, Stock, Category
- Owner can edit/delete products
- Search by name or SKU

---

## Stock In (Inventory)

Owner only - to add inventory:

1. Click **Stock In** in sidebar
2. Select product from dropdown
3. Enter:
   - Quantity - Number of units
   - Purchase Price - Cost per unit
   - Expiry Date - Optional, for tracking
4. Click **Add Stock**

This increases the product's current stock.

---

## POS / New Sale

### Making a Sale
1. Click **POS / Sale** in sidebar
2. Click on products to add to cart
3. Cart shows added items with quantities
4. Adjust quantity using + / - buttons
5. Click **Remove** to remove an item

### Checkout
1. Enter **Cash Tendered** amount
2. System automatically shows **Change**
3. Select payment type:
   - **Cash** - Full payment immediately
   - **Credit** - Customer will pay later
4. If Credit: Enter customer name
5. Click **Confirm Sale**
6. Receipt is shown (can print if needed)

### Change Calculator
- Enter amount customer gives
- Shows exact change to return

---

## Credit / Utang

### Creating Credit (during POS)
1. Make a sale as normal
2. Select **Credit** as payment type
3. Enter customer name
4. Confirm sale
5. Items are saved as credit record

### Viewing Credit Records
1. Click **Credit** in sidebar
2. Cards show all credit records:
   - Customer name
   - Total amount
   - Balance remaining
   - Status (Unpaid/Partial/Paid)
3. Click card header to expand details:
   - Items purchased
   - Payment history
   - Add Payment button

### Adding a Payment
1. Find the credit record
2. Click **Add Payment** button (or expand card first)
3. Enter payment amount
4. Click **Save Payment**
5. Balance updates automatically

### Deleting Credit Records (Owner only)
- Go to **Reports > Credit** tab
- Only fully **Paid** records can be deleted
- Click delete icon (trash) to remove

---

## Reports

### Daily Report
1. Select **Daily** tab
2. Choose date
3. Shows:
   - Total Sales
   - Total Purchases (Stock In cost)
   - Profit (Sales - Purchases)
   - Expired Value
   - List of all transactions

### Monthly Report
1. Select **Monthly** tab
2. Choose month
3. Shows monthly totals and transactions

### Sales Velocity
1. Select **Sales Velocity** tab
2. Shows:
   - **Fast Moving** - Top 20 best-selling items
   - **Slow Moving** - Bottom 10 least sold items

### Inventory
1. Select **Inventory** tab
2. Shows:
   - All products with stock levels
   - Low stock items
   - Near expiry items

### Credit
1. Select **Credit** tab
2. Shows:
   - New credit created today
   - Payments received today
   - Total outstanding
   - All credit records with status
   - Delete option for paid records (Owner only)

---

## User Management (Owner only)

1. Click **Users** in sidebar
2. View all users with their roles
3. Add new user:
   - Click **Add User**
   - Enter username, password
   - Select role (Owner or Teller)
4. Edit user:
   - Click edit icon
   - Change password or role
5. Deactivate/Activate:
   - Click toggle to enable/disable user

---

## Theme

1. Click **Theme** button in sidebar
2. Choose from 10 themes:
   - **Dark themes:** Blue, Purple, Red, Green
   - **Light themes:** Blue, Pink, Purple, Green, Red, Orange
3. Selection is saved automatically
4. Theme applies across all pages

---

## Tips

### First Time Setup
1. Create categories first
2. Add products
3. Add stock (Stock In)
4. Start making sales!

### Daily Workflow
1. Check dashboard for low stock
2. Process sales in POS
3. If customer can't pay → create credit
4. When customer pays → add payment in Credit
5. End of day → check Reports

### Backup
- Copy `db.sqlite3` file regularly to backup data
- Can restore by copying back to folder

---

## Troubleshooting

**Page not loading:**
- Make sure server is running (check command window)
- Refresh browser

**Can't login:**
- Run `createsuperuser` to create new admin
- Check username/password is correct

**Product not showing in POS:**
- Make sure stock is added via Stock In
- Check product is set to Active

**Credit not appearing:**
- Make sure to select "Credit" payment type during sale
- Enter customer name

---

## Support

For issues or questions, contact: WSS @2026