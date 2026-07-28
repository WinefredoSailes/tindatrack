from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, F
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json

from .models import Client, ClientLog, ClientPayment, SubscriptionPlan, Category, Product, StockBatch, Sale, SaleItem, Purchase, UserProfile, CreditRecord, CreditItem, CreditPayment
from .forms import (
    LoginForm, UserCreationForm, UserEditForm,
    CategoryForm, ProductForm, PurchaseForm, SaleForm
)


# Tenant helper
def get_client(request):
    if hasattr(request, 'client') and request.client:
        return request.client
    return None


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
                # Check subscription
                if hasattr(user, 'profile') and user.profile.client:
                    client = user.profile.client
                    if not client.is_active:
                        messages.error(request, 'Your account has been deactivated. Contact support.')
                        return render(request, 'login.html', {'form': LoginForm()})
                    if not client.is_subscription_valid and not user.is_superuser:
                        messages.error(request, 'Your subscription has expired. Contact support to renew.')
                        return render(request, 'login.html', {'form': LoginForm()})
                    # Show warning 3 days before trial or payment expiry
                    if not user.is_superuser:
                        if client.subscription_status == 'trial' and client.trial_end_date:
                            days_left = (client.trial_end_date - timezone.now().date()).days
                            if 0 < days_left <= 3:
                                messages.warning(request, f'Your trial ends in {days_left} day{"s" if days_left > 1 else ""}. Please contact support to renew.')
                        elif client.subscription_status != 'active' and client.paid_until_date:
                            days_left = (client.paid_until_date - timezone.now().date()).days
                            if 0 < days_left <= 3:
                                messages.warning(request, f'Your subscription ends in {days_left} day{"s" if days_left > 1 else ""}. Please contact support to renew.')
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        store_name = request.POST.get('store_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        errors = []
        if not store_name: errors.append('Store name is required.')
        if not username: errors.append('Username is required.')
        if len(username) < 3: errors.append('Username must be at least 3 characters.')
        if len(password) < 6: errors.append('Password must be at least 6 characters.')
        if password != confirm_password: errors.append('Passwords do not match.')
        if User.objects.filter(username=username).exists(): errors.append('Username already taken.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'store_name': store_name, 'username': username,
            })

        client = Client.objects.create(
            name=store_name,
            subdomain=username.lower().replace(' ', '-'),
            subscription_status='trial',
            trial_end_date=timezone.now().date() + timedelta(days=60),
            monthly_rate=299,
        )

        user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(user=user, client=client, role='owner')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome {store_name}! Your 60-day free trial has started.')
            return redirect('dashboard')

        messages.error(request, 'Registration failed. Please try again.')
        return redirect('login')

    return render(request, 'register.html', {
        'store_name': '', 'username': '',
    })


def logout_view(request):
    logout(request)
    return redirect('login')


# ==================== DASHBOARD ====================

@login_required
@teller_can_view
def dashboard(request):
    client = get_client(request)
    today = timezone.now().date()

    # Today's sales
    today_sales = Sale.objects.filter(client=client, sale_date__date=today)
    total_sales = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    transaction_count = today_sales.count()

    # Today's credit payments received
    today_credit_payments = CreditPayment.objects.filter(client=client, payment_date__date=today)
    today_credit_received = today_credit_payments.aggregate(total=Sum('amount'))['total'] or 0

    # Total outstanding credit (all unpaid/partial)
    total_outstanding = CreditRecord.objects.filter(
        client=client, status__in=['unpaid', 'partial']
    ).aggregate(total=Sum('remaining_balance'))['total'] or 0

    # Low stock items
    low_stock_products = []
    for product in Product.objects.filter(client=client, is_active=True):
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
        client=client,
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

    # Client expiry notifications (for superuser)
    expiring_clients = []
    expired_clients = []
    if request.user.is_superuser:
        today = timezone.now().date()
        for c in Client.objects.filter(is_active=True):
            if c.status_display == 'expired':
                expired_clients.append(c)
            elif c.status_display == 'expiring':
                expiring_clients.append(c)

    context = {
        'total_sales': total_sales,
        'transaction_count': transaction_count,
        'low_stock_count': len(low_stock_products),
        'near_expiry_count': len(near_expiry_items),
        'low_stock_products': low_stock_products[:5],
        'near_expiry_items': near_expiry_items[:5],
        'total_outstanding': total_outstanding,
        'today_credit_received': today_credit_received,
        'expiring_clients': expiring_clients,
        'expired_clients': expired_clients,
    }
    return render(request, 'dashboard.html', context)


# ==================== PRODUCTS ====================

@login_required
@teller_can_view
def products(request):
    client = get_client(request)
    search = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')
    status_filter = request.GET.get('status', 'active')

    # Filter by active status
    if status_filter == 'inactive':
        products_qs = Product.objects.filter(client=client, is_active=False).select_related('category')
    else:
        products_qs = Product.objects.filter(client=client, is_active=True).select_related('category')

    if search:
        products_qs = products_qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    if category_filter:
        products_qs = products_qs.filter(category_id=category_filter)

    # Stock filters convert to list (can't paginate queryset after)
    if stock_filter == 'low':
        products = [p for p in products_qs if p.is_low_stock]
        page_obj = None
    elif stock_filter == 'out':
        products = [p for p in products_qs if p.current_stock == 0]
        page_obj = None
    else:
        paginator = Paginator(products_qs, 30)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        products = page_obj

    categories = Category.objects.filter(client=client, is_active=True)

    context = {
        'products': products,
        'categories': categories,
        'search': search,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'status_filter': status_filter,
        'page_obj': page_obj,
    }
    return render(request, 'products.html', context)


@login_required
@owner_required
def add_product(request):
    client = get_client(request)
    if request.method == 'POST':
        form = ProductForm(request.POST, client=client)
        if form.is_valid():
            product = form.save(commit=False)
            product.client = client
            product.save()
            messages.success(request, 'Product added successfully!')
            return redirect('products')
    else:
        form = ProductForm(client=client)

    categories = Category.objects.filter(client=client, is_active=True)
    return render(request, 'product_form.html', {'form': form, 'categories': categories, 'title': 'Add Product'})


@login_required
@owner_required
def edit_product(request, pk):
    client = get_client(request)
    product = get_object_or_404(Product, pk=pk, client=client)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, client=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('products')
    else:
        form = ProductForm(instance=product, client=client)

    categories = Category.objects.filter(client=client, is_active=True)
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
    client = get_client(request)
    product = get_object_or_404(Product, pk=pk, client=client)
    product.is_active = False
    product.save()
    messages.success(request, f'{product.name} has been archived.')
    return redirect('products')


@login_required
@owner_required
def unarchive_product(request, pk):
    client = get_client(request)
    product = get_object_or_404(Product, pk=pk, client=client)
    product.is_active = True
    product.save()
    messages.success(request, f'{product.name} has been restored.')
    return redirect('products')


# ==================== CATEGORIES ====================

@login_required
@owner_required
def categories(request):
    client = get_client(request)
    categories = Category.objects.filter(client=client)
    return render(request, 'categories.html', {'categories': categories})


@login_required
@owner_required
def add_category(request):
    client = get_client(request)
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.client = client
            category.save()
            messages.success(request, 'Category added successfully!')
            return redirect('categories')
    else:
        form = CategoryForm()
    return render(request, 'category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
@owner_required
def edit_category(request, pk):
    client = get_client(request)
    category = get_object_or_404(Category, pk=pk, client=client)
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
    client = get_client(request)
    search = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    products = Product.objects.filter(client=client, is_active=True).select_related('category')
    categories = Category.objects.filter(client=client, is_active=True)

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category_id and category_id.isdigit():
        products = products.filter(category_id=category_id)

    paginator = Paginator(products, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'search': search,
        'category_id': int(category_id) if category_id and category_id.isdigit() else '',
        'categories': categories,
        'page_obj': page_obj,
    }
    return render(request, 'pos.html', context)


@login_required
@teller_can_view
@require_http_methods(["POST"])
def process_sale(request):
    client = get_client(request)
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
            product = Product.objects.get(pk=item['product_id'], client=client)
            total += product.selling_price * item['quantity']

        # Handle Credit / Utang
        if payment_type == 'credit':
            if not customer_name:
                return JsonResponse({'success': False, 'error': 'Customer name required for credit'})
            
            # Check if customer already has unpaid or partial credit
            existing_credit = CreditRecord.objects.filter(
                client=client,
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
                    client=client,
                    customer_name=customer_name,
                    total_amount=total,
                    remaining_balance=total,
                    status='unpaid',
                    created_by=request.user
                )
                message = f'Credit / Utang recorded for {customer_name}!'
            
            # Create credit items (snapshot of products)
            for item in items:
                product = Product.objects.get(pk=item['product_id'], client=client)
                quantity = item['quantity']
                unit_price = product.selling_price
                subtotal = unit_price * quantity
                
                CreditItem.objects.create(
                    client=client,
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

        # Regular sale (cash, gcash, other)
        sale = Sale.objects.create(
            client=client,
            total_amount=total,
            payment_type=payment_type,
            created_by=request.user
        )

        # Process each item with FIFO
        for item in items:
            product = Product.objects.get(pk=item['product_id'], client=client)
            quantity_needed = item['quantity']

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

                SaleItem.objects.create(
                    client=client,
                    sale=sale,
                    product=product,
                    quantity=deduct,
                    unit_price=product.selling_price,
                    subtotal=product.selling_price * deduct
                )

            if quantity_needed > 0:
                SaleItem.objects.create(
                    client=client,
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
    client = get_client(request)
    purchases = Purchase.objects.filter(client=client).select_related('product')[:20]

    if request.method == 'POST':
        form = PurchaseForm(request.POST, client=client)
        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.client = client
            purchase.created_by = request.user
            purchase.save()
            messages.success(request, 'Stock added successfully!')
            return redirect('purchase')
    else:
        form = PurchaseForm(client=client)

    context = {
        'form': form,
        'purchases': purchases,
    }
    return render(request, 'purchase.html', context)


# ==================== REPORTS ====================

@login_required
@owner_required
def reports(request):
    client = get_client(request)
    report_type = request.GET.get('type', 'daily')
    date_str = request.GET.get('date', '')
    month_str = request.GET.get('month', '')

    today = timezone.now().date()

    if report_type == 'daily':
        if date_str:
            selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = today

        sales = Sale.objects.filter(client=client, sale_date__date=selected_date)
        total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0

        purchases = Purchase.objects.filter(client=client, purchase_date=selected_date)
        total_purchases = purchases.aggregate(total=Sum(F('quantity') * F('unit_cost')))['total'] or 0

        profit = total_sales - total_purchases

        transactions = sales.order_by('-sale_date')

        expired_value = 0
        for batch in StockBatch.objects.filter(client=client, remaining_quantity__gt=0, expiry_date__lt=today):
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

        sales = Sale.objects.filter(client=client, sale_date__date__range=[start_date, end_date])
        total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0

        purchases = Purchase.objects.filter(client=client, purchase_date__range=[start_date, end_date])
        total_purchases = purchases.aggregate(total=Sum(F('quantity') * F('unit_cost')))['total'] or 0

        profit = total_sales - total_purchases

        top_products = SaleItem.objects.filter(
            client=client,
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
        products = Product.objects.filter(client=client, is_active=True).select_related('category')

        low_stock = [p for p in products if p.is_low_stock]

        near_expiry = []
        warning_date = today + timedelta(days=7)
        for batch in StockBatch.objects.filter(
            client=client,
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
        today = timezone.now().date()
        
        credit_new_today = CreditRecord.objects.filter(client=client, created_at__date=today).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        credit_payments_today = CreditPayment.objects.filter(client=client, payment_date__date=today).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        credit_outstanding = CreditRecord.objects.filter(
            client=client, status__in=['unpaid', 'partial']
        ).aggregate(total=Sum('remaining_balance'))['total'] or 0
        
        credit_records = []
        for credit in CreditRecord.objects.filter(client=client):
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
        fast_moving = SaleItem.objects.filter(client=client).values('product__name').annotate(
            total_qty=Sum('quantity')
        ).order_by('-total_qty')[:20]

        slow_moving = SaleItem.objects.filter(client=client).values('product__name').annotate(
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
    client = get_client(request)
    users = User.objects.filter(profile__client=client).select_related('profile')
    return render(request, 'users.html', {'users': users})


@login_required
@owner_required
def add_user(request):
    client = get_client(request)
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = user.profile
            profile.client = client
            profile.save()
            messages.success(request, f'User {user.username} created successfully!')
            return redirect('users')
    else:
        form = UserCreationForm()
    return render(request, 'user_form.html', {'form': form, 'title': 'Add User'})


@login_required
@owner_required
def edit_user(request, pk):
    client = get_client(request)
    user = get_object_or_404(User, pk=pk, profile__client=client)

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
    client = get_client(request)
    user = get_object_or_404(User, pk=pk, profile__client=client)
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
    client = get_client(request)
    user = get_object_or_404(User, pk=pk, profile__client=client)
    user.is_active = True
    user.save()
    messages.success(request, f'User {user.username} has been activated.')
    return redirect('users')


# ==================== CREDIT / UTANG VIEWS ====================

@login_required
@teller_can_view
def credit_list(request):
    client = get_client(request)
    filter_status = request.GET.get('status', 'all')
    
    # Recalculate balances if needed
    if request.GET.get('recalculate') == '1':
        for credit in CreditRecord.objects.filter(client=client):
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
    
    credits = CreditRecord.objects.filter(client=client)
    
    if filter_status == 'unpaid':
        credits = credits.filter(status='unpaid')
    elif filter_status == 'partial':
        credits = credits.filter(status='partial')
    elif filter_status == 'paid':
        credits = credits.filter(status='paid')
    
    # Calculate total outstanding
    total_outstanding = CreditRecord.objects.filter(
        client=client, status__in=['unpaid', 'partial']
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
    client = get_client(request)
    credit = get_object_or_404(CreditRecord, pk=pk, client=client)
    
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
                client=client,
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
            Sale.objects.create(
                client=client,
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
    client = get_client(request)
    credit = get_object_or_404(CreditRecord, pk=pk, client=client)
    
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
    client = get_client(request)
    products = Product.objects.filter(client=client, is_active=True)
    data = [{
        'id': p.id, 'name': p.name, 'sku': p.sku,
        'selling_price': str(p.selling_price), 'current_stock': p.current_stock,
    } for p in products]
    return JsonResponse(data, safe=False)


# ==================== CLIENT MANAGEMENT (Superuser only) ====================

@login_required
def client_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    clients = Client.objects.all()
    today = timezone.now().date()
    return render(request, 'clients.html', {
        'clients': clients,
        'today': today,
    })


@login_required
def client_add(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        subdomain = request.POST.get('subdomain', '').strip()
        trial_days = int(request.POST.get('trial_days', 15))
        subscription_status = request.POST.get('subscription_status', 'trial')
        
        if not name or not subdomain:
            messages.error(request, 'Name and subdomain are required.')
            return redirect('client_list')
        
        if Client.objects.filter(subdomain=subdomain).exists():
            messages.error(request, f'Subdomain "{subdomain}" is already taken.')
            return redirect('client_list')
        
        client = Client.objects.create(
            name=name,
            subdomain=subdomain,
            subscription_status=subscription_status,
            trial_end_date=timezone.now().date() + timedelta(days=trial_days) if subscription_status == 'trial' else None,
            notes=request.POST.get('notes', ''),
        )
        
        ClientLog.objects.create(
            client=client,
            action='Client created',
            details=f'Subscription: {subscription_status}',
            changed_by=request.user,
        )
        
        # Create owner user for the client
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username and password:
            user = User.objects.create_user(username=username, password=password)
            UserProfile.objects.create(user=user, client=client, role='owner')
        
        messages.success(request, f'Client "{name}" created successfully!')
        return redirect('client_list')
    
    return redirect('client_list')


@login_required
def client_detail(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=pk)
    payments = ClientPayment.objects.filter(client=client).select_related('plan', 'recorded_by')
    logs = ClientLog.objects.filter(client=client)[:50]
    owner_profile = client.profiles.filter(role='owner').first()
    plans = SubscriptionPlan.objects.filter(is_active=True)
    
    # Compute next due date and amount
    today = timezone.now().date()
    next_due_date = client.paid_until_date if client.paid_until_date and client.paid_until_date >= today else today
    amount_due = client.monthly_rate
    
    return render(request, 'client_detail.html', {
        'c': client,
        'payments': payments,
        'logs': logs,
        'owner_username': owner_profile.user.username if owner_profile else '',
        'today': today,
        'plans': plans,
        'next_due_date': next_due_date,
        'amount_due': amount_due,
    })


@login_required
def client_edit(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        old_status = client.subscription_status
        old_rate = client.monthly_rate
        
        client.name = request.POST.get('name', client.name)
        client.subdomain = request.POST.get('subdomain', client.subdomain)
        client.subscription_status = request.POST.get('subscription_status', client.subscription_status)
        client.is_active = request.POST.get('is_active') == 'on'
        client.monthly_rate = request.POST.get('monthly_rate', client.monthly_rate)
        trial_days = int(request.POST.get('trial_days', 15))
        
        paid_until = request.POST.get('paid_until', '').strip()
        if paid_until:
            client.paid_until_date = paid_until
        
        if client.subscription_status == 'trial':
            client.trial_end_date = timezone.now().date() + timedelta(days=trial_days)
        elif client.subscription_status == 'active':
            client.trial_end_date = None
        else:
            client.trial_end_date = client.trial_end_date
        
        client.notes = request.POST.get('notes', client.notes)
        
        # Build change log details
        changes = []
        if old_status != client.subscription_status:
            changes.append(f'Status: {old_status} → {client.subscription_status}')
        
        client.save()
        
        if changes:
            ClientLog.objects.create(
                client=client,
                action='Client updated',
                details='; '.join(changes),
                changed_by=request.user,
            )
        
        # Update owner username/password if provided
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username and password:
            owner_profile = client.profiles.filter(role='owner').first()
            if owner_profile:
                owner_profile.user.username = username
                owner_profile.user.set_password(password)
                owner_profile.user.save()
        
        messages.success(request, f'Client "{client.name}" updated successfully!')
        return redirect('client_list')
    
    owner_profile = client.profiles.filter(role='owner').first()
    return render(request, 'client_edit.html', {
        'c': client,
        'owner_username': owner_profile.user.username if owner_profile else ''
    })


@login_required
def record_payment(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference = request.POST.get('reference', '')
        paid_until = request.POST.get('paid_until')
        plan_id = request.POST.get('plan_id', '')
        notes = request.POST.get('notes', '')
        
        # Auto-compute paid_until if plan selected and no manual date
        plan = None
        if plan_id and plan_id.isdigit():
            plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
            if not paid_until:
                paid_until = (timezone.now().date() + timedelta(days=plan.duration_days)).isoformat()
        
        if not amount or not paid_until:
            messages.error(request, 'Amount and Paid Until date are required.')
            return redirect('client_detail', pk=client.pk)

        payment = ClientPayment.objects.create(
            client=client,
            plan=plan,
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            paid_until=paid_until,
            notes=notes,
            recorded_by=request.user,
        )

        if client.paid_until_date is None or payment.paid_until > client.paid_until_date:
            client.paid_until_date = payment.paid_until

        if client.subscription_status not in ('active', 'locked'):
            client.subscription_status = 'expired'

        client.save()

        ClientLog.objects.create(
            client=client,
            action=f'Payment recorded: ₱{amount} via {payment_method}',
            details=f'Covered until {paid_until}. Ref: {reference}',
            changed_by=request.user,
        )

        messages.success(request, f'Payment of ₱{amount} recorded for {client.name}!')
        return redirect('client_detail', pk=client.pk)

    return redirect('client_detail', pk=client.pk)


@login_required
def my_subscription(request):
    client = get_client(request)
    today = timezone.now().date()
    payments = ClientPayment.objects.filter(client=client).select_related('plan', 'recorded_by')
    next_due_date = client.paid_until_date if client.paid_until_date and client.paid_until_date >= today else today
    amount_due = client.monthly_rate
    
    return render(request, 'my_subscription.html', {
        'c': client,
        'payments': payments,
        'today': today,
        'next_due_date': next_due_date,
        'amount_due': amount_due,
    })


@login_required
def checkout(request, plan_id):
    client = get_client(request)
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)

    from .paymongo import create_checkout_session
    base_url = request.build_absolute_uri('/')[:-1]
    success_url = base_url + reverse('checkout_success', args=[plan_id])
    cancel_url = base_url + reverse('my_subscription')

    checkout_url, session_id = create_checkout_session(client, plan, success_url, cancel_url)
    if checkout_url:
        return redirect(checkout_url)

    messages.error(request, 'Unable to process payment right now. Please try again later or contact support.')
    return redirect('my_subscription')


@login_required
def checkout_success(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
    client = get_client(request)
    today = timezone.now().date()

    paid_until = max(client.paid_until_date, today) if client.paid_until_date else today
    paid_until += timedelta(days=plan.duration_days)

    ClientPayment.objects.create(
        client=client,
        plan=plan,
        amount=plan.price,
        payment_method='gcash',
        reference=f'Auto-{plan.name}-{timezone.now().strftime("%Y%m%d%H%M%S")}',
        paid_until=paid_until,
        notes=f'Online payment via PayMongo - {plan.name}',
        recorded_by=request.user,
    )

    client.paid_until_date = paid_until
    if client.subscription_status not in ('active', 'locked'):
        client.subscription_status = 'expired'
    client.save()

    ClientLog.objects.create(
        client=client,
        action=f'Auto-payment: ₱{plan.price} via PayMongo',
        details=f'{plan.name} - covered until {paid_until}',
        changed_by=request.user,
    )

    messages.success(request, f'Payment successful! Your subscription is active until {paid_until}.')
    return redirect('my_subscription')


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def paymongo_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        payload = request.body.decode('utf-8')
        data = json.loads(payload)
        event = data.get('data', {}).get('attributes', {}).get('type', '')

        if event == 'checkout_session.payment.paid':
            session_id = data['data']['attributes']['data']['id']
            print(f'PayMongo webhook: payment success for session {session_id}')

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f'PayMongo webhook error: {e}')
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    today = timezone.now().date()
    clients = Client.objects.all()

    total = clients.count()
    active = sum(1 for c in clients if c.status_display == 'active')
    expiring = sum(1 for c in clients if c.status_display == 'expiring')
    expired_count = sum(1 for c in clients if c.status_display == 'expired')

    recent_payments = ClientPayment.objects.select_related('client', 'recorded_by')[:20]
    recent_logs = ClientLog.objects.select_related('client', 'changed_by')[:20]

    monthly_revenue = sum(p.amount for p in ClientPayment.objects.filter(created_at__month=today.month, created_at__year=today.year))

    return render(request, 'admin_dashboard.html', {
        'total_clients': total,
        'active_clients': active,
        'expiring_clients': expiring,
        'expired_clients': expired_count,
        'clients': clients,
        'recent_payments': recent_payments,
        'recent_logs': recent_logs,
        'monthly_revenue': monthly_revenue,
        'today': today,
    })