"""Loopback-only browser harness for the real demo AdminSite and a disposable memory database."""
from http.cookies import SimpleCookie
from pathlib import Path
import json
import sys
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "django-theme/scripts"))
from export_admin_samples import configure_django, create_synthetic_data


def main():
    configure_django()
    from django import forms
    from django.conf import settings
    from django.contrib import auth, messages
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler
    from django.core.wsgi import get_wsgi_application
    from django.db import connections
    from django.http import Http404, HttpResponse, HttpResponseRedirect
    from django.template import engines
    from django.test import override_settings
    from django.urls import path
    from django.utils.translation import override
    from django.views.decorators.clickjacking import xframe_options_sameorigin
    from django.views.static import serve
    from config.urls import urlpatterns
    from nova_admin.preferences import PALETTES

    user, product = create_synthetic_data()
    profiles = {f"{palette}-{density}-{mode}": (palette, density, mode, "en", "standard")
                for palette in PALETTES for density in ("standard", "compact") for mode in ("light", "dark")}
    for mode in ("light", "dark", "auto"):
        profiles[f"high-{mode}"] = ("teal", "standard", mode, "en", "high")
    profiles.update({"standard-auto": ("teal", "standard", "auto", "en", "standard"),
                     "rtl": ("teal", "standard", "light", "ar", "standard")})

    for case in json.loads((ROOT / "django-theme/tests/locales.json").read_text()):
        profiles["locale-" + case["code"]] = ("teal", "standard", "light", case["code"], "standard")

    def start(request, profile, page):
        routes = {"login": "/admin/login/", "list": "/admin/catalog/product/",
                  "form": f"/admin/catalog/product/{product.pk}/change/", "dashboard": "/admin/",
                  "messages": "/admin/catalog/product/", "delete": f"/admin/catalog/product/{product.pk}/delete/"}
        if profile not in profiles or page not in routes:
            raise Http404
        request.session.flush()
        if page != "login":
            auth.login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if page == "messages":
            messages.success(request, "تم الحفظ SKU-123")
        response = HttpResponseRedirect(routes[page])
        response.set_cookie("visual_profile", profile)
        return response

    def components(request, kind):
        if kind not in ("image", "slider"):
            raise Http404
        template = engines["django"].from_string((Path(__file__).parent / "components.html").read_text())
        widget = {"name": "verification", "alternative": {"url": "#help", "label": "خيارات إضافية"},
                  "subwidgets": [{"template_name": "django/forms/widgets/text.html",
                                  "type": "text", "name": "answer", "attrs": {"aria-label": "الرمز"}}]}
        context = {"widget": widget, "image": "/static/admin/img/icon-yes.svg",
                   "nova_captcha_help": "تعليمات بديلة لتسجيل الدخول"}
        renderer = forms.renderers.DjangoTemplates()
        widget_html = renderer.render("nova_admin/" + ("captcha_widget" if kind == "image" else "slider_widget") + ".html", context)
        return HttpResponse(template.render({"kind": kind, "widget_html": widget_html}, request))

    urlpatterns[:0] = [
        path("components/<slug:kind>/", components),
        path("ready/", lambda request: HttpResponse("ready")),
        path("case/<slug:profile>/<slug:page>/", start),
        path("editor/<path:path>", xframe_options_sameorigin(serve), {"document_root": ROOT / "dist"}),
    ]
    settings.DEBUG_PROPAGATE_EXCEPTIONS = True
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    settings.LOCALE_PATHS = [ROOT / "django-theme/tests/locale", *settings.LOCALE_PATHS]
    app = get_wsgi_application()
    settings_lock = Lock()

    def scoped(environ, respond):
        cookies = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        name = cookies["visual_profile"].value if "visual_profile" in cookies else ""
        palette, density, mode, lang, contrast = profiles.get(name, profiles["default-standard-light"])
        with settings_lock, override_settings(NOVA_ADMIN_MARKDOWN=lang == "ar", NOVA_ADMIN_DEFAULT_PALETTE=palette, PROJECT_ADMIN_COMPACT=density == "compact",
                               NOVA_ADMIN_DEFAULT_MODE=mode, NOVA_ADMIN_DEFAULT_CONTRAST=contrast), override(lang):
            return app(environ, respond)

    # Browser preconnects can idle before sending an HTTP request. Accept those
    # sockets concurrently, and serialize only the request-scoped host settings.
    database = connections["default"]
    database.inc_thread_sharing()
    try:
        with ThreadedWSGIServer(("127.0.0.1", 4189), WSGIRequestHandler,
                                connections_override={"default": database}) as server:
            server.set_app(StaticFilesHandler(scoped))
            server.serve_forever()
    finally:
        database.dec_thread_sharing()


if __name__ == "__main__":
    main()
