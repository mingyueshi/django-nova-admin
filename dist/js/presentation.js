// This hint changes presentation only; the existing handler accepts both modifiers.
export function searchShortcut(platform = navigator.userAgentData?.platform || navigator.platform) {
  return /Mac|iPhone|iPad|iPod/i.test(platform || '')
    ? { label: '⌘ K', spoken: 'Command 加 K', keys: 'Meta+k' }
    : { label: 'Ctrl K', spoken: 'Control 加 K', keys: 'Control+k' };
}
