'use strict';
(() => {
    const {scope, model, sections} = document.currentScript.dataset;
    const form = document.querySelector('body.change-form #content-main > form');
    if (!form) return;

    const links = document.createElement('nav');
    links.className = 'nova-form-sections';
    links.setAttribute('aria-label', sections);
    const storagePrefix = scope && model ? 'nova.form.sections.v1.' + scope + '.' + model + '.' : '';
    const errors = Array.from(form.querySelectorAll('.errorlist')).filter(list => list.textContent.trim());
    function reveal(element) {
        for (let parent = element.parentElement; parent && parent !== form; parent = parent.parentElement) {
            if (parent.matches('details')) parent.open = true;
        }
    }
    errors.forEach(reveal);

    for (const heading of form.querySelectorAll('fieldset.module :is(.fieldset-heading, .inline-heading)[id]')) {
        const group = heading.closest('fieldset.module');
        const inline = group.closest('.inline-group');
        if ((inline && !heading.matches('.inline-heading')) || group.parentElement.closest('fieldset.module') ||
            group.closest('.empty-form, [hidden], .hidden') || !heading.getClientRects().length) continue;
        const details = group.querySelector(':scope > details');
        if (details && storagePrefix && !errors.some(error => group.contains(error))) {
            // Native heading IDs for main fieldsets are positional. Use their declared field names
            // so a permission-dependent insertion or reordering cannot inherit another group's state.
            const fields = Array.from(group.querySelectorAll('.form-row'))
                .flatMap(row => Array.from(row.classList).filter(name => name.startsWith('field-'))).sort();
            const identity = inline?.id || (fields.length && JSON.stringify(fields));
            if (identity) {
                const key = storagePrefix + identity;
                try {
                    const saved = sessionStorage.getItem(key);
                    if (saved === '1' || saved === '0') details.open = saved === '1';
                } catch (_) { /* Native disclosure still works without storage. */ }
                let previous = details.open;
                const remember = () => {
                    if (previous === details.open) return;
                    try {
                        sessionStorage.setItem(key, details.open ? '1' : '0');
                        previous = details.open;
                    } catch (_) { /* Tab-local preference only. */ }
                };
                details.addEventListener('toggle', remember);
                // A link or refresh can navigate before the native toggle event is dispatched.
                window.addEventListener('pagehide', remember);
            }
        }
        const link = document.createElement('a');
        link.href = '#' + encodeURIComponent(heading.id);
        link.textContent = heading.textContent.trim();
        heading.tabIndex = -1;
        link.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            reveal(heading);
            heading.focus({preventScroll: true});
        });
        links.append(link);
    }
    if (links.childElementCount > 1) {
        const first = form.querySelector('fieldset.module, .inline-group');
        if (first) first.before(links);
    }

    // Wait for Django's add-form autofocus and enhanced widgets before selecting the error target.
    if (errors.length) {
        const focusError = () => {
            const error = errors[0];
            const container = error.closest('.fieldBox, .errors, td, .form-row');
            const field = container?.querySelector('[aria-invalid="true"]');
            if (field && !field.disabled && field.getClientRects().length) field.focus();
            if (field && document.activeElement === field) return;
            error.tabIndex = -1;
            error.focus();
        };
        if (document.readyState === 'complete') focusError();
        else window.addEventListener('load', focusError, {once: true});
    }
})();
