import { palettes } from './palette.js';

const roles = [
  ['正文', '--body-fg'],
  ['面板', '--nova-panel'],
  ['页面背景', '--body-bg'],
  ['链接', '--link-fg'],
  ['焦点环', '--accent'],
  ['链接悬停', '--link-hover-color'],
  ['选中底色', '--selected-bg'],
  ['按钮底色', '--button-bg'],
  ['按钮悬停', '--button-hover-bg'],
  ['按钮文字', '--button-fg'],
  ['错误文字', '--error-fg'],
  ['控件边界', '--border-color'],
];
const pairs = [
  ['正文 / 面板', '--body-fg', '--nova-panel'],
  ['正文 / 页面', '--body-fg', '--body-bg'],
  ['正文 / 选中行', '--body-fg', '--selected-bg'],
  ['链接 / 选中行', '--link-fg', '--selected-bg'],
  ['悬停链接 / 选中行', '--link-hover-color', '--selected-bg'],
  ['按钮', '--button-fg', '--button-bg'],
  ['悬停按钮', '--button-fg', '--button-hover-bg'],
  ['错误 / 面板', '--error-fg', '--nova-panel'],
  ['焦点环 / 面板', '--accent', '--nova-panel', 3],
  ['输入边界 / 面板', '--border-color', '--nova-panel', 3],
];
const byId = (id) => document.getElementById(id);
const frame = byId('preview');
const preset = byId('preset');
const edits = new Map();
const controls = new Map();
let mode = 'light';
const presetColors = {};

function luminance(hex) {
  const [r, g, b] = hex
    .slice(1)
    .match(/../g)
    .map((part) => {
      const c = parseInt(part, 16) / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function edited(scheme) {
  const key = preset.value + '/' + scheme;
  if (!edits.has(key)) edits.set(key, new Map());
  return edits.get(key);
}

function cssCode() {
  const scope = 'body.nova-admin.nova-palette-' + preset.value + ':not(.nova-contrast-high)';
  function rule(selector, scheme) {
    const values = byId('full-export').checked
      ? new Map([...Object.entries(presetColors[scheme]), ...edited(scheme)])
      : edited(scheme);
    const lines = Array.from(values, ([key, value]) => '  ' + key + ': ' + value + ';');
    return lines.length ? selector + ' {\n' + lines.join('\n') + '\n}' : '';
  }
  const automatic = (scheme) => {
    const css = rule(scope + '.nova-mode-auto', scheme);
    return css && '@media (prefers-color-scheme: ' + scheme + ') {\n' + css + '\n}';
  };
  return [
    rule(scope + '.nova-mode-light', 'light'),
    rule(scope + '.nova-mode-dark', 'dark'),
    automatic('light'),
    automatic('dark'),
  ]
    .filter(Boolean)
    .join('\n\n');
}

function render() {
  const body = frame.contentDocument.body;
  const colors = { ...presetColors[mode], ...Object.fromEntries(edited(mode)) };
  for (const [, key] of roles) body.style.setProperty(key, colors[key]);
  let failed = 0;
  const checks = byId('checks');
  checks.replaceChildren();
  for (const [label, fg, bg, minimum = 4.5] of pairs) {
    const a = luminance(colors[fg]),
      b = luminance(colors[bg]);
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const row = checks.insertRow();
    row.insertCell().textContent = label;
    row.insertCell().textContent = ratio.toFixed(2) + ':1';
    const result = row.insertCell();
    result.textContent = ratio >= minimum ? '通过' : '未通过';
    if (ratio < minimum) {
      failed++;
      result.className = 'fail';
    }
    row.insertCell().textContent = minimum === 3 ? '—' : ratio >= 7 ? '通过' : '未通过';
  }
  byId('summary').textContent =
    '当前外观 ' +
    pairs.length +
    ' 组颜色中，' +
    failed +
    ' 组低于 AA 阈值。增强文字按普通字号 7:1 计算。';
  byId('settings-code').value = 'NOVA_ADMIN_DEFAULT_PALETTE = "' + preset.value + '"';
  byId('css-code').value = cssCode();
  byId('custom-export').hidden = !byId('css-code').value;
  byId('copy').textContent = byId('css-code').value ? '复制 CSS' : '复制配置';
  byId('export-help').textContent = byId('css-code').value
    ? '先设置基础配色，再将 CSS 粘贴到项目样式文件。两种外观分别保存。'
    : '将此行粘贴到项目设置，作为新会话的默认配色。';
  const invalid = byId('colors').querySelector('[aria-invalid=true]');
  byId('copy').disabled = Boolean(invalid);
  byId('copy-status').textContent = invalid ? ' 请先修正标记的 HEX 色值。' : '';
}

function refresh() {
  const body = frame.contentDocument.body;
  if (!body?.classList.contains('preview')) return;
  body.removeAttribute('style');
  const classes = (scheme) =>
    'preview nova-admin nova-mode-' + scheme + ' nova-palette-' + preset.value;
  for (const scheme of ['light', 'dark']) {
    body.className = classes(scheme);
    const style = frame.contentWindow.getComputedStyle(body);
    presetColors[scheme] = Object.fromEntries(
      roles.map(([, key]) => {
        const value = style.getPropertyValue(key).trim().toLowerCase();
        const hex = value.replace(/^#([0-9a-f])([0-9a-f])([0-9a-f])$/, '#$1$1$2$2$3$3');
        return [key, hex];
      }),
    );
  }
  body.className = classes(mode);
  for (const [, key] of roles) {
    const [picker, hex] = controls.get(key);
    picker.value = hex.value = edited(mode).get(key) || presetColors[mode][key];
    hex.removeAttribute('aria-invalid');
    hex.setCustomValidity('');
  }
  render();
}

for (const [key, name] of palettes) preset.add(new Option(name, key));
preset.value = 'teal';
for (const [name, key] of roles) {
  const row = document.createElement('div');
  row.className = 'color-row';
  const label = document.createElement('label'),
    picker = document.createElement('input'),
    hex = document.createElement('input');
  label.textContent = name;
  picker.type = 'color';
  picker.id = 'color' + key;
  label.htmlFor = picker.id;
  hex.type = 'text';
  hex.maxLength = 7;
  hex.setAttribute('aria-label', name + ' HEX');
  function change(input) {
    const value = input.value.toLowerCase();
    if (!/^#[0-9a-f]{6}$/.test(value)) {
      hex.setAttribute('aria-invalid', 'true');
      hex.setCustomValidity('请输入六位十六进制颜色，例如 #123456');
      byId('copy').disabled = true;
      byId('copy-status').textContent = ' 请先修正标记的 HEX 色值。';
      return;
    }
    hex.removeAttribute('aria-invalid');
    hex.setCustomValidity('');
    hex.value = picker.value = value;
    if (value === presetColors[mode]?.[key]) edited(mode).delete(key);
    else edited(mode).set(key, value);
    render();
  }
  for (const input of [picker, hex]) input.addEventListener('input', () => change(input));
  row.append(label, picker, hex);
  byId('colors').append(row);
  controls.set(key, [picker, hex]);
}
preset.addEventListener('change', refresh);
for (const radio of document.querySelectorAll('[name=mode]'))
  radio.addEventListener('change', () => {
    mode = radio.value;
    refresh();
  });
byId('full-export').addEventListener('change', refresh);
byId('reset').addEventListener('click', () => {
  edited('light').clear();
  edited('dark').clear();
  refresh();
});
byId('copy').addEventListener('click', async () => {
  const output = byId('css-code').value ? byId('css-code') : byId('settings-code');
  try {
    await navigator.clipboard.writeText(output.value);
    byId('copy-status').textContent = ' 已复制';
  } catch {
    output.focus();
    output.select();
    byId('copy-status').textContent = ' 已选中，可手动复制';
  }
});
frame.addEventListener('load', refresh);
frame.src = './palette-preview.html';
