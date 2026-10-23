// Display-only identity shared by the local dashboard and login preview.
export const defaultBrandName = 'NOVA';

export function brandName(value) {
  const name = typeof value === 'string' ? value.trim() : '';
  return name ? Array.from(name).slice(0, 64).join('') : defaultBrandName;
}

export function brandInitial(value) {
  const character = brandName(value)
    .normalize('NFKC')
    .match(/[\p{L}\p{N}]/u)?.[0];
  return character ? Array.from(character.toUpperCase())[0] : '?';
}

export function savedBrandName() {
  try {
    const settings = JSON.parse(localStorage.getItem('nova-settings'));
    // Match the dashboard's existing settings schema when reading shared data.
    if (
      !settings ||
      typeof settings.workspace !== 'string' ||
      typeof settings.animations !== 'boolean'
    )
      return defaultBrandName;
    return brandName(settings.brandName);
  } catch {
    return defaultBrandName;
  }
}

export function updateLoginBrand(name) {
  name = brandName(name);
  for (const node of document.querySelectorAll('[data-brand-name]')) node.textContent = name;
  for (const node of document.querySelectorAll('[data-brand-initial]'))
    node.textContent = brandInitial(name);
  document.title = `登录页预览 · ${name}`;
}
