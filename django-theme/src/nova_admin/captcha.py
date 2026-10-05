"""Explicit, optional django-simple-captcha 0.7.0 login integration.

Import this module only after adding ``captcha`` to INSTALLED_APPS. Core Nova
never imports it. Keep each project's existing AdminSite and auth backends.
"""
import re

from captcha.conf import settings as captcha_settings
from captcha.fields import CaptchaField, CaptchaTextInput
from captcha.models import CaptchaStore
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import router
from django.forms import MultiValueField
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import pgettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


_TOKEN_SALT = "nova_admin.login-captcha.v1"
_KEY_RE = re.compile(r"\A[a-f0-9]{40}\Z")
_INVALID = pgettext_lazy("Nova Admin", "The verification code is incorrect or expired. Please try the new image.")


def _check_settings():
    # Pool keys can be shared by unrelated clients. Test mode is never accepted
    # by this adapter, including in DEBUG: tests use real synthetic DB answers.
    if captcha_settings.CAPTCHA_TEST_MODE or captcha_settings.CAPTCHA_GET_FROM_POOL:
        raise ImproperlyConfigured(
            "Nova login CAPTCHA requires CAPTCHA_TEST_MODE=False and "
            "CAPTCHA_GET_FROM_POOL=False."
        )


def _sign_key(key):
    # Only an opaque identifier is signed; never the challenge or answer.
    return signing.dumps(key, salt=_TOKEN_SALT)


def _read_key(token):
    if not isinstance(token, str) or len(token) > 240:
        raise signing.BadSignature("Invalid challenge token")
    key = signing.loads(token, salt=_TOKEN_SALT)
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
        raise signing.BadSignature("Invalid challenge key")
    return key


def _consume(key):
    """Return the server-only row iff this request wins its atomic deletion.

    Unlike upstream's instance.delete(), acceptance depends on the affected
    CaptchaStore row count. Two readers may see the row, but only one can delete
    it. Use the write DB for both operations, never a lagging read replica.
    Database errors propagate (fail closed); they must not trigger auth.
    """
    alias = router.db_for_write(CaptchaStore)
    rows = CaptchaStore.objects.using(alias)
    store = rows.filter(hashkey=key).first()
    if store is None:
        return None
    _, deleted_by_model = rows.filter(pk=store.pk, hashkey=key).delete()
    if deleted_by_model.get(CaptchaStore._meta.label, 0) != 1:
        return None
    return store


class NovaCaptchaTextInput(CaptchaTextInput):
    template_name = "nova_admin/captcha_widget.html"
    # One visible answer input; the other subwidget is only an opaque key.
    use_fieldset = False
    refresh_url_name = "nova-captcha-refresh"

    def render(self, name, value, attrs=None, renderer=None):
        _check_settings()
        return super().render(name, value, attrs, renderer)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["subwidgets"][0]["value"] = _sign_key(self._key)
        context["nova_captcha_refresh_url"] = reverse(self.refresh_url_name)
        context["nova_captcha_help"] = getattr(
            settings, "NOVA_ADMIN_CAPTCHA_HELP_TEXT",
            pgettext_lazy("Nova Admin", "If you cannot use this challenge, contact your administrator for an alternative sign-in method."),
        )
        context["nova_captcha_support_url"] = getattr(settings, "NOVA_ADMIN_CAPTCHA_SUPPORT_URL", "")
        return context


class SingleUseCaptchaField(CaptchaField):
    """Upstream generator/widget with a checked atomic-consumption adapter."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", NovaCaptchaTextInput())
        kwargs.setdefault("label", pgettext_lazy("Nova Admin", "Verification code"))
        kwargs.setdefault("help_text", pgettext_lazy("Nova Admin", "Enter the characters shown in the image. Letters are not case-sensitive."))
        kwargs.setdefault("error_messages", {"invalid": _INVALID})
        super().__init__(*args, **kwargs)

    def clean(self, value):
        _check_settings()
        # Skip CaptchaField.clean: its SELECT/delete acceptance is not atomic.
        # Retain Django's standard multi-value required/format validation.
        try:
            MultiValueField.clean(self, value)
        except ValidationError:
            # Even a blank answer consumes a supplied challenge, preventing a
            # stale form from later reusing it after an invalid submission.
            if value and isinstance(value, (list, tuple)):
                try:
                    _consume(_read_key(value[0]))
                except (signing.BadSignature, IndexError):
                    pass
            raise
        try:
            store = _consume(_read_key(value[0]))
        except signing.BadSignature:
            store = None
        response = (value[1] or "").strip().lower()
        if store is None or store.expiration <= timezone.now() or not constant_time_compare(store.response, response):
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        # Do not retain the submitted answer in cleaned_data.
        return [value[0], ""]


class CaptchaAdminAuthenticationForm(AdminAuthenticationForm):
    captcha = SingleUseCaptchaField()

    def clean(self):
        # AuthenticationForm.clean executes even with field errors. Never call
        # an authentication backend until this CAPTCHA has passed validation.
        if "captcha" in self.errors:
            return self.cleaned_data
        return super().clean()


@never_cache
@csrf_protect
@require_POST
def captcha_refresh(request):
    """Consume a signed Nova login challenge and issue exactly one replacement."""
    _check_settings()
    try:
        old = _consume(_read_key(request.POST.get("key", "")))
    except signing.BadSignature:
        old = None
    if old is None:
        return JsonResponse({"error": "challenge_unavailable"}, status=409)
    # A refreshed token is a distinct DB challenge; no answer leaves the server.
    key = CaptchaStore.generate_key()
    return JsonResponse({
        "key": _sign_key(key),
        "image_url": reverse("captcha-image", kwargs={"key": key}),
        "audio_url": reverse("captcha-audio", kwargs={"key": key}) if captcha_settings.CAPTCHA_FLITE_PATH else None,
    })
