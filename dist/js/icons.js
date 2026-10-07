import { iconCatalog } from './icons-data.js';

// Names select package-owned geometry; neither names nor CSS classes become SVG.
const paths = new Map(iconCatalog.map(({ name, path }) => [name, path]));
const classNames = (value) =>
  typeof value === 'string' && value.length <= 256
    ? value
        .split(/\s+/)
        .filter((token) => /^[A-Za-z_][A-Za-z0-9_-]{0,63}$/.test(token))
        .join(' ')
    : '';

// Keep the established icon(name, cls) API and neutral fallback for unknown names.
export const icon = (name, cls = '') => {
  const classes = classNames(cls);
  const path = typeof name === 'string' ? paths.get(name) : undefined;
  return `<svg class="icon${classes ? ` ${classes}` : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${path || paths.get('grid')}"></path></svg>`;
};

export { iconCatalog, iconCategories } from './icons-data.js';
