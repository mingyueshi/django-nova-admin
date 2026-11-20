/* Keep Django's table, links and bound form controls in place. */
'use strict';
(() => {
    const labels = document.currentScript.dataset;
    const table = document.querySelector('#changelist-form .results > #result_list');
    const header = table?.tHead?.rows[0];
    if (!header || table.tHead.rows.length !== 1 || table.querySelector(':scope > colgroup')) return;
    const headings = Array.from(header.cells);
    if (headings.some(cell => cell.colSpan !== 1 || cell.rowSpan !== 1)) return;
    const business = headings.filter(cell => !cell.matches('.action-checkbox-column') && !cell.querySelector('#action-toggle'));
    const first = business.find(cell => cell.getClientRects().length);
    if (!first) return;
    first.classList.add('nova-pinned');
    for (const body of table.tBodies) {
        for (const row of body.rows) {
            const cell = row.cells[first.cellIndex];
            if (row.cells.length === headings.length && cell && !cell.hasAttribute('colspan')) {
                cell.classList.add('nova-pinned');
            }
        }
    }

    // Preferences move the actual header nodes. Key widths by those nodes, never by a visual index.
    const widths = new Map();
    const automatic = new Map();
    const handles = new Map();
    const viewport = table.parentElement;
    // Leave room to reach the other columns, including after a change in viewport size.
    const pinnedLimit = () => Math.max(64, Math.floor(viewport.clientWidth * 0.65));
    function measure() {
        table.classList.remove('nova-sized');
        for (const cell of headings) automatic.set(cell, cell.getBoundingClientRect().width);
    }
    function layout() {
        let total = 0;
        for (const cell of headings) {
            if (!automatic.get(cell)) continue;
            let width = widths.get(cell) ?? automatic.get(cell);
            if (cell === first && widths.has(cell)) width = Math.min(width, pinnedLimit());
            cell.style.setProperty('--nova-column-width', width + 'px');
            handles.get(cell)?.setAttribute('aria-valuenow', Math.round(width));
            total += width;
        }
        table.style.setProperty('--nova-table-width', total + 'px');
        table.classList.toggle('nova-sized', widths.size > 0);
    }
    function reset(cell) {
        widths.delete(cell);
        measure();
        layout();
    }
    table.addEventListener('nova:columns-changed', () => {
        measure();
        layout();
    });
    if (window.ResizeObserver) {
        new ResizeObserver(() => {
            if (widths.has(first)) layout();
        }).observe(viewport);
    }

    for (const cell of business) {
        const title = cell.querySelector('.text')?.textContent.trim();
        if (!title) continue;
        const handle = document.createElement('span');
        handle.className = 'nova-column-grip';
        handle.tabIndex = 0;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'vertical');
        handle.setAttribute('aria-controls', table.id);
        handle.setAttribute('aria-label', labels.resize + ' · ' + title);
        handle.title = labels.help;
        handle.setAttribute('aria-description', labels.help);
        const minimum = Math.max(64, (parseFloat(getComputedStyle(cell.querySelector('.nova-sort-heading') || cell).minWidth) || 0) + 12);
        const maximum = () => cell === first ? Math.max(minimum, pinnedLimit()) :
            Math.max(1600, minimum, Math.ceil(automatic.get(cell) || 0));
        handle.setAttribute('aria-valuemin', minimum);
        const updateValue = () => {
            const value = Math.round(cell.getBoundingClientRect().width);
            handle.setAttribute('aria-valuemax', Math.max(value, maximum()));
            handle.setAttribute('aria-valuenow', value);
        };
        handle.addEventListener('focus', updateValue);
        handles.set(cell, handle);
        cell.append(handle);
        updateValue();

        const direction = getComputedStyle(cell).direction === 'rtl' ? -1 : 1;
        function resize(value) {
            if (!widths.size) measure();
            widths.set(cell, Math.round(Math.max(minimum, Math.min(maximum(), value))));
            layout();
        }
        let drag = null;
        handle.addEventListener('pointerdown', event => {
            if (!event.isPrimary || event.button !== 0) return;
            handle.setPointerCapture(event.pointerId);
            handle.focus({preventScroll: true});
            drag = {id: event.pointerId, x: event.clientX, start: cell.getBoundingClientRect().width, previous: widths.get(cell)};
            event.preventDefault();
        });
        handle.addEventListener('pointermove', event => {
            if (drag?.id === event.pointerId && (event.clientX !== drag.x || widths.has(cell))) {
                resize(drag.start + (event.clientX - drag.x) * direction);
            }
        });
        handle.addEventListener('pointerup', event => {
            if (drag?.id === event.pointerId) drag = null;
        });
        handle.addEventListener('lostpointercapture', event => {
            if (drag?.id !== event.pointerId) return;
            if (drag.previous === undefined) reset(cell);
            else resize(drag.previous);
            drag = null;
        });
        handle.addEventListener('dblclick', () => reset(cell));
        handle.addEventListener('keydown', event => {
            if (event.altKey || event.ctrlKey || event.metaKey) return;
            if (event.key === 'Home') reset(cell);
            else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                const delta = event.key === 'ArrowLeft' ? -16 : 16;
                resize(cell.getBoundingClientRect().width + delta * direction);
            } else return;
            event.preventDefault();
        });
    }
})();
