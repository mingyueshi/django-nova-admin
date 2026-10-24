"""Explicit optional CAPTCHA mount with Nova's live-challenge audio guard.

Keep upstream names, patterns and GET-refresh exposure. Projects may apply
their own wrappers/filtering (for example Axes) to these patterns explicitly.
Importing this module does not mutate upstream patterns or an AdminSite.
"""
from captcha import urls as upstream_captcha_urls
from django.urls import URLPattern

from .captcha import captcha_audio


urlpatterns = [
    URLPattern(route.pattern, captcha_audio, route.default_args, route.name)
    if route.name == "captcha-audio" else route
    for route in upstream_captcha_urls.urlpatterns
]
