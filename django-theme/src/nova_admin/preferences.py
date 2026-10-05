"""Server-side presentation preferences; no authentication or permission changes."""
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

SESSION_KEY = "nova_admin_mode"
MODES = frozenset({"dark", "light", "auto", "native"})


def selected_mode(request):
    default = getattr(settings, "NOVA_ADMIN_DEFAULT_MODE", "dark")
    if not isinstance(default, str) or default not in MODES:
        default = "dark"
    session = getattr(request, "session", {})
    mode = session.get(SESSION_KEY, default)
    return mode if isinstance(mode, str) and mode in MODES else default


def safe_admin_return(request, candidate, admin_index):
    """Only return to a canonical local path inside this admin URL prefix.

    Do not trust HTTP Referer. Reject absolute URLs, path traversal (including
    percent-encoded traversal), backslashes, and control characters.
    """
    if not candidate or any(ord(char) < 32 for char in candidate):
        return admin_index
    if not url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return admin_index
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return admin_index
    decoded = unquote(parsed.path)
    if (
        parsed.scheme or parsed.netloc or not parsed.path.startswith(admin_index)
        or not decoded.startswith(admin_index) or "\\" in decoded or "//" in decoded
        or any(part in {".", ".."} for part in decoded.split("/"))
        or any(ord(char) < 32 for char in decoded)
    ):
        return admin_index
    return candidate
