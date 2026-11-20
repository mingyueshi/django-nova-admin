/* Django owns the action, its queryset, confirmations, and the editable formset. */
'use strict';
(() => {
    const labels = document.currentScript.dataset;
    const key = 'nova.admin.action-selection.v1';
    const form = document.getElementById('changelist-form');
    const toggle = form?.querySelector('#action-toggle');
    const rows = Array.from(form?.querySelectorAll('#result_list input.action-select[name="_selected_action"]:enabled') || []);
    const bars = Array.from(form?.querySelectorAll('.actions') || []);
    const ids = new Set();
    let all = false;
    let storage;

    function restore() {
        ids.clear();
        all = false;
        const raw = storage.getItem(key);
        if (!raw) return;
        let state;
        try { state = JSON.parse(raw); } catch (_) { /* Discard unreadable state. */ }
        if (state?.scope === labels.scope) {
            if (state.mode === 'all' && !('ids' in state)) { all = true; return; }
            if (state.mode === 'manual' && Array.isArray(state.ids) && state.ids.every(id => typeof id === 'string' && id.length)) {
                for (const id of state.ids) ids.add(id);
                return;
            }
        }
        // Keep just one query in this tab. Returning to an old filter starts afresh.
        storage.removeItem(key);
    }

    const feedback = document.createElement('span');
    feedback.setAttribute('role', 'status');
    bars[0]?.append(feedback);
    try { storage = window.sessionStorage; restore(); }
    catch (_) { feedback.textContent = labels.unavailable; return; }
    if (!toggle || !rows.length || !bars.length || !('FormDataEvent' in window) ||
        bars.some(bar => !bar.querySelector('.action-counter') || !bar.querySelector('input.select-across'))) return;

    const clearButtons = bars.map(bar => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button';
        button.textContent = labels.clear;
        bar.append(button);
        return button;
    });

    function render() {
        let pageCount = 0;
        for (const box of rows) {
            box.checked = all || ids.has(box.value);
            box.closest('tr').classList.toggle('selected', box.checked);
            if (box.checked) pageCount++;
        }
        toggle.checked = pageCount === rows.length;
        toggle.indeterminate = pageCount > 0 && !toggle.checked;
        for (const bar of bars) {
            bar.querySelector('input.select-across').value = all ? '1' : '0';
            const counter = bar.querySelector('.action-counter');
            counter.classList.remove('hidden');
            counter.textContent = all ? labels.all : labels.manual.replace('{page}', pageCount).replace('{total}', ids.size);
            bar.querySelector('.question')?.classList.toggle('hidden', all || !toggle.checked);
            bar.querySelector('.all')?.classList.add('hidden');
            bar.querySelector('.clear')?.classList.add('hidden');
        }
        for (const button of clearButtons) button.hidden = !all && !ids.size;
    }

    function persist() {
        if (storage) {
            try {
                if (all || ids.size) {
                    const state = all ? {scope: labels.scope, mode: 'all'} : {scope: labels.scope, mode: 'manual', ids: [...ids]};
                    storage.setItem(key, JSON.stringify(state));
                } else storage.removeItem(key);
            } catch (_) {
                try { storage.removeItem(key); } catch (_) { /* Storage may be disabled. */ }
                storage = null;
            }
        }
        if (!storage) {
            // Keep only the requested page checkboxes. A failed write must not submit invisible IDs.
            const visible = new Set(rows.map(box => box.value));
            for (const id of ids) if (!visible.has(id)) ids.delete(id);
            feedback.textContent = labels.unavailable;
        }
        render();
    }

    function readPage() {
        all = false;
        for (const box of rows) {
            if (box.checked) ids.add(box.value);
            else ids.delete(box.value);
        }
        feedback.textContent = '';
        persist();
    }

    // Bubble after actions.js has applied the page toggle or Shift-click range.
    form.addEventListener('change', event => {
        if (rows.includes(event.target)) readPage();
    });
    form.addEventListener('click', event => {
        if (event.target === toggle) readPage();
        else if (toggle.checked && event.target.closest('.actions .question a') &&
                 event.target.closest('.actions').querySelector('input.select-across').value === '1') {
            all = true;
            ids.clear();
            feedback.textContent = '';
            persist();
        } else if (clearButtons.includes(event.target) || event.target.closest('.actions .clear a')) {
            ids.clear();
            all = false;
            feedback.textContent = '';
            persist();
            toggle.focus();
        }
    });

    let actionSubmit;
    function finishSubmit(submission) {
        if (!submission || submission !== actionSubmit) return;
        actionSubmit = null;
        if (submission.serialized && !submission.event.defaultPrevented) {
            // Django now owns the selection, including intermediate confirmation pages.
            ids.clear();
            all = false;
            persist();
        }
    }
    form.addEventListener('submit', event => {
        actionSubmit = null;
        const button = event.submitter;
        if (event.defaultPrevented || button?.name !== 'index' || !button.closest('.actions')?.querySelector('[name="action"]')?.value) return;
        const current = rows.filter(box => box.checked).length;
        if (!all && ids.size > current && labels.maxFields) {
            // Include native formset fields and the clicked submit button in Django's request budget.
            const fields = Array.from(new FormData(form).keys()).length + 1 + ids.size - current;
            if (fields > Number(labels.maxFields)) {
                event.preventDefault();
                feedback.textContent = labels.limit;
                return;
            }
        }
        const submission = {event, serialized: false};
        actionSubmit = submission;
        setTimeout(() => finishSubmit(submission), 0);
    });
    form.addEventListener('formdata', event => {
        const data = event.formData;
        if (!actionSubmit || actionSubmit.event.defaultPrevented || !data.has('index') || data.has('_save')) return;
        actionSubmit.serialized = true;
        data.set('select_across', all ? '1' : '0');
        if (!all) {
            data.delete('_selected_action');
            for (const id of ids) data.append('_selected_action', id);
        }
    });
    window.addEventListener('pagehide', () => finishSubmit(actionSubmit));

    render();
    // Django updates its own counter on pageshow. Restore after that update, including BFCache.
    window.addEventListener('pageshow', () => setTimeout(() => {
        if (storage) {
            try { restore(); } catch (_) { storage = null; feedback.textContent = labels.unavailable; }
        }
        render();
    }, 0));
})();
