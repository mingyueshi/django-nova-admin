from django.apps import AppConfig


class NovaAdminConfig(AppConfig):
    name = "nova_admin"
    verbose_name = "Nova Admin theme"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import checks  # noqa: F401 — register Django system checks.
