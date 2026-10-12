// Synchronous, CSP-compatible first paint. Keep whitelist aligned with palette.js.
(() => {
  const root = document.documentElement;
  let mode = 'light';
  let palette = 'default';
  try {
    const value = localStorage.getItem('nova-theme');
    if (['light', 'dark', 'auto'].includes(value)) mode = value;
  } catch {}
  try {
    const value = localStorage.getItem('nova-palette');
    if (['default', 'teal', 'indigo', 'violet', 'terracotta'].includes(value)) palette = value;
  } catch {}
  root.dataset.palette = palette;
  root.dataset.themeMode = mode;
  root.dataset.theme =
    mode === 'auto'
      ? window.matchMedia?.('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : mode;
})();
