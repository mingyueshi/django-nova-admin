#!/usr/bin/env python3
"""Build a bounded navigation-only interaction fixture from synthetic Django views.

Requires the theme's test dependencies. No persistent database is read or written.
This does not run an admin backend or publish any files.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import sys
from html import escape

from bs4 import BeautifulSoup

SOURCE_ROOT = Path(__file__).resolve().parents[1]
CSP = "default-src 'none'; script-src 'self'; connect-src 'none'; style-src 'self'; img-src 'self' data:; font-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'"


def build(theme: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(theme / "src"), str(theme / "demo")]
    import django
    from django.conf import settings
    if settings.configured:
        raise RuntimeError("Run this generator as a fresh process")
    config = importlib.import_module("config.extensions_settings")
    values = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    values.update(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        SECRET_KEY="synthetic-navigation-lab-only-not-a-deployment-key",
        ALLOWED_HOSTS=["testserver"], DEBUG=False, STATIC_URL="/static/",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
    )
    settings.configure(**values)
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from django.test import Client, override_settings
    from django.urls import reverse
    from django.utils import translation
    if connection.settings_dict["NAME"] != ":memory:":
        raise RuntimeError("Refusing to use a persistent database")
    call_command("migrate", interactive=False, verbosity=0)
    user = get_user_model()(username="synthetic-navigation-menu", is_staff=True, is_superuser=True)
    user.set_unusable_password()
    user.save()
    from catalog.models import Product
    Product.objects.bulk_create([
        Product(name=f"合成导航商品 {index}", sku=f"NAV-LAB-{index}", price="9.99", stock=3)
        for index in range(1, 4)
    ])
    client = Client()
    client.force_login(user)
    assets = [
        "admin/css/base.css", "admin/css/nav_sidebar.css", "admin/css/responsive.css",
        "admin/js/nav_sidebar.js", "nova_admin/theme.css", "nova_admin/tokens.css", "nova_admin/navigation.js",
        "catalog/enterprise.css",
    ]
    for asset in assets:
        source = Path(finders.find(asset))
        destination = output / "static" / asset
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    # Follow only local CSS url() dependencies, never any remote imports/resources.
    pending = [output / "static" / name for name in assets if name.endswith('.css')]
    seen = set()
    static_root = (output / "static").resolve()
    while pending:
        css = pending.pop()
        if css in seen:
            continue
        seen.add(css)
        text = css.read_text()
        if re.search(r"@import|https?://", text):
            raise RuntimeError(f"Unvetted external CSS dependency: {css}")
        for url in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", text):
            if url.startswith("data:"):
                continue
            path = (css.parent / url.split('#', 1)[0]).resolve()
            if not path.is_relative_to(static_root):
                raise RuntimeError("CSS asset escapes fixture")
            relative = path.relative_to(static_root).as_posix()
            found = finders.find(relative)
            if not found:
                raise RuntimeError(f"Missing CSS asset: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(found, path)
            if path.suffix == ".css":
                pending.append(path)
    distribution = importlib.metadata.distribution("Django")
    license_file = next(item for item in distribution.files if item.name == "LICENSE" and "dist-info" in str(item))
    shutil.copyfile(distribution.locate_file(license_file), output / "DJANGO-LICENSE.txt")
    shutil.copyfile(theme / "LICENSE", output / "NOVA-LICENSE.txt")
    output_files = []
    for language in ("zh-hans", "en"):
        chinese = language == "zh-hans"
        labels = ["业务管理", "系统管理"] if chinese else ["Business", "System management"]
        groups = [{"key": "business", "label": labels[0], "apps": ["catalog"]},
                  {"key": "system", "label": labels[1], "apps": ["auth"]}]
        with override_settings(NOVA_ADMIN_NAV_GROUPS=groups), translation.override(language):
            response = client.get(reverse("admin:catalog_product_changelist"))
        if response.status_code != 200:
            raise RuntimeError(f"Synthetic admin render returned {response.status_code}")
        source = BeautifulSoup(response.content.decode(), "html.parser")
        nav = source.select_one("nav.nova-navigation")
        toggle = source.select_one("#toggle-nav-sidebar")
        mobile_toggle = source.select_one("#nova-mobile-nav-toggle")
        if not nav or not toggle or not mobile_toggle:
            raise RuntimeError("The real template did not render Nova navigation")
        # Replace even the synthetic user scope with an explicit public-fixture scope.
        # Languages share collapse settings; this key contains no user/session data.
        nav["data-nova-nav-scope"] = hashlib.sha256(b"nova-navigation-interaction-lab-v1").hexdigest()
        for link in nav.select("a"):
            link["href"] = "#navigation-destination"
            for attr in ("target", "download", "ping"):
                link.attrs.pop(attr, None)
        toggle["type"] = "button"
        fragment = str(mobile_toggle) + str(toggle) + str(nav)
        parsed = BeautifulSoup(fragment, "html.parser")
        if parsed.select("form, script, iframe, input[type=hidden], input[type=password], input[type=file]"):
            raise RuntimeError("Unexpected active or sensitive navigation markup")
        for tag in parsed.find_all(True):
            for name in tag.attrs:
                if name.startswith("on") or name in {"name", "action", "formaction", "src"}:
                    raise RuntimeError(f"Unexpected attribute {name}")
        if re.search(r"csrfmiddlewaretoken|csrftoken|sessionid|_auth_user|/admin/", fragment, re.I):
            raise RuntimeError("Backend/auth residue in navigation fragment")
        label = "导航交互样例，合成权限菜单，无业务后端" if chinese else "Navigation interaction sample: synthetic permission menu, no business backend"
        header = "NOVA · 导航预览" if chinese else "NOVA · Navigation preview"
        heading = "收藏与导航" if chinese else "Favorites and navigation"
        instructions = ("分组与应用默认折叠；可以用键盘或鼠标展开/收起，搜索分组、应用或模型名称，并刷新验证状态保留。手机上点击「导航菜单」展开；Esc 先清空筛选，再次按下可收起菜单。全部菜单链接只跳到本页说明，不执行管理操作。" if chinese else "Groups and apps start collapsed. Use the keyboard or mouse to expand/collapse them. Search group, app or model names and reload to check saved state. On phones, open Navigation; Escape clears a search, then closes the menu on the next press. Every menu destination is a local page anchor and performs no admin action.")
        privacy = ("折叠状态仅保存在此浏览器的 localStorage，筛选保存在当前标签页的 sessionStorage。此样例执行两份经过核验的导航脚本；不登录、不提交表单、不请求业务 API。应用/模型名称来自宿主示例项目，不由主题翻译。" if chinese else "Collapse preferences stay in this browser’s localStorage; the filter stays in this tab’s sessionStorage. This sample executes two verified navigation scripts only. It has no login, form submission or business API calls. App/model names are supplied by the example host project, not translated by the theme.")
        variants = [(f"{lang}-{mode}.html", f"{lang} · {mode}") for lang in ("zh-hans", "en") for mode in ("dark", "light", "auto")]
        variants += [("zh-hans-light-custom.html", "自定义品牌 · 浅色"), ("zh-hans-dark-custom.html", "自定义品牌 · 深色")]
        links = " ".join(f'<a href="{name}">{escape(title)}</a>' for name, title in variants)
        for mode in ("dark", "light", "auto"):
            name = f"{language}-{mode}.html"
            html = f'''<!doctype html><html lang="{language}" data-theme="{mode}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><meta name="referrer" content="no-referrer"><title>{escape(label)} · {mode}</title><link rel="stylesheet" href="static/admin/css/base.css"><link rel="stylesheet" href="static/admin/css/nav_sidebar.css"><link rel="stylesheet" href="static/admin/css/responsive.css"><link rel="stylesheet" href="static/nova_admin/theme.css"><link rel="stylesheet" href="static/nova_admin/tokens.css"><link rel="stylesheet" href="static/catalog/enterprise.css"><link rel="stylesheet" href="static/lab.css"><script src="static/admin/js/nav_sidebar.js" defer></script><script src="static/nova_admin/navigation.js" defer></script></head><body class="nova-admin nova-mode-{mode}"><div id="container"><header id="header"><strong>{escape(header)}</strong></header><div class="main" id="main">{fragment}<main class="content" id="content"><h1>{escape(heading)}</h1><p>{escape(label)}</p><p>{escape(instructions)}</p><p>{escape(privacy)}</p><nav class="lab-variants" aria-label="Sample variants">{links}</nav><section id="navigation-destination" tabindex="-1"><h2>{'仅本地交互' if chinese else 'Local interactions only'}</h2><p>{'由真实 Django ' if chinese else 'Rendered from real Django '}{django.get_version()} {'模板与合成内存数据库生成；这是静态导航交互样例，不是运行中的 Django 管理服务。' if chinese else 'templates and a synthetic in-memory database. This is a static navigation fixture, not a running Django admin service.'}</p></section></main></div></div></body></html>'''
            (output / name).write_text(html)
            output_files.append(name)
    (output / "static" / "lab.css").write_text("""/* Fixture explanation only; Nova navigation styling remains unchanged. */
body.nova-admin #header { align-items: start; gap: 12px; }
body.nova-admin #content { max-width: none; }
.lab-variants { display: flex; gap: 16px; flex-wrap: wrap; margin: 24px 0; }
#navigation-destination { margin-top: 40px; padding: 24px; border: 1px solid var(--hairline-color); border-radius: 12px; }
body.nova-admin p { max-width: 65ch; line-height: 1.7; }
""")
    (output / "static" / "custom-brand.css").write_text("""/* Project example: seven token overrides, no component rewrite. */
body.nova-admin {
  --nova-brand-light: #0f766e;
  --nova-brand-light-hover: #115e59;
  --nova-brand-dark: #5eead4;
  --nova-brand-dark-hover: #99f6e4;
  --nova-density: .9;
  --nova-spacing: .95;
  --nova-radius: 10px;
}
""")
    for mode in ("light", "dark"):
        name = f"zh-hans-{mode}-custom.html"
        html = (output / f"zh-hans-{mode}.html").read_text()
        html = html.replace('<link rel="stylesheet" href="static/lab.css">', '<link rel="stylesheet" href="static/custom-brand.css"><link rel="stylesheet" href="static/lab.css">')
        (output / name).write_text(html)
        output_files.append(name)
    hashes = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((output / "static").rglob("*")) if path.is_file()}
    manifest = {"fixture": "navigation interaction only", "django": django.get_version(), "pages": output_files, "upstream_and_theme_asset_sha256": hashes, "backend_endpoints": 0, "forms": 0, "inline_scripts": 0, "remote_assets": 0, "csp": CSP}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (output / "README.md").write_text(f'''# Nova navigation interaction fixture

导航交互样例，合成权限菜单，无业务后端。
Navigation interaction sample: synthetic permission menu, no business backend.

Open the zh-hans/en dark, light, or auto HTML variants through an ordinary static HTTP server. This is **not** a running Django admin service. It is distinct from the inert full-page admin snapshot export. No deployment or public upload is performed by the generator.

Generated by Django {django.get_version()} TestClient using the current theme's real navigation templates and permission-filtered AdminSite menus. The database is explicitly :memory:, the fixture account has an unusable password, and only the resulting navigation/toggle elements survive extraction. All model/home/add links point to one local explanatory anchor. The exported preference scope is a deterministic public fixture namespace, not an account/session value.

The only executable assets are unchanged installed Django {django.get_version()} nav_sidebar.js and the current Nova navigation.js. They provide desktop sidebar visibility, a mobile Navigation disclosure, group/app/model search, native details/summary collapse, bounded site/user-scoped preference behavior (using the fixture scope here), and Escape clearing. Mobile Escape clears a search first, then closes the menu and returns focus to Navigation. Without JavaScript the mobile menu remains visible. Mobile disclosure never changes the stored desktop sidebar preference. The filter query uses sessionStorage; collapse uses localStorage. Browser storage blocking does not disable Nova's filter/collapse or mobile disclosure, but the upstream desktop sidebar toggle itself has unguarded storage access. No application API, form, login, CSRF value, auth session field, iframe, inline script or remote asset is included. CSP forbids connect and form-action; only same-origin script/style/assets are permitted.

Reproduce from the accompanying source package root, in a fresh process with Django and beautifulsoup4 installed (the generator is source-only, not part of this static sample):

    python scripts/generate_navigation_lab.py --output generated-navigation-lab

The base files show Chinese/English theme text and dark/light/auto styling. Two additional Chinese custom-brand files load only seven CSS token overrides (teal palette, .9 density, .95 spacing and10px radius). Favorites and common models are real theme navigation controls with an explicit synthetic storage scope; the badge3 comes from three synthetic Product rows and the scoped demo hook. App/model names remain those supplied by the host demo, which includes Chinese catalog names; theme gettext does not override host-model labels. Use native summary focus plus Space/Enter in a real browser to verify keyboard behavior. DOM tests alone are not full browser/accessibility certification.

## Attribution

Django {django.get_version()}: Copyright Django Software Foundation and individual contributors, BSD 3-Clause. Full license: DJANGO-LICENSE.txt. Exact assets copied from the installed distribution's django/contrib/admin/static/admin tree; source: https://github.com/django/django. Any embedded SVG attribution remains in the unchanged files.

Nova Django Admin Theme: MIT, full license NOVA-LICENSE.txt. Source: accompanying theme directory. Asset hashes and exact Django version: manifest.json. The lab CSS and generator are fixture support code.
''')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=SOURCE_ROOT / "generated-navigation-lab",
                        help="Absolute or relative output directory; defaults outside scripts")
    args = parser.parse_args()
    theme = args.theme.resolve()
    output = args.output.resolve()
    if output == theme or output == theme / "scripts":
        parser.error("Choose a separate output directory, not the package root or scripts")
    build(theme, output)
