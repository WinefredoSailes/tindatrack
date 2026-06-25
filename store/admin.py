from django.contrib import admin
from .models import Category, Product, StockBatch, Sale, SaleItem, Purchase, UserProfile, SubscriptionPlan, ClientPayment

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    search_fields = ['user__username']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'selling_price', 'current_stock', 'is_active']
    list_filter = ['is_active', 'category', 'track_expiry']
    search_fields = ['name', 'sku']

@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'remaining_quantity', 'expiry_date', 'purchase_date']
    list_filter = ['expiry_date']
    search_fields = ['product__name']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale_date', 'total_amount', 'payment_type', 'created_by']
    list_filter = ['sale_date', 'payment_type']
    date_hierarchy = 'sale_date'

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'subtotal']
    search_fields = ['product__name', 'sale__id']

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'unit_cost', 'purchase_date', 'supplier_name']
    list_filter = ['purchase_date']
    search_fields = ['product__name', 'supplier_name']

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'is_active']
    list_filter = ['is_active']

@admin.register(ClientPayment)
class ClientPaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'plan', 'amount', 'payment_method', 'paid_until', 'created_at']
    list_filter = ['payment_method', 'created_at']
    search_fields = ['client__name', 'reference']