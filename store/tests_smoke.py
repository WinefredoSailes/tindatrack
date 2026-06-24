"""
Smoke tests for all TindaTrack workflows.
Run: python manage.py test store.tests_smoke --verbosity=2
"""
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Client, UserProfile, Product, Category, Sale, SaleItem, StockBatch, CreditRecord, CreditItem, CreditPayment, ClientPayment, ClientLog


class SmokeTests(TestCase):
    def setUp(self):
        # Create a default client (matching setup.py behavior)
        self.client_obj = Client.objects.create(
            name='Default Store',
            subdomain='default',
            subscription_status='active',
            is_active=True,
        )

        # Create superuser
        self.superuser = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
        UserProfile.objects.create(user=self.superuser, client=self.client_obj, role='owner')

        # Create owner
        self.owner = User.objects.create_user('owner', password='owner123')
        UserProfile.objects.create(user=self.owner, client=self.client_obj, role='owner')

        # Create teller
        self.teller = User.objects.create_user('teller', password='teller123')
        UserProfile.objects.create(user=self.teller, client=self.client_obj, role='teller')

        # Create category and product
        self.category = Category.objects.create(client=self.client_obj, name='Test Category')
        self.product = Product.objects.create(
            client=self.client_obj, name='Test Product', sku='TP001',
            selling_price=100, cost_price=50, category=self.category,
            reorder_level=5, track_expiry=False
        )
        self.stock_batch = StockBatch.objects.create(
            client=self.client_obj, product=self.product,
            quantity=100, remaining_quantity=100, unit_cost=50,
            purchase_date=timezone.now().date()
        )

        self.test_client = TestClient()

    # ============ 1. LOGIN TESTS ============
    def test_login_page_loads(self):
        r = self.test_client.get(reverse('login'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sign In')

    def test_superuser_login(self):
        r = self.test_client.post(reverse('login'), {'username': 'admin', 'password': 'admin123'})
        self.assertRedirects(r, reverse('dashboard'))

    def test_owner_login(self):
        r = self.test_client.post(reverse('login'), {'username': 'owner', 'password': 'owner123'})
        self.assertRedirects(r, reverse('dashboard'))

    def test_teller_login(self):
        r = self.test_client.post(reverse('login'), {'username': 'teller', 'password': 'teller123'})
        self.assertRedirects(r, reverse('dashboard'))

    def test_invalid_login(self):
        r = self.test_client.post(reverse('login'), {'username': 'nonexist', 'password': 'wrong'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Invalid')

    def test_subscription_expired_blocks_login(self):
        self.client_obj.subscription_status = 'expired'
        self.client_obj.save()
        r = self.test_client.post(reverse('login'), {'username': 'owner', 'password': 'owner123'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'expired')

    def test_superuser_logs_in_despite_expired(self):
        self.client_obj.subscription_status = 'expired'
        self.client_obj.save()
        r = self.test_client.post(reverse('login'), {'username': 'admin', 'password': 'admin123'})
        self.assertRedirects(r, reverse('dashboard'))

    # ============ 2. DASHBOARD TESTS ============
    def test_dashboard_loads(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Dashboard')

    def test_dashboard_shows_stats(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('dashboard'))
        self.assertContains(r, "Today's Sales")
        self.assertContains(r, '₱0.00')

    # ============ 3. POS TESTS ============
    def test_pos_page_loads(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('pos'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'POS')
        self.assertContains(r, 'Test Product')

    def test_pos_pagination(self):
        self.test_client.login(username='teller', password='teller123')
        # Create 30 more products to test pagination
        for i in range(30):
            Product.objects.create(
                client=self.client_obj, name=f'Product {i}', sku=f'SKU{i:03d}',
                selling_price=10, cost_price=5, category=self.category
            )
        r = self.test_client.get(reverse('pos'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Page 1')
        self.assertContains(r, '&raquo;')

    def test_pos_search(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('pos') + '?search=Test')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Test Product')

    def test_pos_category_filter(self):
        self.test_client.login(username='teller', password='teller123')
        other_cat = Category.objects.create(client=self.client_obj, name='Other Cat')
        Product.objects.create(client=self.client_obj, name='Other Product', sku='OP001',
                               selling_price=50, cost_price=25, category=other_cat)
        r = self.test_client.get(reverse('pos') + f'?category={self.category.id}')
        self.assertContains(r, 'Test Product')
        self.assertNotContains(r, 'Other Product')

    def test_process_sale_cash(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Test Product', 'price': 100, 'quantity': 2}],
            'payment_type': 'cash',
            'customer_name': '',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])

    def test_process_sale_credit(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Test Product', 'price': 100, 'quantity': 1}],
            'payment_type': 'credit',
            'customer_name': 'Juan',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(CreditRecord.objects.filter(customer_name='Juan').exists())

    # ============ 4. PRODUCT TESTS ============
    def test_products_page_loads(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('products'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Test Product')

    def test_products_pagination(self):
        self.test_client.login(username='owner', password='owner123')
        for i in range(35):
            Product.objects.create(
                client=self.client_obj, name=f'Bulk Product {i}', sku=f'BP{i:03d}',
                selling_price=10, cost_price=5, category=self.category
            )
        r = self.test_client.get(reverse('products'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Page 1')

    def test_add_product(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.post(reverse('add_product'), {
            'name': 'New Product', 'sku': 'NP001', 'category': self.category.id,
            'selling_price': 200, 'cost_price': 100, 'reorder_level': 10,
        })
        self.assertRedirects(r, reverse('products'))
        self.assertTrue(Product.objects.filter(sku='NP001').exists())

    def test_archive_product(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('archive_product', args=[self.product.id]))
        self.assertRedirects(r, reverse('products'))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_unarchive_product(self):
        self.product.is_active = False
        self.product.save()
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('unarchive_product', args=[self.product.id]))
        self.assertRedirects(r, reverse('products'))
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    # ============ 5. CREDIT TESTS ============
    def test_credit_page_loads(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('credit_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Credit')

    def test_credit_add_payment(self):
        self.test_client.login(username='owner', password='owner123')
        cr = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=500, remaining_balance=500, status='unpaid'
        )
        CreditItem.objects.create(client=self.client_obj, credit_record=cr,
                                  product=self.product, quantity=1, unit_price=500, subtotal=500)
        r = self.test_client.post(reverse('credit_add_payment', args=[cr.id]), {
            'amount': 500, 'payment_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('credit_list'))
        cr.refresh_from_db()
        self.assertEqual(cr.remaining_balance, 0)
        self.assertEqual(cr.status, 'paid')

    # ============ 6. CLIENT MANAGEMENT TESTS ============
    def test_client_list_superuser_only(self):
        # Owner cannot access
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('client_list'))
        self.assertRedirects(r, reverse('dashboard'))

        # Superuser can access
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.get(reverse('client_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Default Store')

    def test_add_client(self):
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.post(reverse('client_add'), {
            'name': 'New Store', 'subdomain': 'newstore',
            'subscription_status': 'trial', 'trial_days': 15,
        })
        self.assertRedirects(r, reverse('client_list'))
        self.assertTrue(Client.objects.filter(subdomain='newstore').exists())

    def test_client_detail(self):
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.get(reverse('client_detail', args=[self.client_obj.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Default Store')
        self.assertContains(r, 'Client Info')

    def test_client_edit(self):
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.post(reverse('client_edit', args=[self.client_obj.id]), {
            'name': 'Updated Store', 'subdomain': 'default',
            'subscription_status': 'active', 'is_active': 'on',
        })
        self.assertRedirects(r, reverse('client_list'))
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.name, 'Updated Store')

    def test_record_payment(self):
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.post(reverse('record_payment', args=[self.client_obj.id]), {
            'amount': 500, 'payment_method': 'gcash',
            'reference': 'REF001', 'paid_until': '2026-12-31',
            'notes': 'Test payment',
        })
        self.assertRedirects(r, reverse('client_detail', args=[self.client_obj.id]))
        self.assertTrue(ClientPayment.objects.filter(reference='REF001').exists())
        self.client_obj.refresh_from_db()
        self.assertIsNotNone(self.client_obj.paid_until_date)
        self.assertTrue(ClientLog.objects.filter(client=self.client_obj).exists())

    def test_admin_dashboard(self):
        self.test_client.login(username='admin', password='admin123')
        r = self.test_client.get(reverse('admin_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Admin Portal')

    def test_admin_dashboard_blocks_owner(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('admin_dashboard'))
        self.assertRedirects(r, reverse('dashboard'))

    # ============ 7. ACCESS CONTROL TESTS ============
    def test_teller_cannot_access_categories(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('categories'))
        self.assertRedirects(r, reverse('dashboard'))

    def test_teller_cannot_access_stock_in(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('purchase'))
        self.assertRedirects(r, reverse('dashboard'))

    def test_teller_cannot_access_reports(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('reports'))
        self.assertRedirects(r, reverse('dashboard'))

    def test_teller_cannot_access_users(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('users'))
        self.assertRedirects(r, reverse('dashboard'))

    def test_teller_can_access_pos(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('pos'))
        self.assertEqual(r.status_code, 200)

    def test_teller_can_access_products(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('products'))
        self.assertEqual(r.status_code, 200)

    def test_teller_can_access_credit(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('credit_list'))
        self.assertEqual(r.status_code, 200)

    # ============ 8. SUBSCRIPTION MIDDLEWARE ============
    def test_expired_subscription_blocked(self):
        self.client_obj.subscription_status = 'expired'
        self.client_obj.save()
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('products'))
        self.assertRedirects(r, reverse('logout'), target_status_code=302)

    def test_active_subscription_allowed(self):
        self.client_obj.subscription_status = 'active'
        self.client_obj.save()
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('products'))
        self.assertEqual(r.status_code, 200)

    def test_paid_until_date_considered_valid(self):
        self.client_obj.subscription_status = 'expired'
        self.client_obj.paid_until_date = timezone.now().date() + timedelta(days=10)
        self.client_obj.save()
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('products'))
        self.assertEqual(r.status_code, 200)

    # ============ 9. DATA ISOLATION ============
    def test_client_data_isolation(self):
        # Create another client with its own product
        other_client = Client.objects.create(name='Other Store', subdomain='other')
        other_cat = Category.objects.create(client=other_client, name='Other Cat')
        Product.objects.create(client=other_client, name='Other Product', sku='OTH001',
                               selling_price=999, cost_price=500, category=other_cat)

        # Owner from default store should not see other store's products
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('products'))
        self.assertContains(r, 'Test Product')
        self.assertNotContains(r, 'Other Product')

    # ============ 10. REPORTS ============
    def test_reports_page_loads(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('reports'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Reports')

    # ============ 11. API ============
    def test_api_products(self):
        self.test_client.login(username='teller', password='teller123')
        r = self.test_client.get(reverse('api_products'))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Test Product')

    # ============ 12. PURCHASE ============
    def test_purchase_page_loads(self):
        self.test_client.login(username='owner', password='owner123')
        r = self.test_client.get(reverse('purchase'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Stock In')
