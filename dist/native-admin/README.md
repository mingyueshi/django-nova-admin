# 真实 Django 模板渲染样本

These are Django 6.1.1 server-rendered Admin responses, sanitized for a public, static demonstration. They are not a running admin and contain no production data.

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
- Optional `--with-palettes`: 36 additional representative pages, six palettes × light/dark × dashboard/product list/login. Standard density only; auto/compact/native combinations retain default coverage.
- `static/admin/`: exact Django CSS and image assets, with upstream attribution
- `static/nova_admin/`: actual theme assets from this checkout
- `static/catalog/`: demo-owned enterprise branding/density overrides, business-image geometry and three bundled synthetic WebP sheets
- `static/sample.css`: export-only disclosure/navigation styles
- `THIRD_PARTY_NOTICES.txt`, `DJANGO-LICENSE.txt`, `NOVA-LICENSE.txt` and the bundled Select2 license: preserved redistribution attribution and license text
- `manifest.json`: source versions, template names, source/output hashes, render status and sanitization checks

Copy the entire directory unchanged under any URL prefix. Every navigation URL is relative and targets a generated HTML fixture; each static URL resolves within this directory. Unavailable links are disabled rather than pointing to real admin endpoints. A local preview can use `python -m http.server 8765 --directory exported-admin-samples`, then open `http://127.0.0.1:8765/`. No build process is needed. `--output PATH` supports a different empty output directory; an existing non-empty directory is replaced only if it contains this export's identity marker.

## Intentional safety and fidelity limits

- The visible Chinese disclosure is `真实 Django 模板渲染样本` on every page
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
