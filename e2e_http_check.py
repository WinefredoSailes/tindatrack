"""Real HTTP end-to-end session test against a running server."""
import re
import sys
import requests

BASE = 'http://127.0.0.1:8765'
s = requests.Session()
failures = []

def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {name}' + (f' - {detail}' if detail and not cond else ''))
    if not cond:
        failures.append(name)

# 1. Login page loads
r = s.get(f'{BASE}/login/', timeout=10)
check('login page loads', r.status_code == 200 and 'Sign In' in r.text)

# 2. Get CSRF token from cookies
csrf = s.cookies.get('csrftoken')

# 3. Login as superuser
r = s.post(f'{BASE}/login/', data={
    'username': 'admin', 'password': 'admin123', 'csrfmiddlewaretoken': csrf,
}, headers={'Referer': f'{BASE}/login/'}, allow_redirects=False, timeout=10)
check('login redirects to dashboard', r.status_code == 302 and r.headers.get('Location', '').endswith('/'))

# 4. Dashboard loads
r = s.get(f'{BASE}/', timeout=10)
check('dashboard loads after login', r.status_code == 200 and 'Dashboard' in r.text)

# 5. POS loads
r = s.get(f'{BASE}/pos/', timeout=10)
check('pos page loads', r.status_code == 200)

# 6. Products page loads
r = s.get(f'{BASE}/products/', timeout=10)
check('products page loads', r.status_code == 200)

# 7. Credit page loads
r = s.get(f'{BASE}/credit/', timeout=10)
check('credit page loads', r.status_code == 200)

# 8. Reports page loads (owner required - admin has profile role owner)
r = s.get(f'{BASE}/reports/', timeout=10)
check('reports page loads', r.status_code == 200)

# 9. Users page loads
r = s.get(f'{BASE}/users/', timeout=10)
check('users page loads', r.status_code == 200)

# 10. Categories page loads
r = s.get(f'{BASE}/categories/', timeout=10)
check('categories page loads', r.status_code == 200)

# 11. My Subscription page loads
r = s.get(f'{BASE}/my-subscription/', timeout=10)
check('my-subscription page loads', r.status_code == 200)

# 12. Admin portal loads
r = s.get(f'{BASE}/admin-portal/', timeout=10)
check('admin portal loads', r.status_code == 200)

# 13. Clients list loads
r = s.get(f'{BASE}/clients/', timeout=10)
check('clients page loads', r.status_code == 200)

# 14. Checkout page (without PayMongo keys -> graceful fallback redirect)
r = s.get(f'{BASE}/checkout/1/', timeout=10, allow_redirects=False)
check('checkout redirects gracefully without keys', r.status_code == 302)

# 15. Register page loads
r = s.get(f'{BASE}/register/', timeout=10)
check('register page loads', r.status_code == 200)

# 16. Static files
for path in ['/static/manifest.json', '/static/sw.js']:
    r = s.get(f'{BASE}{path}', timeout=10)
    check(f'static file serves {path}', r.status_code == 200)

# 17. API products (authenticated)
r = s.get(f'{BASE}/api/products/', timeout=10)
check('api products returns json', r.status_code == 200 and r.headers.get('Content-Type', '').startswith('application/json'))

# 18. Logout works
r = s.get(f'{BASE}/logout/', timeout=10, allow_redirects=False)
check('logout works', r.status_code == 302)

# 19. After logout, dashboard requires login
r = s.get(f'{BASE}/', timeout=10, allow_redirects=False)
check('dashboard redirects when logged out', r.status_code == 302)

print()
if failures:
    print(f'RESULT: {len(failures)} FAILURES: {failures}')
    sys.exit(1)
print('RESULT: ALL 19 HTTP CHECKS PASSED')
