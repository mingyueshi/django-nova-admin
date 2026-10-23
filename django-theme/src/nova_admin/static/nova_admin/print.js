/* Copy only currently displayed list text into a temporary, inert print sheet.
   Never clone markup, submit a form, follow a link, fetch data or store history. */
'use strict';
(() => {
    if (!document.body.matches('.nova-admin.change-list') || document.body.classList.contains('popup') ||
        typeof window.print !== 'function' || typeof window.matchMedia !== 'function') return;
    const list = document.getElementById('changelist');
    const tool = document.querySelector('[data-nova-print-tool]');
    const button = tool?.querySelector('[data-nova-print]');
    if (!list || !button || button.dataset.novaPrintReady ||
        getComputedStyle(button).getPropertyValue('--nova-print-available').trim() !== '1') return;
    button.dataset.novaPrintReady = 'true';
    const media = window.matchMedia('print');
    const excluded = '[hidden],[inert],[aria-hidden="true"],[data-nova-no-print],[data-nova-print-exclude],.visually-hidden,.sr-only,.action-checkbox,.action-checkbox-column,.sortoptions,script,style,template,button,input[type="hidden"],input[type="password"],input[type="file"]';
    let screenNodes = new WeakSet();
    let sheet = null;
    let opener = null;
    let requesting = false;
    function notHidden(element) {
        if (element.closest(excluded)) return false;
        for (let parent = element; parent; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' ||
                Number(style.opacity || 1) === 0 || style.contentVisibility === 'hidden' ||
                (style.clip && style.clip !== 'auto') || (style.clipPath && style.clipPath !== 'none')) return false;
        }
        return true;
    }
    function visible(element) {
        if (!notHidden(element)) return false;
        const style = getComputedStyle(element);
        return style.display === 'contents' || Array.from(element.getClientRects()).some(rect => rect.width > 1 && rect.height > 1);
    }
    function rememberScreen() {
        // beforeprint can run AFTER print media applies. Keep eligibility from
        // screen mode so host print CSS can never reveal a hidden source value.
        if (media.matches || sheet) return;
        const next = new WeakSet();
        const title = document.querySelector('#content h1');
        for (const element of [title, ...list.querySelectorAll('#result_list, #result_list *')]) {
            if (element && (element.matches('option,br') ? notHidden(element) : visible(element))) next.add(element);
        }
        screenNodes = next;
    }
    function allowed(element) { return screenNodes.has(element) && visible(element); }
    function text(node) {
        if (node.nodeType === Node.TEXT_NODE) return node.parentElement && allowed(node.parentElement) ? node.textContent : '';
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        if (node.matches('br')) return screenNodes.has(node) && notHidden(node) ? '\n' : '';
        if (!allowed(node)) return '';
        if (node.matches('input')) {
            if (['checkbox', 'radio'].includes(node.type)) return node.checked ? button.dataset.yes : button.dataset.no;
            return ['text', 'search', 'email', 'url', 'tel', 'number', 'date', 'datetime-local', 'month', 'week', 'time', 'color', 'range'].includes(node.type) ? node.value : '';
        }
        if (node.matches('textarea')) return node.value;
        if (node.matches('select')) return Array.from(node.selectedOptions).filter(option => {
            return screenNodes.has(option) && notHidden(option);
        }).map(option => option.textContent).join(', ');
        if (node.matches('img')) return node.alt || '';
        return Array.from(node.childNodes).map(text).join('');
    }
    const tidy = value => value.trim().replace(/[\t ]+/g, ' ');
    function append(parent, tag, content) {
        const element = document.createElement(tag);
        element.textContent = content;
        parent.append(element);
        return element;
    }
    function prepare() {
        if (sheet || !document.body.classList.contains('nova-admin')) return;
        if (!media.matches) rememberScreen();
        opener = document.activeElement;
        sheet = document.createElement('article');
        sheet.className = 'nova-print-sheet';
        const title = document.querySelector('#content h1');
        append(sheet, 'h1', button.dataset.title);
        if (title && allowed(title)) append(sheet, 'p', tidy(text(title)));
        append(sheet, 'p', button.dataset.scope);
        const table = list.querySelector('#result_list');
        const headers = table ? Array.from(table.querySelectorAll('thead > tr:first-child > th')) : [];
        const columns = headers.map((header, index) => ({header, index})).filter(({header}) => allowed(header));
        const rows = table && allowed(table) ? Array.from(table.querySelectorAll('tbody > tr')).filter(allowed) : [];
        const range = (button.dataset.range || '').replace('{page}', button.dataset.page || '1').replace('{count}', String(rows.length));
        append(sheet, 'p', range);
        if (button.dataset.editable === 'true') append(sheet, 'p', button.dataset.unsaved);
        if (columns.length && rows.length) {
            const output = document.createElement('table');
            const head = output.createTHead().insertRow();
            columns.forEach(({header}) => {
                const cell = append(head, 'th', tidy(text(header.querySelector('.text') || header)));
                cell.scope = 'col';
            });
            const body = output.createTBody();
            rows.forEach(row => {
                const line = body.insertRow();
                columns.forEach(({index}) => append(line, 'td', row.cells[index] ? tidy(text(row.cells[index])) : ''));
            });
            sheet.append(output);
        } else append(sheet, 'p', button.dataset.empty);
        document.body.append(sheet);
        document.body.classList.add('nova-printing');
    }
    function cleanup() {
        if (!sheet) return;
        sheet.remove(); sheet = null;
        document.body.classList.remove('nova-printing');
        const target = opener; opener = null;
        if (target?.isConnected && visible(target) && (document.activeElement === document.body || document.activeElement === target)) target.focus({preventScroll: true});
    }
    tool.hidden = false;
    button.hidden = false;
    rememberScreen();
    const observer = new MutationObserver(rememberScreen);
    observer.observe(list, {subtree: true, childList: true, characterData: true, attributes: true});
    window.addEventListener('resize', rememberScreen);
    window.addEventListener('beforeprint', prepare);
    window.addEventListener('afterprint', cleanup);
    media.addEventListener?.('change', () => { if (!media.matches) { cleanup(); rememberScreen(); } });
    window.addEventListener('focus', () => { if (!media.matches) cleanup(); });
    window.addEventListener('pagehide', cleanup);
    button.addEventListener('click', () => {
        if (requesting) return;
        requesting = true;
        try { prepare(); window.print(); }
        catch (_) { /* A blocked/failed dialog leaves the original page intact. */ }
        finally { requesting = false; if (!media.matches) cleanup(); }
    });
})();
