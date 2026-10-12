import { applyPalette, savedPalette, paletteOptions } from './palette.js';
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
  const values = new Uint32Array(4);
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
        `<text x="${21 + index * 30}" y="33" transform="rotate(${[-12, 9, -7, 12][index]} ${21 + index * 30} 27)" fill="${['#27447b', '#436098', '#1b557a', '#345491'][index]}" font-family="ui-monospace,monospace" font-weight="700" font-size="26" text-anchor="middle">${letter}</text>`,
    )
    .join('');
  $('#captcha-graphic').innerHTML =
    `<svg viewBox="0 0 136 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect width="136" height="48" fill="#eaf0ff"/><path d="M-3 17Q37 39 72 15T139 26M-5 38Q40 7 77 31T139 14" fill="none" stroke="#728ab6" stroke-width="1.2" opacity=".65"/>${glyphs}<path d="M8 10L126 39M22 42L112 6" stroke="#557db4" opacity=".25"/></svg>`;
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
  const answer = $('#demo-captcha').value.trim().toUpperCase();
  if (!username) fieldError('username', '请输入演示用户名');
  if (!password) fieldError('password', '请输入演示密码');
  if (!answer) fieldError('captcha', '请输入验证码');
  const invalid = form.querySelector('[aria-invalid="true"]');
  if (invalid) {
    invalid.focus();
    return;
  }
  if (Date.now() >= expiresAt) {
    fieldError('captcha', '验证码已过期，请换一张后重试');
    announce('验证码已过期，尚未进行演示登录。');
    $('#demo-captcha').focus();
    return;
  }
  if (answer !== challenge) {
    refreshChallenge({ focus: true, announceChange: false });
    fieldError('captcha', '验证码不正确，已更新，请重新输入');
    announce('验证码不正确，已生成新的验证码。');
    return;
  }
  const attempt = ++generation;
  const fail = $('#fail-login').checked;
  $('#fail-login').checked = false;
  setPending(true);
  submitTimer = setTimeout(() => {
    if (attempt !== generation) return;
    setPending(false);
    if (Date.now() >= expiresAt) {
      updateExpiry();
      fieldError('captcha', '验证码已过期，请换一张后重试');
      $('#demo-captcha').focus();
      return;
    }
    if (fail || username !== 'demo_admin' || password !== 'NovaPreview123') {
      refreshChallenge({ announceChange: false });
      feedback(
        fail
          ? '请求失败（模拟）。请输入新验证码后重试。'
          : '演示用户名或密码不正确，请使用页面提供的测试账号。',
      );
      $('#login-feedback').focus();
      return;
    }
    challenge = '';
    expiresAt = 0;
    clearTimeout(expiryTimer);
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
  refreshChallenge();
  fields[0].focus();
});
window.addEventListener('pagehide', () => {
  cancelPending();
  clearTimeout(expiryTimer);
  fields[1].value = '';
});
refreshChallenge({ announceChange: false });
