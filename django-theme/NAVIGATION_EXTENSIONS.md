# Optional navigation extensions

Nova uses the existing `AdminSite` and its already permission-filtered
`available_apps`. It does not register models, invent destinations, fetch a
second app list, or count model rows automatically. All extensions below are
opt-in and disappear with native mode, `NOVA_ADMIN_NAVIGATION = False`, or
`NOVA_ADMIN_ENABLED = False`.

```python
NOVA_ADMIN_NAVIGATION = True
NOVA_ADMIN_NAV_FAVORITES = True  # Default: False
NOVA_ADMIN_NAV_COMMON_MODELS = ["catalog.product", "catalog.category"]  # Default: ()
NOVA_ADMIN_NAV_ICONS = {
    "catalog": "folder",
    "catalog.product": "box",
    "catalog.category": "tag",
}  # Default: {}
```

Keys use the app label and lowercase model object name. Unknown, unregistered,
unpermitted, duplicate, and add-only models do not become shortcuts. Common
models retain configuration order, with at most 50 configured entries. The
original application/model navigation remains available. Unlinked labels stay
unlinked. Original native add URLs and permissions are preserved.

## Browser-local favorites

Each permitted model list gets a keyboard-accessible star button with
`aria-pressed`. Selected models appear under Favorites; common models are the
project-configured shortcuts above it. Search filters both the main navigation
and shortcuts using model/application/group names; count text is not searched.

Favorites are local to this browser and this authenticated user/AdminSite. The
server derives an opaque scope using its secret, the user model and primary key,
and the site's index URL. Browser storage receives at most 50 compact model
fingerprints under `nova.admin.favorites.v1.<opaque-scope>`, never a user ID,
username, destination URL, or display label. The identifiers are preference
keys, not authorization tokens. Rotating `SECRET_KEY` resets the browser scope.

Each render uses only current server-provided links. Revoked models are removed
from stored favorites on the next visit and cannot be reconstructed from old
storage, including when the user has no remaining list permissions. Temporarily
disabling the favorites feature preserves saved choices until it is enabled
again. Different users or site index URLs do not share preferences. Clearing
site data clears favorites. These preferences do not sync across devices.
Browser extensions and other scripts on the same origin can access local
storage, so this is not a confidentiality boundary or suitable for shared
accounts. The 50-favorite limit disables additional unselected star buttons
until a favorite is removed.

With JavaScript disabled, common models and native navigation still work; star
buttons and the browser-only Favorites section remain hidden. Unavailable,
corrupt, oversized, or quota-limited storage is harmless. With blocked storage,
favorites work for the current page. Without an authenticated opaque scope,
favorites remain hidden and nothing is persisted. Public static mockups should
use a synthetic scope unrelated to any real account, or omit it entirely.

No endpoint or server mutation is added. Existing theme preference POSTs retain
their exact `AdminSite.admin_view`, same-site return validation, and Django CSRF
protection.

## Icons and one bulk badge provider

The catalog now includes 98 built-in business icons; all original names remain
valid. See the Chinese [icon catalog and integration guide](ICON_GUIDE.md), or
open `dist/icons.html` in the repository preview. Applications use `app_label`;
models use `app_label.lowercase_model_name`. Unknown or unset navigation names
continue to omit the icon without changing the link. Names select fixed,
package-owned SVG paths. Icon values
cannot inject HTML, template paths, CSS, links, or remote assets. Unknown values
are ignored. Icons are decorative; native labels remain the accessible names.

Optional project hooks accept a callable or a dotted callable path:

```python
NOVA_ADMIN_NAV_ICON_PROVIDER = "project.admin_navigation.icons"
NOVA_ADMIN_NAV_BADGE_PROVIDER = "project.admin_navigation.badges"
```

Both providers use `provider(request, available_apps) -> dict`. Each configured
provider is invoked once per rendered sidebar, and only if at least one app is
visible. They receive independent copies of the already permission-filtered app
list, including native model metadata. The reusable package adds no database
queries and does not call providers once per model. Providers are trusted host
code and are responsible for their own performance and data permissions.

Icon mappings can use app keys (`catalog`) and model keys (`catalog.product`).
Provider icon values override the static mapping for the same visible key. Badge
mappings use model keys only. Only integer counts from 0 through 2,147,483,647 are
rendered; booleans, strings, HTML, negative values, and unknown keys are ignored.
An add-only model cannot gain a badge. A missing badge key hides its count; zero
is displayed as zero. Provider errors, import failures, or malformed top-level
results leave native links usable and omit the affected metadata. Runtime error
logs name the provider setting without including exception text or user data.

Example using request-scoped data already computed by the host project:

```python
def badges(request, available_apps):
    allowed = {
        f"{app['app_label']}.{model['object_name'].lower()}"
        for app in available_apps
        for model in app["models"]
        if model.get("admin_url")
    }
    # Host-provided, precomputed counts from the same tenant/row visibility
    # rules as its ModelAdmin querysets. Missing data means no badge.
    counts = getattr(request, "admin_badge_counts", {})
    return {key: counts[key] for key in allowed if key in counts}

def icons(request, available_apps):
    return {"catalog": "folder", "catalog.product": "box"}
```

Permission-filtered navigation is model-level access, not proof that a user may
see every row. For row or tenant restrictions, aggregate the host's properly
scoped queryset or a user/tenant-scoped cache. Do not loop over all installed
models, call `.count()` per navigation model, or reuse one user's counts for
another. The host decides count meaning and freshness; Nova does not infer
whether it means all rows, pending work, or a filtered subset.

The demo provides the explicitly selected
`catalog.navigation.demo_product_badges` hook: it counts only Product, with one
count query, only when the passed list contains its permitted list destination.
It resolves the real `AdminSite` from the request's resolved admin view, rechecks
that site's and its registered ModelAdmin's permissions, and uses that exact
`ModelAdmin.get_queryset(request)`, preserving any tenant/row filtering there.
An unresolved site, unregistered model, or denied permission returns no badge;
there is no fallback to the default site's registry. Custom row rules outside
`get_queryset()` still need a project-specific hook. Authentication/permission
checks may perform their own usual queries. The sample is deliberately not
enabled in demo settings.

## Django integration checks

`python manage.py check` registers these nonfatal Nova warnings:

- `nova_admin.W001`: the theme context processor is missing from DjangoTemplates
- `nova_admin.W002`: an explicitly configured URL namespace mapping is malformed,
  or cannot resolve the existing site's index and its preference endpoint
- `nova_admin.W003`: malformed favorites/common-model/icon/provider configuration

Mount the optional preference URLs before the existing site's catch-all and map
its name if needed:

```python
path("staff/_theme/", include(for_admin(staff_site), namespace="staff_theme")),
path("staff/", staff_site.urls),

NOVA_ADMIN_URL_NAMESPACES = {"staff": "staff_theme"}
```

Nested instance names are supported, for example
`{"east:staff": "east:staff_theme"}`. Bare site names inside surrounding
application namespaces also work with Django's current-app resolution. Checks
never call a badge/icon provider or inspect the model registry. Omitting the
optional URL mapping/endpoint or explicitly using `{}` is supported and emits
no namespace warning. Remove stale explicit mappings to omit their controls.
The theme still renders if a configured endpoint is missing. Request-specific
URLconfs should use matching runtime mappings; system checks inspect the root
URLconf and cannot validate every middleware-selected route configuration.

## Verification

`tests.test_navigation_extensions` exercises permission-filtered hooks, provider
isolation, call counts, zero-query default behavior, bad metadata, failures,
escaping boundaries, no-permission/add-only shortcuts, and the demo count bound.
`tests.test_checks` covers registration, missing processors, optional routes,
malformed mappings, and named/nested sites. `scripts/test-navigation.mjs` covers
favorite state, scope isolation, revoked model pruning, filter behavior,
malformed/blocked storage, and unchanged native Django sidebar behavior.
