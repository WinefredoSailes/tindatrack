from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, F
from django.utils import timezone


class Client(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('locked', 'Locked'),
    ]
    name = models.CharField(max_length=200)
    subdomain = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    trial_end_date = models.DateField(null=True, blank=True)
    paid_until_date = models.DateField(null=True, blank=True)
    subscription_status = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='trial')
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_subscription_valid(self):
        if self.subscription_status == 'active':
            return True
        if self.subscription_status == 'trial' and self.trial_end_date:
            return self.trial_end_date >= timezone.now().date()
        if self.subscription_status == 'expired' and self.paid_until_date:
            return self.paid_until_date >= timezone.now().date()
        return False

    @property
    def days_until_expiry(self):
        today = timezone.now().date()
        if self.subscription_status == 'active':
            return 999
        if self.subscription_status == 'trial' and self.trial_end_date:
            return (self.trial_end_date - today).days
        if self.subscription_status == 'expired' and self.paid_until_date:
            return (self.paid_until_date - today).days
        return 0

    @property
    def status_display(self):
        if self.days_until_expiry <= 0:
            return 'expired'
        if self.days_until_expiry <= 7:
            return 'expiring'
        return 'active'


class ClientPayment(models.Model):
    PAYMENT_METHODS = [
        ('gcash', 'GCash'),
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=200, blank=True, help_text='GCash ref no., bank ref, etc.')
    paid_until = models.DateField(help_text='Covered until this date')
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client.name} - ₱{self.amount} ({self.payment_method})'


class ClientLog(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.client.name} - {self.action}'


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('teller', 'Teller'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='profiles', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teller')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_teller(self):
        return self.role == 'teller'


class Category(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True, null=True, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_level = models.IntegerField(default=10)
    track_expiry = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def current_stock(self):
        return StockBatch.objects.filter(product=self, remaining_quantity__gt=0).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    @property
    def status(self):
        if not self.is_active:
            return 'Inactive'
        if self.current_stock == 0:
            return 'Out of Stock'
        if self.is_low_stock:
            return 'Low Stock'
        return 'Active'

    @property
    def near_expiry_batches(self):
        if not self.track_expiry:
            return []
        from datetime import timedelta
        warning_date = timezone.now().date() + timedelta(days=7)
        return self.stock_batches.filter(
            remaining_quantity__gt=0,
            expiry_date__lte=warning_date,
            expiry_date__gte=timezone.now().date()
        )

    @property
    def expired_batches(self):
        if not self.track_expiry:
            return []
        return self.stock_batches.filter(
            remaining_quantity__gt=0,
            expiry_date__lt=timezone.now().date()
        )


class StockBatch(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='stock_batches', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_batches')
    quantity = models.IntegerField()
    remaining_quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['purchase_date', 'expiry_date']

    def __str__(self):
        return f"{self.product.name} - {self.quantity} (Remaining: {self.remaining_quantity})"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        from datetime import timedelta
        return self.expiry_date <= timezone.now().date() + timedelta(days=7)


class Sale(models.Model):
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('gcash', 'GCash'),
        ('other', 'Other'),
        ('credit_payment', 'Credit Payment'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sales', null=True, blank=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date']

    def __str__(self):
        return f"Sale #{self.id} - {self.sale_date.strftime('%Y-%m-%d %H:%M')}"


class SaleItem(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sale_items', null=True, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Purchase(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='purchases', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    supplier_name = models.CharField(max_length=200, blank=True)
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='purchases')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchase_date']

    def __str__(self):
        return f"{self.product.name} - {self.quantity} units"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Create stock batch when purchase is created
        if self.pk:
            StockBatch.objects.get_or_create(
                client=self.client,
                product=self.product,
                quantity=self.quantity,
                remaining_quantity=self.quantity,
                unit_cost=self.unit_cost,
                expiry_date=self.expiry_date,
                purchase_date=self.purchase_date,
            )


class CreditRecord(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='credit_records', null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='credit_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_name} - ₱{self.remaining_balance} ({self.status})"


class CreditItem(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='credit_items', null=True, blank=True)
    credit_record = models.ForeignKey(CreditRecord, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class CreditPayment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='credit_payments', null=True, blank=True)
    credit_record = models.ForeignKey(CreditRecord, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='credit_payments')

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"₱{self.amount} on {self.payment_date.strftime('%Y-%m-%d')}"