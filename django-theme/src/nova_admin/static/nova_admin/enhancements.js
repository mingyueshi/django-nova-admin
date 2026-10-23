/* Presentation only: preserve Django's forms, controls, GET data and help. */
'use strict';
(() => {
    if (!document.body.classList.contains('nova-admin')) return;
    const script = document.currentScript || document.querySelector('script[data-nova-search-placeholder]');
    const label = (name, fallback) => script?.dataset[name] || fallback;
    const input = document.querySelector('#changelist-search #searchbar');
    if (input && !input.hasAttribute('placeholder') && !input.disabled && !input.readOnly) {
        const help = document.getElementById('searchbar_helptext');
        const text = (help?.textContent || script?.dataset.novaSearchPlaceholder || '').trim().replace(/\s+/g, ' ');
        if (text) input.placeholder = text.length > 120 ? `${text.slice(0, 119)}…` : text;
    }

    const changelist = document.getElementById('changelist');
    if (!changelist || changelist.dataset.novaEnhanced) return;
    changelist.dataset.novaEnhanced = 'true';

    // Use Django's own links and state. In particular, primary and toggle have
    // different meanings for a secondary sort; never synthesize an `o` value.
    const sortedHeaders = changelist.querySelectorAll('#result_list thead th.sortable.sorted');
    changelist.querySelectorAll('#result_list thead th.sortable').forEach(header => {
        const text = header.querySelector('.text');
        const primary = text?.querySelector('a[href]');
        if (!primary) return;
        const options = header.querySelector('.sortoptions');
        const toggle = options?.querySelector('a.toggle');
        const remove = options?.querySelector('a.sortremove');
        const priority = options?.querySelector('.sortpriority');
        const column = primary.textContent.trim();
        const sorted = header.classList.contains('sorted');
        const ascending = header.classList.contains('ascending');
        const next = sorted && ascending
            ? label('novaSortDescending', 'Sort descending')
            : label('novaSortAscending', 'Sort ascending');
        const state = sorted ? [
            ascending ? label('novaAscending', 'Ascending') : label('novaDescending', 'Descending'),
            priority?.getAttribute('title'),
        ].filter(Boolean).join('; ') : '';
        const describe = (link, action) => {
            if (!link) return;
            const description = [column, state, action].filter(Boolean).join('. ');
            if (!link.hasAttribute('aria-label')) link.setAttribute('aria-label', description);
            if (!link.hasAttribute('title')) link.title = description;
        };
        describe(primary, `${next}. ${label('novaSortPrimary', 'Make primary sort')}`);
        describe(toggle, next);
        describe(remove, remove?.title || label('novaSortRemove', 'Remove from sorting'));
        // aria-sort describes one primary column; secondary directions and
        // priorities remain available in the links' accessible names.
        if (sorted && (priority ? priority.textContent.trim() === '1' : sortedHeaders.length === 1)
            && !header.hasAttribute('aria-sort')) {
            header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
        }
        const heading = document.createElement('div');
        heading.className = 'nova-sort-heading';
        if (column.length > 20) heading.classList.add('nova-sort-heading--long');
        text.before(heading);
        heading.append(text);
        if (options) heading.append(options);
    });

    const refreshScrollbars = [];
    const filter = changelist.querySelector('#changelist-filter');
    if (filter) {
        const controls = document.createElement('div');
        controls.className = 'nova-changelist-controls';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'nova-filter-toggle';
        toggle.setAttribute('aria-controls', filter.id);
        controls.append(toggle);
        const toolbar = changelist.querySelector('#toolbar');
        if (toolbar) toolbar.append(controls);
        else changelist.before(controls);
        const storageKey = `nova.changelist.filters:${window.location.pathname}`;
        const setCollapsed = (collapsed) => {
            if (collapsed && filter.contains(document.activeElement)) toggle.focus();
            filter.hidden = collapsed;
            changelist.classList.toggle('nova-filters-collapsed', collapsed);
            toggle.setAttribute('aria-expanded', String(!collapsed));
            toggle.textContent = collapsed
                ? label('novaShowFilters', 'Show filters')
                : label('novaHideFilters', 'Hide filters');
            refreshScrollbars.forEach(refresh => refresh());
        };
        let collapsed = filter.hidden;
        try {
            const saved = window.sessionStorage.getItem(storageKey);
            if (saved === '1' || saved === '0') collapsed = saved === '1';
        } catch (_) { /* Storage is optional; the current page remains usable. */ }
        setCollapsed(collapsed);
        toggle.addEventListener('click', () => {
            setCollapsed(!filter.hidden);
            try { window.sessionStorage.setItem(storageKey, filter.hidden ? '1' : '0'); }
            catch (_) { /* Private/blocked storage must not disable the control. */ }
        });
    }

    changelist.querySelectorAll('.results').forEach((results, index) => {
        const table = results.querySelector('table');
        if (!table) return;
        if (!results.id) {
            let id = `nova-results-${index + 1}`;
            while (document.getElementById(id)) id += '-scroll';
            results.id = id;
        }
        const tools = document.createElement('div');
        tools.className = 'nova-results-scroll-tools';
        tools.hidden = true;
        const button = (className, name, fallback, glyph) => {
            const control = document.createElement('button');
            control.type = 'button';
            control.className = `nova-results-scroll-button ${className}`;
            control.setAttribute('aria-label', label(name, fallback));
            control.setAttribute('aria-controls', results.id);
            control.textContent = glyph;
            return control;
        };
        const left = button('nova-results-scroll-left', 'novaScrollLeft', 'Scroll table left', '←');
        const right = button('nova-results-scroll-right', 'novaScrollRight', 'Scroll table right', '→');
        const scrollbar = document.createElement('input');
        scrollbar.type = 'range';
        scrollbar.className = 'nova-results-scrollbar';
        scrollbar.min = '0';
        scrollbar.max = '0';
        scrollbar.step = '1';
        scrollbar.value = '0';
        scrollbar.setAttribute('aria-label', label('novaScrollTable', 'Scroll table horizontally'));
        scrollbar.setAttribute('aria-controls', results.id);
        tools.append(left, scrollbar, right);
        results.before(tools);

        let maximum = 0;
        let rtl = false;
        const limits = () => rtl ? [-maximum, 0] : [0, maximum];
        const updateControls = () => {
            const [minimum, max] = limits();
            const offset = Math.max(minimum, Math.min(max, results.scrollLeft));
            scrollbar.value = String(rtl ? -offset : offset);
            left.disabled = offset <= minimum + 1;
            right.disabled = offset >= max - 1;
        };
        const scrollTo = position => {
            const [minimum, max] = limits();
            results.scrollLeft = Math.max(minimum, Math.min(max, position));
            updateControls();
        };
        const refresh = () => {
            maximum = Math.max(0, results.scrollWidth - results.clientWidth);
            rtl = window.getComputedStyle(results).direction === 'rtl';
            scrollbar.dir = rtl ? 'rtl' : 'ltr';
            const hidden = maximum <= 1 || results.clientWidth === 0;
            if (hidden && tools.contains(document.activeElement)) {
                if (!results.hasAttribute('tabindex')) results.tabIndex = -1;
                results.focus({preventScroll: true});
            }
            tools.hidden = hidden;
            scrollbar.disabled = hidden;
            scrollbar.max = String(maximum);
            scrollTo(results.scrollLeft);
        };
        const applySlider = () => scrollTo((rtl ? -1 : 1) * scrollbar.valueAsNumber);
        scrollbar.addEventListener('input', applySlider);
        scrollbar.addEventListener('change', applySlider);
        results.addEventListener('scroll', updateControls, {passive: true});
        const page = () => Math.max(120, results.clientWidth * 0.75);
        left.addEventListener('click', () => scrollTo(results.scrollLeft - page()));
        right.addEventListener('click', () => scrollTo(results.scrollLeft + page()));
        scrollbar.addEventListener('keydown', event => {
            if (event.target !== scrollbar || event.altKey || event.ctrlKey || event.metaKey) return;
            const positions = {
                ArrowLeft: results.scrollLeft - 40,
                ArrowRight: results.scrollLeft + 40,
                Home: 0,
                End: rtl ? -maximum : maximum,
            };
            if (!(event.key in positions)) return;
            event.preventDefault();
            scrollTo(positions[event.key]);
        });
        if (window.ResizeObserver) {
            const observer = new ResizeObserver(refresh);
            observer.observe(results);
            observer.observe(table);
        }
        window.addEventListener('resize', refresh, {passive: true});
        refreshScrollbars.push(refresh);
        refresh();
    });
})();
