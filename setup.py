import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tindatrack.settings')
django.setup()

from django.contrib.auth.models import User
from store.models import UserProfile, Client, Category, Product, StockBatch, Sale, SaleItem, Purchase, CreditRecord, CreditItem, CreditPayment, SubscriptionPlan

# Create default client if not exists
default_client, created = Client.objects.get_or_create(
    subdomain='default',
    defaults={'name': 'Default Store', 'subscription_status': 'active'}
)
if created:
    print('Created default client')
else:
    print('Default client already exists')

# Assign existing records to default client if they have no client
models_to_update = [Category, Product, StockBatch, Sale, SaleItem, Purchase, CreditRecord, CreditItem, CreditPayment]
for model in models_to_update:
    count = model.objects.filter(client__isnull=True).update(client=default_client)
    if count:
        print(f'Assigned {count} {model.__name__} records to default client')

# Assign existing user profiles to default client
profile_count = UserProfile.objects.filter(client__isnull=True).update(client=default_client)
if profile_count:
    print(f'Assigned {profile_count} user profiles to default client')

# Create superuser if not exists
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123'
    )
    UserProfile.objects.create(user=user, role='owner', client=default_client)
    print('Created admin user (owner)')
else:
    user = User.objects.get(username='admin')
    if not hasattr(user, 'profile'):
        UserProfile.objects.create(user=user, role='owner', client=default_client)
    else:
        # Ensure existing admin has a client
        profile = user.profile
        if not profile.client:
            profile.client = default_client
            profile.save()
    print('Admin user already exists')

# Seed subscription plans
monthly, created = SubscriptionPlan.objects.get_or_create(
    name='Monthly', defaults={'price': 299, 'duration_days': 30}
)
if created:
    print('Created Monthly plan (299/30d)')
annual, created = SubscriptionPlan.objects.get_or_create(
    name='Annual', defaults={'price': 2999, 'duration_days': 365}
)
if created:
    print('Created Annual plan (2999/365d)')

# Create default categories if none exist
if not Category.objects.filter(client=default_client).exists():
    categories = ['Drinks', 'Snacks', 'Toiletries', 'Home Essentials', 'Other']
    for name in categories:
        Category.objects.get_or_create(name=name, client=default_client)
    print('Created default categories')
else:
    print('Categories already exist')