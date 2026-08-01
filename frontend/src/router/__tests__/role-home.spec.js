import { describe, expect, it } from 'vitest'

import { homeForRole, ROLE_HOME } from '../roleHome.js'

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
