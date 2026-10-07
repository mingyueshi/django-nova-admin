import { icon, iconCatalog, iconCategories } from './icons.js';

export function initIconGuide(doc) {
  const grid = doc.querySelector('#icon-grid');
  if (!grid || grid.dataset.initialized === 'true') return;
  grid.dataset.initialized = 'true';
  const search = doc.querySelector('#icon-search');
  const category = doc.querySelector('#icon-category');
  for (const [value, label] of Object.entries(iconCategories)) {
    const option = doc.createElement('option');
    option.value = value;
    option.textContent = label;
    category.append(option);
  }
  const cards = iconCatalog.map((entry) => {
    const card = doc.createElement('li');
    card.className = 'icon-card';
    // Only the fixed catalog icon helper produces markup; user input stays text.
    card.innerHTML = icon(entry.name);
    const name = doc.createElement('code');
    name.textContent = entry.name;
    const label = doc.createElement('span');
    label.textContent = entry.label;
    card.append(name, label);
    grid.append(card);
    return { card, entry };
  });
  const filter = () => {
    const query = search.value.trim().toLowerCase();
    let count = 0;
    for (const { card, entry } of cards) {
      card.hidden =
        (category.value && category.value !== entry.category) ||
        !`${entry.name} ${entry.label} ${iconCategories[entry.category]}`
          .toLowerCase()
          .includes(query);
      if (!card.hidden) count++;
    }
    doc.querySelector('#icon-results').textContent = `显示 ${count} / ${iconCatalog.length} 个图标`;
    doc.querySelector('#icon-empty').hidden = count !== 0;
  };
  search.addEventListener('input', filter);
  category.addEventListener('change', filter);
  doc.querySelector('#icon-reset').addEventListener('click', () => {
    search.value = '';
    category.value = '';
    filter();
    search.focus();
  });
  filter();
}

if (typeof document !== 'undefined') initIconGuide(document);
