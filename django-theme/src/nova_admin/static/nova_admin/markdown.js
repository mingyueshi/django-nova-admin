/* Opt-in NOVA_ADMIN_MARKDOWN enhancement for host-marked textareas.
   Local, dependency-free toolbar: inserts Markdown syntax around the current
   selection. Never submits, fetches, stores history or rewrites content
   beyond the selection. Without JavaScript the textarea stays untouched. */
'use strict';
(() => {
    const body = document.body;
    if (!body || !body.matches('.nova-admin') || body.classList.contains('popup')) return;
    let labels = null;
    try {
        labels = JSON.parse(document.getElementById('nova-md-labels')?.textContent || 'null');
    } catch {
        labels = null;
    }
    if (!labels || typeof labels !== 'object') return;
    const actions = [
        { key: 'bold', glyph: 'B', prefix: '**', suffix: '**', placeholder: 'text' },
        { key: 'italic', glyph: 'I', prefix: '*', suffix: '*', placeholder: 'text' },
        { key: 'code', glyph: '</>', prefix: '`', suffix: '`', placeholder: 'code' },
        { key: 'link', glyph: '↗', prefix: '[', suffix: '](https://)', placeholder: 'label' },
        { key: 'heading', glyph: 'H2', prefix: '## ', suffix: '', placeholder: '' },
        { key: 'list', glyph: '≡', prefix: '- ', suffix: '', placeholder: '' },
        { key: 'quote', glyph: '❝', prefix: '> ', suffix: '', placeholder: '' },
    ];
    function apply(textarea, action) {
        const start = textarea.selectionStart ?? textarea.value.length;
        const end = textarea.selectionEnd ?? start;
        const chosen = textarea.value.slice(start, end) || action.placeholder;
        textarea.value = textarea.value.slice(0, start) + action.prefix + chosen +
            action.suffix + textarea.value.slice(end);
        const inner = start + action.prefix.length;
        textarea.setSelectionRange(inner, inner + chosen.length);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.focus();
    }
    function enhance(textarea) {
        if (textarea.dataset.novaMdReady || textarea.disabled || textarea.readOnly ||
            textarea.closest('.nova-md-field')) return;
        textarea.dataset.novaMdReady = 'true';
        const bar = document.createElement('div');
        bar.className = 'nova-md-toolbar';
        bar.setAttribute('role', 'toolbar');
        bar.setAttribute('aria-label', labels.toolbar || 'Markdown formatting');
        for (const action of actions) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'nova-md-button nova-md-' + action.key;
            button.textContent = action.glyph;
            button.setAttribute('aria-label', labels[action.key] || action.key);
            button.addEventListener('click', () => apply(textarea, action));
            bar.appendChild(button);
        }
        textarea.closest('.form-row, .field, div')?.classList.add('nova-md-field');
        textarea.before(bar);
    }
    function scan() {
        document.querySelectorAll('textarea[data-nova-markdown]').forEach(enhance);
    }
    // Deferred scripts run after parsing with body present; an async script may
    // still be mid-document. scan() is idempotent, so both paths are safe.
    if (document.body) {
        scan();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scan, { once: true });
    }
})();
