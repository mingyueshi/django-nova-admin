"""Small declarative branding boundary; settings contain data, never markup."""
import re
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.templatetags.static import static
from django.utils.encoding import force_str
from django.utils.functional import Promise


_STATIC_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_IMAGE_SUFFIXES = {"svg", "png", "jpg", "jpeg", "gif", "webp", "avif"}


def local_static_url(path, *, favicon=False):
    """Resolve only project-controlled image paths to same-origin static URLs.

    Remote storage/CDN URLs are deliberately outside this settings interface.
    Projects opting into them can own a reviewed template and their CSP policy.
    Invalid paths or a missing manifest entry omit the optional image.
    """
    if not isinstance(path, str) or not _STATIC_PATH.fullmatch(path):
        return ""
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return ""
    allowed = _IMAGE_SUFFIXES | ({"ico"} if favicon else set())
    if path.rsplit(".", 1)[-1].lower() not in allowed:
        return ""
    try:
        url = static(path)
        # urlsplit strips raw tabs/newlines. Reject them before parsing so the
        # returned URL cannot differ from the string that was validated.
        if not isinstance(url, str) or any(ord(char) < 33 or ord(char) == 127 for char in url):
            return ""
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return ""
    decoded = unquote(parsed.path)
    if (not decoded.startswith("/") or "//" in decoded or "\\" in decoded
            or any(ord(char) < 33 or ord(char) == 127 for char in decoded)
            or any(part in {".", ".."} for part in decoded.split("/"))):
        return ""
    return url


def _text(value):
    # Templates use force_escape too, even if a project passed mark_safe().
    return force_str(value) if isinstance(value, (str, Promise)) else ""


def branding():
    """Return independent, validated values without changing project settings."""
    config = getattr(settings, "NOVA_ADMIN_BRANDING", {})
    if not isinstance(config, dict):
        config = {}
    return {
        "logo_url": local_static_url(config.get("logo")),
        "logo_alt": _text(config.get("logo_alt", "")),
        "favicon_url": local_static_url(config.get("favicon"), favicon=True),
        "login_background_url": local_static_url(config.get("login_background")),
        "footer": _text(config.get("footer", "")),
    }
