"""
PayMongo integration for subscription payments.
Replace SECRET_KEY with your live key when ready.
"""
import json
import hmac
import hashlib
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import requests


def create_checkout_session(client, plan, success_url, cancel_url):
    payload = {
        'data': {
            'attributes': {
                'billing': {
                    'name': client.name,
                    'email': '',
                },
                'line_items': [{
                    'currency': 'PHP',
                    'amount': int(plan.price * 100),
                    'name': f'TindaTrack - {plan.name}',
                    'quantity': 1,
                }],
                'payment_method_types': ['gcash', 'card', 'paymaya'],
                'success_url': success_url,
                'cancel_url': cancel_url,
                'description': f'{plan.name} subscription for {client.name} (plan #{plan.id})',
            }
        }
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    if settings.PAYMONGO_SECRET_KEY:
        headers['Authorization'] = f'Basic {settings.PAYMONGO_SECRET_KEY}'

    try:
        r = requests.post(
            'https://api.paymongo.com/v1/checkout_sessions',
            json=payload,
            headers=headers,
            timeout=30,
        )
        if r.status_code in (200, 201):
            data = r.json()
            checkout_url = data['data']['attributes']['checkout_url']
            session_id = data['data']['id']
            return checkout_url, session_id
        else:
            print(f'PayMongo error: {r.status_code} {r.text}')
            return None, None
    except Exception as e:
        print(f'PayMongo exception: {e}')
        return None, None


def verify_webhook_signature(payload, signature):
    if not settings.PAYMONGO_WEBHOOK_SECRET:
        return True
    expected = hashlib.sha256(
        (payload + settings.PAYMONGO_WEBHOOK_SECRET).encode()
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
