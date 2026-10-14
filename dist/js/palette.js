// Independent presentation preference. Never touches theme or business storage.
export const palettes = Object.freeze([
  ['default', '默认配色'],
  ['teal', '医疗青'],
  ['indigo', '专业靛'],
  ['violet', '文教紫'],
  ['terracotta', '零售陶'],
  ['graphite', '石墨黑'],
  ['midnight', '午夜蓝'],
]);
export function normalizePalette(value) {
  return palettes.some(([key]) => key === value) ? value : 'default';
}
export function savedPalette() {
  try {
    return normalizePalette(localStorage.getItem('nova-palette'));
  } catch {
    return 'default';
  }
}
export function applyPalette(value, persist = false) {
  const palette = normalizePalette(value);
  document.documentElement.dataset.palette = palette;
  document.querySelectorAll('[data-palette-select]').forEach((select) => {
    select.value = palette;
  });
  if (persist) {
    try {
      localStorage.setItem('nova-palette', palette);
    } catch {
      return false;
    }
  }
  return true;
}
export function paletteOptions(value) {
  return palettes
    .map(
      ([key, label]) =>
        `<option value="${key}"${key === normalizePalette(value) ? ' selected' : ''}>${label}</option>`,
    )
    .join('');
}
// Keep open preview pages consistent without writing back or touching other keys.
window.addEventListener('storage', (event) => {
  if (event.key !== 'nova-palette' && event.key !== null) return;
  try {
    if (event.storageArea && event.storageArea !== localStorage) return;
  } catch {
    return;
  }
  applyPalette(event.newValue);
});
