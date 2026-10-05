// All records are synthetic. Replace this module at the integration boundary.
const names = [
  '林知夏',
  '陈屿',
  '苏念',
  '周予安',
  '沈言',
  '许清和',
  '江晚',
  '陆景明',
  '白亦舟',
  '顾星遥',
  '宋未央',
  '叶知秋',
  '温书宁',
  '黎初',
  '程野',
  '孟云舒',
  '何雨桐',
  '方聿',
  '唐月白',
  '秦序',
  '乔安',
  '夏泽',
  '莫青',
  '简宁',
];
export const initialUsers = names.map((name, i) => ({
  id: i + 1,
  name,
  email: `demo${String(i + 1).padStart(2, '0')}@example.com`,
  role: ['管理员', '编辑', '只读成员', '编辑', '编辑', '只读成员'][i % 6],
  status: i % 7 === 6 ? '已停用' : i % 5 === 4 ? '待激活' : '正常',
  team: ['产品设计', '研发中心', '内容运营', '客户服务'][i % 4],
  joined: `2026-09-${String(28 - (i % 22)).padStart(2, '0')}`,
  color: ['violet', 'blue', 'peach', 'mint'][i % 4],
}));
export const initialPermissions = {
  管理员: [true, true, true, true, true, true, true, true, true, true, true, true],
  编辑: [true, true, true, false, true, true, true, false, true, false, false, false],
  只读成员: [true, false, false, false, true, false, false, false, true, false, false, false],
};
export const nav = [
  ['overview', 'grid', '工作概览'],
  ['users', 'users', '用户管理'],
  ['roles', 'shield', '角色权限'],
  ['audit', 'history', '操作日志'],
  ['components', 'layers', '组件预览'],
];
export const metricSets = {
  7: [1286, 326, 98.6, 8420],
  30: [8420, 1286, 99.2, 28640],
  90: [22640, 3812, 98.9, 89410],
};
