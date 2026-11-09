# Recent additions review · 2026-11-09

## Scope

Reviewed `main` at `9a5e7b4dc6ccf4f0597846eadc33f8f21e7f6264` in a fresh cloud checkout, preserving existing workspaces. Recent additions include article editing and optional Markdown controls, nine additional light/dark palettes, and workflow demonstrations (import, board, approvals, tree, calendar, column preferences, recycle bin, task progress, notifications, bilingual copy and inline editing).

The workflow pages are synthetic previews, not production Django workflow endpoints. This patch does not change authentication, database schemas, permissions, dependencies or package versions, and does not publish or deploy anything.

## Confirmed and corrected

- **Inline editing:** typing now exposes save/revert immediately without replacing active inputs, selections or pending click targets. Discard-all restores the most recently saved values instead of overwriting the baseline. Invalid stock keeps focus and exposes an associated accessible error; unsafe integers are rejected.
- **Column preferences:** hidden columns remain available to re-enable; reload preserves the exact saved subset and order. Invalid saved configurations fall back to defaults. Failed persistence reports that the change is current-page only.
- **Tree and calendar:** expand-all visits grandchildren after a full collapse. Month changes discard the old month's date selection.
- **Task lifecycle and reset:** leaving tasks pauses their state and clears their interval. Returning requires explicit resume. Global reset also restores flow state and the in-memory column cache, rather than only removing storage keys.
- **Django Markdown:** each marked textarea gets its own toolbar, including multiple fields sharing a form row. Existing buttons respect subsequent readonly/disabled changes and disabled fieldsets. Empty inline templates remain pristine; real `formset:added` rows receive working handlers. Only boolean `True` enables the feature; malformed settings still warn and remain off.
- **Export safety gate:** the palette inventory test still expected 96 representative/153 total pages after nine new palettes added 54 pages. Updated the strict contract to 150 representative/207 total pages; no safety checks were removed or relaxed. Future export help/README text now reflects the current inventory. Existing generated sample bytes were not regenerated.

## Cloud validation

- Node 24.22.1 / npm 11.9.0: clean lockfile install; complete `npm test` passed, including formatting and syntax checks, 21 suites and 1,564 front-end checks. Flow coverage increased 51 → 75.
- Theme JavaScript: 309 checks passed, including three installed Django sidebar versions, command palette, appearance, changelist, print, messages, Markdown (10 → 15), CAPTCHA and dialog tests.
- Python 3.12.14 with Django 5.2.17, 6.0.8 and 6.1.1: each core source run discovered 444 tests, with 441 passing and three optional-integration skips. The new Markdown wiring test is included. No claim of the complete supported Python/wheel/CAPTCHA matrix is made.
- Actual Django jQuery and inline scripts from all three versions were exercised with two newly added Markdown inline rows: independent field IDs, management counts and formatting actions passed without altering the empty template or original row.
- CI/support script tests: 105 passed. Matrix runner tests: 25 passed.
- Palette role-contrast checks: 4,575 passed. CSS budget passed without CSS changes.
- Export safety: 23 tests passed after correcting the stale inventory. Export checker verified 207 HTML pages, 4,522 inert controls, 660 inert forms, zero functional forms/scripts/live endpoints/external requests.
- Independent review of implementation changes found no blocking regression. Local DOM tests are not a browser rendering or assistive-technology certification.

The cloud browser could not reach the container's loopback preview (`ERR_CONNECTION_REFUSED`). Real browser acceptance is therefore outstanding rather than reported as passed. The CI matrix uses different pinned runtime patch versions and must be checked on the eventual pushed commit separately.

## Local acceptance on Mac mini

Use a clean checkout of the final commit; preserve any uncommitted local work. Do not replace a running production environment or database.

1. Run `npm ci`, then `npm run dev` and open `http://127.0.0.1:4173/` in Safari and Chrome.
2. On `#inline`, type a stock value and click Save once without first clicking elsewhere. Confirm one save, stable cursor while typing, error focus for a negative value, and that discard-all restores saved stock/status/Chinese remarks. Repeat using Tab and Chinese IME.
3. On `#columns`, hide a column, reload, then re-enable it. Reorder columns and reload again. Confirm at least one column remains visible.
4. On `#tree`, collapse all then expand all and verify the nested backpack node. Change months after selecting a calendar day. Start a task, leave, return and verify paused state until Continue. Reset demo state and verify all flow defaults return.
5. In an isolated Django demo or host staging configuration with `NOVA_ADMIN_MARKDOWN = True`, mark two textareas in the same row and a dynamic inline textarea. Add two inlines, format each independently, then test a field made readonly/disabled by the host. Verify normal save/validation, keyboard focus and screen-reader announcements. Do not enable the feature globally or change production data merely for acceptance.
6. Spot-check new palettes in light/dark modes and narrow Safari viewport. Existing CSS contrast calculations do not certify focus visibility, native widgets or VoiceOver behavior.

These are verification tasks, not authorization to release or deploy the patch.
