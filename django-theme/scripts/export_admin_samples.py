#!/usr/bin/env python3
"""Export inert, portable Django Admin HTML rendered from synthetic in-memory data.

Run from any directory with Django and beautifulsoup4 installed. No demo database
is read or written. The default output is ../exported-admin-samples next to this
script. --check validates an existing export without configuring Django.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "exported-admin-samples"
MARKER = ".nova-admin-samples"
LABEL = "真实 Django 模板渲染样本"
MODES = {
    "light": "企业浅色 · 标准密度", "dark": "企业深色 · 标准密度",
    "auto": "跟随系统 · 标准密度", "compact-light": "企业浅色 · 紧凑密度",
    "compact-dark": "企业深色 · 紧凑密度", "compact-auto": "跟随系统 · 紧凑密度",
    "native": "Django 原生外观",
}


def theme_mode(mode):
    return mode.removeprefix("compact-")

PAGES = {
    "index": "工作台",
    "changelist": "商品列表 · 方形图片",
    "members": "会员列表 · 圆形头像",
    "news": "新闻列表 · 横向封面",
    "changeform": "商品编辑 · 关系字段与内联",
    "validation-error": "原生表单校验错误",
    "delete-confirm": "原生删除确认",
    "login": "原生登录页",
}
PALETTES = {
    "teal": "医疗青", "indigo": "专业靛", "violet": "文教紫", "terracotta": "零售陶",
    "graphite": "石墨黑", "midnight": "午夜蓝", "forest": "松林绿", "amber": "暖琥珀",
    "ocean": "深海青", "slate": "雾岩灰", "plum": "暮梅紫", "coffee": "摩卡棕",
}
PALETTE_PAGES = ("index", "changelist", "login")


def sample_profiles(with_palettes=False):
    profiles = [(mode, mode, "default", tuple(PAGES)) for mode in MODES]
    if with_palettes:
        profiles += [(f"palette-{palette}-{mode}", mode, palette, PALETTE_PAGES)
                     for palette in PALETTES for mode in ("light", "dark")]
    return profiles


STATIC_SUFFIXES = {".css", ".svg", ".png", ".gif", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf", ".ico"}
SUBMISSION_ATTRS = {"action", "method", "enctype", "accept-charset", "target", "name", "form", "formaction", "formmethod", "formenctype", "formtarget", "formnovalidate"}
FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "base", "applet", "audio", "video", "source", "track", "template", "foreignobject"}
SAFE_ATTRS = {
    "class", "id", "lang", "dir", "title", "role", "tabindex", "style",
    "href", "src", "rel", "type", "media", "charset", "http-equiv", "content",
    "alt", "width", "height", "loading", "decoding", "for", "colspan", "rowspan", "scope", "headers",
    "value", "placeholder", "selected", "checked", "multiple", "disabled", "readonly",
    "min", "max", "step", "size", "maxlength", "rows", "cols", "open", "hidden",
    "viewbox", "fill", "fill-rule", "clip-rule", "d", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "xmlns", "xlink:href", "points", "cx", "cy", "r",
}
CSP = "default-src 'none'; script-src 'none'; connect-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'"
URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_django(with_captcha=False, with_extensions=False):
    # Importing this settings module only defines values; settings.configure is
    # called once with the in-memory database BEFORE django.setup/connections.
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "demo")]
    import django
    from django.conf import settings
    if settings.configured:
        raise RuntimeError("Run this exporter as a fresh process, not inside a configured Django shell")
    config = importlib.import_module("config.captcha_settings" if with_captcha else "config.settings")
    values = {key: getattr(config, key) for key in dir(config) if key.isupper()}
    if with_extensions:
        extension_config = importlib.import_module("config.extensions_settings")
        values.update({key: getattr(extension_config, key) for key in dir(extension_config) if key.startswith("NOVA_ADMIN_BRANDING") or key.startswith("NOVA_ADMIN_NAV_")})
    values.update(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        SECRET_KEY="synthetic-export-only-never-a-deployment-key",
        DEBUG=False,
        ALLOWED_HOSTS=["testserver"],
        STATIC_URL="/static/",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
    )
    settings.configure(**values)
    django.setup()
    from django.db import connection
    if connection.settings_dict["NAME"] != ":memory:":
        raise RuntimeError("Refusing to render against a persistent database")
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    call_command("migrate", verbosity=0, interactive=False)
    setup_test_environment()
    return django


def create_synthetic_data():
    from django.contrib.auth import get_user_model
    from catalog.models import Category, MemberProfile, NewsItem, Product, ProductVariant, Tag
    user = get_user_model()(username="sample-admin", first_name="示例", last_name="管理员", is_staff=True, is_superuser=True)
    user.set_unusable_password()  # There is no shared credential to export.
    user.save()
    category = Category.objects.create(pk=101, name="设计工作室", slug="sample-design-studio")
    tag = Tag.objects.create(pk=201, name="新品", slug="sample-new")
    Tag.objects.create(pk=202, name="精选", slug="sample-featured")
    rows = [
        (1001, "Orbit 折叠支架", "SAMPLE-ORBIT-01", "269.00", 128, "active"),
        (1002, "Grid 桌面收纳盒", "SAMPLE-GRID-02", "89.00", 64, "draft"),
        (1003, "Halo 无线键盘", "SAMPLE-HALO-03", "399.00", 32, "active"),
        (1004, "Arc 无线充电座", "SAMPLE-ARC-04", "199.00", 0, "archived"),
    ]
    for pk, name, sku, price, stock, status in rows:
        product = Product.objects.create(pk=pk, name=name, sku=sku, price=price, stock=stock, status=status, category=category, featured=pk in {1001, 1003}, image_key={1001: "4", 1002: "1", 1003: "0", 1004: ""}[pk])
        product.tags.add(tag)
        Product.objects.filter(pk=pk).update(updated_at=datetime(2026, 10, 1, 12 if pk == 1001 else 9, tzinfo=timezone.utc))
    from datetime import date
    for index, name in enumerate(("林知夏", "周亦辰", "陈安宁", "许景行", "沈若晴", "顾书远")):
        MemberProfile.objects.create(pk=2001 + index, name=name, member_code=f"DEMO-M{index + 1:03}", avatar_key=str(index) if index < 5 else "", tier="premium" if index % 2 == 0 else "standard", active=index != 4, joined_at=date(2026, 9, 10 + index))
    for index, (title, section, key) in enumerate((("光与结构：城市美术馆的新视角", "design", "0"), ("让协作自然发生的工作空间", "community", "1"), ("山湖之间，寻找日常的留白", "places", "2"), ("设计手记：下一场展览即将到来", "design", ""))):
        NewsItem.objects.create(pk=3001 + index, title=title, section=section, cover_key=key, status="published" if index < 3 else "draft", published_on=date(2026, 9, 30 - index) if index < 3 else None)
    target = Product.objects.get(pk=1001)
    ProductVariant.objects.create(pk=301, product=target, name="颜色", value="石墨灰")
    ProductVariant.objects.create(pk=302, product=target, name="尺寸", value="标准版")
    return user, target


def local_static(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    if not parsed.path.startswith("/static/"):
        return None
    relative = unquote(parsed.path[len("/static/"):])
    if "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        return None
    if Path(relative).suffix.lower() not in STATIC_SUFFIXES:
        return None
    return "../static/" + relative


def sanitize_html(raw: str, *, mode: str, page: str, django_version: str, routes: dict[str, str], palette: str = "default") -> str:
    if palette not in {"default", *PALETTES} or (palette != "default" and (mode not in {"light", "dark"} or page not in PALETTE_PAGES)):
        raise ValueError("Unsupported palette sample profile")
    profile_label = MODES[mode] + (f" · {PALETTES[palette]}配色代表页" if palette != "default" else "")
    soup = BeautifulSoup(raw, "html.parser")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for tag in list(soup.find_all(True)):
        if tag.name in FORBIDDEN_TAGS or (tag.name == "input" and tag.get("type", "").lower() == "hidden"):
            tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name == "meta" and tag.get("http-equiv", "").lower() in {"refresh", "content-security-policy"}:
            tag.decompose()
            continue
        if tag.name == "link" and "stylesheet" not in tag.get("rel", []):
            tag.decompose()
            continue
        # Retain semantic forms so Django's form-dependent desktop/mobile CSS
        # stays intact. Never rely on an absent/blank action alone: every control
        # is disabled and unnamed, submit/association attrs are stripped, and an
        # exact early-head CSP independently disallows all form submissions.
        if tag.name == "form":
            tag["data-sample-form"] = "inert"
        for attr in list(tag.attrs):
            if attr == "name" and tag.name == "meta" and tag[attr] in {"viewport", "color-scheme", "robots", "referrer"}:
                continue
            if attr not in SAFE_ATTRS and not attr.startswith("aria-") and attr != "data-sample-form":
                del tag[attr]
        if tag.has_attr("style") and re.search(r"url\s*\(|@import|expression\s*\(|(?:^|[;{])\s*behavior\s*:", str(tag["style"]), re.I):
            del tag["style"]
        if tag.name == "style":
            # Inline styles in a future upstream template must not introduce a
            # new asset/network channel. None are required by current templates.
            tag.decompose()
            continue
        if tag.name in {"input", "select", "textarea", "button"}:
            tag["disabled"] = "disabled"
            tag["aria-disabled"] = "true"
        if tag.name == "button":
            tag["type"] = "button"
        if tag.name == "input" and tag.get("type", "").lower() in {"password", "file"}:
            tag["type"] = "text"
            tag["value"] = ""
            tag["placeholder"] = "静态样本不接受输入"
        for attr in ("href", "src", "xlink:href"):
            if not tag.has_attr(attr):
                continue
            value = str(tag[attr]).strip()
            if value.startswith("#") and len(value) > 1:
                if soup.find(id=value[1:]) is not None:
                    continue
            if attr == "href" and tag.name == "a":
                parsed = urlsplit(value)
                destination = routes.get(parsed.path) if not parsed.scheme and not parsed.netloc and not parsed.query and not parsed.fragment else None
                if destination:
                    tag[attr] = destination + ".html"
                    continue
            if tag.name in {"link", "img"}:
                rewritten = local_static(value)
                if rewritten:
                    tag[attr] = rewritten
                    continue
            del tag[attr]
            if tag.name == "a":
                tag["aria-disabled"] = "true"
                tag["tabindex"] = "-1"
                tag["title"] = "静态渲染样本：此操作不可用"
        if tag.name == "a" and not tag.has_attr("href"):
            tag["aria-disabled"] = "true"
            tag["tabindex"] = "-1"
    # Scripts are intentionally absent. Choose a stable native light baseline
    # rather than depending on Django's removed localStorage/theme JavaScript.
    soup.html["data-theme"] = theme_mode(mode) if theme_mode(mode) in {"dark", "light", "auto"} else "light"
    main = soup.find(id="main")
    sidebar = soup.find(id="nav-sidebar")
    if main is not None and sidebar is not None:
        main["class"] = list(dict.fromkeys(main.get("class", []) + ["shifted"]))
        sidebar["aria-expanded"] = "true"
        toggle = soup.find(id="toggle-nav-sidebar")
        if toggle is not None:
            toggle["aria-expanded"] = "true"
    if soup.title:
        soup.title.string = f"{PAGES[page]} · {profile_label} · {LABEL}"
    for attrs in reversed((
        {"charset": "utf-8"},
        {"http-equiv": "Content-Security-Policy", "content": CSP},
        {"name": "referrer", "content": "no-referrer"},
        {"name": "robots", "content": "noindex, nofollow"},
    )):
        soup.head.insert(0, soup.new_tag("meta", attrs=attrs))
    soup.head.append(soup.new_tag("link", attrs={"rel": "stylesheet", "href": "../static/sample.css"}))
    banner = soup.new_tag("aside", attrs={"class": "sample-banner", "aria-label": LABEL})
    heading = soup.new_tag("strong")
    heading.string = LABEL
    banner.append(heading)
    note = soup.new_tag("p")
    note.string = f"Django {django_version} · {profile_label} · 合成数据。只读静态导出，无登录、保存或删除能力；原生脚本及增强控件已移除。列表开关保留禁用的原生复选框，仅展示已保存状态。"
    if soup.select_one(".nova-captcha"):
        note.string += " 验证码为合成数据库生成的静态PNG，密钥和提交能力已移除。"
    banner.append(note)
    navigation = soup.new_tag("nav", attrs={"aria-label": "样本导航"})
    page_options = PAGES if palette == "default" else {slug: PAGES[slug] for slug in PALETTE_PAGES}
    mode_options = [(label, f"../{slug}/{page}.html", slug == mode) for slug, label in MODES.items()] if palette == "default" else [(MODES[slug], f"../palette-{palette}-{slug}/{page}.html", slug == mode) for slug in ("light", "dark")]
    for label, href, current in [("全部样本", "../index.html", False)] + [(label, f"{slug}.html", slug == page) for slug, label in page_options.items()] + mode_options:
        anchor = soup.new_tag("a", href=href)
        anchor.string = label
        if current:
            anchor["aria-current"] = "page"
        navigation.append(anchor)
    picker = soup.new_tag("details", attrs={"class": "sample-navigation"})
    summary = soup.new_tag("summary")
    summary.string = "切换页面与外观"
    picker.append(summary)
    picker.append(navigation)
    banner.append(picker)
    soup.body.insert(0, banner)
    for notice in soup.select(".nova-list-edit-help"):
        notice.string = "精选推荐为已保存状态的只读快照；本页面不能修改或保存。真实 Django 中需点击保存才生效。"
    return str(soup)


SAMPLE_CSS = """/* Export-only safety/navigation chrome. Not part of the Nova theme. */
.sample-banner{box-sizing:border-box;background:#edf3ff;color:#203452;border-bottom:1px solid #bac8e2;padding:12px 24px;font:12px/1.55 system-ui,sans-serif;position:relative;z-index:1000}
.sample-banner strong{font-size:14px;color:#183254}.sample-banner p{margin:4px 0 8px;padding:0;color:#344a69;font-size:12px}
.sample-banner nav{display:flex;flex-wrap:wrap;gap:6px 14px}.sample-banner a{color:#274d91;text-decoration:underline;font-size:12px}
.sample-navigation summary{cursor:pointer;min-height:24px;font-size:12px}.sample-navigation[open] nav{padding-top:8px}
.sample-banner a[aria-current=page]{font-weight:700;text-decoration:none}.sample-banner a:focus-visible{outline:2px solid #274d91;outline-offset:3px}
a[aria-disabled=true]{cursor:default}.sample-gallery{margin:0;background:#f3f5fa;color:#1c2940;font:15px/1.65 system-ui,sans-serif}
.sample-gallery main{max-width:1080px;margin:0 auto;padding:32px 20px}.sample-gallery h1{font-size:30px;line-height:1.2}.sample-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.sample-card{background:white;padding:22px;border:1px solid #dce2ed;border-radius:12px}.sample-card h2{margin-top:0}.sample-card ul{padding-left:20px}.sample-card a{color:#274d91}.sample-gallery footer{font-size:13px;color:#52617a;margin-top:24px}
@media(max-width:760px){.sample-grid{grid-template-columns:1fr}.sample-banner{padding:10px 14px}.sample-banner nav{gap:6px 10px}.sample-gallery main{padding:22px 14px}}
"""


def gallery(version: str, with_palettes=False) -> str:
    cards = "".join(f'<section class="sample-card"><h2>{label}</h2><ul>' + "".join(f'<li><a href="{mode}/{page}.html">{name}</a></li>' for page, name in PAGES.items()) + "</ul></section>" for mode, label in MODES.items())
    if with_palettes:
        cards += "".join(f'<section class="sample-card"><h2>{PALETTES[palette]} · {MODES[mode]}</h2><p>配色代表页：仅标准密度浅色／深色；名称为场景参考，非行业标准</p><ul>' + "".join(f'<li><a href="{directory}/{page}.html">{PAGES[page]}</a></li>' for page in pages) + "</ul></section>" for directory, mode, palette, pages in sample_profiles(True) if palette != "default")
    return f'''<!doctype html><html lang="zh-hans"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="referrer" content="no-referrer"><meta name="robots" content="noindex,nofollow"><title>{LABEL} · Nova Admin</title><link rel="stylesheet" href="static/sample.css"></head><body class="sample-gallery"><main><h1>{LABEL}</h1><p>由 Django {version} 的真实 Admin 视图、模板和合成数据库生成。选择外观与页面，查看可逆主题在原生管理后台中的真实结构。</p><p>这些页面是只读快照；所有提交、认证、远程请求及 Django JavaScript 均已移除。自动完成、双栏多选和动态新增内联等增强效果请在本地可运行 Demo 中验收。</p><div class="sample-grid">{cards}</div><footer>不含生产数据、账户凭据、会话或 CSRF token。Django 原生样本固定使用其原生浅色主题。文件可整体放到任意 URL 前缀，无需服务器端 Django。</footer></main></body></html>'''


def copy_static(output: Path):
    import django.contrib.admin
    from django.contrib.staticfiles import finders
    django_static = Path(django.contrib.admin.__file__).parent / "static" / "admin"
    target = output / "static" / "admin"
    for source in sorted(django_static.rglob("*")):
        if source.is_file() and source.suffix.lower() in STATIC_SUFFIXES:
            destination = target / source.relative_to(django_static)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    # Include associated upstream attribution without copying executable JS.
    distribution = importlib.metadata.distribution("Django")
    license_files = [item for item in distribution.files or [] if item.name == "LICENSE" and "dist-info" in str(item)]
    if not license_files:
        raise RuntimeError("Django distribution license missing")
    shutil.copyfile(distribution.locate_file(license_files[0]), output / "DJANGO-LICENSE.txt")
    for source in sorted(django_static.rglob("LICENSE*")):
        if source.is_file() and "js" not in source.relative_to(django_static).parts:
            destination = target / source.relative_to(django_static)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    nova_source = ROOT / "src" / "nova_admin" / "static" / "nova_admin"
    for source in sorted(nova_source.rglob("*")):
        if source.is_file() and source.suffix.lower() in STATIC_SUFFIXES:
            resolved = finders.find("nova_admin/" + source.relative_to(nova_source).as_posix())
            if not resolved:
                raise RuntimeError(f"Missing Nova static asset: {source.name}")
            destination = output / "static" / "nova_admin" / source.relative_to(nova_source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved, destination)
    demo_source = ROOT / "demo" / "catalog" / "static" / "catalog"
    for source in sorted(demo_source.rglob("*")):
        if source.is_file() and source.suffix.lower() in STATIC_SUFFIXES:
            resolved = finders.find("catalog/" + source.relative_to(demo_source).as_posix())
            if not resolved:
                raise RuntimeError(f"Missing demo media: {source.name}")
            destination = output / "static" / "catalog" / source.relative_to(demo_source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved, destination)
    shutil.copyfile(ROOT / "LICENSE", output / "NOVA-LICENSE.txt")
    svg_notices = set()
    for source in sorted(django_static.rglob("*.svg")):
        for comment in re.findall(r"<!--(.*?)-->", source.read_text(encoding="utf-8"), flags=re.S):
            if re.search(r"copyright|license", comment, re.I):
                svg_notices.add(" ".join(comment.strip().lstrip("!").split()))
    project_urls = distribution.metadata.get_all("Project-URL") or []
    django_source = next((entry.split(",", 1)[1].strip() for entry in project_urls if entry.startswith("Source,")), "https://github.com/django/django")
    notices = f"""THIRD-PARTY NOTICES — SYNTHETIC DJANGO ADMIN SAMPLES

Django {distribution.version}
Copyright (c) Django Software Foundation and individual contributors.
License: BSD 3-Clause; full unchanged license in DJANGO-LICENSE.txt.
Project: https://www.djangoproject.com/
Source repository: {django_source}
Exact source release: installed Django {distribution.version} distribution.
Assets copied from django/contrib/admin/static/admin in that distribution.
The Django license was located through importlib.metadata.distribution('Django').files:
{license_files[0]}
Rendered template source hashes and copied-asset hashes are in manifest.json.

Nova Django Admin Theme
Copyright (c) 2026 Nova Theme contributors.
License: MIT; full unchanged license in NOVA-LICENSE.txt.
Source: the accompanying Nova repository; exact project version and source hashes
are in manifest.json. Nova CSS is in static/nova_admin/.

Select2 stylesheet assets bundled with Django {distribution.version}
Copyright (c) 2012-2017 Kevin Brown, Igor Vaynberg, and Select2 contributors.
License: MIT; full unchanged license in
static/admin/css/vendor/select2/LICENSE-SELECT2.md.
No Select2, jQuery or other third-party JavaScript is redistributed by this export.

SVG ICON ATTRIBUTION
The following upstream copyright/license notices are retained in the original SVG
files in static/admin/img/. Asset contents have not been modified by the exporter.
"""
    notices += "\n".join(sorted(svg_notices)) + "\n\nDEMO MEDIA\nThree AI-generated sheets: fictional adult avatars, unbranded products and fictional editorial scenes. No private photographs or hotlinked stock. Bundled WebP images are same-dimension encodings of the synthetic source assets. These public demo assets are not private-media examples.\n"
    (output / "THIRD_PARTY_NOTICES.txt").write_text(notices, encoding="utf-8")
    (output / "static" / "sample.css").write_text(SAMPLE_CSS, encoding="utf-8")


def validate_relative_url(value: str, source: Path, root: Path, *, html_link: bool = False):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or value.startswith("/") or "\\" in value or any(ord(c) < 32 for c in value):
        raise AssertionError(f"Non-portable or active URL in {source.name}: {value!r}")
    if not parsed.path and parsed.fragment:
        return
    destination = (source.parent / unquote(parsed.path)).resolve()
    if not destination.is_relative_to(root.resolve()) or not destination.is_file():
        raise AssertionError(f"Missing or escaping asset/link in {source.name}: {value!r}")
    if html_link and destination.suffix != ".html":
        raise AssertionError(f"Navigation target is not a generated HTML fixture: {value!r}")


def validate_inert_forms_and_csp(soup: BeautifulSoup, source: str = "HTML") -> dict:
    csps = soup.find_all("meta", attrs={"http-equiv": lambda value: value and value.lower() == "content-security-policy"})
    if len(csps) != 1 or csps[0].get("content") != CSP or csps[0].parent is not soup.head:
        raise AssertionError(f"Missing, duplicate, misplaced or changed export CSP in {source}")
    for previous in csps[0].previous_siblings:
        if getattr(previous, "name", None) not in {None, "meta", "title"}:
            raise AssertionError(f"Export CSP must precede resource-loading head elements in {source}")
        if getattr(previous, "name", None) == "meta" and previous.get("http-equiv", "").lower() == "refresh":
            raise AssertionError(f"Meta refresh before export CSP in {source}")
    if soup.find("meta", attrs={"http-equiv": lambda value: value and value.lower() == "refresh"}):
        raise AssertionError(f"Meta refresh in {source}")
    if soup.find(FORBIDDEN_TAGS | {"style"}):
        raise AssertionError(f"Active or unvetted element in {source}")
    forms = controls = 0
    for tag in soup.find_all(True):
        for attr in tag.attrs:
            if attr.startswith("on") or attr in SUBMISSION_ATTRS | {"srcset", "ping", "autofocus", "contenteditable"}:
                if attr == "name" and tag.name == "meta":
                    continue
                raise AssertionError(f"Active or serializable attribute {attr} in {source}")
        if tag.name == "form":
            if tag.get("data-sample-form") != "inert" or tag.find_parent("form") is not None:
                raise AssertionError(f"Unmarked or nested semantic form in {source}")
            forms += 1
        if tag.name in {"input", "select", "textarea", "button"}:
            if not tag.has_attr("disabled") or tag.get("type", "").lower() in {"password", "hidden", "file"}:
                raise AssertionError(f"Active or sensitive control in {source}")
            controls += 1
    return {"inert_forms": forms, "functional_forms": 0, "inert_controls": controls}


def validate_export(output: Path, *, with_palettes=None) -> dict:
    if not (output / MARKER).is_file():
        raise AssertionError("Missing export identity marker")
    for notice in ("DJANGO-LICENSE.txt", "NOVA-LICENSE.txt", "THIRD_PARTY_NOTICES.txt", "static/admin/css/vendor/select2/LICENSE-SELECT2.md"):
        if not (output / notice).is_file() or not (output / notice).read_text(encoding="utf-8").strip():
            raise AssertionError(f"Required redistribution notice missing: {notice}")
    pages = sorted(output.rglob("*.html"))
    if with_palettes is None:
        manifest_path = output / "manifest.json"
        with_palettes = json.loads(manifest_path.read_text()).get("palette_representatives", False) if manifest_path.is_file() else False
    expected = {"index.html"} | {f"{directory}/{page}.html" for directory, mode, palette, profile_pages in sample_profiles(with_palettes) for page in profile_pages}
    if {p.relative_to(output).as_posix() for p in pages} != expected:
        raise AssertionError("Fixture inventory does not match the declared appearance/density export contract")
    total_links = total_controls = total_forms = total_switches = checked_switches = total_media = 0
    for path in pages:
        raw = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(raw, "html.parser")
        if soup.find("meta", attrs={"charset": "utf-8"}) is None:
            raise AssertionError(f"Missing UTF-8 declaration in {path.name}")
        if soup.find("meta", attrs={"name": "viewport"}) is None:
            raise AssertionError(f"Missing responsive viewport in {path.name}")
        if LABEL not in soup.get_text():
            raise AssertionError(f"Missing honest sample label in {path.name}")
        if re.search(r"csrfmiddlewaretoken|csrftoken|sessionid|_auth_user|/admin/|/static/", raw, re.I):
            # ../static/ and copied Django asset subdirectories are intentional.
            scrubbed = re.sub(r"\.\./static/|(?<=[\"'])static/|static/admin/", "", raw)
            if re.search(r"csrfmiddlewaretoken|csrftoken|sessionid|_auth_user|/admin/|/static/", scrubbed, re.I):
                raise AssertionError(f"Live endpoint, token or session residue in {path}")
        safety = validate_inert_forms_and_csp(soup, str(path))
        total_forms += safety["inert_forms"]
        total_controls += safety["inert_controls"]
        switches = soup.select("input.nova-switch")
        for switch in switches:
            if switch.get("type") != "checkbox" or not switch.has_attr("disabled") or not switch.get("aria-label") or switch.has_attr("name"):
                raise AssertionError(f"Switch must remain a labeled inert native checkbox in {path}")
        total_switches += len(switches)
        checked_switches += sum(switch.has_attr("checked") for switch in switches)
        if path.stem == "changelist":
            if len(switches) != 4 or sum(switch.has_attr("checked") for switch in switches) != 2:
                raise AssertionError("List snapshot must preserve four synthetic Boolean values, two checked")
            if len(soup.select(".nova-status")) != 4:
                raise AssertionError("List snapshot must preserve four text status labels")
        thumbnails = soup.select(".nova-media-thumb")
        total_media += len(thumbnails)
        if path.stem in {"changelist", "members", "news"}:
            expected_media = {"changelist": ("product", 4), "members": ("avatar", 6), "news": ("cover", 4)}[path.stem]
            if len(thumbnails) != expected_media[1] or any("nova-media-thumb--" + expected_media[0] not in thumb.get("class", []) for thumb in thumbnails):
                raise AssertionError(f"Unexpected image-column inventory: {path}")
            if len(soup.select(".nova-media-thumb--empty")) != 1:
                raise AssertionError(f"Each list must include one honest missing-media example: {path}")
        for img in soup.select(".nova-media-slice img"):
            if not img.get("alt") or img.get("loading") != "lazy" or not str(img.get("width", "")).isdigit() or not str(img.get("height", "")).isdigit():
                raise AssertionError(f"Image lost semantic/fixed-size/lazy attributes: {path}")
        for tag in soup.find_all(True):
            for attr, value in tag.attrs.items():
                if attr.startswith("data-") and attr not in {"data-theme", "data-sample-form"}:
                    raise AssertionError(f"Unvetted data attribute {attr} in {path}")
                if attr in {"href", "src", "xlink:href"}:
                    validate_relative_url(str(value), path, output, html_link=tag.name == "a")
                    total_links += 1
        if path.parent.name == "native" and ("nova_admin/theme.css" in raw or "nova-admin" in soup.body.get("class", [])):
            raise AssertionError("Native fixture must not activate Nova CSS")
        if path.parent != output and path.parent.name.startswith("palette-"):
            _, palette, mode = path.parent.name.split("-")
            if f"nova-palette-{palette}" not in soup.body.get("class", []) or f"nova-mode-{mode}" not in soup.body.get("class", []) or soup.html.get("data-theme") != mode:
                raise AssertionError(f"Palette/mode mismatch in {path}")
            if "nova_admin/presets.css" not in raw:
                raise AssertionError(f"Palette fixture missing palette stylesheet: {path}")
        if path.parent.name in {"dark", "light"} and "nova_admin/theme.css" not in raw:
            raise AssertionError("Themed fixture is missing actual Nova CSS")
    css_files = list(output.rglob("*.css"))
    for path in css_files:
        css = path.read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        imports = re.findall(r"@import\s+([^;]+);", stripped, re.I)
        for imported in imports:
            imported = imported.strip()
            match = re.fullmatch(r"url\(\s*(['\"]?)(.*?)\1\s*\)", imported, re.I)
            if match:
                validate_relative_url(match.group(2), path, output)
            elif len(imported) >= 2 and imported[0] == imported[-1] and imported[0] in {"'", '"'}:
                validate_relative_url(imported[1:-1], path, output)
            else:
                raise AssertionError(f"Unrecognized CSS import: {path}")
        without_imports = re.sub(r"@import\s+[^;]+;", "", stripped, flags=re.I)
        if re.search(r"@import|expression\s*\(|(?:^|[;{])\s*behavior\s*:", without_imports, re.I):
            raise AssertionError(f"CSS contains an unvetted import or executable construct: {path}")
        for _, value in URL_RE.findall(stripped):
            if value.startswith("data:image/"):
                continue
            validate_relative_url(value, path, output)
    for path in output.rglob("*.svg"):
        svg = ET.fromstring(path.read_bytes())
        for tag in svg.iter():
            local_tag = tag.tag.rsplit("}", 1)[-1].lower()
            if local_tag in FORBIDDEN_TAGS or local_tag == "style":
                raise AssertionError(f"Active SVG asset: {path}")
            for key, value in tag.attrib.items():
                local_key = key.rsplit("}", 1)[-1].lower()
                if local_key.startswith("on"):
                    raise AssertionError(f"SVG event handler: {path}")
                if local_key in {"href", "src"}:
                    validate_relative_url(value, path, output)
                if local_key == "style" and re.search(r"url\s*\(|@import|expression\s*\(", value, re.I):
                    raise AssertionError(f"SVG unvetted style resource: {path}")
    if any(path.suffix.lower() in {".js", ".map", ".sqlite3", ".db", ".py", ".env"} for path in output.rglob("*") if path.is_file()):
        raise AssertionError("Executable source, database or environment file in export")
    return {"status": "passed", "html_pages": len(pages), "css_files": len(css_files), "checked_urls": total_links, "inert_controls": total_controls, "inert_forms": total_forms, "inert_switches": total_switches, "checked_switches": checked_switches, "media_thumbnails": total_media, "functional_forms": 0, "scripts": 0, "live_endpoints": 0, "external_requests": 0}


def verify_manifest(output: Path):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    declared = set(manifest["output_sha256"]) | {"manifest.json"}
    observed = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    if declared != observed:
        raise AssertionError("Output inventory differs from the provenance manifest")
    for relative, expected in manifest["output_sha256"].items():
        resolved = (output / relative).resolve()
        if not resolved.is_relative_to(output.resolve()):
            raise AssertionError("Manifest path escapes the export directory")
        if sha256(resolved) != expected:
            raise AssertionError(f"Output hash mismatch: {relative}")


def sanitizer_self_test():
    # A hostile future template must not turn static samples into live forms or
    # network clients. These strings are test input only and never exported.
    hostile = '''<!doctype html><html><head><title>Probe</title><base href="https://example.invalid"><meta http-equiv="refresh" content="0;url=https://example.invalid"><link rel="preload" href="https://example.invalid"></head><body><script>alert(1)</script><iframe src="https://example.invalid"></iframe><form action="/admin/login/" method="post"><input type="hidden" name="csrfmiddlewaretoken" value="SECRET"><input type="password" name="password" value="SECRET"><input name="username" onfocus="alert(1)"><button formaction="https://example.invalid">Submit</button></form><a href="javascript:alert(1)" onclick="alert(1)">bad</a><img src="https://example.invalid/a" srcset="https://example.invalid/b 2x"><select data-ajax--url="/admin/autocomplete/"></select><div style="background:url(https://example.invalid)">probe</div></body></html>'''
    result = sanitize_html(hostile, mode="native", page="login", django_version="self-test", routes={})
    for forbidden in ("SECRET", "example.invalid", "javascript:", "alert(1)", "csrfmiddlewaretoken", "data-ajax", "srcset", "<script", "<iframe"):
        if forbidden in result:
            raise AssertionError(f"Sanitizer regression: {forbidden}")
    safe = BeautifulSoup(result, "html.parser")
    counts = validate_inert_forms_and_csp(safe, "sanitizer self-test")
    if counts["inert_forms"] != 1 or safe.form.get("data-sample-form") != "inert":
        raise AssertionError("Sanitizer must preserve the original inert semantic form")
    # Fail closed if a later edit reintroduces even empty submission attributes,
    # an externally associated control, enabled control, or weakens the CSP.
    for attribute in SUBMISSION_ATTRS:
        mutated = BeautifulSoup(result, "html.parser")
        target = mutated.input if attribute.startswith("form") or attribute == "name" else mutated.form
        target[attribute] = ""
        try:
            validate_inert_forms_and_csp(mutated, "submission mutation self-test")
        except AssertionError:
            pass
        else:
            raise AssertionError(f"Validator accepted submission attribute: {attribute}")
    for mutation in ("enabled", "weak-csp", "missing-csp", "late-csp", "unmarked-form"):
        mutated = BeautifulSoup(result, "html.parser")
        csp = mutated.find("meta", attrs={"http-equiv": "Content-Security-Policy"})
        if mutation == "enabled":
            del mutated.input["disabled"]
        elif mutation == "weak-csp":
            csp["content"] = CSP.replace("form-action 'none'", "form-action 'self'")
        elif mutation == "missing-csp":
            csp.decompose()
        elif mutation == "late-csp":
            mutated.head.append(csp.extract())
        else:
            del mutated.form["data-sample-form"]
        try:
            validate_inert_forms_and_csp(mutated, mutation)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"Validator accepted unsafe mutation: {mutation}")


def readme(version: str) -> str:
    return f'''# {LABEL}

These are Django {version} server-rendered Admin responses, sanitized for a public, static demonstration. They are not a running admin and contain no production data.

## Run / regenerate

From the repository root, use a fresh Python process with a supported Django version and Beautiful Soup:

```sh
python -m pip install "beautifulsoup4>=4.12,<5"
python scripts/export_admin_samples.py
python scripts/export_admin_samples.py --check exported-admin-samples
python scripts/test_export_safety.py --export-dir exported-admin-samples
```

Use the intended Django environment when running the command; the exporter records the exact installed version rather than claiming compatibility from a version string. It inserts `src/` and `demo/` into its import path, configures SQLite `:memory:` before `django.setup()`, migrates only this ephemeral database, creates synthetic models and an unusable-password administrator, then obtains responses with Django TestClient. It does not read, migrate or write `demo/db.sqlite3`. Validation-error pages are real invalid POST responses; generation verifies the model data is unchanged by those POSTs. No HTTP listener, production account, saved browser session, or external service is used.

## Portable files

- `index.html`: gallery
- `light/`, `dark/`, `auto/`, `compact-light/`, `compact-dark/`, `compact-auto/`, `native/`: eight pages each (`index`, `changelist`, `members`, `news`, `changeform`, `validation-error`, `delete-confirm`, `login`)
- Optional `--with-palettes`: 48 additional representative pages, eight palettes × light/dark × dashboard/product list/login. Standard density only; auto/compact/native combinations retain default coverage.
- `static/admin/`: exact Django CSS and image assets, with upstream attribution
- `static/nova_admin/`: actual theme assets from this checkout
- `static/catalog/`: demo-owned enterprise branding/density overrides, business-image geometry and three bundled synthetic WebP sheets
- `static/sample.css`: export-only disclosure/navigation styles
- `THIRD_PARTY_NOTICES.txt`, `DJANGO-LICENSE.txt`, `NOVA-LICENSE.txt` and the bundled Select2 license: preserved redistribution attribution and license text
- `manifest.json`: source versions, template names, source/output hashes, render status and sanitization checks

Copy the entire directory unchanged under any URL prefix. Every navigation URL is relative and targets a generated HTML fixture; each static URL resolves within this directory. Unavailable links are disabled rather than pointing to real admin endpoints. A local preview can use `python -m http.server 8765 --directory exported-admin-samples`, then open `http://127.0.0.1:8765/`. No build process is needed. `--output PATH` supports a different empty output directory; an existing non-empty directory is replaced only if it contains this export's identity marker.

## Intentional safety and fidelity limits

- The visible Chinese disclosure is `{LABEL}` on every page
- All people, products, news items, categories, tags and inline rows are synthetic; portrait subjects are fictional adults; IDs have meaning only in the ephemeral database
- Real Django view/template output is retained, with disclosure and safe fixture navigation added
- Original semantic `<form>` tags, IDs and classes are retained so Django's form-dependent responsive CSS survives. Every form is marked `data-sample-form="inert"`; every control is disabled and unnamed. Hidden fields, CSRF tokens, authentication/session metadata, password/file inputs, form action/method/encoding/target attributes, external form associations and live URLs are removed. Former password/file inputs become blank, disabled text placeholders; no credentials survive
- Scripts, event handlers, executable embeds, active data attributes and external CSS imports are removed or rejected. No JavaScript files are included. The exact CSP appears in `<head>` before resource-loading elements and independently disallows scripts, connections and all form submission (`form-action 'none'`). An absent action alone would be insufficient; the validator requires every layer of this contract
- Autocomplete, two-column many-to-many selection, dynamic inline insertion, actions, filters, theme preference submission, login, save and delete are intentionally inactive. Their full behavior belongs to the local Django app
- Image thumbnails are local, fixed-size, lazy semantic images with three 3×2 sheets and one missing-media example per list. Object links only survive where an exact read-only fixture exists; these pages do not open a live media preview or private media. The underlying Django demo uses existing permission-checked object change views. Static image failures retain a fixed placeholder and alternative text, without error-handler scripts.
- Native samples omit Nova and enterprise CSS/body classes while preserving the explicit host-project Chinese vocabulary/label policy, and use Django's native light baseline for deterministic comparison. Where a sidebar exists, the export sets `#main.shifted` and `aria-expanded=true`, the open state normally established by Django JavaScript; this is a visual-only stabilization
- The validation-error sample is produced by Django's ModelForm and inline formset validation, not manually written error markup
- `--check` checks the complete page inventory, labels, semantic inert forms, disabled controls, forbidden submission/association attributes, exact early-head CSP, URL containment/existence, native/themed distinction, token/endpoint residue, CSS URLs, SVG assets and forbidden file types. Export also runs adversarial sanitizer and validator mutation probes, and detects source changes during generation. `inert_forms` counts retained presentation forms; `functional_forms` must be zero

This file and `manifest.json` are provenance, not a claim of production readiness, full accessibility certification or dynamic widget testing.
'''


def capture_login_captcha(raw: str, client, output: Path, mode: str) -> str:
    """Freeze only the synthetic PNG, never a live key, answer input or endpoint."""
    soup = BeautifulSoup(raw, "html.parser")
    image = soup.select_one(".nova-captcha-image")
    if image is None:
        raise AssertionError("Optional CAPTCHA login did not render its image")
    source = image.get("src", "")
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not re.fullmatch(r"/admin/_captcha/image/[a-f0-9]{40}/", parsed.path):
        raise AssertionError("Unexpected CAPTCHA image endpoint")
    response = client.get(source)
    data = b"".join(response.streaming_content) if response.streaming else response.content
    if response.status_code != 200 or response.get("Content-Type") != "image/png" or not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 131072:
        raise AssertionError("Expected a bounded locally generated CAPTCHA PNG")
    name = f"captcha-login-{mode}.png"
    (output / "static" / "nova_admin" / name).write_bytes(data)
    image["src"] = "/static/nova_admin/" + name
    image["alt"] = "静态验证码图片，仅作界面样本，不能用于登录"
    return str(soup)


def export(output: Path, with_captcha=False, with_extensions=False, with_palettes=False):
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / "demo") or output.is_relative_to(ROOT / "src"):
        raise ValueError("Output must not replace the repository, source or demo database tree")
    if output.exists() and any(output.iterdir()) and not (output / MARKER).is_file():
        raise ValueError("Refusing to replace a non-empty directory without an export marker")
    sanitizer_self_test()
    django = configure_django(with_captcha=with_captcha, with_extensions=with_extensions)
    from django.conf import settings
    from django.db import connection
    from django.test import Client
    from catalog.models import Product, ProductVariant
    runtime_suffixes = {".py", ".html", ".css", ".js", ".po", ".mo", ".webp", ".svg", ".txt"}
    sources = sorted({path for directory in (ROOT / "src", ROOT / "demo") for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in runtime_suffixes and "__pycache__" not in path.parts})
    sources += [ROOT / "pyproject.toml", Path(__file__).resolve(), ROOT / "scripts" / "test_export_safety.py"]
    before_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources}
    user, product = create_synthetic_data()
    routes = {"/admin/": "index", "/admin/catalog/": "index", "/admin/catalog/product/": "changelist", "/admin/catalog/memberprofile/": "members", "/admin/catalog/newsitem/": "news", f"/admin/catalog/product/{product.pk}/change/": "changeform", f"/admin/catalog/product/{product.pk}/delete/": "delete-confirm", "/admin/login/": "login"}
    endpoints = {page: path for path, page in routes.items()}
    endpoints["index"] = "/admin/"
    endpoints["validation-error"] = endpoints["changeform"]
    invalid_data = {"name": "", "sku": product.sku, "price": "-1", "stock": "-3", "status": "active", "featured": "on", "category": "101", "tags": ["201"], "variants-TOTAL_FORMS": "3", "variants-INITIAL_FORMS": "2", "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000", "variants-0-id": "301", "variants-0-product": str(product.pk), "variants-0-name": "颜色", "variants-0-value": "", "variants-1-id": "302", "variants-1-product": str(product.pk), "variants-1-name": "尺寸", "variants-1-value": "标准版", "variants-2-name": "", "variants-2-value": "", "_save": "Save"}
    original_data = (list(Product.objects.values()), list(ProductVariant.objects.values()))
    render_records = []
    template_hashes = {}
    with tempfile.TemporaryDirectory(prefix="nova-admin-samples-") as temporary:
        stage = Path(temporary)
        (stage / MARKER).write_text("Synthetic inert Django Admin samples. Regenerate with scripts/export_admin_samples.py\n", encoding="utf-8")
        copy_static(stage)
        for directory, mode, palette, profile_pages in sample_profiles(with_palettes):
            settings.NOVA_ADMIN_DEFAULT_PALETTE = palette
            settings.NOVA_ADMIN_DEFAULT_MODE = theme_mode(mode)
            settings.PROJECT_ADMIN_COMPACT = mode.startswith("compact-")
            client = Client()
            client.force_login(user)
            session = client.session
            session["nova_admin_mode"] = theme_mode(mode)
            session["nova_admin_palette"] = palette
            session.save()
            (stage / directory).mkdir()
            profile_routes = {url: page for url, page in routes.items() if page in profile_pages}
            for page in profile_pages:
                response = Client().get(endpoints[page]) if page == "login" else client.post(endpoints[page], invalid_data) if page == "validation-error" else client.get(endpoints[page])
                if response.status_code != 200:
                    raise AssertionError(f"Unexpected {response.status_code} rendering {mode}/{page}")
                if page == "validation-error":
                    if not response.context["adminform"].form.errors or not any(formset.formset.errors for formset in response.context["inline_admin_formsets"]):
                        raise AssertionError("Expected real ModelForm AND inline-formset validation errors")
                    if (list(Product.objects.values()), list(ProductVariant.objects.values())) != original_data:
                        raise AssertionError("Invalid export POST unexpectedly changed data")
                original_html = response.content.decode("utf-8")
                if page == "login" and with_captcha:
                    original_html = capture_login_captcha(original_html, client, stage, directory)
                rendered = sanitize_html(original_html, mode=mode, page=page, django_version=django.get_version(), routes=profile_routes, palette=palette)
                original_form_count = len(BeautifulSoup(original_html, "html.parser").find_all("form"))
                rendered_form_count = len(BeautifulSoup(rendered, "html.parser").find_all("form"))
                if original_form_count != rendered_form_count:
                    raise AssertionError("Export must preserve original semantic form count")
                (stage / directory / f"{page}.html").write_text(rendered, encoding="utf-8")
                for template in response.templates:
                    origin = getattr(template, "origin", None)
                    if origin and Path(origin.name).is_file():
                        source = Path(origin.name).resolve()
                        if source.is_relative_to(ROOT):
                            identity = source.relative_to(ROOT).as_posix()
                        elif source.is_relative_to(Path(django.__file__).parent):
                            identity = "django/" + source.relative_to(Path(django.__file__).parent).as_posix()
                        else:
                            raise AssertionError("Template resolved outside the expected source trees")
                        template_hashes[identity] = sha256(source)
                render_records.append({"mode": mode, "palette": palette, "page": page, "file": f"{directory}/{page}.html", "status": response.status_code, "semantic_forms_preserved": original_form_count, "render_method": "POST (invalid, no writes)" if page == "validation-error" else "GET", "templates": sorted({template.name for template in response.templates if template.name})})
        (stage / "index.html").write_text(gallery(django.get_version(), with_palettes=with_palettes), encoding="utf-8")
        (stage / "README.md").write_text(readme(django.get_version()), encoding="utf-8")
        validation = validate_export(stage, with_palettes=with_palettes)
        after_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources}
        if before_hashes != after_hashes:
            raise RuntimeError("Sources changed while generating samples; rerun after edits are complete")
        import tomllib
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        manifest = {
            "format_version": 2, "palette_representatives": with_palettes, "label": LABEL, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {"django": django.get_version(), "python": sys.version.split()[0], "beautifulsoup4": importlib.metadata.version("beautifulsoup4"), "theme_project": project["name"], "theme_version": project["version"], "optional_extensions": with_extensions, "optional_captcha": importlib.metadata.version("django-simple-captcha") if with_captcha else None, "source_sha256": before_hashes, "rendered_template_sha256": dict(sorted(template_hashes.items()))},
            "data": {"provenance": "synthetic-only", "database": ":memory:", "real_database_accessed": False, "password": "unusable; no credential created", "persistent_business_writes": False, "media": "Three bundled synthetic sheets: fictional adult avatars, unbranded products and fictional editorial scenes; no remote URLs or private media", "fixed_product_timestamp_utc": "2026-10-01T12:00:00+00:00"},
            "rendered_pages": render_records, "visual_stabilization": ["Native theme fixed to light", "Server-rendered sidebars marked open (#main.shifted; aria-expanded=true)"], "safety_validation": validation,
            "output_sha256": {p.relative_to(stage).as_posix(): sha256(p) for p in sorted(stage.rglob("*")) if p.is_file()},
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if connection.settings_dict["NAME"] != ":memory:":
            raise AssertionError("Database isolation invariant changed")
        output.mkdir(parents=True, exist_ok=True)
        for existing in output.iterdir():
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        shutil.copytree(stage, output, dirs_exist_ok=True)
    verify_manifest(output)
    print(json.dumps({"output": str(output), "django": django.get_version(), **validation}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Output directory (empty or previously generated)")
    parser.add_argument("--check", type=Path, metavar="EXPORT_DIR", help="Validate an existing export without touching Django or any database")
    parser.add_argument("--with-captcha", action="store_true", help="Render optional CAPTCHA with synthetic local PNGs; requires the captcha extra")
    parser.add_argument("--with-extensions", action="store_true", help="Render the explicit local branding/navigation configuration; all exported controls remain inert")
    parser.add_argument("--with-palettes", action="store_true", help="Add 72 light/dark standard-density palette representatives (dashboard/list/login); preserve all 57 default/native pages")
    args = parser.parse_args()
    if args.check:
        sanitizer_self_test()
        result = validate_export(args.check.resolve())
        verify_manifest(args.check.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        export(args.output, with_captcha=args.with_captcha, with_extensions=args.with_extensions, with_palettes=args.with_palettes)


if __name__ == "__main__":
    main()
