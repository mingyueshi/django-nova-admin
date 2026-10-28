"""Enforce the bare demo's local-only boundary independently of Host headers."""
from ipaddress import ip_address

from django.conf import settings
from django.http import HttpResponseForbidden


class LoopbackOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "NOVA_DEMO_LOOPBACK_ONLY", True):
            try:
                local = ip_address(request.META.get("REMOTE_ADDR", "")).is_loopback
            except ValueError:
                local = False
            if not local:
                return HttpResponseForbidden("This demonstration accepts loopback connections only.")
        return self.get_response(request)
