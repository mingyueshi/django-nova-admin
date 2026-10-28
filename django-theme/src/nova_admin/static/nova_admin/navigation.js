/* Nova's optional, permission-filtered navigation. Django owns desktop sidebar
   visibility and every destination/permission. Native mode never loads this file. */
'use strict';
{
    const navigation = document.querySelector('body.nova-admin .nova-navigation');
    const originalFilter = navigation && navigation.querySelector('#nav-filter');
    if (originalFilter && !navigation.dataset.novaNavigationReady) {
        navigation.dataset.novaNavigationReady = 'true';
        // Django attaches anonymous model-only handlers before this deferred script
        // and offers no teardown hook. Replace only Nova's own input to establish
        // one filter owner; native mode and the sidebar toggle remain untouched.
        // Cloning preserves markup/labels/ARIA, but third-party listeners attached
        // to this optional Nova control before initialization are not supported.
        const focused = document.activeElement === originalFilter;
        const selection = [originalFilter.selectionStart, originalFilter.selectionEnd];
        const filter = originalFilter.cloneNode(true);
        originalFilter.replaceWith(filter);
        const MAX_NODES = 200;
        const MAX_QUERY = 200;
        const MAX_FAVORITES = 50;
        // These compact hashes identify preferences, not authorization or secrets.
        // Do not persist display names, destination URLs, or a copy of available_apps.
        const fingerprint = value => {
            let a = 2166136261;
            let b = 5381;
            for (let index = 0; index < value.length; index++) {
                const code = value.charCodeAt(index);
                a = Math.imul(a ^ code, 16777619);
                b = Math.imul(b, 33) ^ code;
            }
            return (a >>> 0).toString(16).padStart(8, '0') +
                (b >>> 0).toString(16).padStart(8, '0');
        };
        const normalize = value => value.trim().toLowerCase();
        const sections = Array.from(navigation.querySelectorAll('.nova-nav-section'));
        const apps = Array.from(navigation.querySelectorAll('.nova-nav-group'));
        const details = [...sections, ...apps];
        const keys = new Map();
        apps.forEach(app => keys.set(app, 'a:' + fingerprint(app.dataset.novaNavApp || '')));
        const sectionKeyCounts = new Map();
        sections.forEach(section => {
            const key = section.dataset.novaNavSection;
            sectionKeyCounts.set(key, (sectionKeyCounts.get(key) || 0) + 1);
        });
        sections.forEach(section => {
            const members = Array.from(section.querySelectorAll('.nova-nav-group'))
                .map(app => app.dataset.novaNavApp || '').sort();
            // Explicit keys survive label, ordering and membership changes.
            const identity = section.dataset.novaNavSection;
            const stable = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$/.test(identity || '') &&
                sectionKeyCounts.get(identity) === 1;
            keys.set(section, 's:' + fingerprint(stable ? 'key:' + identity : JSON.stringify(members)));
        });
        const records = apps.map(app => ({
            node: app,
            section: app.closest('.nova-nav-section'),
            title: normalize(app.querySelector('summary > span')?.textContent || ''),
            rows: Array.from(app.querySelectorAll('tbody > tr')).map(row => ({
                node: row,
                title: normalize((row.querySelector('.nova-nav-model-label') || row.querySelector('th[scope="row"]'))?.textContent || ''),
                key: row.dataset.novaNavModel || '',
                modelKey: row.dataset.novaModelKey || '',
            })),
        }));
        const sectionTitles = new Map(sections.map(section => [
            section, normalize(section.querySelector('summary > span')?.textContent || ''),
        ]));
        const signature = fingerprint(JSON.stringify(records.map(record => [
            keys.get(record.node), keys.get(record.section), record.rows.map(row => row.key).sort(),
        ]).sort()));
        const scope = navigation.dataset.novaNavScope || '';
        const scoped = /^[a-f0-9]{64}$/.test(scope);
        const storageKey = scoped ? 'nova.admin.navigation.v2.' + scope : '';
        const filterKey = scoped ? 'nova.admin.navigation.v1.' + scope : '';
        // v1 mixed automatic expansion with manual choices. Do not migrate it:
        // guessing which entries were intentional would reopen untouched menus.
        // Search is tab-scoped (like Django's original filter); collapse persists
        // across visits. Disabled/quota-limited/corrupt storage is never fatal.
        const read = (kind, limit, key = storageKey, version = 1) => {
            if (!key) return null;
            let raw;
            try {
                raw = window[kind].getItem(key);
            } catch (_) {
                return undefined; // Unread preferences must never be overwritten.
            }
            if (!raw || raw.length > limit) return null;
            try {
                const value = JSON.parse(raw);
                return value && value.version === version ? value : null;
            } catch (_) {
                return null; // Successfully read but malformed data can be reset.
            }
        };
        const write = (kind, value, key = storageKey) => {
            if (!key) return false;
            try {
                window[kind].setItem(key, JSON.stringify(value));
                return true;
            } catch (_) {
                // Navigation remains usable when browser storage is unavailable.
                return false;
            }
        };
        const stored = read('localStorage', 16000, storageKey, 2);
        // Favorites store bounded opaque model fingerprints, never labels/URLs.
        // All links remain server-rendered from this visit's permitted app list.
        const favoriteKey = storageKey ? 'nova.admin.favorites.v1.' + scope : '';
        const favoritesEnabled = navigation.dataset.novaFavoritesEnabled === 'true';
        const favoriteButtons = Array.from(navigation.querySelectorAll('[data-nova-favorite]'));
        const favoriteModels = new Set(favoriteButtons.map(button => fingerprint(button.dataset.novaFavorite)));
        const favoriteState = favoritesEnabled ? read('localStorage', 2000, favoriteKey) : null;
        const favorites = new Set(favoriteState && Array.isArray(favoriteState.models) &&
            favoriteState.models.length <= MAX_FAVORITES ? favoriteState.models.filter(key =>
                typeof key === 'string' && /^[a-f0-9]{16}$/.test(key) && favoriteModels.has(key)) : []);
        const shortcuts = Array.from(navigation.querySelectorAll('.nova-nav-shortcuts'));
        const visibleModels = new Map(records.flatMap(record => record.rows.map(row => [row.modelKey, row])));
        const updateShortcuts = () => {
            favoriteButtons.forEach(button => {
                const selected = favorites.has(fingerprint(button.dataset.novaFavorite));
                button.hidden = !favoritesEnabled || !favoriteKey;
                button.setAttribute('aria-pressed', String(selected));
                button.disabled = !selected && favorites.size >= MAX_FAVORITES;
                const star = button.querySelector('[aria-hidden="true"]');
                if (star) star.textContent = selected ? '★' : '☆';
            });
            shortcuts.forEach(section => {
                let visible = false;
                section.querySelectorAll('[data-nova-shortcut-model]').forEach(item => {
                    const key = item.dataset.novaShortcutModel;
                    const row = visibleModels.get(key);
                    const selected = !item.hasAttribute('data-nova-favorite-shortcut') ||
                        (favoritesEnabled && favoriteKey && favorites.has(fingerprint(key)));
                    item.hidden = !row || row.node.hidden || !selected;
                    visible = visible || !item.hidden;
                });
                section.hidden = !visible;
            });
        };
        const persistFavorites = () => {
            if (favoritesEnabled && favoriteState !== undefined) write('localStorage', {
                version: 1, models: Array.from(favorites).slice(0, MAX_FAVORITES),
            }, favoriteKey);
        };
        favoriteButtons.forEach(button => button.addEventListener('click', () => {
            if (!favoritesEnabled) return;
            const key = fingerprint(button.dataset.novaFavorite);
            if (favorites.has(key)) favorites.delete(key);
            else if (favorites.size < MAX_FAVORITES) favorites.add(key);
            persistFavorites();
            updateShortcuts();
        }));
        // An enabled page with zero permitted models must prune all old IDs.
        // Disabling the feature deliberately preserves its previous choices.
        if (favoritesEnabled && favoriteKey) persistFavorites();
        const decodeNodes = value => {
            const nodes = new Map();
            if (value && Array.isArray(value.nodes) && value.nodes.length <= MAX_NODES) value.nodes.forEach(entry => {
                if (Array.isArray(entry) && entry.length === 2 &&
                    typeof entry[0] === 'string' && /^(a|s):[a-f0-9]{16}$/.test(entry[0]) &&
                    typeof entry[1] === 'boolean') nodes.set(entry[0], entry[1]);
            });
            return nodes;
        };
        let savedNodes = decodeNodes(stored);
        // Route visibility is transient, separate from the user's stored choices.
        // Use server-rendered markers so host-specific menu ownership is retained.
        const currentPath = new Set(details.filter(item => item.matches('.current-app') ||
            item.querySelector('.current-app, .current-model, [aria-current="page"]')));
        const currentChoices = new Map();
        const effectiveOpen = item => currentPath.has(item) ?
            (currentChoices.has(item) ? currentChoices.get(item) : true) :
            savedNodes.get(keys.get(item)) === true;
        const openState = new Map();
        const setOpen = (item, value) => { item.open = value; };
        details.forEach(item => {
            const value = effectiveOpen(item);
            openState.set(item, value);
            setOpen(item, value);
        });
        // Only explicit clicks are saved. Unrelated untouched nodes stay closed.
        let openWriteFailed = false;
        const persistOpen = () => {
            // A failed initial read means existing choices are unknown. Keep
            // this page memory-only, including later clicks, until a fresh load
            // can read them. Never replace unread preferences with a partial map.
            if (stored === undefined) {
                openWriteFailed = true;
                return;
            }
            openWriteFailed = !write('localStorage', {
                version: 2,
                nodes: details.filter(item => savedNodes.has(keys.get(item))).slice(0, MAX_NODES)
                    .map(item => [keys.get(item), savedNodes.get(keys.get(item))]),
            });
        };
        let filtering = false;
        let previousQuery = null;
        const applyFilter = () => {
            filter.value = filter.value.slice(0, MAX_QUERY);
            const query = normalize(filter.value);
            if (storedFilter !== undefined) write('sessionStorage', {version: 1, signature, query: filter.value}, filterKey);
            if (query === previousQuery) return;
            let hasMatches = false;
            records.forEach(record => {
                const parentMatches = query && (record.title.includes(query) ||
                    (record.section && sectionTitles.get(record.section).includes(query)));
                let appMatches = false;
                record.rows.forEach(row => {
                    const match = !query || parentMatches || row.title.includes(query);
                    row.node.hidden = !match;
                    appMatches = appMatches || Boolean(match);
                });
                record.node.hidden = Boolean(query) && !appMatches;
                if (query && appMatches) setOpen(record.node, true);
                hasMatches = hasMatches || appMatches;
            });
            sections.forEach(section => {
                const match = records.some(record => record.section === section && !record.node.hidden);
                section.hidden = Boolean(query) && !match;
                if (query && match) setOpen(section, true);
            });
            if (!query && filtering) details.forEach(item => setOpen(item, openState.get(item)));
            filter.classList.toggle('no-results', Boolean(query) && !hasMatches);
            updateShortcuts();
            filtering = Boolean(query);
            previousQuery = query;
        };
        details.forEach(item => item.querySelector(':scope > summary')?.addEventListener('click', event => {
            if (event.defaultPrevented || event.button !== 0) return;
            // Native summaries synthesize click for Enter/Space as well as a
            // pointer. Record synchronously: queued toggle events can be lost on
            // immediate navigation or coalesced by rapid clicks. Keep native
            // keyboard/focus semantics without extra roles or ARIA state copies.
            event.preventDefault();
            const value = !item.open;
            setOpen(item, value);
            if (!filtering) {
                if (currentPath.has(item)) currentChoices.set(item, value);
                openState.set(item, value);
                savedNodes.set(keys.get(item), value);
                persistOpen();
            }
        }));
        ['input', 'change', 'keyup'].forEach(name => filter.addEventListener(name, event => {
            if (event.key === 'Escape') filter.value = '';
            applyFilter();
        }));
        // Django initializes earlier and may have applied its native stored filter
        // to these rows. Reset that initial display once; only Nova's handlers
        // are attached to the replacement input, so the two filters do not race.
        records.forEach(record => record.rows.forEach(row => { row.node.style.display = ''; }));
        const storedFilter = read('sessionStorage', 2000, filterKey);
        // A previous page's search must not hide this page's current location.
        // A fresh search remains available and clearing it restores in-page choices.
        filter.value = !currentPath.size && storedFilter && storedFilter.signature === signature &&
            typeof storedFilter.query === 'string' && storedFilter.query.length <= MAX_QUERY ?
            storedFilter.query : '';
        persistOpen(); // Prune stale nodes; saved state never creates DOM or links.
        applyFilter();
        const restoreStoredOpen = () => {
            if (openWriteFailed) return; // Do not replace unsaved in-page choices with stale storage.
            const latest = read('localStorage', 16000, storageKey, 2);
            if (latest === undefined) return; // Keep this page usable when storage is blocked.
            savedNodes = decodeNodes(latest);
            details.forEach(item => {
                const value = effectiveOpen(item);
                openState.set(item, value);
                if (!filtering) setOpen(item, value);
            });
        };
        window.addEventListener('pageshow', event => {
            // Back/Forward may restore the entire DOM without executing scripts.
            if (event.persisted) restoreStoredOpen();
        });
        window.addEventListener('storage', event => {
            if (event.key === storageKey || event.key === null) restoreStoredOpen();
        });
        if (focused) {
            filter.focus({preventScroll: true});
            filter.setSelectionRange(...selection);
        }
    }
    const mobileToggle = navigation && document.getElementById('nova-mobile-nav-toggle');
    if (mobileToggle && window.matchMedia && !mobileToggle.dataset.novaMobileReady) {
        mobileToggle.dataset.novaMobileReady = 'true';
        const viewport = window.matchMedia('(max-width: 767px)');
        const desktopToggle = document.getElementById('toggle-nav-sidebar');
        let mobile = false;
        let open = false;
        let desktopExpanded = navigation.getAttribute('aria-expanded');
        const show = value => {
            open = value;
            mobileToggle.setAttribute('aria-expanded', String(open));
            navigation.hidden = !open;
            navigation.setAttribute('aria-expanded', String(open));
        };
        const updateViewport = () => {
            const focused = document.activeElement;
            if (viewport.matches) {
                if (!mobile) desktopExpanded = navigation.getAttribute('aria-expanded');
                mobile = true;
                mobileToggle.hidden = false;
                // Preserve keyboard focus when zoom/rotation enters the mobile
                // layout while the user is already navigating the sidebar.
                show(open || navigation.contains(focused));
                if (focused === desktopToggle) mobileToggle.focus();
            } else {
                mobile = false;
                navigation.hidden = false;
                mobileToggle.hidden = true;
                if (desktopExpanded === null) navigation.removeAttribute('aria-expanded');
                else navigation.setAttribute('aria-expanded', desktopExpanded);
                // Django's main.shifted and stored desktop preference were never
                // changed. Do not leave focus in newly hidden mobile UI/sidebar.
                if (focused === mobileToggle ||
                    (navigation.contains(focused) && desktopExpanded === 'false')) {
                    desktopToggle?.focus();
                }
            }
        };
        mobileToggle.addEventListener('click', () => {
            if (!mobile) return;
            show(!open);
            if (!open) mobileToggle.focus();
        });
        const closeOnEscape = event => {
            if (!mobile || !open || event.key !== 'Escape' || event.defaultPrevented) return;
            // Keep Django/Nova's established first Escape-to-clear search. A
            // second Escape, or Escape elsewhere in the menu, closes disclosure.
            if (event.target.id === 'nav-filter' && event.target.value) return;
            event.preventDefault();
            show(false);
            mobileToggle.focus();
        };
        navigation.addEventListener('keydown', closeOnEscape);
        mobileToggle.addEventListener('keydown', closeOnEscape);
        viewport.addEventListener('change', updateViewport);
        updateViewport();
    }
}
