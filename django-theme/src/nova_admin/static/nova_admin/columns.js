'use strict';
(() => {
    const panel = document.querySelector('.nova-columns');
    if (!panel || typeof window.fetch !== 'function') return;
    const form = panel.querySelector('form');
    const list = form.querySelector('ol');
    const items = () => Array.from(list.children);
    const key = item => item.querySelector('[name="order"]').value;
    const checkbox = item => item.querySelector('[name="visible"]');
    const defaults = items().sort((a, b) => Number(a.dataset.defaultIndex) - Number(b.dataset.defaultIndex));
    const status = form.querySelector('[role="status"]');
    const table = document.querySelector('#result_list');
    const rows = [];
    if (table) {
        const header = table.tHead?.rows[0];
        if (!header) return;
        const headings = Array.from(header.cells);
        const positions = defaults.map(item => headings.findIndex(cell => cell.classList.contains('column-' + key(item))));
        if (positions.includes(-1)) return;
        for (const row of [header, ...Array.from(table.tBodies).flatMap(body => Array.from(body.rows))]) {
            // Django renders non-field validation errors in a separate spanning row.
            if (row.cells.length === 1 && row.cells[0].hasAttribute('colspan')) continue;
            const cells = new Map(defaults.map((item, i) => [key(item), row.cells[positions[i]]]));
            if (defaults.some(item => {
                const cell = cells.get(key(item));
                return !cell || (row !== header && (
                    !cell.classList.contains('field-' + key(item)) ||
                    cell.querySelector('input:not([type="hidden"]), select, textarea, .errorlist')
                ));
            })) return;
            rows.push({row, cells, positions});
        }
    }

    function apply() {
        const ordered = items();
        for (const {row, cells, positions} of rows) {
            const slots = positions.map(i => row.cells[i]);
            const targets = ordered.map(item => cells.get(key(item)));
            if (targets.some((cell, i) => cell !== slots[i])) {
                const markers = slots.map(cell => {
                    const marker = document.createComment('');
                    cell.before(marker);
                    return marker;
                });
                markers.forEach((marker, i) => marker.replaceWith(targets[i]));
            }
            ordered.forEach((item, i) => targets[i].toggleAttribute('data-nova-column-hidden', !checkbox(item).checked));
        }
        table?.dispatchEvent(new Event('nova:columns-changed'));
    }

    function updateButtons() {
        for (const item of items()) {
            item.querySelector('[data-move="-1"]').disabled = !item.previousElementSibling;
            item.querySelector('[data-move="1"]').disabled = !item.nextElementSibling;
        }
    }
    form.addEventListener('click', event => {
        const button = event.target.closest('button[data-move]');
        if (!button) return;
        const item = button.closest('li');
        if (button.dataset.move === '-1') item.previousElementSibling?.before(item);
        else item.nextElementSibling?.after(item);
        updateButtons();
        (button.disabled ? item.querySelector('button:not(:disabled)') : button)?.focus();
        status.textContent = '';
    });
    form.addEventListener('change', () => { status.textContent = ''; });
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (form.getAttribute('aria-busy') === 'true') return;
        const action = event.submitter?.value || 'save';
        const data = new FormData(form);
        data.set('_nova_columns', action);
        form.setAttribute('aria-busy', 'true');
        const focused = document.activeElement;
        const controls = form.querySelectorAll('button, input[type="checkbox"]');
        controls.forEach(el => { el.disabled = true; });
        status.textContent = '';
        try {
            const response = await fetch(form.action, {
                method: 'POST', body: data, mode: 'same-origin', redirect: 'error',
            });
            if (!response.ok || (await response.json()).saved !== true) throw new Error();
            if (action === 'reset') {
                for (const item of defaults) {
                    checkbox(item).checked = true;
                    list.append(item);
                }
            }
            apply();
            status.textContent = form.dataset.saved;
        } catch {
            status.textContent = form.dataset.error;
        } finally {
            form.removeAttribute('aria-busy');
            controls.forEach(el => { el.disabled = false; });
            updateButtons();
            if (form.contains(focused) && document.activeElement === document.body) {
                focused.focus({preventScroll: true});
            }
        }
    });
    updateButtons();
    apply();
    panel.hidden = false;
})();
