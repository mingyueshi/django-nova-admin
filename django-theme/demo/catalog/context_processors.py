"""Demo-owned preferences. They do not change reusable Nova defaults."""
from django.conf import settings
from django.apps import apps


def project_admin(request):
    return {
        "project_admin_compact": bool(getattr(settings, "PROJECT_ADMIN_COMPACT", False)),
        "project_nova_installed": apps.is_installed("nova_admin"),
    }
