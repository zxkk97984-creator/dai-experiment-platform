import { beforeEach, describe, expect, it, vi } from 'vitest'

import { homeForRole, ROLE_HOME } from '../roleHome.js'

// ── 路由守卫测试：/student/feedback 为学生专属，匿名与跨角色均被重定向 ──

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  role: null,
  user: null,
  tryRestoreSession: vi.fn(),
  fetchMe: vi.fn(),
}))

vi.mock('../../stores/auth.js', () => ({
  useAuthStore: () => authState,
}))

import router from '../index.js'

async function navigate(path) {
  await router.push(path)
  await router.isReady().catch(() => {})
  return router.currentRoute.value.path
}

describe('roleHome 角色首页映射', () => {
  it('每个角色映射到其根首页', () => {
    expect(ROLE_HOME.student).toBe('/student')
    expect(ROLE_HOME.teacher).toBe('/teacher')
    expect(ROLE_HOME.admin).toBe('/admin/users')
    expect(ROLE_HOME.developer).toBe('/developer/templates')
  })

  it('homeForRole 为已知角色返回首页', () => {
    expect(homeForRole('student')).toBe('/student')
    expect(homeForRole('teacher')).toBe('/teacher')
    expect(homeForRole('admin')).toBe('/admin/users')
    expect(homeForRole('developer')).toBe('/developer/templates')
  })

  it('未知角色回退到登录页', () => {
    expect(homeForRole('unknown')).toBe('/login')
    expect(homeForRole(null)).toBe('/login')
  })
})

describe('/student/feedback 路由守卫', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.role = null
    authState.user = null
    authState.tryRestoreSession.mockReset()
    authState.fetchMe.mockReset()
  })

  it('路由已注册且为学生专属', () => {
    const route = router.getRoutes().find((r) => r.path === '/student/feedback')
    expect(route).toBeTruthy()
    expect(route.meta.role).toBe('student')
  })

  it('匿名访问重定向到 /login', async () => {
    authState.tryRestoreSession.mockResolvedValue(false)
    const path = await navigate('/student/feedback')
    expect(path).toBe('/login')
  })

  it('非学生角色被重定向到其角色首页', async () => {
    authState.isAuthenticated = true
    authState.role = 'teacher'
    authState.user = { role: 'teacher' }
    authState.fetchMe.mockResolvedValue({ role: 'teacher' })
    const path = await navigate('/student/feedback')
    expect(path).toBe('/teacher')
  })
})
