from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q, F
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json

from .models import Category, Product, StockBatch, Sale, SaleItem, Purchase, UserProfile, CreditRecord, CreditItem, CreditPayment
from .forms import (
    LoginForm, UserCreationForm, UserEditForm,
    CategoryForm, ProductForm, PurchaseForm, SaleForm
)


# Decorator for owner-only views
def owner_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_owner:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# Decorator for teller-restricted views
def teller_can_view(view_func):
    def wrapper(request, *args, **kwargs):
        if hasattr(request.user, 'profile') and request.user.profile.is_teller:
            # Tellers can only access certain views
            allowed = ['dashboard', 'pos', 'products', 'logout', 'process_sale', 'credit_list', 'credit_add_payment']
            if view_func.__name__ not in allowed:
                messages.error(request, "You don't have permission to access this page.")
                return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== AUTH VIEWS ====================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ==================== DASHBOARD ====================

@login_required
@teller_can_view
def dashboard(request):
    today = timezone.now().date()

    # Today's sales
    today_sales = Sale.objects.filter(sale_date__date=today)
    total_sales = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    transaction_count = today_sales.count()

    # Today's credit payments received
    today_credit_payments = CreditPayment.objects.filter(payment_date__date=today)
    today_credit_received = today_credit_payments.aggregate(total=Sum('amount'))['total'] or 0

    # Total outstanding credit (all unpaid/partial)
    total_outstanding = CreditRecord.objects.filter(
        status__in=['unpaid', 'partial']
    ).aggregate(total=Sum('remaining_balance'))['total'] or 0

    # Low stock items
    low_stock_products = []
    for product in Product.objects.filter(is_active=True):
        if product.is_low_stock:
            low_stock_products.append({
                'name': product.name,
                'current_stock': product.current_stock,
                'reorder_level': product.reorder_level
            })

    # Near expiry items
    near_expiry_items = []
    warning_date = today + timedelta(days=7)
    for batch in StockBatch.objects.filter(
        remaining_quantity__gt=0,
        expiry_date__lte=warning_date,
        expiry_date__gte=today,
        product__track_expiry=True
    ).select_related('product'):
        days_left = (batch.expiry_date - today).days
        near_expiry_items.append({
            'product': batch.product.name,
            'expiry_date': batch.expiry_date.strftime('%b %d, %Y'),
            'days_left': days_left
        })

    context = {
        'total_sales': total_sales,
        'transaction_count': transaction_count,
        'low_stock_count': len(low_stock_products),
        'near_expiry_count': len(near_expiry_items),
        'low_stock_products': low_stock_products[:5],
        'near_expiry_items': near_expiry_items[:5],
        'total_outstanding': total_outstanding,
        'today_credit_received': today_credit_received,
    }
    return render(request, 'dashboard.html', context)


# ==================== PRODUCTS ====================

@login_required
@teller_can_view
def products(request):
    search = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')
    status_filter = request.GET.get('status', 'active')

    # Filter by active status
    if status_filter == 'inactive':
        products = Product.objects.filter(is_active=False).select_related('category')
    else:
        products = Product.objects.filter(is_active=True).select_related('category')

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    if category_filter:
        products = products.filter(category_id=category_filter)

    if stock_filter == 'low':
        products = [p for p in products if p.is_low_stock]
    elif stock_filter == 'out':
        products = [p for p in products if p.current_stock == 0]

    categories = Category.objects.filter(is_active=True)

    context = {
        'products': products,
        'categories': categories,
        'search': search,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'status_filter': status_filter,
    }
    return render(request, 'products.html', context)


@login_required
@owner_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully!')
            return redirect('products')
    else:
        form = ProductForm()

    categories = Category.objects.filter(is_active=True)
    return render(request, 'product_form.html', {'form': form, 'categories': categories, 'title': 'Add Product'})


@login_required
@owner_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('products')
    else:
        form = ProductForm(instance=product)

    categories = Category.objects.filter(is_active=True)
    stock_batches = product.stock_batches.all().order_by('purchase_date')

    return render(request, 'product_form.html', {
        'form': form,
        'categories': categories,
        'product': product,
        'stock_batches': stock_batches,
        'title': 'Edit Product'
    })


@login_required
@owner_required
def archive_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save()
    messages.success(request, f'{product.name} has been archived.')
    return redirect('products')


@login_required
@owner_required
def unarchive_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = True
    product.save()
    messages.success(request, f'{product.name} has been restored.')
    return redirect('products')


# ==================== CATEGORIES ====================

@login_required
@owner_required
def categories(request):
    categories = Category.objects.all()
    return render(request, 'categories.html', {'categories': categories})


@login_required
@owner_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully!')
            return redirect('categories')
    else:
        form = CategoryForm()
    return render(request, 'category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
@owner_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'category_form.html', {'form': form, 'title': 'Edit Category'})


# ==================== POS / SALES ====================

@login_required
@teller_can_view
def pos(request):
    search = request.GET.get('search', '')
    products = Product.objects.filter(is_active=True).select_related('category')

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    context = {
        'products': products[:20],
        'search': search,
    }
    return render(request, 'pos.html', context)


@login_required
@teller_can_view
@require_http_methods(["POST"])
def process_sale(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        payment_type = data.get('payment_type', 'cash')
        customer_name = data.get('customer_name', '').strip()

        if not items:
            return JsonResponse({'success': False, 'error': 'No items in cart'})

        # Calculate total
        total = 0
        for item in items:
            product = Product.objects.get(pk=item['product_id'])
            total += product.selling_price * item['quantity']

        # Handle Credit / Utang
        if payment_type == 'credit':
            if not customer_name:
                return JsonResponse({'success': False, 'error': 'Customer name required for credit'})
            
            # Check if customer already has unpaid or partial credit
            existing_credit = CreditRecord.objects.filter(
                customer_name__iexact=customer_name,
                status__in=['unpaid', 'partial']
            ).first()
            
            if existing_credit:
                # Add to existing credit record
                existing_credit.total_amount += total
                existing_credit.remaining_balance += total
                existing_credit.save()
                credit = existing_credit
                message = f'Added to existing credit for {customer_name}. Total owed: ₱{existing_credit.remaining_balance}'
            else:
                # Create new credit record
                credit = CreditRecord.objects.create(
                    customer_name=customer_name,
                    total_amount=total,
                    remaining_balance=total,
                    status='unpaid',
                    created_by=request.user
                )
                message = f'Credit / Utang recorded for {customer_name}!'
            
            # Create credit items (snapshot of products)
            for item in items:
                product = Product.objects.get(pk=item['product_id'])
                quantity = item['quantity']
                unit_price = product.selling_price
                subtotal = unit_price * quantity
                
                CreditItem.objects.create(
                    credit_record=credit,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                
                # Deduct inventory (FIFO) - same as regular sale
                quantity_needed = quantity
                batches = product.stock_batches.filter(
                    remaining_quantity__gt=0
                ).order_by('purchase_date', 'expiry_date')
                
                for batch in batches:
                    if quantity_needed <= 0:
                        break
                    if batch.is_expired:
                        continue
                    
                    deduct = min(batch.remaining_quantity, quantity_needed)
                    batch.remaining_quantity -= deduct
                    batch.save()
                    quantity_needed -= deduct
            
            return JsonResponse({'success': True, 'sale_id': credit.id, 'total': str(total), 'message': message})

        # Regular sale (cash, gcash, other) - add to today's revenue
        sale = Sale.objects.create(
            total_amount=total,
            payment_type=payment_type,
            created_by=request.user
        )

        # Process each item with FIFO
        for item in items:
            product = Product.objects.get(pk=item['product_id'])
            quantity_needed = item['quantity']

            # Get batches in order (FIFO)
            batches = product.stock_batches.filter(
                remaining_quantity__gt=0
            ).order_by('purchase_date', 'expiry_date')

            for batch in batches:
                if quantity_needed <= 0:
                    break

                # Check if batch is expired
                if batch.is_expired:
                    continue

                # Deduct from batch
                deduct = min(batch.remaining_quantity, quantity_needed)
                batch.remaining_quantity -= deduct
                batch.save()
                quantity_needed -= deduct

                # Create sale item
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=deduct,
                    unit_price=product.selling_price,
                    subtotal=product.selling_price * deduct
                )

            # If still needed more after clearing all batches
            if quantity_needed > 0:
                # Create sale item for remaining (should not happen in normal flow)
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity_needed,
                    unit_price=product.selling_price,
                    subtotal=product.selling_price * quantity_needed
                )

        return JsonResponse({'success': True, 'sale_id': sale.id, 'total': str(total)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ==================== PURCHASE / STOCK IN ====================

@login_required
@owner_required
def purchase(request):
    purchases = Purchase.objects.all().select_related('product')[:20]

    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.created_by = request.user
            purchase.save()
            messages.success(request, 'Stock added successfully!')
            return redirect('purchase')
    else:
        form = PurchaseForm()

    context = {
        'form': form,
        'purchases': purchases,
    }
    return render(request, 'purchase.html', context)


# ==================== REPORTS ====================

@login_required
@owner_required
def reports(request):
    report_type = request.GET.get('type', 'daily')
    date_str = request.GET.get('date', '')
    month_str = request.GET.get('month', '')

    today = timezone.now().date()

    if report_type == 'daily':
        if date_str:
            selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = today

        sales = Sale.objects.filter(sale_date__date=selected_date)
        total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0

        purchases = Purchase.objects.filter(purchase_date=selected_date)
        total_purchases = purchases.aggregate(total=Sum(F('quantity') * F('unit_cost')))['total'] or 0

        profit = total_sales - total_purchases

        # Get transactions
        transactions = sales.order_by('-sale_date')

        # Calculate expired value (rough estimate)
        expired_value = 0
        for batch in StockBatch.objects.filter(remaining_quantity__gt=0, expiry_date__lt=today):
            expired_value += batch.remaining_quantity * batch.unit_cost

        context = {
            'report_type': 'daily',
            'selected_date': selected_date,
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'profit': profit,
            'expired_value': expired_value,
            'transactions': transactions,
        }

    elif report_type == 'monthly':
        if month_str:
            year, month = map(int, month_str.split('-'))
            start_date = timezone.datetime(year, month, 1).date()
            if month == 12:
                end_date = timezone.datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = timezone.datetime(year, month + 1, 1).date() - timedelta(days=1)
        else:
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        sales = Sale.objects.filter(sale_date__date__range=[start_date, end_date])
        total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0

        purchases = Purchase.objects.filter(purchase_date__range=[start_date, end_date])
        total_purchases = purchases.aggregate(total=Sum(F('quantity') * F('unit_cost')))['total'] or 0

        profit = total_sales - total_purchases

        # Top products
        top_products = SaleItem.objects.filter(
            sale__sale_date__date__range=[start_date, end_date]
        ).values('product__name').annotate(
            total_qty=Sum('quantity'),
            total_sales=Sum('subtotal')
        ).order_by('-total_sales')[:5]

        context = {
            'report_type': 'monthly',
            'start_date': start_date,
            'end_date': end_date,
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'profit': profit,
            'top_products': top_products,
        }

    elif report_type == 'inventory':
        products = Product.objects.filter(is_active=True).select_related('category')

        low_stock = [p for p in products if p.is_low_stock]

        near_expiry = []
        warning_date = today + timedelta(days=7)
        for batch in StockBatch.objects.filter(
            remaining_quantity__gt=0,
            expiry_date__lte=warning_date,
            expiry_date__gte=today,
            product__track_expiry=True
        ).select_related('product'):
            near_expiry.append({
                'product': batch.product.name,
                'batch': batch,
                'days_left': (batch.expiry_date - today).days
            })

        context = {
            'report_type': 'inventory',
            'products': products,
            'low_stock': low_stock,
            'near_expiry': near_expiry,
        }
    
    elif report_type == 'credit':
        # Credit report
        today = timezone.now().date()
        
        # New credit created today
        credit_new_today = CreditRecord.objects.filter(created_at__date=today).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Payments received today
        credit_payments_today = CreditPayment.objects.filter(payment_date__date=today).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Total outstanding
        credit_outstanding = CreditRecord.objects.filter(
            status__in=['unpaid', 'partial']
        ).aggregate(total=Sum('remaining_balance'))['total'] or 0
        
        # All credit records with paid amount
        credit_records = []
        for credit in CreditRecord.objects.all():
            paid = credit.total_amount - credit.remaining_balance
            credit_records.append({
                'id': credit.id,
                'customer_name': credit.customer_name,
                'created_at': credit.created_at,
                'total_amount': credit.total_amount,
                'remaining_balance': credit.remaining_balance,
                'paid': paid,
                'status': credit.status,
                'get_status_display': credit.get_status_display,
            })
        
        context = {
            'report_type': 'credit',
            'credit_new_today': credit_new_today,
            'credit_payments_today': credit_payments_today,
            'credit_outstanding': credit_outstanding,
            'credit_records': credit_records,
        }

    elif report_type == 'velocity':
        # Sales Velocity - all time fast/slow moving items
        fast_moving = SaleItem.objects.values('product__name').annotate(
            total_qty=Sum('quantity')
        ).order_by('-total_qty')[:20]

        slow_moving = SaleItem.objects.values('product__name').annotate(
            total_qty=Sum('quantity')
        ).order_by('total_qty')[:10]

        context = {
            'report_type': 'velocity',
            'fast_moving': fast_moving,
            'slow_moving': slow_moving,
        }

    return render(request, 'reports.html', context)


# ==================== USER MANAGEMENT ====================

@login_required
@owner_required
def users(request):
    users = User.objects.all().select_related('profile')
    return render(request, 'users.html', {'users': users})


@login_required
@owner_required
def add_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.username} created successfully!')
            return redirect('users')
    else:
        form = UserCreationForm()
    return render(request, 'user_form.html', {'form': form, 'title': 'Add User'})


@login_required
@owner_required
def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()
            if hasattr(user, 'profile'):
                user.profile.role = form.cleaned_data['role']
                user.profile.save()
            messages.success(request, 'User updated successfully!')
            return redirect('users')
    else:
        form = UserEditForm(instance=user)

    return render(request, 'user_form.html', {'form': form, 'user': user, 'title': 'Edit User'})


@login_required
@owner_required
def deactivate_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate yourself.")
    else:
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.username} has been deactivated.')
    return redirect('users')


@login_required
@owner_required
def activate_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_active = True
    user.save()
    messages.success(request, f'User {user.username} has been activated.')
    return redirect('users')


# ==================== CREDIT / UTANG VIEWS ====================

@login_required
@teller_can_view
def credit_list(request):
    filter_status = request.GET.get('status', 'all')
    
    # Recalculate balances if needed
    if request.GET.get('recalculate') == '1':
        for credit in CreditRecord.objects.all():
            paid = credit.payments.aggregate(total=Sum('amount'))['total'] or 0
            credit.remaining_balance = credit.total_amount - paid
            if credit.remaining_balance <= 0:
                credit.remaining_balance = 0
                credit.status = 'paid'
            elif paid > 0:
                credit.status = 'partial'
            else:
                credit.status = 'unpaid'
            credit.save()
        messages.success(request, 'Credit balances recalculated.')
    
    credits = CreditRecord.objects.all()
    
    if filter_status == 'unpaid':
        credits = credits.filter(status='unpaid')
    elif filter_status == 'partial':
        credits = credits.filter(status='partial')
    elif filter_status == 'paid':
        credits = credits.filter(status='paid')
    
    # Calculate total outstanding
    total_outstanding = CreditRecord.objects.filter(
        status__in=['unpaid', 'partial']
    ).aggregate(total=Sum('remaining_balance'))['total'] or 0
    
    context = {
        'credits': credits,
        'filter_status': filter_status,
        'total_outstanding': total_outstanding,
    }
    return render(request, 'credit.html', context)


@login_required
@teller_can_view
def credit_add_payment(request, pk):
    credit = get_object_or_404(CreditRecord, pk=pk)
    
    if request.method == 'POST':
        try:
            amount_str = request.POST.get('amount', '')
            if not amount_str:
                messages.error(request, 'Please enter an amount.')
                return redirect('credit_list')
            
            amount = Decimal(str(amount_str))
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount.')
                return redirect('credit_list')
            
            if amount > credit.remaining_balance:
                messages.error(request, f'Amount exceeds remaining balance of ₱{credit.remaining_balance}.')
                return redirect('credit_list')
            
            # Create payment record
            CreditPayment.objects.create(
                credit_record=credit,
                amount=amount,
                created_by=request.user
            )
            
            # Update remaining balance and status
            credit.remaining_balance -= amount
            if credit.remaining_balance <= 0:
                credit.remaining_balance = 0
                credit.status = 'paid'
            else:
                credit.status = 'partial'
            credit.save()
            
            # If payment made on credit sale, also record as sale revenue
            from .models import Sale, SaleItem
            Sale.objects.create(
                total_amount=amount,
                payment_type='credit_payment',
                created_by=request.user
            )
            
            messages.success(request, f'Payment of ₱{amount:.2f} recorded for {credit.customer_name}.')
        except ValueError:
            messages.error(request, 'Invalid amount. Please enter a number.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('credit_list')


@login_required
@owner_required
def credit_delete(request, pk):
    credit = get_object_or_404(CreditRecord, pk=pk)
    
    if credit.status != 'paid':
        messages.error(request, 'Only fully paid credit records can be deleted.')
        return redirect('reports')
    
    customer_name = credit.customer_name
    credit.delete()
    messages.success(request, f'Credit record for {customer_name} has been deleted.')
    return redirect('reports')


# ==================== API VIEWS ====================

@login_required
def api_products(request):
    products = Product.objects.filter(is_active=True).values('id', 'name', 'sku', 'selling_price', 'current_stock')
    return JsonResponse(list(products), safe=False)