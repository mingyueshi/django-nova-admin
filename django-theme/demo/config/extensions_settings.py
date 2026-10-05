"""Optional local example: branding + permission-filtered navigation extensions."""
from .settings import *  # noqa: F403

NOVA_ADMIN_BRANDING = {
    "logo": "catalog/brand/logo.svg",
    "logo_alt": "NOVA",
    "favicon": "catalog/brand/favicon.svg",
    "login_background": "catalog/brand/login-background.svg",
    "footer": "NOVA · 本地演示",
}
NOVA_ADMIN_NAV_FAVORITES = True
NOVA_ADMIN_NAV_COMMON_MODELS = ["catalog.product", "catalog.newsitem"]
NOVA_ADMIN_NAV_ICONS = {
    "catalog": "folder", "catalog.product": "box", "catalog.newsitem": "file",
    "catalog.memberprofile": "users", "auth": "settings",
}
# Badge provider deliberately remains opt-in. See catalog.navigation for a
# bounded sample that respects the registered ModelAdmin queryset/permissions.
NOVA_ADMIN_NAV_BADGE_PROVIDER = "catalog.navigation.demo_product_badges"
