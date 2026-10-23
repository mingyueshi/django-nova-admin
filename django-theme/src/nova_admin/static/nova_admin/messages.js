/* Enhance existing message nodes in place. Never copy/store message content. */
'use strict';
(() => {
    const root = document.querySelector('body.nova-admin [data-nova-messages]');
    if (!root || root.dataset.novaMessagesReady ||
        getComputedStyle(root).getPropertyValue('--nova-messages-available').trim() !== '1') return;
    root.dataset.novaMessagesReady = 'true';
    function focusable(element) {
        if (!element.isConnected || element.tabIndex < 0 || element.matches(':disabled,[disabled]') ||
            element.closest('[hidden],[inert],[aria-hidden="true"],[aria-disabled="true"]')) return false;
        for (let parent = element; parent; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' ||
                Number(style.opacity || 1) === 0 || style.contentVisibility === 'hidden' ||
                (style.clip && style.clip !== 'auto') || (style.clipPath && style.clipPath !== 'none')) return false;
        }
        return Array.from(element.getClientRects()).some(rect => rect.width > 1 && rect.height > 1);
    }
    const targets = () => Array.from(root.querySelectorAll('a[href],button')).filter(focusable);
    function focusTarget(element) {
        if (!focusable(element)) return false;
        try { element.focus({preventScroll: true}); }
        catch (_) { return false; }
        return document.activeElement === element;
    }
    function focusMain() {
        const main = document.getElementById('content-start') || document.getElementById('content');
        if (!main) return;
        const previous = main.getAttribute('tabindex');
        if (previous === null) {
            main.tabIndex = -1;
            main.addEventListener('blur', () => main.removeAttribute('tabindex'), {once: true});
        }
        main.focus({preventScroll: true});
    }
    for (const group of root.querySelectorAll(':scope > [data-nova-message-group]')) {
        const toggle = group.querySelector(':scope > .nova-message-heading > [data-nova-message-toggle]');
        const list = group.querySelector(':scope > [data-nova-message-list]');
        const count = group.querySelector('[data-nova-message-count]');
        const level = group.querySelector('[data-nova-message-level]');
        if (!toggle || !list || !count || !level) continue;
        toggle.hidden = false;
        toggle.addEventListener('click', () => {
            const collapse = !list.hidden;
            if (collapse && list.contains(document.activeElement)) toggle.focus({preventScroll: true});
            list.hidden = collapse;
            toggle.setAttribute('aria-expanded', String(!collapse));
            const label = collapse ? root.dataset.expandLabel : root.dataset.collapseLabel;
            toggle.textContent = label;
            toggle.setAttribute('aria-label', label + ': ' + level.textContent);
        });
        for (const item of list.querySelectorAll(':scope > [data-nova-message-item]')) {
            const close = item.querySelector(':scope > [data-nova-message-dismiss]');
            if (!close) continue;
            close.hidden = false;
            close.addEventListener('click', () => {
                const restore = item.contains(document.activeElement);
                const before = targets();
                const index = before.indexOf(document.activeElement);
                item.remove();
                const remaining = list.querySelectorAll(':scope > [data-nova-message-item]').length;
                count.textContent = String(remaining);
                if (!remaining) group.remove();
                const empty = !root.querySelector(':scope > [data-nova-message-group]');
                if (empty) root.remove();
                if (restore) {
                    const candidates = [...before.slice(index + 1), ...before.slice(0, index).reverse()];
                    if (!candidates.some(focusTarget)) focusMain();
                }
            });
        }
    }
})();
