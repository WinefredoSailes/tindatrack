from django.shortcuts import redirect
from django.contrib import messages


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

            if not is_allowed and not request.client.is_subscription_valid:
                messages.error(request, 'Your trial has expired. Contact support to renew your subscription.')
                return redirect('logout')

        return self.get_response(request)
