import { applyPalette, savedPalette, paletteOptions } from './palette.js';
import './login-slider-demo.js';
import { savedBrandName, updateLoginBrand } from './branding.js';
updateLoginBrand(savedBrandName());
window.addEventListener('storage', (event) => {
  if (event.key === 'nova-settings' || event.key === null) updateLoginBrand(savedBrandName());
});
// Public interaction demo only. No authentication, fetch, cookies or credential storage.
// The optional Django integration validates its challenge independently on the server.
const $ = (selector) => document.querySelector(selector);
const form = $('#demo-login-form');
const fields = [$('#demo-username'), $('#demo-password'), $('#demo-captcha')];
const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const lifetime = 120000;
let challenge = '',
  expiresAt = 0,
  generation = 0,
  pending = false,
  alternative = false;
let submitTimer, expiryTimer;
let failures = 0,
  forcedRisk = false,
  slider = null;
const requiresCaptcha = () =>
  $('#captcha-policy').value === 'always' || failures >= 2 || forcedRisk;
const usesImage = () => $('#captcha-provider').value === 'image';

function updateVerification({ renew = true } = {}) {
  const required = requiresCaptcha();
  $('#image-captcha-section').hidden = !required || !usesImage();
  $('#slider-captcha-section').hidden = !required || usesImage();
  $('#demo-captcha').disabled = !required || !usesImage();
  $('#demo-captcha').required = required && usesImage();
  $('#captcha-length-control').hidden = !usesImage();
  $('#expire-captcha').disabled = !required;
  $('#login-risk-status').textContent = required
    ? $('#captcha-policy').value === 'always'
      ? '每次登录前完成安全验证。'
      : '检测到异常尝试，请先完成安全验证。'
    : `当前无需验证码；连续 2 次失败后将显示安全验证。${failures ? ' 已失败 1 次。' : ''}`;
  if (!required || usesImage()) {
    slider?.remove();
    slider = null;
  }
  if (required && usesImage()) {
    if (renew || !challenge) refreshChallenge({ announceChange: false });
  } else {
    clearTimeout(expiryTimer);
    challenge = '';
    $('#demo-captcha').value = '';
    if (required && !slider) {
      slider = document.createElement('nova-slider-demo');
      slider.setAttribute('endpoint', './demo-only/');
      slider.setAttribute('purpose', 'login');
      slider.setAttribute('role', 'group');
      slider.setAttribute('aria-label', '演示拼图滑块验证');
      slider.setAttribute('aria-describedby', 'slider-error');
      $('#slider-captcha-mount').append(slider);
    } else if (required && renew) slider.refresh();
  }
}
function recordFailure() {
  failures++;
  updateVerification({ renew: false });
}
for (const id of ['captcha-policy', 'captcha-provider', 'captcha-length']) {
  $('#' + id).addEventListener('change', () => {
    cancelPending();
    clearErrors();
    updateVerification();
  });
}
$('#trigger-risk').addEventListener('click', () => {
  cancelPending();
  clearErrors();
  forcedRisk = true;
  updateVerification();
});
$('#reset-risk').addEventListener('click', () => {
  cancelPending();
  clearErrors();
  failures = 0;
  forcedRisk = false;
  updateVerification();
});

let appearance = 'light';
try {
  const saved = localStorage.getItem('nova-theme');
  if (['light', 'dark', 'auto'].includes(saved)) appearance = saved;
} catch {}
const system = window.matchMedia?.('(prefers-color-scheme: dark)');
function applyAppearance(mode, persist = false) {
  appearance = ['light', 'dark', 'auto'].includes(mode) ? mode : 'light';
  document.documentElement.dataset.themeMode = appearance;
  document.documentElement.dataset.theme =
    appearance === 'auto' ? (system?.matches ? 'dark' : 'light') : appearance;
  $('#login-appearance').value = appearance;
  if (persist) {
    try {
      localStorage.setItem('nova-theme', appearance);
    } catch {}
  }
}
$('#login-appearance').addEventListener('change', (event) =>
  applyAppearance(event.target.value, true),
);
system?.addEventListener?.('change', () => {
  if (appearance === 'auto') applyAppearance('auto');
});
applyAppearance(appearance);
$('#login-palette').innerHTML = paletteOptions(savedPalette());
applyPalette(savedPalette());
$('#login-palette').addEventListener('change', (event) => {
  const saved = applyPalette(event.target.value, true);
  $('#palette-status').textContent = saved ? '' : '配色已在当前页应用，浏览器未能保存偏好';
});

function randomCode() {
  const values = new Uint32Array(Number($('#captcha-length').value) || 6);
  if (window.crypto?.getRandomValues) window.crypto.getRandomValues(values);
  else
    values.forEach((_, index) => {
      values[index] = Math.floor(Math.random() * 1000000);
    });
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join('');
}
function announce(message) {
  $('#captcha-announcement').textContent = message;
}
function setPending(value) {
  pending = value;
  form.setAttribute('aria-busy', String(value));
  $('#login-submit').disabled = value;
  $('#login-submit').textContent = value ? '正在校验…' : '登录';
  fields.forEach((field) => {
    field.readOnly = value;
  });
}
function cancelPending() {
  generation++;
  clearTimeout(submitTimer);
  setPending(false);
}
function clearErrors() {
  $('#slider-error').textContent = '';
  $('#login-feedback').hidden = true;
  $('#login-feedback').textContent = '';
  for (const name of ['username', 'password', 'captcha']) {
    $('#' + name + '-error').textContent = '';
    $('#demo-' + name).removeAttribute('aria-invalid');
  }
}
function fieldError(name, message) {
  $('#' + name + '-error').textContent = message;
  $('#demo-' + name).setAttribute('aria-invalid', 'true');
}
function feedback(message) {
  $('#login-feedback').textContent = message;
  $('#login-feedback').hidden = false;
}
function renderTextAlternative() {
  $('#captcha-text').hidden = !alternative;
  $('#captcha-graphic').hidden = alternative;
  $('#captcha-text').innerHTML =
    `请按顺序输入：<strong>${challenge}</strong><br>仅为演示提供文字替代，不代表真实防护。`;
  $('#captcha-alternative').textContent = alternative ? '图形验证' : '文字验证';
  $('#captcha-alternative').setAttribute('aria-expanded', String(alternative));
}
function updateExpiry() {
  if (Date.now() >= expiresAt) {
    $('#captcha-expiry').textContent = '已过期';
    $('#captcha-expiry').classList.remove('login-visually-hidden');
    announce('验证码已过期，请换一张。');
  }
}
function refreshChallenge({ focus = false, announceChange = true } = {}) {
  cancelPending();
  clearTimeout(expiryTimer);
  const previous = challenge;
  challenge = randomCode();
  if (challenge === previous)
    challenge =
      alphabet[(alphabet.indexOf(challenge[0]) + 1) % alphabet.length] + challenge.slice(1);
  expiresAt = Date.now() + lifetime;
  $('#demo-captcha').value = '';
  $('#demo-captcha').removeAttribute('aria-invalid');
  $('#captcha-error').textContent = '';
  $('#captcha-expiry').textContent = '2 分钟内有效';
  $('#captcha-expiry').classList.add('login-visually-hidden');
  const glyphs = Array.from(challenge)
    .map(
      (letter, index) =>
        `<text x="${24 + index * 30}" y="39" transform="rotate(${[-12, 9, -7, 12][index % 4]} ${24 + index * 30} 32)" fill="${['#27447b', '#436098', '#1b557a', '#345491'][index % 4]}" font-family="ui-monospace,monospace" font-weight="700" font-size="30" text-anchor="middle">${letter}</text>`,
    )
    .join('');
  $('#captcha-graphic').innerHTML =
    `<svg viewBox="0 0 ${challenge.length * 30 + 18} 58" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect width="100%" height="58" fill="#eaf0ff"/><path d="M0 20Q60 50 130 20T280 35M0 44Q80 10 160 35T280 15" fill="none" stroke="#728ab6" stroke-width="1.2" opacity=".65"/>${glyphs}<path d="M8 10L260 49M22 52L222 6" stroke="#557db4" opacity=".25"/></svg>`;
  renderTextAlternative();
  expiryTimer = setTimeout(updateExpiry, lifetime + 20);
  if (announceChange) announce('验证码已更新，有效期2分钟。');
  if (focus) $('#demo-captcha').focus();
}
$('#refresh-captcha').addEventListener('click', () => {
  clearErrors();
  refreshChallenge({ focus: true });
});
$('#captcha-alternative').addEventListener('click', () => {
  alternative = !alternative;
  renderTextAlternative();
  announce(alternative ? '已切换到可读文字验证，仅用于本地演示。' : '已返回图形验证。');
});
$('#expire-captcha').addEventListener('click', () => {
  cancelPending();
  if (!usesImage()) {
    if (slider) {
      clearTimeout(slider.timer);
      slider.demoExpires = slider.demoProofExpires = 0;
      slider.field.value = '';
      slider.setState('expired', 'expired');
    }
    return;
  }
  expiresAt = 0;
  clearTimeout(expiryTimer);
  updateExpiry();
  fieldError('captcha', '当前验证码已过期，请换一张');
  $('#demo-captcha').focus();
});
$('#password-visible').addEventListener('click', () => {
  const show = $('#demo-password').type === 'password';
  $('#demo-password').type = show ? 'text' : 'password';
  $('#password-visible').textContent = show ? '隐藏' : '显示';
  $('#password-visible').setAttribute('aria-label', show ? '隐藏演示密码' : '显示演示密码');
  $('#password-visible').setAttribute('aria-pressed', String(show));
});
form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (pending) return;
  clearErrors();
  const username = $('#demo-username').value.trim();
  const password = $('#demo-password').value;
  const required = requiresCaptcha();
  const imageRequired = required && usesImage();
  const answer = $('#demo-captcha').value.trim().toUpperCase();
  if (!username) fieldError('username', '请输入演示用户名');
  if (!password) fieldError('password', '请输入演示密码');
  if (imageRequired && !answer) fieldError('captcha', '请输入验证码');
  const invalid = form.querySelector('[aria-invalid="true"]');
  if (invalid) {
    recordFailure();
    invalid.focus();
    return;
  }
  if (imageRequired && Date.now() >= expiresAt) {
    recordFailure();
    fieldError('captcha', '验证码已过期，请换一张后重试');
    announce('验证码已过期，尚未进行演示登录。');
    $('#demo-captcha').focus();
    return;
  }
  if (imageRequired && answer !== challenge) {
    recordFailure();
    refreshChallenge({ focus: true, announceChange: false });
    fieldError('captcha', '验证码不正确，已更新，请重新输入');
    announce('验证码不正确，已生成新的验证码。');
    return;
  }
  if (required && !usesImage() && !slider?.getToken()) {
    recordFailure();
    $('#slider-error').textContent = '请先完成拼图滑块验证';
    slider?.range?.focus();
    return;
  }
  const attempt = ++generation;
  const fail = $('#fail-login').checked;
  $('#fail-login').checked = false;
  setPending(true);
  submitTimer = setTimeout(() => {
    if (attempt !== generation) return;
    setPending(false);
    if (imageRequired && Date.now() >= expiresAt) {
      updateExpiry();
      fieldError('captcha', '验证码已过期，请换一张后重试');
      $('#demo-captcha').focus();
      return;
    }
    if (required && !usesImage() && !slider?.consumeDemoToken()) {
      $('#slider-error').textContent = '验证凭证已过期或已使用，请重新完成拼图';
      slider?.refresh();
      return;
    }
    if (fail || username !== 'demo_admin' || password !== 'NovaPreview123') {
      recordFailure();
      updateVerification();
      feedback(
        fail
          ? '请求失败（模拟）。请重试并完成当前要求的安全验证。'
          : '演示用户名或密码不正确，请使用页面提供的测试账号。',
      );
      $('#login-feedback').focus();
      return;
    }
    challenge = '';
    expiresAt = 0;
    clearTimeout(expiryTimer);
    slider?.remove();
    slider = null;
    failures = 0;
    forcedRisk = false;
    fields.forEach((field) => {
      field.value = '';
    });
    form.hidden = true;
    $('#login-success').hidden = false;
    $('#login-success-title').focus();
  }, 350);
});
$('#login-again').addEventListener('click', () => {
  clearErrors();
  fields[0].value = 'demo_admin';
  fields[1].value = 'NovaPreview123';
  fields[1].type = 'password';
  $('#password-visible').textContent = '显示';
  $('#password-visible').setAttribute('aria-label', '显示演示密码');
  $('#password-visible').setAttribute('aria-pressed', 'false');
  form.hidden = false;
  $('#login-success').hidden = true;
  updateVerification();
  fields[0].focus();
});
window.addEventListener('pagehide', () => {
  cancelPending();
  clearTimeout(expiryTimer);
  fields[1].value = '';
  slider?.remove();
  slider = null;
});
updateVerification();
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    cancelPending();
    updateVerification();
  }
});
