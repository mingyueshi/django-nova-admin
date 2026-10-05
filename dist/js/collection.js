// Local list mechanics only: no DOM, routing, storage, permissions or network.
// Each screen retains its own matching rules, markup and commit workflow.
export function createCollection({
  getRecords,
  filters,
  matches,
  compare,
  pageSize = 10,
  sort = null,
  pageBeforeSort = false,
}) {
  const pageSizes = Object.freeze([10, 20, 50, 100]);
  if (!pageSizes.includes(pageSize)) throw new RangeError('Unsupported default page size');
  const defaultPageSize = pageSize;
  const positiveInteger = (value) =>
    /^\d+$/.test(String(value ?? '')) && Number.isSafeInteger(Number(value)) && Number(value) > 0
      ? Number(value)
      : null;
  const defaults = Object.fromEntries(
    Object.entries(filters).map(([key, field]) => [key, field.default]),
  );
  const state = {
    ...defaults,
    page: 1,
    pageSize: defaultPageSize,
    selected: new Set(),
    ...(sort ? { sort } : {}),
  };

  function filtered() {
    const rows = getRecords().filter((record) => matches(record, state));
    return compare ? rows.sort((a, b) => compare(a, b, state)) : rows;
  }

  function pageItems() {
    const all = filtered();
    const pages = Math.max(1, Math.ceil(all.length / state.pageSize));
    state.page = Math.min(positiveInteger(state.page) || 1, pages);
    const rows = all.slice((state.page - 1) * state.pageSize, state.page * state.pageSize);
    const selectedVisible = rows.filter((record) => state.selected.has(record.id)).length;
    return {
      all,
      rows,
      pages,
      selectedVisible,
      indeterminate: selectedVisible > 0 && selectedVisible < rows.length,
    };
  }

  function restore(route) {
    const previous = Object.keys(filters)
      .map((key) => state[key])
      .join('\0');
    const params = new URLSearchParams(route.split('?')[1] || '');
    for (const [key, field] of Object.entries(filters)) {
      const value = params.get(field.param || key);
      state[key] = field.parse ? field.parse(value) : value || field.default;
    }
    state.page = positiveInteger(params.get('page')) || 1;
    const size = positiveInteger(params.get('per_page'));
    state.pageSize = pageSizes.includes(size) ? size : defaultPageSize;
    if (sort) state.sort = params.get('sort') === 'asc' ? 'asc' : 'desc';
    if (
      previous !==
      Object.keys(filters)
        .map((key) => state[key])
        .join('\0')
    )
      state.selected.clear();
  }

  function queryString() {
    const params = new URLSearchParams();
    for (const [key, field] of Object.entries(filters)) {
      if (state[key] !== field.default) params.set(field.param || key, state[key]);
    }
    if (state.pageSize !== defaultPageSize) params.set('per_page', state.pageSize);
    const addPage = () => {
      if (state.page > 1) params.set('page', state.page);
    };
    if (pageBeforeSort) addPage();
    if (sort && state.sort !== sort) params.set('sort', state.sort);
    if (!pageBeforeSort) addPage();
    return params.size ? '?' + params.toString() : '';
  }

  function setPage(value) {
    const parsed = positiveInteger(value);
    if (parsed === null) return false;
    state.page = parsed;
    pageItems();
    return true;
  }

  function setPageSize(value) {
    const parsed = positiveInteger(value);
    if (!pageSizes.includes(parsed)) return false;
    state.pageSize = parsed;
    state.page = 1;
    return true;
  }

  function setFilter(key, value) {
    state[key] = value;
    state.page = 1;
    state.selected.clear();
  }

  function resetFilters({ resetSort = false, resetPageSize = false } = {}) {
    Object.assign(state, defaults, { page: 1 });
    state.selected.clear();
    if (resetSort && sort) state.sort = sort;
    if (resetPageSize) state.pageSize = defaultPageSize;
  }

  function select(id, checked) {
    if (checked) state.selected.add(id);
    else state.selected.delete(id);
  }

  function selectPage(checked) {
    pageItems().rows.forEach((record) => select(record.id, checked));
  }

  return {
    state,
    get pageSize() {
      return state.pageSize;
    },
    pageSizes,
    setPage,
    setPageSize,
    filtered,
    pageItems,
    restore,
    queryString,
    setFilter,
    resetFilters,
    select,
    selectPage,
  };
}
