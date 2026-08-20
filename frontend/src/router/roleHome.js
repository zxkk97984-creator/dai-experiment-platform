// 角色 → 登录后首页的单一事实来源（登录跳转、守卫回退、侧栏 logo 共用）

export const ROLE_HOME = Object.freeze({
  student: '/student',
  teacher: '/teacher',
  admin: '/admin/users',
})

export function homeForRole(role) {
  return ROLE_HOME[role] || '/login'
}
