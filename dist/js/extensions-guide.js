// Isolated documentation appearance preference; no login or application API.
const button = document.getElementById('guide-theme');
function apply(mode) {
  document.documentElement.dataset.theme = mode;
  button.textContent = mode === 'dark' ? '切换浅色' : '切换深色';
  button.setAttribute('aria-label', button.textContent);
}
try {
  const saved = localStorage.getItem('nova-theme');
  apply(
    saved === 'dark' || (saved === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches)
      ? 'dark'
      : 'light',
  );
} catch {
  apply('light');
}
button.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  apply(next);
  try {
    localStorage.setItem('nova-theme', next);
  } catch {
    // The page remains usable when browser storage is unavailable.
  }
});
