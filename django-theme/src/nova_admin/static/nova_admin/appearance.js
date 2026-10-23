/* Django filters.js binds storage handlers to every details element. This new
   disclosure owns its toggle event; real filter details keep Django's handler.
   Native opening/closing and the original form require no initialization. */
'use strict';
(() => {
    const details = document.querySelector('body.nova-admin details.nova-appearance');
    if (!details || details.dataset.novaAppearanceReady) return;
    details.dataset.novaAppearanceReady = 'true';
    details.addEventListener('toggle', event => {
        if (event.target === details) event.stopImmediatePropagation();
    }, {capture: true});
})();
