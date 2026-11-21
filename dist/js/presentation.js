// This hint changes presentation only; the existing handler accepts both modifiers.
export function searchShortcut(platform = navigator.userAgentData?.platform || navigator.platform) {
  return /Mac|iPhone|iPad|iPod/i.test(platform || '')
    ? { label: '⌘ K', spoken: 'Command 加 K', keys: 'Meta+k' }
    : { label: 'Ctrl K', spoken: 'Control 加 K', keys: 'Control+k' };
}

export function localDateString(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}
