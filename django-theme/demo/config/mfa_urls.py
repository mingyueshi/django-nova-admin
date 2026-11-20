from django.contrib import admin

from .security_urls import urlpatterns  # noqa: F401
from host_mfa.forms import SecondFactorForm

# Keep the same Axes-protected login and CAPTCHA routes, including their order.
admin.site.login_form = SecondFactorForm
