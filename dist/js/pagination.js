// Shared DOM presentation for the three local collections. No persistence or routing.
export function pagination(collection, name, attribute, label, unit = '条') {
  const { all, pages } = collection.pageItems();
  const { page, pageSize } = collection.state;
  const pageNumbers = new Set([1, pages, page - 1, page, page + 1]);
  const ordered = [...pageNumbers].filter((n) => n > 0 && n <= pages).sort((a, b) => a - b);
  const numbered = ordered
    .map(
      (n, i) =>
        `${i && n - ordered[i - 1] > 1 ? '<span class="pagination-gap" aria-hidden="true">…</span>' : ''}<button type="button" ${attribute}="${n}" class="${page === n ? 'active' : ''}" ${page === n ? 'aria-current="page"' : ''} aria-label="${label}第 ${n} 页">${n}</button>`,
    )
    .join('');
  return `<div class="table-footer collection-footer"><span class="collection-total" role="status">共 ${all.length} ${unit}${all.length ? ` · 第 ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, all.length)} 条` : ''}</span><div class="collection-paging"><select id="${name}-page-size" data-page-size="${name}" aria-label="${label}每页条数">${collection.pageSizes.map((size) => `<option value="${size}" ${size === pageSize ? 'selected' : ''}>${size} 条/页</option>`).join('')}</select><nav class="pagination" aria-label="${label}分页"><button type="button" ${attribute}="${page - 1}" ${page === 1 ? 'disabled' : ''} aria-label="${label}上一页">‹</button>${numbered}<button type="button" ${attribute}="${page + 1}" ${page === pages ? 'disabled' : ''} aria-label="${label}下一页">›</button></nav><form class="page-jump" data-page-jump="${name}" novalidate><label for="${name}-page-input">前往</label><input id="${name}-page-input" name="page" type="text" inputmode="numeric" pattern="[0-9]*" value="${page}" maxlength="16" aria-label="${label}跳转页码" aria-describedby="${name}-page-error" ${pages === 1 ? 'disabled' : ''}><span>/${pages} 页</span><button type="submit" class="btn" aria-label="${label}跳转" ${pages === 1 ? 'disabled' : ''}>跳转</button><span id="${name}-page-error" class="page-jump-error" role="alert"></span></form></div></div>`;
}

export function submitPageJump(event, collection, name, navigate) {
  const form = event.target;
  if (!form.matches(`[data-page-jump="${name}"]`)) return false;
  event.preventDefault();
  const input = form.elements.page;
  if (!collection.setPage(input.value.trim())) {
    input.setAttribute('aria-invalid', 'true');
    form.querySelector('.page-jump-error').textContent = '请输入有效的正整数页码';
    input.focus();
    return true;
  }
  navigate(`#${name}-page-input`);
  return true;
}
