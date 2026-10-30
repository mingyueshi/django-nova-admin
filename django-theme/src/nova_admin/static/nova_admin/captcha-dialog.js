/* Submit -> basic validation -> modal verification -> one native login POST.
 * The existing provider/server remains the verification authority.
 */
(() => {
  'use strict';
  const form = document.getElementById('login-form');
  const challenge = form?.querySelector('[data-nova-login-challenge]');
  const dialog = form?.querySelector('[data-nova-captcha-dialog]');
  if (!challenge || !dialog) return;
  const sliderTemplate = challenge.querySelector('[data-nova-slider-template]');
  const mountSlider = () => {
    if (sliderTemplate && !challenge.querySelector('nova-slider'))
      sliderTemplate.after(sliderTemplate.content.cloneNode(true));
  };
  if (typeof dialog.showModal !== 'function' || typeof form.requestSubmit !== 'function') {
    mountSlider();
    return;
  }
  const slot = dialog.querySelector('[data-nova-captcha-slot]');
  const heading = dialog.querySelector('h2');
  const unavailable = dialog.querySelector('[data-nova-captcha-unavailable]');
  const continueButton = dialog.querySelector('[data-nova-captcha-continue]');
  const isImage = challenge.dataset.novaLoginChallenge === 'image';
  let pending = false, sending = false, resuming = false, resumeEvent, submitter, previousFocus, snapshot;
  const basics = () => Array.from(form.elements).filter(el => !challenge.contains(el) &&
    !dialog.contains(el) && !['submit', 'button', 'reset', 'hidden'].includes(el.type));
  const values = () => basics().map(el => [el, el.value, el.checked]);
  const unchanged = () => snapshot?.every(([el, value, checked]) => el.value === value && el.checked === checked);
  const validate = elements => {
    const invalid = elements.find(el => el.willValidate && !el.checkValidity());
    if (!invalid) return true;
    invalid.reportValidity();
    invalid.focus();
    return false;
  };
  const emit = name => challenge.dispatchEvent(new CustomEvent(name));
  const cancel = () => {
    pending = false;
    snapshot = null;
    emit('nova-captcha-cancel');
    if (sliderTemplate) challenge.querySelector('nova-slider')?.remove();
    if (isImage) challenge.querySelectorAll('input[type="text"]').forEach(el => { el.value = ''; });
    if (dialog.open) dialog.close();
    if (!sending && previousFocus?.isConnected) previousFocus.focus({preventScroll: true});
  };
  const complete = () => {
    if (!pending || !dialog.open || sending || resuming || continueButton?.disabled) return;
    if (!unchanged()) { cancel(); return; }
    if (!validate(basics())) { cancel(); return; }
    if (isImage && !validate(Array.from(challenge.querySelectorAll('input,select,textarea')))) return;
    resuming = true;
    resumeEvent = null;
    try { form.requestSubmit(submitter?.isConnected ? submitter : undefined); }
    finally { resuming = false; }
    if (resumeEvent && !resumeEvent.defaultPrevented) {
      sending = true;
      pending = false;
      snapshot = null;
      dialog.close();
      Array.from(form.elements).filter(el => el.type === 'submit').forEach(el => { el.disabled = true; });
    }
  };
  // Host adapters recheck their proof/deadline during the resumed submit.
  form.novaCaptchaDialog = {
    get active() { return pending && dialog.open; },
    complete, cancel,
    setBlocked(blocked) { if (continueButton) continueButton.disabled = blocked; },
  };
  form.noValidate = true; // Validate credentials before hidden challenge fields.
  slot.appendChild(challenge);
  form.addEventListener('submit', event => {
    if (resuming) { resumeEvent = event; return; }
    event.preventDefault();
    if (sending) return;
    // Native forms ignore nested requestSubmit() while firing submit events.
    if (dialog.open) { if (isImage) queueMicrotask(complete); return; }
    if (!validate(basics())) return;
    pending = true;
    snapshot = values();
    submitter = event.submitter || form.querySelector('[type="submit"]');
    previousFocus = document.activeElement;
    unavailable.hidden = true;
    dialog.showModal();
    heading.focus({preventScroll: true});
    mountSlider();
    emit('nova-captcha-open');
    if (!isImage && !challenge.querySelector('nova-slider')?.live) unavailable.hidden = false;
  }, true);
  form.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.isComposing || !(event.target instanceof HTMLInputElement)) return;
    if (challenge.contains(event.target)) {
      if (isImage && dialog.open) { event.preventDefault(); queueMicrotask(complete); }
    } else if (!['button', 'submit', 'reset', 'checkbox', 'radio'].includes(event.target.type)) {
      event.preventDefault();
      form.requestSubmit(form.querySelector('[type="submit"]'));
    }
  });
  challenge.addEventListener('verified', event => {
    const widget = challenge.querySelector('nova-slider');
    if (event.target === widget && widget.state === 'success' && widget.getToken() === event.detail?.token && event.detail.token)
      complete();
  });
  dialog.querySelector('[data-nova-captcha-close]').addEventListener('click', cancel);
  continueButton?.addEventListener('click', complete);
  dialog.addEventListener('cancel', event => { event.preventDefault(); cancel(); });
  dialog.addEventListener('close', () => { if (pending && !dialog.open) cancel(); });
  form.addEventListener('input', event => { if (pending && !challenge.contains(event.target)) cancel(); });
  form.addEventListener('reset', cancel);
  window.addEventListener('pagehide', cancel);
  window.addEventListener('pageshow', event => { if (event.persisted) { sending = false; cancel(); } });
})();
