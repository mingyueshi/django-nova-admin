# Text and code editors in the admin

Nova stays a presentation theme: it never bundles a third-party editor, and the
package ships no editor runtime. Hosts choose their own editor for rich
content fields. Two supported paths:

## Path 1 · opt-in Markdown toolbar (`NOVA_ADMIN_MARKDOWN`)

A zero-dependency, locally served toolbar for plain textareas. Off by default;
no files load until the host explicitly enables it:

```python
NOVA_ADMIN_MARKDOWN = True
```

Mark the textareas that should receive the toolbar through the widget of the
model form; unmarked textareas are untouched:

```python
class ArticleForm(forms.ModelForm):
    class Meta:
        widgets = {
            "body": forms.Textarea(attrs={"data-nova-markdown": True}),
        }
```

Behavior and boundaries:

- Buttons (bold, italic, inline code, link, heading, list, quote) insert
  Markdown syntax around the current selection and keep it selected. Labels are
  translated (`Nova Admin` catalog) and served through `json_script`, so no
  inline script and no CSP exception is needed.
- The toolbar is injected by `markdown.js` only for `body.nova-admin` pages
  that are not popups. Disabled and readonly textareas never change. Re-running
  the script is idempotent.
- Without JavaScript nothing renders: the form degrades to the plain textarea,
  and the saved value stays the same text either way. The host remains
  responsible for parsing and rendering Markdown server-side.
- Changing textarea values programmatically dispatches a bubbling `input`
  event, so host-side autosave or preview listeners keep working.
- Styling uses existing admin tokens (`--border-color`, `--darkened-bg`,
  `--body-fg`, `--link-fg`, `--nova-action-radius`), so the toolbar follows
  every palette and the light/dark appearance without extra mapping. No editor
  asset is rendered in `native` mode, popups, or when the theme is disabled.
- A malformed setting fails loudly: `NOVA_ADMIN_MARKDOWN` must be a boolean,
  reported as `nova_admin.W004` by the system check.

## Path 2 · rich text editors brought by the host

For CKEditor, TinyMCE, TipTap and similar packages the theme deliberately does
not ship an adapter. Integration guidance:

1. Install the editor package in the host project and attach it through the
   widget. Load the editor skin after `nova_admin/presets.css`; the documented
   order is `theme.css` → `tokens.css` → `presets.css` → host CSS, and later
   host rules keep precedence.
2. Map the editor skin to Nova tokens for dark mode. The tokens exposed on
   `body.nova-admin` (`--body-bg`, `--body-fg`, `--secondary`, `--hairline-color`,
   `--border-color`, and the palette surface variables) are the supported hook
   points. iframe-based editors need the host to push these values across the
   frame boundary themselves; Nova never reaches into foreign documents.
3. Sanitize rich-text HTML on the server before storing or rendering. Nova
   performs no sanitization and adds no allowlist.
4. Review the host CSP: editor packages often need style or frame allowances.
   Nova's own assets stay nonce-friendly and locally served.

## What this intentionally does not do

- No editor runtime, no CDN, no remote fonts: the package keeps zero network
  dependencies.
- No storage of editor content or history; the toolbar only edits the visible
  textarea value.
- No widening of the supported Python/Django matrix: editor packages are host
  dependencies and their compatibility is the host's to verify.
- The static preview demo shows the interaction pattern with a demonstration
  toolbar; that code is not part of the distributable package.
