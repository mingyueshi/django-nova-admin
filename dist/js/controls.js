// Opt-in searchable select. The original select remains the form's value source.
// No application data is fetched and no native Django widget is replaced here.
let current = null;
const instances = new WeakMap();
export function enhanceControls(root = document) {
  for (const select of root.querySelectorAll('select[data-searchable]')) {
    if (instances.has(select)) {
      instances.get(select).sync();
      continue;
    }
    const wrap = document.createElement('div');
    wrap.className = 'search-select';
    select.before(wrap);
    wrap.append(select);
    select.hidden = true;
    const input = document.createElement('input');
    input.type = 'text';
    input.id = select.id + '-combobox';
    input.className = 'combobox-input';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', select.id + '-options');
    const label = document.querySelector(`label[for="${select.id}"]`);
    if (label) {
      label.htmlFor = input.id;
      label.id = label.id || select.id + '-label';
      input.setAttribute('aria-labelledby', label.id);
    } else input.setAttribute('aria-label', select.getAttribute('aria-label') || '选择选项');
    const chevron = document.createElement('span');
    chevron.className = 'combobox-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '⌄';
    const popup = document.createElement('div');
    popup.className = 'combobox-popup';
    popup.hidden = true;
    const hint = document.createElement('div');
    hint.className = 'combobox-hint';
    hint.textContent = '输入关键词筛选 · ↑↓ 选择 · Enter 确认';
    const list = document.createElement('div');
    list.id = select.id + '-options';
    list.setAttribute('role', 'listbox');
    const count = document.createElement('div');
    count.className = 'combobox-count';
    count.setAttribute('role', 'status');
    popup.append(hint, list, count);
    wrap.append(input, chevron, popup);
    let shown = [],
      active = -1,
      open = false;
    const optionDisabled = (option) =>
      option.disabled || option.parentElement?.matches('optgroup:disabled');
    const sync = () => {
      input.disabled = select.matches(':disabled');
      input.required = select.required;
      input.setAttribute('aria-required', String(select.required));
      if (input.disabled && open) {
        close();
        return;
      }
      if (!open) input.value = select.selectedOptions[0]?.textContent || '';
      for (const name of ['aria-invalid', 'aria-describedby']) {
        const v = select.getAttribute(name);
        if (v) input.setAttribute(name, v);
        else input.removeAttribute(name);
      }
    };
    const close = () => {
      open = false;
      popup.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      sync();
      if (current?.input === input) current = null;
    };
    const highlight = () => {
      list.querySelectorAll('[role=option]').forEach((el, i) => {
        el.classList.toggle('is-active', i === active);
      });
      if (shown[active]) {
        input.setAttribute('aria-activedescendant', `${select.id}-option-${active}`);
        list.children[active]?.scrollIntoView?.({ block: 'nearest' });
      } else input.removeAttribute('aria-activedescendant');
    };
    const choose = (index) => {
      const option = shown[index];
      if (!option || optionDisabled(option)) return;
      select.value = option.value;
      close();
      select.dispatchEvent(new Event('change', { bubbles: true }));
      input.focus();
    };
    const populate = (query) => {
      shown = Array.from(select.options).filter((o) =>
        o.textContent.toLowerCase().includes(query.trim().toLowerCase()),
      );
      list.replaceChildren();
      shown.forEach((option, i) => {
        const el = document.createElement('div');
        el.id = `${select.id}-option-${i}`;
        el.setAttribute('role', 'option');
        el.setAttribute('aria-selected', String(option.selected));
        if (optionDisabled(option)) el.setAttribute('aria-disabled', 'true');
        const text = document.createElement('span');
        text.textContent = option.textContent;
        const tick = document.createElement('span');
        tick.className = 'combobox-tick';
        tick.textContent = option.selected ? '✓' : '';
        tick.setAttribute('aria-hidden', 'true');
        el.append(text, tick);
        el.addEventListener('pointerdown', (e) => e.preventDefault());
        el.addEventListener('mousedown', (e) => e.preventDefault());
        el.addEventListener('click', () => choose(i));
        list.append(el);
      });
      active = shown.findIndex((o) => o.selected && !optionDisabled(o));
      if (active < 0) active = shown.findIndex((o) => !optionDisabled(o));
      count.textContent = shown.length ? `${shown.length} 个选项` : '没有匹配选项，试试其他关键词';
      highlight();
    };
    const show = () => {
      if (input.disabled) return;
      if (current?.input !== input) current?.close();
      open = true;
      popup.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      current = { input, close };
      populate('');
    };
    input.addEventListener('click', () => {
      if (!open) show();
      input.select();
    });
    input.addEventListener('input', (e) => {
      e.stopPropagation();
      if (!open) show();
      populate(input.value);
    });
    input.addEventListener('change', (e) => e.stopPropagation());
    input.addEventListener('blur', () => close());
    input.addEventListener('keydown', (e) => {
      if (['ArrowDown', 'ArrowUp', 'Enter', 'Escape', 'Home', 'End'].includes(e.key)) {
        if (['Home', 'End'].includes(e.key) && !open) return;
        e.preventDefault();
        e.stopPropagation();
        if (e.key === 'Escape') {
          close();
          return;
        }
        if (!open) {
          show();
          return;
        }
        if (e.key === 'Enter') {
          choose(active);
          return;
        }
        const enabled = shown.map((o, i) => (!optionDisabled(o) ? i : -1)).filter((i) => i >= 0);
        if (e.key === 'Home') active = enabled[0] ?? -1;
        else if (e.key === 'End') active = enabled.at(-1) ?? -1;
        else {
          const index = enabled.indexOf(active),
            delta = e.key === 'ArrowDown' ? 1 : -1;
          active = enabled[(index + delta + enabled.length) % enabled.length] ?? -1;
        }
        highlight();
      } else if (e.key === 'Tab') close();
    });
    select.addEventListener('change', sync);
    select.addEventListener('invalid', (e) => {
      e.preventDefault();
      input.focus();
    });
    const observer = new MutationObserver(sync);
    observer.observe(select, {
      attributes: true,
      attributeFilter: ['disabled', 'required', 'aria-invalid', 'aria-describedby'],
    });
    const fieldset = select.closest('fieldset');
    if (fieldset) observer.observe(fieldset, { attributes: true, attributeFilter: ['disabled'] });
    select.form?.addEventListener('reset', () => setTimeout(sync, 0));
    instances.set(select, { sync, close });
    sync();
  }
  if (current && !current.input.isConnected) {
    current.close();
    current = null;
  }
}
