from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            request.client = request.user.profile.client
        else:
            request.client = None

        return self.get_response(request)


class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.client:
            allowed_paths = ['/logout/', '/login/', '/clients/']
            is_allowed = any(request.path.startswith(p) for p in allowed_paths)

            # Block expired subscriptions
            if not is_allowed and not request.client.is_subscription_valid and not request.user.is_superuser:
                messages.error(request, 'Your subscription has expired. Contact support to renew.')
                return redirect('logout')

            # Show warning 3 days before trial or payment expiry
            if not is_allowed and not request.user.is_superuser:
                if request.client.subscription_status == 'trial' and request.client.trial_end_date:
                    days_left = (request.client.trial_end_date - timezone.now().date()).days
                    if 0 < days_left <= 3:
                        messages.warning(request, f'Your trial ends in {days_left} day{"s" if days_left > 1 else ""}. Please contact support to renew.')
                elif request.client.subscription_status != 'active' and request.client.paid_until_date:
                    days_left = (request.client.paid_until_date - timezone.now().date()).days
                    if 0 < days_left <= 3:
                        messages.warning(request, f'Your subscription ends in {days_left} day{"s" if days_left > 1 else ""}. Please contact support to renew.')

        return self.get_response(request)
