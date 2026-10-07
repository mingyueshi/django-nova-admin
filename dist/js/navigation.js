// Route labels and the entire navigation hierarchy share one definition.
export const navigationTree = [
  { id: 'overview', label: '工作概览', icon: 'grid' },
  {
    key: 'business',
    label: '业务管理',
    icon: 'layers',
    children: [
      { id: 'catalog', label: '商品管理', icon: 'layers' },
      { id: 'news', label: '新闻资讯', icon: 'book' },
      {
        key: 'organization',
        label: '组织与成员',
        children: [
          { id: 'users', label: '用户管理', icon: 'users' },
          { id: 'roles', label: '角色权限', icon: 'shield' },
        ],
      },
    ],
  },
  {
    key: 'system',
    label: '系统与审计',
    icon: 'settings',
    children: [
      { id: 'audit', label: '操作日志', icon: 'history' },
      { id: 'settings', label: '系统设置', icon: 'settings' },
    ],
  },
  {
    key: 'developer',
    label: '开发与集成',
    icon: 'terminal',
    children: [
      { id: 'components', label: '组件预览', icon: 'layers' },
      { id: 'native-samples', label: '原生模板样本', icon: 'book' },
      { id: 'login-preview', label: '登录页预览', icon: 'shield' },
    ],
  },
];
export function navigationTrail(id, nodes = navigationTree, path = []) {
  for (const n of nodes) {
    if (n.id === id) return [...path, n];
    if (n.children) {
      const result = navigationTrail(id, n.children, [...path, n]);
      if (result.length) return result;
    }
  }
  return [];
}
export function flattenedNavigation(nodes = navigationTree) {
  return nodes.flatMap((n) =>
    n.children ? flattenedNavigation(n.children) : [[n.id, n.icon, n.label]],
  );
}
// Preview preferences are separate from real AdminSite/user-scoped state.
// v1 was seeded with open defaults, so it cannot identify manual choices.
const branchKeys = new Set();
const unreadPreferences = new WeakSet();
(function collect(nodes) {
  for (const node of nodes) {
    if (node.children) {
      branchKeys.add(node.key);
      collect(node.children);
    }
  }
})(navigationTree);
export function navigationPreferenceKey() {
  return 'nova.preview.navigation.v2.' + new URL('.', window.location.href).pathname;
}
export function readNavigationPreferences(fallback) {
  const result = Object.create(null);
  let raw;
  try {
    raw = window.localStorage.getItem(navigationPreferenceKey());
  } catch {
    if (!fallback) unreadPreferences.add(result);
    return fallback || result;
  }
  if (!raw || raw.length > 4000) return result;
  try {
    const saved = JSON.parse(raw);
    if (saved?.version !== 2 || !saved.nodes || Array.isArray(saved.nodes)) return result;
    for (const key of branchKeys) {
      if (Object.hasOwn(saved.nodes, key) && typeof saved.nodes[key] === 'boolean') {
        result[key] = saved.nodes[key];
      }
    }
  } catch {
    // Successfully read but malformed data can be replaced by a fresh choice.
  }
  return result;
}
export function saveNavigationPreference(opened, key, value) {
  if (!branchKeys.has(key) || typeof value !== 'boolean') return false;
  opened[key] = value;
  // Never overwrite unread choices with this page's partial, in-memory state.
  // Reload after storage access recovers to resume safe persistence.
  if (unreadPreferences.has(opened)) return false;
  const nodes = Object.create(null);
  for (const name of branchKeys) {
    if (Object.hasOwn(opened, name) && typeof opened[name] === 'boolean') {
      nodes[name] = opened[name];
    }
  }
  try {
    window.localStorage.setItem(navigationPreferenceKey(), JSON.stringify({ version: 2, nodes }));
    return true;
  } catch {
    // Keep explicit choices in memory even without persistent storage.
    return false;
  }
}
export function renderNavigation(state, icon, escape, opened) {
  const activeKeys = new Set(
    navigationTrail(state.view)
      .map((n) => n.key)
      .filter(Boolean),
  );
  const draw = (nodes, depth = 0) =>
    nodes
      .map((n) => {
        if (n.children) {
          const isOpen = opened[n.key] === true;
          return `<div class="navigation-branch depth-${depth}"><button type="button" class="nav-group ${activeKeys.has(n.key) ? 'contains-active' : ''}" data-nav-group="${n.key}" aria-expanded="${isOpen}" aria-controls="nav-group-${n.key}">${n.icon ? icon(n.icon) : '<span class="nav-tree-dot"></span>'}<span>${n.label}</span>${icon('chevron', 'group-chevron')}</button><div id="nav-group-${n.key}" class="nav-children" ${isOpen ? '' : 'hidden'}>${draw(n.children, depth + 1)}</div></div>`;
        }
        const isActive = state.view === n.id;
        return `<a href="#${n.id}" class="nav-item depth-${depth} ${isActive ? 'active' : ''}" ${isActive ? 'aria-current="page"' : ''}>${depth === 0 ? icon(n.icon) : '<span class="nav-tree-dot"></span>'}<span>${escape(n.label)}</span>${n.id === 'users' ? `<span class="counter">${state.users.length}</span>` : ''}</a>`;
      })
      .join('');
  return draw(navigationTree);
}
export function renderBreadcrumb(state, icon, escape, detail = '') {
  const trail = navigationTrail(state.view);
  return `<nav class="breadcrumb-trail" aria-label="面包屑"><a href="#overview" class="breadcrumb-root">工作空间</a>${trail.map((n, i) => `${icon('chevron')} ${n.id && (i < trail.length - 1 || detail) ? `<a href="#${n.id}">${escape(n.label)}</a>` : `<span ${i === trail.length - 1 && !detail ? 'aria-current="page"' : ''}>${escape(n.label)}</span>`}`).join('')}${detail ? `${icon('chevron')}<strong aria-current="page">${escape(detail)}</strong>` : ''}</nav>`;
}
