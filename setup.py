import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tindatrack.settings')
django.setup()

from django.contrib.auth.models import User
from store.models import UserProfile

# Create superuser if not exists
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123'
    )
    UserProfile.objects.create(user=user, role='owner')
    print('Created admin user (owner)')
else:
    user = User.objects.get(username='admin')
    if not hasattr(user, 'profile'):
        UserProfile.objects.create(user=user, role='owner')
    print('Admin user already exists')

# Create default categories
from store.models import Category
categories = ['Drinks', 'Snacks', 'Toiletries', 'Home Essentials', 'Other']
for name in categories:
    Category.objects.get_or_create(name=name)
print('Created default categories')