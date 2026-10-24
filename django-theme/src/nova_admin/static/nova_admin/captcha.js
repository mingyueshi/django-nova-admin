/* Progressive enhancement. The server validates/consumes every challenge. */
(function () {
  'use strict';
  document.querySelectorAll('[data-nova-captcha]').forEach(function (root) {
    const form = root.closest('form');
    const token = root.querySelector('input[type="hidden"]');
    const answer = root.querySelector('input[type="text"]');
    const image = root.querySelector('[data-captcha-image]');
    const audio = root.querySelector('[data-captcha-audio]');
    const player = root.querySelector('[data-captcha-player]');
    const button = root.querySelector('[data-captcha-refresh]');
    const status = root.querySelector('[data-captcha-status]');
    if (!form || !token || !answer || !image || !button || !status) return;
    function sameOriginURL(value) {
      if (typeof value !== 'string' || !value.trim()) throw new Error('missing URL');
      const url = new URL(value, window.location.href);
      if (!['http:', 'https:'].includes(url.protocol) || url.origin !== window.location.origin) {
        throw new Error('external CAPTCHA URL');
      }
      return url.href;
    }
    let busy = false;
    let blocked = false;
    let generation = 0;
    let controller = null;
    function clearAudio() {
      if (player) {
        if (typeof player.pause === 'function') player.pause();
        player.removeAttribute('src');
        if (typeof player.load === 'function') player.load();
        player.hidden = true;
      }
      if (audio) { audio.removeAttribute('href'); audio.hidden = true; }
    }
    function replaceAudio(url) {
      if (player) {
        player.hidden = !url;
        if (url) {
          player.src = url;
          if (typeof player.load === 'function') player.load();
        }
      }
      if (audio) { audio.hidden = !url; if (url) audio.href = url; }
    }
    const submitters = Array.from(form.querySelectorAll('[type="submit"]'));
    const disabledBefore = submitters.map(function (item) { return item.disabled; });
    function lock(value) {
      answer.readOnly = value;
      submitters.forEach(function (item, index) { item.disabled = value || disabledBefore[index]; });
    }
    function announce(message, state) {
      status.textContent = message;
      root.dataset.captchaState = state;
    }
    function imageFailed() {
      if (busy) return;
      blocked = true;
      lock(true);
      announce(root.dataset.imageErrorMessage, 'error');
    }
    image.addEventListener('error', imageFailed);
    if (image.complete && image.naturalWidth === 0) imageFailed();
    form.addEventListener('submit', function (event) {
      if (busy || blocked) { event.preventDefault(); button.focus(); }
    });
    button.hidden = false;
    if (answer.getAttribute('aria-invalid') === 'true' && !blocked) answer.focus();
    button.addEventListener('click', async function () {
      if (busy) return; // Repeated keyboard/click activation issues one request.
      busy = true;
      blocked = true;
      clearAudio();
      const current = ++generation;
      button.disabled = true;
      lock(true);
      answer.value = '';
      root.setAttribute('aria-busy', 'true');
      announce(root.dataset.loadingMessage, 'loading');
      controller = new AbortController();
      const timer = setTimeout(function () { controller.abort(); }, 15000);
      try {
        const csrf = form.querySelector('[name="csrfmiddlewaretoken"]');
        const refreshURL = sameOriginURL(root.dataset.refreshUrl);
        const response = await fetch(refreshURL, {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf ? csrf.value : '' },
          body: new URLSearchParams({ key: token.value })
        });
        if (!response.ok) throw new Error('refresh failed');
        const next = await response.json();
        if (current !== generation) return;
        if (!next.key || !next.image_url) throw new Error('invalid response');
        // Validate every destination before preloading or mutating any asset.
        // A malformed server response must never introduce a third-party request.
        const imageURL = sameOriginURL(next.image_url);
        const audioURL = next.audio_url ? sameOriginURL(next.audio_url) : null;
        // Old key is already consumed. Retain the replacement key even if its
        // image fails so a subsequent refresh can replace that challenge.
        token.value = next.key;
        await new Promise(function (resolve, reject) {
          const preload = new Image();
          const imageTimer = setTimeout(function () { reject(new Error('image timeout')); }, 15000);
          preload.onload = function () { clearTimeout(imageTimer); resolve(); };
          preload.onerror = function () { clearTimeout(imageTimer); reject(new Error('image failed')); };
          preload.src = imageURL;
        });
        if (current !== generation) return;
        image.src = imageURL;
        replaceAudio(audioURL);
        blocked = false;
        announce(root.dataset.successMessage, 'ready');
        answer.focus();
      } catch (error) {
        if (current !== generation) return;
        clearAudio();
        announce(root.dataset.errorMessage, 'error');
      } finally {
        clearTimeout(timer);
        if (current === generation) {
          busy = false;
          button.disabled = false;
          root.removeAttribute('aria-busy');
          lock(blocked);
          if (blocked) button.focus();
        }
      }
    });
    window.addEventListener('pagehide', function () { generation += 1; if (controller) controller.abort(); clearAudio(); });
    window.addEventListener('pageshow', function (event) {
      // A restored one-use form may have been consumed while away.
      if (event.persisted) window.location.reload();
    });
  });
}());
