"""
End-to-end workflow tests for TindaTrack.
Covers: registration, subscription lifecycle, PayMongo checkout/webhook,
purchase stock batches, FIFO sales, reports, categories, users, credit delete,
client edit logging, and PWA static files.
Run: python manage.py test store.tests_e2e --verbosity=2
"""
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import (Client, UserProfile, Product, Category, Sale, SaleItem,
                     StockBatch, Purchase, CreditRecord, CreditItem, CreditPayment,
                     ClientPayment, ClientLog, SubscriptionPlan)


class E2ETests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name='Default Store', subdomain='default',
            subscription_status='active', is_active=True,
        )
        self.superuser = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
        UserProfile.objects.create(user=self.superuser, client=self.client_obj, role='owner')

        self.owner = User.objects.create_user('owner', password='owner123')
        UserProfile.objects.create(user=self.owner, client=self.client_obj, role='owner')

        self.teller = User.objects.create_user('teller', password='teller123')
        UserProfile.objects.create(user=self.teller, client=self.client_obj, role='teller')

        self.category = Category.objects.create(client=self.client_obj, name='Snacks')
        self.product = Product.objects.create(
            client=self.client_obj, name='Chips', sku='CH001',
            selling_price=100, cost_price=50, category=self.category,
            reorder_level=5, track_expiry=False,
        )
        self.stock_batch = StockBatch.objects.create(
            client=self.client_obj, product=self.product,
            quantity=100, remaining_quantity=100, unit_cost=50,
            purchase_date=timezone.now().date(),
        )
        self.monthly = SubscriptionPlan.objects.create(
            name='Monthly', price=299, duration_days=30, is_active=True,
        )
        self.annual = SubscriptionPlan.objects.create(
            name='Annual', price=2999, duration_days=365, is_active=True,
        )
        self.test_client = TestClient()

    def login(self, username='owner', password='owner123'):
        self.assertTrue(self.test_client.login(username=username, password=password))

    # ============ 1. SELF-SERVICE REGISTRATION ============
    def test_register_page_loads(self):
        r = self.test_client.get(reverse('register'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Start Free Trial')

    def test_register_creates_client_with_60day_trial(self):
        r = self.test_client.post(reverse('register'), {
            'store_name': 'Maria Store',
            'username': 'maria',
            'password': 'secret123',
            'confirm_password': 'secret123',
        })
        # Should auto-login and redirect to dashboard
        self.assertRedirects(r, reverse('dashboard'))

        client = Client.objects.get(subdomain='maria')
        self.assertEqual(client.name, 'Maria Store')
        self.assertEqual(client.subscription_status, 'trial')
        self.assertEqual(client.monthly_rate, 299)
        expected_end = timezone.now().date() + timedelta(days=60)
        self.assertEqual(client.trial_end_date, expected_end)

        user = User.objects.get(username='maria')
        self.assertTrue(user.profile.client == client)
        self.assertTrue(user.profile.is_owner)

        # User is actually logged in and can access dashboard
        r = self.test_client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_register_duplicate_username(self):
        r = self.test_client.post(reverse('register'), {
            'store_name': 'Dup Store',
            'username': 'owner',
            'password': 'secret123',
            'confirm_password': 'secret123',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already taken')
        self.assertFalse(Client.objects.filter(subdomain='owner').exists())

    def test_register_password_mismatch(self):
        r = self.test_client.post(reverse('register'), {
            'store_name': 'Mismatch Store',
            'username': 'mismatch',
            'password': 'secret123',
            'confirm_password': 'different99',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'do not match')

    def test_register_short_password(self):
        r = self.test_client.post(reverse('register'), {
            'store_name': 'Short Store',
            'username': 'shorty',
            'password': 'abc',
            'confirm_password': 'abc',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'at least 6')

    def test_register_redirects_if_logged_in(self):
        self.login('admin', 'admin123')
        r = self.test_client.get(reverse('register'))
        self.assertRedirects(r, reverse('dashboard'))

    # ============ 2. SUBSCRIPTION LIFE CYCLE ============
    def test_my_subscription_page(self):
        # Non-active client sees plan options
        self.client_obj.subscription_status = 'expired'
        self.client_obj.save()
        self.login('admin', 'admin123')
        r = self.test_client.get(reverse('my_subscription'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'My Subscription')
        self.assertContains(r, 'Monthly')
        self.assertContains(r, 'Annual')

    def test_expired_client_can_still_access_subscription_and_checkout(self):
        # Expired client must be able to reach renewal pages (not blocked by middleware)
        self.client_obj.subscription_status = 'expired'
        self.client_obj.save()
        self.login('owner', 'owner123')

        r = self.test_client.get(reverse('my_subscription'))
        self.assertEqual(r.status_code, 200)

        # Checkout without PayMongo keys configured: graceful fallback
        r = self.test_client.get(reverse('checkout', args=[self.monthly.id]))
        self.assertRedirects(r, reverse('my_subscription'))

    def test_checkout_success_activates_and_extends_from_today(self):
        self.login('owner', 'owner123')
        self.client_obj.subscription_status = 'trial'
        self.client_obj.trial_end_date = timezone.now().date() + timedelta(days=10)
        self.client_obj.paid_until_date = None
        self.client_obj.save()

        r = self.test_client.get(reverse('checkout_success', args=[self.monthly.id]))
        self.assertRedirects(r, reverse('my_subscription'))

        self.client_obj.refresh_from_db()
        expected = timezone.now().date() + timedelta(days=30)
        self.assertEqual(self.client_obj.subscription_status, 'active')
        self.assertEqual(self.client_obj.paid_until_date, expected)
        self.assertTrue(ClientPayment.objects.filter(client=self.client_obj, plan=self.monthly).exists())
        self.assertTrue(ClientLog.objects.filter(client=self.client_obj, action__contains='Auto-payment').exists())

    def test_checkout_success_stacks_on_existing_coverage(self):
        self.login('owner', 'owner123')
        base = timezone.now().date() + timedelta(days=20)
        self.client_obj.paid_until_date = base
        self.client_obj.save()

        self.test_client.get(reverse('checkout_success', args=[self.monthly.id]))
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.paid_until_date, base + timedelta(days=30))

    def test_checkout_success_invalid_plan(self):
        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('checkout_success', args=[9999]))
        self.assertEqual(r.status_code, 404)

    # ============ 3. PAYMONGO WEBHOOK ============
    def _webhook_payload(self, status='paid'):
        return {
            'data': {
                'id': 'evt_test',
                'type': 'event',
                'attributes': {
                    'type': 'checkout_session.payment.paid',
                    'data': {
                        'id': 'cs_test123',
                        'type': 'checkout_session',
                        'attributes': {
                            'status': status,
                            'payments': [{'id': 'pay_test123'}],
                            'line_items': [{
                                'description': f'Monthly subscription for Default Store (client#{self.client_obj.id} plan#{self.monthly.id})',
                            }],
                        },
                    },
                },
            }
        }

    def test_webhook_rejects_non_post(self):
        r = self.test_client.get(reverse('paymongo_webhook'))
        self.assertEqual(r.status_code, 405)

    def test_webhook_processes_paid_payment(self):
        self.client_obj.subscription_status = 'expired'
        self.client_obj.paid_until_date = timezone.now().date() - timedelta(days=5)
        self.client_obj.save()

        r = self.test_client.post(
            reverse('paymongo_webhook'),
            data=self._webhook_payload(),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)

        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.subscription_status, 'active')
        today = timezone.now().date()
        # Original paid_until (5 days ago) is before today, so coverage extends from today
        self.assertEqual(self.client_obj.paid_until_date, today + timedelta(days=30))

        payment = ClientPayment.objects.filter(client=self.client_obj, plan=self.monthly).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.reference, 'PayMongo-cs_test123')
        self.assertTrue(ClientLog.objects.filter(client=self.client_obj).exists())

    def test_webhook_ignores_non_paid_events(self):
        r = self.test_client.post(
            reverse('paymongo_webhook'),
            data=self._webhook_payload(status='pending'),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ClientPayment.objects.filter(client=self.client_obj).exists())

    def test_webhook_rejects_invalid_signature(self):
        from django.test import override_settings
        with override_settings(PAYMONGO_WEBHOOK_SECRET='test-secret'):
            r = self.test_client.post(
                reverse('paymongo_webhook'),
                data=self._webhook_payload(),
                content_type='application/json',
                HTTP_PAYMONGO_SIGNATURE='wrong-signature',
            )
            self.assertEqual(r.status_code, 401)
            self.assertFalse(ClientPayment.objects.filter(client=self.client_obj).exists())

    def test_webhook_accepts_valid_signature(self):
        import hashlib
        from django.test import override_settings
        payload = self._webhook_payload()
        with override_settings(PAYMONGO_WEBHOOK_SECRET='test-secret'):
            body = str(payload).encode('utf-8')
            # Verify against the raw request body format used by PayMongo
            import json as jsonlib
            body = jsonlib.dumps(payload).encode('utf-8')
            expected = hashlib.sha256(body + b'test-secret').hexdigest()
            r = self.test_client.post(
                reverse('paymongo_webhook'),
                data=body,
                content_type='application/json',
                HTTP_PAYMONGO_SIGNATURE=expected,
            )
            self.assertEqual(r.status_code, 200)
            self.assertTrue(ClientPayment.objects.filter(client=self.client_obj).exists())

    def test_webhook_bad_json(self):
        r = self.test_client.post(
            reverse('paymongo_webhook'),
            data='not-json{{{',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    # ============ 4. PURCHASE / STOCK ============
    def test_purchase_creates_stock_batch(self):
        self.login('owner', 'owner123')
        before = self.product.current_stock
        r = self.test_client.post(reverse('purchase'), {
            'product': self.product.id,
            'quantity': 50,
            'unit_cost': 60,
            'purchase_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('purchase'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, before + 50)

        batch = StockBatch.objects.filter(product=self.product, quantity=50).first()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.remaining_quantity, 50)
        self.assertEqual(batch.unit_cost, 60)
        self.assertTrue(Purchase.objects.filter(product=self.product, quantity=50).exists())

    def test_purchase_save_does_not_duplicate_batch(self):
        # Regression test: saving a purchase twice must not create 2 batches
        self.login('owner', 'owner123')
        r = self.test_client.post(reverse('purchase'), {
            'product': self.product.id,
            'quantity': 30,
            'unit_cost': 55,
            'purchase_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('purchase'))

        purchase = Purchase.objects.get(product=self.product, quantity=30)
        purchase.unit_cost = 58
        purchase.save()

        batches = StockBatch.objects.filter(product=self.product, quantity=30)
        self.assertEqual(batches.count(), 1)

    def test_purchase_saves_expiry_date(self):
        self.login('owner', 'owner123')
        expiry = timezone.now().date() + timedelta(days=30)
        self.test_client.post(reverse('purchase'), {
            'product': self.product.id,
            'quantity': 10,
            'unit_cost': 55,
            'purchase_date': timezone.now().date().isoformat(),
            'expiry_date': expiry.isoformat(),
        })
        batch = StockBatch.objects.get(product=self.product, quantity=10)
        self.assertEqual(batch.expiry_date, expiry)

    # ============ 5. FIFO SALE WITH MULTIPLE BATCHES ============
    def test_sale_deducts_oldest_batch_first(self):
        self.login('teller', 'teller123')
        # Newer batch
        new_batch = StockBatch.objects.create(
            client=self.client_obj, product=self.product,
            quantity=100, remaining_quantity=100, unit_cost=60,
            purchase_date=timezone.now().date() + timedelta(days=10),
        )
        # Old batch has 10 remaining
        self.stock_batch.remaining_quantity = 10
        self.stock_batch.save()

        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 25}],
            'payment_type': 'cash',
            'customer_name': '',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

        self.stock_batch.refresh_from_db()
        new_batch.refresh_from_db()
        self.assertEqual(self.stock_batch.remaining_quantity, 0)   # oldest used first
        self.assertEqual(new_batch.remaining_quantity, 85)

    def test_sale_skips_expired_batches(self):
        self.login('teller', 'teller123')
        expired = StockBatch.objects.create(
            client=self.client_obj, product=self.product,
            quantity=50, remaining_quantity=50, unit_cost=40,
            purchase_date=timezone.now().date() - timedelta(days=100),
            expiry_date=timezone.now().date() - timedelta(days=1),
        )
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 20}],
            'payment_type': 'cash',
            'customer_name': '',
        }, content_type='application/json')
        self.assertTrue(r.json()['success'])

        expired.refresh_from_db()
        self.stock_batch.refresh_from_db()
        self.assertEqual(expired.remaining_quantity, 50)  # untouched
        self.assertEqual(self.stock_batch.remaining_quantity, 80)

    def test_sale_saleitem_created_with_correct_prices(self):
        self.login('teller', 'teller123')
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 3}],
            'payment_type': 'cash',
            'customer_name': '',
        }, content_type='application/json')
        self.assertTrue(r.json()['success'])

        sale = Sale.objects.get(client=self.client_obj)
        self.assertEqual(sale.total_amount, 300)
        item = SaleItem.objects.get(sale=sale)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_price, 100)
        self.assertEqual(item.subtotal, 300)

    def test_sale_requires_items(self):
        self.login('teller', 'teller123')
        r = self.test_client.post(reverse('process_sale'), {
            'items': [], 'payment_type': 'cash', 'customer_name': '',
        }, content_type='application/json')
        self.assertFalse(r.json()['success'])

    def test_credit_sale_requires_customer_name(self):
        self.login('teller', 'teller123')
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 1}],
            'payment_type': 'credit',
            'customer_name': '',
        }, content_type='application/json')
        self.assertFalse(r.json()['success'])
        self.assertFalse(CreditRecord.objects.exists())

    def test_credit_sale_merges_into_existing_record(self):
        self.login('teller', 'teller123')
        credit = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=100, remaining_balance=100, status='unpaid',
        )
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 1}],
            'payment_type': 'credit',
            'customer_name': 'juan',
        }, content_type='application/json')
        self.assertTrue(r.json()['success'])
        self.assertContains(r, 'Added to existing credit')

        credit.refresh_from_db()
        self.assertEqual(credit.remaining_balance, 200)
        self.assertEqual(CreditRecord.objects.count(), 1)

    # ============ 6. REPORTS ============
    def test_daily_report_shows_sales(self):
        self.login('owner', 'owner123')
        sale = Sale.objects.create(
            client=self.client_obj, total_amount=300,
            payment_type='cash', created_by=self.owner,
        )
        SaleItem.objects.create(
            client=self.client_obj, sale=sale, product=self.product,
            quantity=3, unit_price=100, subtotal=300,
        )
        r = self.test_client.get(reverse('reports') + '?type=daily')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '₱300.00')
        self.assertContains(r, 'Chips')

    def test_monthly_report_loads(self):
        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('reports') + '?type=monthly')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Monthly')

    def test_reports_requires_owner(self):
        self.login('teller', 'teller123')
        r = self.test_client.get(reverse('reports'))
        self.assertRedirects(r, reverse('dashboard'))

    # ============ 7. CATEGORIES ============
    def test_add_category(self):
        self.login('owner', 'owner123')
        r = self.test_client.post(reverse('add_category'), {'name': 'Frozen'})
        self.assertRedirects(r, reverse('categories'))
        self.assertTrue(Category.objects.filter(client=self.client_obj, name='Frozen').exists())

    def test_edit_category(self):
        self.login('owner', 'owner123')
        r = self.test_client.post(reverse('edit_category', args=[self.category.id]), {'name': 'Snacks & Candies'})
        self.assertRedirects(r, reverse('categories'))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Snacks & Candies')

    def test_teller_cannot_edit_category(self):
        self.login('teller', 'teller123')
        r = self.test_client.get(reverse('edit_category', args=[self.category.id]))
        self.assertRedirects(r, reverse('dashboard'))

    # ============ 8. USER MANAGEMENT ============
    def test_add_user_owner(self):
        self.login('owner', 'owner123')
        r = self.test_client.post(reverse('add_user'), {
            'username': 'newcashier',
            'password': 'cashier123',
            'role': 'teller',
        })
        self.assertRedirects(r, reverse('users'))
        user = User.objects.get(username='newcashier')
        self.assertEqual(user.profile.client, self.client_obj)
        self.assertTrue(user.profile.is_teller)

    def test_edit_user_role(self):
        self.login('owner', 'owner123')
        r = self.test_client.post(reverse('edit_user', args=[self.teller.id]), {
            'username': 'teller',
            'first_name': '',
            'last_name': '',
            'email': '',
            'role': 'owner',
        })
        self.assertRedirects(r, reverse('users'))
        self.teller.refresh_from_db()
        self.assertTrue(self.teller.profile.is_owner)

    def test_deactivate_self_blocked(self):
        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('deactivate_user', args=[self.owner.id]))
        self.assertRedirects(r, reverse('users'))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_deactivate_teller(self):
        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('deactivate_user', args=[self.teller.id]))
        self.assertRedirects(r, reverse('users'))
        self.teller.refresh_from_db()
        self.assertFalse(self.teller.is_active)

        # Deactivated user cannot login
        self.test_client.logout()
        r = self.test_client.post(reverse('login'), {'username': 'teller', 'password': 'teller123'})
        self.assertEqual(r.status_code, 200)

    def test_activate_teller(self):
        self.teller.is_active = False
        self.teller.save()
        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('activate_user', args=[self.teller.id]))
        self.assertRedirects(r, reverse('users'))
        self.teller.refresh_from_db()
        self.assertTrue(self.teller.is_active)

    # ============ 9. CLIENT MANAGEMENT ============
    def test_client_edit_logs_changes(self):
        self.login('admin', 'admin123')
        before_logs = ClientLog.objects.count()
        r = self.test_client.post(reverse('client_edit', args=[self.client_obj.id]), {
            'name': 'Default Store',
            'subdomain': 'default',
            'subscription_status': 'locked',
            'is_active': 'on',
            'monthly_rate': '299',
            'trial_days': '15',
            'notes': '',
        })
        self.assertRedirects(r, reverse('client_list'))
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.subscription_status, 'locked')
        self.assertTrue(ClientLog.objects.count() > before_logs)

    def test_client_edit_trial_sets_trial_end(self):
        self.login('admin', 'admin123')
        r = self.test_client.post(reverse('client_edit', args=[self.client_obj.id]), {
            'name': 'Default Store',
            'subdomain': 'default',
            'subscription_status': 'trial',
            'is_active': 'on',
            'monthly_rate': '299',
            'trial_days': '15',
            'notes': '',
        })
        self.assertRedirects(r, reverse('client_list'))
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.trial_end_date, timezone.now().date() + timedelta(days=15))

    def test_record_payment_with_plan(self):
        self.login('admin', 'admin123')
        r = self.test_client.post(reverse('record_payment', args=[self.client_obj.id]), {
            'amount': '299',
            'payment_method': 'gcash',
            'reference': 'GCSH-REF-001',
            'plan_id': self.monthly.id,
            'paid_until': (timezone.now().date() + timedelta(days=30)).isoformat(),
            'notes': 'Monthly payment',
        })
        self.assertRedirects(r, reverse('client_detail', args=[self.client_obj.id]))
        payment = ClientPayment.objects.get(reference='GCSH-REF-001')
        self.assertEqual(payment.plan, self.monthly)
        self.assertEqual(payment.amount, 299)

    def test_record_payment_autofills_paid_until_from_plan(self):
        self.login('admin', 'admin123')
        r = self.test_client.post(reverse('record_payment', args=[self.client_obj.id]), {
            'amount': '299',
            'payment_method': 'gcash',
            'reference': 'GCSH-REF-002',
            'plan_id': self.monthly.id,
            'notes': '',
        })
        self.assertRedirects(r, reverse('client_detail', args=[self.client_obj.id]))
        payment = ClientPayment.objects.get(reference='GCSH-REF-002')
        self.assertEqual(payment.paid_until, timezone.now().date() + timedelta(days=30))

    # ============ 10. CREDIT DELETE ============
    def test_unpaid_credit_cannot_be_deleted(self):
        self.login('owner', 'owner123')
        credit = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=500, remaining_balance=500, status='unpaid',
        )
        r = self.test_client.get(reverse('credit_delete', args=[credit.id]))
        self.assertRedirects(r, reverse('reports'))
        self.assertTrue(CreditRecord.objects.filter(pk=credit.id).exists())

    def test_paid_credit_can_be_deleted(self):
        self.login('owner', 'owner123')
        credit = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=500, remaining_balance=0, status='paid',
        )
        r = self.test_client.get(reverse('credit_delete', args=[credit.id]))
        self.assertRedirects(r, reverse('reports'))
        self.assertFalse(CreditRecord.objects.filter(pk=credit.id).exists())

    # ============ 11. PWA STATIC FILES ============
    def test_manifest_exists(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / 'static' / 'manifest.json'
        self.assertTrue(p.exists())
        content = p.read_text(encoding='utf-8')
        self.assertIn('short_name', content)
        self.assertIn('TindaTrack', content)

    def test_service_worker_exists(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / 'static' / 'sw.js'
        self.assertTrue(p.exists())
        content = p.read_text(encoding='utf-8')
        self.assertIn('addEventListener', content)
        self.assertIn('caches', content)

    def test_icons_exist(self):
        from pathlib import Path
        base = Path(__file__).resolve().parent.parent / 'static' / 'icons'
        self.assertTrue((base / 'icon-192.png').exists())
        self.assertTrue((base / 'icon-512.png').exists())

    # ============ 12. CREDIT PAYMENT VALIDATION ============
    def test_credit_payment_validation(self):
        self.login('owner', 'owner123')
        credit = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=500, remaining_balance=500, status='unpaid',
        )
        # Amount exceeding balance rejected
        r = self.test_client.post(reverse('credit_add_payment', args=[credit.id]), {
            'amount': '600', 'payment_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('credit_list'))
        credit.refresh_from_db()
        self.assertEqual(credit.remaining_balance, 500)

        # Empty amount rejected
        r = self.test_client.post(reverse('credit_add_payment', args=[credit.id]), {
            'amount': '', 'payment_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('credit_list'))
        credit.refresh_from_db()
        self.assertEqual(credit.remaining_balance, 500)

        # Non-numeric rejected
        r = self.test_client.post(reverse('credit_add_payment', args=[credit.id]), {
            'amount': 'abc', 'payment_date': timezone.now().date().isoformat(),
        })
        self.assertRedirects(r, reverse('credit_list'))
        credit.refresh_from_db()
        self.assertEqual(credit.remaining_balance, 500)

    def test_credit_payment_does_not_create_fake_sale(self):
        self.login('owner', 'owner123')
        credit = CreditRecord.objects.create(
            client=self.client_obj, customer_name='Juan',
            total_amount=500, remaining_balance=500, status='unpaid',
        )
        self.test_client.post(reverse('credit_add_payment', args=[credit.id]), {
            'amount': '200', 'payment_date': timezone.now().date().isoformat(),
        })
        self.assertEqual(Sale.objects.count(), 0)

    # ============ 13. DATA ISOLATION ============
    def test_user_edit_isolated_to_own_client(self):
        other = Client.objects.create(name='Other Store', subdomain='other')
        other_user = User.objects.create_user('otheruser', password='other123')
        UserProfile.objects.create(user=other_user, client=other, role='teller')

        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('edit_user', args=[other_user.id]))
        self.assertEqual(r.status_code, 404)

    def test_category_edit_isolated_to_own_client(self):
        other = Client.objects.create(name='Other Store', subdomain='other')
        other_cat = Category.objects.create(client=other, name='Other Cat')

        self.login('owner', 'owner123')
        r = self.test_client.get(reverse('edit_category', args=[other_cat.id]))
        self.assertEqual(r.status_code, 404)

    # ============ 14. FULL DAY WORKFLOW ============
    def test_full_day_workflow(self):
        """A complete day: stock in -> sell cash -> sell credit -> collect credit payment -> verify reports."""
        self.login('owner', 'owner123')

        # 1. Stock in 50 units
        self.test_client.post(reverse('purchase'), {
            'product': self.product.id, 'quantity': 50, 'unit_cost': 60,
            'purchase_date': timezone.now().date().isoformat(),
        })
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 150)

        # 2. Cash sale of 10 units
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 10}],
            'payment_type': 'cash', 'customer_name': '',
        }, content_type='application/json')
        self.assertTrue(r.json()['success'])

        # 3. Credit sale of 5 units to Juan
        r = self.test_client.post(reverse('process_sale'), {
            'items': [{'product_id': self.product.id, 'name': 'Chips', 'price': 100, 'quantity': 5}],
            'payment_type': 'credit', 'customer_name': 'Juan',
        }, content_type='application/json')
        self.assertTrue(r.json()['success'])
        credit = CreditRecord.objects.get(customer_name='Juan')
        self.assertEqual(credit.remaining_balance, 500)

        # 4. Juan pays 300
        self.test_client.post(reverse('credit_add_payment', args=[credit.id]), {
            'amount': '300', 'payment_date': timezone.now().date().isoformat(),
        })
        credit.refresh_from_db()
        self.assertEqual(credit.remaining_balance, 200)
        self.assertEqual(credit.status, 'partial')

        # 5. Verify stock and reports
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 135)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Sale.objects.get().total_amount, 1000)
        self.assertEqual(CreditPayment.objects.get().amount, 300)

        r = self.test_client.get(reverse('reports') + '?type=daily')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '₱1000.00')

        # 6. Dashboard shows today's numbers
        r = self.test_client.get(reverse('dashboard'))
        self.assertContains(r, '₱1000.00')
