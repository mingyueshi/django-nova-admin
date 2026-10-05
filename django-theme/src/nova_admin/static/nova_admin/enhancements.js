/* Presentation only: preserve Django's search form, label, GET data and help. */
'use strict';
{
    const input = document.querySelector('body.nova-admin #changelist-search #searchbar');
    const script = document.currentScript || document.querySelector('script[data-nova-search-placeholder]');
    if (input && !input.hasAttribute('placeholder') && !input.disabled && !input.readOnly) {
        const help = document.getElementById('searchbar_helptext');
        const text = (help?.textContent || script?.dataset.novaSearchPlaceholder || '').trim().replace(/\s+/g, ' ');
        if (text) input.placeholder = text.length > 120 ? `${text.slice(0, 119)}…` : text;
    }
}
