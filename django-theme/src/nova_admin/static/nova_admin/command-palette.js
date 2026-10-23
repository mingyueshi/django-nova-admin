/* Navigation destinations come only from this response's permission-filtered
   sidebar. No registry, request, history or menu storage belongs to this module. */
'use strict';
(() => {
    const nav = document.querySelector('body.nova-admin .nova-navigation');
    const trigger = document.querySelector('[data-nova-command-open]');
    const dialog = document.getElementById('nova-command-palette');
    if (!nav || !trigger || !dialog || dialog.dataset.novaCommandReady ||
        typeof dialog.showModal !== 'function' || typeof dialog.close !== 'function') return;
    const query = dialog.querySelector('[data-nova-command-query]');
    const list = dialog.querySelector('[data-nova-command-results]');
    const status = dialog.querySelector('[data-nova-command-status]');
    const empty = dialog.querySelector('[data-nova-command-empty]');
    const closeButton = dialog.querySelector('[data-nova-command-close]');
    if (!query || !list || !status || !empty || !closeButton) return;
    const normalize = value => value.normalize('NFKC').trim().toLowerCase();
    function localURL(raw) {
        if (typeof raw !== 'string' || !raw || raw.length > 2048 ||
            /[\u0000-\u0020\u007f\\]/.test(raw) || raw.startsWith('//')) return null;
        try {
            const url = new URL(raw, window.location.href);
            const decoded = decodeURIComponent(url.pathname);
            if (!['http:', 'https:'].includes(url.protocol) || url.origin !== window.location.origin ||
                url.username || url.password || url.search || url.hash || /[\u0000-\u0020\u007f\\]/.test(decoded) ||
                decoded.includes('//') || decoded.split('/').some(part => part === '.' || part === '..')) return null;
            return url;
        } catch (_) { return null; }
    }
    function collect() {
        const home = nav.querySelector('.nova-nav-home[href]');
        const base = home && localURL(home.getAttribute('href'));
        if (!base || !base.pathname.endsWith('/')) return [];
        const items = [{href: base.href, title: home.textContent.replace(/↗/g, '').trim(), app: ''}];
        const seen = new Set([base.href]);
        nav.querySelectorAll('.nova-nav-group').forEach(app => {
            const appName = app.querySelector('summary > span')?.textContent.trim() || '';
            // Add-only rows have no anchor in their row heading. Add links and
            // favorite/common duplicates are never used as list destinations.
            app.querySelectorAll('tbody > tr').forEach(row => {
                const anchor = row.querySelector('th[scope="row"] a[href]');
                const label = row.querySelector('.nova-nav-model-label');
                const url = anchor && localURL(anchor.getAttribute('href'));
                if (!url || !label || !url.pathname.startsWith(base.pathname) || seen.has(url.href)) return;
                seen.add(url.href);
                items.push({href: url.href, title: label.textContent.trim(), app: appName});
            });
        });
        return items;
    }
    if (!collect().length) return;
    dialog.dataset.novaCommandReady = 'true';
    const shortcut = trigger.querySelector('[data-nova-command-shortcut]');
    if (shortcut) shortcut.textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl+K';
    trigger.hidden = false;
    let opener = null;
    let composing = false;
    let selected = 0;
    let entries = [];
    let failed = false;
    const links = () => Array.from(list.querySelectorAll('a'));
    function select(index, focus = false) {
        const choices = links();
        if (!choices.length) { selected = 0; return; }
        selected = Math.max(0, Math.min(index, choices.length - 1));
        choices.forEach((link, item) => {
            link.tabIndex = item === selected ? 0 : -1;
            link.toggleAttribute('data-active', item === selected);
        });
        if (focus && choices[selected]) {
            choices[selected].focus();
            choices[selected].scrollIntoView?.({block: 'nearest'});
        }
    }
    function render() {
        const terms = normalize(query.value.slice(0, 200)).split(/\s+/).filter(Boolean);
        const matches = entries.filter(item => terms.every(term => normalize(item.app + ' ' + item.title).includes(term)));
        list.replaceChildren();
        matches.forEach(item => {
            const row = document.createElement('li');
            const link = document.createElement('a');
            link.href = item.href;
            const label = document.createElement('span');
            label.textContent = item.title;
            link.append(label);
            if (item.app) {
                const app = document.createElement('small');
                app.textContent = item.app;
                link.append(app);
            }
            link.addEventListener('click', event => {
                // Recheck the current DOM and site boundary before activation.
                if (!collect().some(current => current.href === item.href)) {
                    event.preventDefault();
                    entries = collect();
                    render();
                    query.focus();
                }
            });
            row.append(link);
            list.append(row);
        });
        empty.hidden = matches.length !== 0;
        status.textContent = (dialog.dataset.countMessage || '').replace('{count}', String(matches.length));
        select(0);
    }
    function reset() {
        query.value = '';
        entries = [];
        list.replaceChildren();
        status.textContent = '';
        composing = false;
    }
    function open() {
        if (failed || dialog.open) return;
        entries = collect();
        if (!entries.length) return;
        // A native close may have queued its event just before reopening.
        // Do not record a now-closed dialog descendant as the return target.
        opener = dialog.contains(document.activeElement) ? (opener || trigger) : document.activeElement;
        query.value = '';
        render();
        dialog.hidden = false;
        try { dialog.showModal(); query.focus(); }
        catch (_) { dialog.hidden = true; trigger.hidden = true; failed = true; opener = null; reset(); }
    }
    function finishClose() {
        dialog.hidden = true;
        reset();
        const returnTo = opener;
        opener = null;
        if (returnTo?.isConnected) returnTo.focus({preventScroll: true});
    }
    function close() {
        if (!dialog.open) return;
        dialog.close();
        // Native close events are queued. Clear this round synchronously so a
        // quick reopen cannot inherit its menu or be hidden by its close event.
        finishClose();
    }
    dialog.addEventListener('close', () => {
        if (!dialog.open) finishClose();
    });
    trigger.addEventListener('click', open);
    closeButton.addEventListener('click', close);
    dialog.addEventListener('cancel', event => { event.preventDefault(); if (!composing) close(); });
    dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
    });
    query.addEventListener('compositionstart', () => { composing = true; });
    query.addEventListener('compositionend', () => { composing = false; render(); });
    query.addEventListener('input', () => { if (!composing) render(); });
    dialog.addEventListener('keydown', event => {
        if (event.isComposing || composing || event.keyCode === 229) return;
        const choices = links();
        const index = choices.indexOf(document.activeElement);
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
        else if (event.key === 'ArrowDown' && (event.target === query || index >= 0)) {
            event.preventDefault(); if (choices.length) select(index < 0 ? 0 : (index + 1) % choices.length, true);
        } else if (event.key === 'ArrowUp' && (event.target === query || index >= 0)) {
            event.preventDefault();
            if (index === 0) query.focus();
            else select(index < 0 ? choices.length - 1 : index - 1, true);
        } else if (event.key === 'Enter' && event.target === query) {
            event.preventDefault(); choices[selected]?.click();
        } else if (event.key === 'Tab') {
            const focusable = [closeButton, query, ...choices.filter(link => link.tabIndex === 0)];
            const first = focusable[0], last = focusable[focusable.length - 1];
            if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
                event.preventDefault(); last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault(); first.focus();
            }
        }
    });
    document.addEventListener('keydown', event => {
        if (failed || event.defaultPrevented || event.isComposing || event.keyCode === 229 ||
            event.altKey || event.shiftKey || !(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k') return;
        // Leave editing/browser shortcuts alone, including rich-text/shadow inputs.
        if (document.designMode === 'on' || event.composedPath().some(node => node.matches?.(
            'input,textarea,select,[contenteditable],[role="textbox"],[role="combobox"]'))) return;
        event.preventDefault();
        open();
    });
    window.addEventListener('pagehide', () => { opener = null; close(); reset(); });
})();
