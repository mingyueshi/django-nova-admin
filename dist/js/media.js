// Synthetic local image sheets only. No user supplied URL is ever rendered.
const sources = {
  avatar: 'avatars-sheet.webp',
  product: 'products-sheet.webp',
  cover: 'covers-sheet.webp',
};
const labels = { avatar: '头像', product: '商品图片', cover: '新闻封面' };
const imageStates = new Map();
let api;
const esc = (x) =>
  String(x ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
export function imageSpec(kind, id, title) {
  let index = 0,
    state = 'ready';
  if (kind === 'avatar') {
    index = (Math.max(1, Number(id) || 1) - 1) % 6;
    if (Number(id) === 5 || Number(id) > 24 || !id) state = 'missing';
    if (Number(id) === 6) state = 'error';
  } else if (kind === 'product') {
    index = Math.max(0, Number(id) - (Number(id) >= 108 ? 108 : 101)) % 6;
    if (Number(id) === 107 || Number(id) > 124 || !id) state = 'missing';
    if (Number(id) === 106) state = 'error';
  } else {
    index =
      { 201: 0, 202: 1, 203: 2, 204: 3, 205: 3, 206: 4, 207: 5, 208: 1 }[Number(id)] ??
      Math.max(0, Number(id) - 209) % 6;
    if (Number(id) === 204) state = 'missing';
    if (Number(id) === 205) state = 'error';
  }
  return { kind, index, title, state };
}
function normalized(spec) {
  const kind = Object.hasOwn(sources, spec.kind) ? spec.kind : 'product';
  const index =
    Number.isInteger(Number(spec.index)) && spec.index >= 0 && spec.index < 6
      ? Number(spec.index)
      : 0;
  const key = kind + ':' + index;
  return {
    ...spec,
    kind,
    index,
    key,
    state:
      spec.state === 'missing'
        ? 'missing'
        : imageStates.get(key) || (spec.state === 'error' ? 'error' : 'ready'),
  };
}
export function thumbnail(spec, extra = '') {
  const m = normalized(spec),
    label = labels[m.kind],
    missing = m.state === 'missing';
  return `<button type="button" class="media-thumb media-${m.kind} ${missing ? 'media-missing' : 'media-loading'} ${extra}" data-media-kind="${m.kind}" data-media-index="${m.index}" data-media-state="${m.state}" data-media-key="${m.key}" data-media-title="${esc(m.title)}" aria-label="${esc(m.title)}，${missing ? '未设置' + label : '预览' + label}" aria-busy="${!missing}">${surface(m, false)}<span class="media-zoom" aria-hidden="true">＋</span></button>`;
}
function surface(m, large) {
  const label = labels[m.kind],
    missing = m.state === 'missing';
  return `<span class="media-fallback" ${missing ? '' : 'aria-hidden="true"'}><span aria-hidden="true">▧</span><span class="media-fallback-copy">${missing ? '未设置' + label : '加载中'}</span></span>${missing ? '' : `<span class="media-slice" style="--tile-column:${m.index % 3};--tile-row:${Math.floor(m.index / 3)};--tile-ratio:${m.kind === 'cover' ? '16 / 9' : '1'}"><img data-demo-media data-simulate-failure="${m.state === 'error'}" src="./assets/demo/${sources[m.kind]}" alt="${esc(m.title)}的${label}，合成演示素材" width="${m.kind === 'cover' ? 2048 : 1536}" height="${m.kind === 'cover' ? 768 : 1024}" loading="${large ? 'eager' : 'lazy'}" decoding="async"></span>`}`;
}
function openPreview(spec) {
  const m = normalized(spec);
  api.openOverlay(
    `<section class="modal media-preview" role="dialog" aria-modal="true" aria-labelledby="media-preview-title"><div class="media-preview-header"><div><h2 id="media-preview-title">${esc(m.title)}</h2><p>${labels[m.kind]} · AI 生成的合成演示素材</p></div><button class="icon-button" data-action="close" aria-label="关闭图片预览">${api.icon('close')}</button></div><div class="media-preview-stage"><div class="media-full media-${m.kind} ${m.state === 'missing' ? 'media-missing' : 'media-loading'}" data-media-key="${m.key}" data-media-state="${m.state}" aria-busy="${m.state !== 'missing'}" aria-describedby="media-preview-status">${surface(m, true)}</div></div><div class="media-preview-footer"><span id="media-preview-status" role="status">${m.state === 'missing' ? '此记录没有设置图片，列表保留固定占位。' : m.state === 'error' ? '加载失败示例，点击重新加载可恢复本地素材。' : '本地素材 · 不读取或上传个人照片'}</span>${m.state !== 'missing' ? `<button class="btn" data-media-retry="${m.kind}:${m.index}">重新加载示例</button>` : ''}<button class="btn primary" data-action="close">关闭预览</button>${m.state !== 'missing' ? '<details class="switch-demo-tools media-demo-tools"><summary>图片状态演示</summary><label class="check-label"><input type="checkbox" class="checkbox" id="media-fail-next">下次重新加载时模拟失败</label><p>仅模拟本地图片状态；可反复体验失败、重试与恢复，不请求外部地址。</p></details>' : ''}</div></section>`,
    true,
  );
}
function updatePreview(box, state) {
  const preview = box.closest('.media-preview');
  if (!preview) return;
  const retry = preview.querySelector('[data-media-retry]'),
    status = preview.querySelector('#media-preview-status');
  if (retry) {
    retry.disabled = state === 'loading';
    retry.textContent = state === 'loading' ? '正在重新加载…' : '重新加载示例';
  }
  if (status)
    status.textContent =
      state === 'error'
        ? '图片加载失败，可以再次重新加载；当前记录未改变。'
        : state === 'loading'
          ? '正在重新加载本地示例图片…'
          : '图片已加载 · 本地合成素材，不读取或上传个人照片';
}
function loaded(img) {
  if (img.dataset.simulateFailure === 'true') {
    failed(img);
    return;
  }
  const box = img.closest('.media-thumb,.media-full');
  if (!box) return;
  imageStates.set(box.dataset.mediaKey, 'ready');
  box.dataset.mediaState = 'ready';
  box.classList.remove('media-loading', 'media-error');
  box.classList.add('media-loaded');
  box.setAttribute('aria-busy', 'false');
  box.querySelector('.media-fallback')?.setAttribute('aria-hidden', 'true');
  if (box.matches('button'))
    box.setAttribute(
      'aria-label',
      box.dataset.mediaTitle + '，预览' + labels[box.dataset.mediaKind],
    );
  updatePreview(box, 'ready');
}
function failed(img) {
  const box = img.closest('.media-thumb,.media-full');
  if (!box) return;
  imageStates.set(box.dataset.mediaKey, 'error');
  box.dataset.mediaState = 'error';
  box.classList.remove('media-loading', 'media-loaded');
  box.classList.add('media-error');
  box.setAttribute('aria-busy', 'false');
  box.querySelector('.media-fallback')?.removeAttribute('aria-hidden');
  const copy = box.querySelector('.media-fallback-copy');
  if (copy) copy.textContent = '加载失败';
  if (box.matches('button'))
    box.setAttribute('aria-label', box.dataset.mediaTitle + '，图片加载失败，查看详情');
  updatePreview(box, 'error');
}
// Overlay parents are detached while a nested preview is open. Refresh a parent
// thumbnail only after its local sheet has successfully recovered elsewhere.
export function restoreMedia(root) {
  for (const box of root.querySelectorAll('.media-thumb')) {
    if (imageStates.get(box.dataset.mediaKey) !== 'ready' || box.dataset.mediaState !== 'error')
      continue;
    const img = box.querySelector('img');
    if (!img) continue;
    box.classList.remove('media-error', 'media-loaded');
    box.classList.add('media-loading');
    box.setAttribute('aria-busy', 'true');
    box.querySelector('.media-fallback-copy').textContent = '加载中';
    box.querySelector('.media-fallback')?.setAttribute('aria-hidden', 'true');
    img.dataset.simulateFailure = 'false';
    img.src = './assets/demo/' + sources[box.dataset.mediaKind];
  }
}
export function initMedia(a) {
  api = a;
  document.addEventListener(
    'load',
    (e) => {
      if (e.target.matches?.('img[data-demo-media]')) loaded(e.target);
    },
    true,
  );
  document.addEventListener(
    'error',
    (e) => {
      if (e.target.matches?.('img[data-demo-media]')) failed(e.target);
    },
    true,
  );
  document.addEventListener('click', (e) => {
    const retry = e.target.closest('[data-media-retry]');
    if (retry) {
      if (retry.disabled) return;
      const [kind, raw] = retry.dataset.mediaRetry.split(':'),
        index = Number(raw);
      if (!Object.hasOwn(sources, kind) || !Number.isInteger(index) || index < 0 || index > 5)
        return;
      const failureControl = document.querySelector('#media-fail-next'),
        simulateFailure = !!failureControl?.checked;
      if (failureControl) failureControl.checked = false;
      document.querySelectorAll(`[data-media-key="${kind}:${index}"]`).forEach((box) => {
        const img = box.querySelector('img');
        if (!img) return;
        box.classList.remove('media-error', 'media-loaded');
        box.classList.add('media-loading');
        box.setAttribute('aria-busy', 'true');
        box.querySelector('.media-fallback')?.setAttribute('aria-hidden', 'true');
        box.querySelector('.media-fallback-copy').textContent = '加载中';
        img.dataset.simulateFailure = String(simulateFailure);
        updatePreview(box, 'loading');
        img.src = './assets/demo/' + sources[kind];
      });
      return;
    }
    const button = e.target.closest('[data-media-kind]');
    if (button) {
      e.preventDefault();
      openPreview({
        kind: button.dataset.mediaKind,
        index: Number(button.dataset.mediaIndex),
        state: button.dataset.mediaState,
        title: button.dataset.mediaTitle,
      });
    }
  });
}
