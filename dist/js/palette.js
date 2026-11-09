// Independent presentation preference. Never touches theme or business storage.
export const palettes = Object.freeze([
  ['default', '默认配色'],
  ['teal', '医疗青'],
  ['indigo', '专业靛'],
  ['violet', '文教紫'],
  ['terracotta', '零售陶'],
  ['graphite', '石墨黑'],
  ['midnight', '午夜蓝'],
  ['forest', '松林绿'],
  ['amber', '暖琥珀'],
  ['ocean', '深海青'],
  ['slate', '雾岩灰'],
  ['plum', '暮梅紫'],
  ['coffee', '摩卡棕'],
  ['glacier', '冰川蓝'],
  ['rose', '胭脂红'],
  ['olive', '苔原绿'],
  ['ink', '极夜黑'],
  ['cinnabar', '朱砂红'],
  ['gilded', '鎏金黄'],
  ['emerald', '翡翠绿'],
  ['peacock', '孔雀蓝'],
  ['sunset', '霞光紫'],
  ['industrial', '工业橙'],
  ['lilac', '兰花紫'],
  ['terminal', '终端绿'],
  ['parchment', '宣纸黄'],
]);
// The gallery count and cards share one list; the default option is not a card.
export const palettePresets = Object.freeze(palettes.filter(([key]) => key !== 'default'));
const paletteScenes = Object.freeze({
  teal: '医疗服务 · 清爽专注',
  indigo: '企业办公 · 专业沉稳',
  violet: '文教管理 · 灵感创作',
  terracotta: '零售运营 · 温暖亲和',
  graphite: '通用后台 · 中性克制',
  midnight: '夜间工作 · 深靛层次',
  forest: '自然主题 · 森林薄荷',
  amber: '暖调空间 · 琥珀光感',
  ocean: '监控运维 · 深海冰青',
  slate: '密集表格 · 冷灰秩序',
  plum: '内容审稿 · 柔和梅紫',
  coffee: '阅读写作 · 奶咖暖棕',
  glacier: '科技工作台 · 清冷钢蓝',
  rose: '品牌运营 · 玫瑰酒红',
  olive: '项目管理 · 橄榄苔绿',
  ink: '低干扰办公 · 极夜银灰',
  cinnabar: '政务审批 · 庄重醒目',
  gilded: '金融理财 · 财富质感',
  emerald: '生鲜电商 · 自然新鲜',
  peacock: '交通物流 · 航空出行',
  sunset: '直播文娱 · 游戏运营',
  industrial: '生产制造 · 设备运维',
  lilac: '社交社区 · 婚庆花艺',
  terminal: '研发运维 · 脚本日志',
  parchment: '档案文书 · 合同审阅',
});
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
  syncPaletteCards();
  if (persist) {
    try {
      localStorage.setItem('nova-palette', palette);
    } catch {
      return false;
    }
  }
  return true;
}
export function paletteSummary(value = document.documentElement.dataset.palette) {
  const label = palettes.find(([key]) => key === normalizePalette(value))[1];
  const mode = document.documentElement.dataset.theme === 'dark' ? '深色' : '浅色';
  const automatic = document.documentElement.dataset.themeMode === 'auto' ? '跟随系统 · ' : '';
  return `当前：${label} · ${automatic}${mode}预览`;
}
export function syncPaletteCards() {
  const palette = normalizePalette(document.documentElement.dataset.palette);
  document.querySelectorAll('[data-palette-card]').forEach((card) => {
    card.setAttribute('aria-pressed', String(card.dataset.paletteCard === palette));
    card.querySelector('.palette-card-state').textContent =
      card.dataset.paletteCard === palette ? '使用中' : '点击应用';
  });
  document.querySelectorAll('[data-palette-current]').forEach((status) => {
    status.textContent = paletteSummary(palette);
  });
}
export function renderPaletteCards(value) {
  const selected = normalizePalette(value);
  return palettePresets
    .map(
      ([key, label], index) => `
        <button type="button" class="palette-card" data-palette-card="${key}" aria-pressed="${key === selected}" aria-label="应用${label}配色">
          <span class="palette-mini" aria-hidden="true">
            <span class="palette-mini-sidebar"><i></i><b></b><b></b><b></b></span>
            <span class="palette-mini-main"><span class="palette-mini-top"><i></i><b></b></span><span class="palette-mini-stats"><i></i><i></i><i></i></span><span class="palette-mini-table"><i></i><i></i><i></i></span></span>
          </span>
          <span class="palette-card-heading"><strong>${label}</strong><span class="palette-card-number" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span><span class="palette-card-check" aria-hidden="true">✓</span></span>
          <span class="palette-card-scene">${paletteScenes[key]}</span>
          <span class="palette-card-footer"><span class="palette-swatches" aria-hidden="true"><i class="palette-swatch-bg"></i><i class="palette-swatch-sidebar"></i><i class="palette-swatch-panel"></i><i class="palette-swatch-accent"></i><i class="palette-swatch-text"></i></span><span class="palette-card-state" aria-hidden="true">${key === selected ? '使用中' : '点击应用'}</span></span>
        </button>`,
    )
    .join('');
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
