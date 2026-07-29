import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'


const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  login: vi.fn(),
  refresh: vi.fn(),
  me: vi.fn(),
}))

vi.mock('../../api/auth.js', () => ({
  authAPI: mocks,
}))

import { useAuthStore } from '../auth.js'


describe('useAuthStore logout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('用 access token 快照发起服务端退出，并立即清除本地会话', async () => {
    let resolveLogout
    mocks.logout.mockImplementation(
      () => new Promise((resolve) => {
        resolveLogout = resolve
      }),
    )
    const auth = useAuthStore()
    auth.setAccessToken('access-token')
    auth.setUser({ id: 1, username: 'teacher', role: 'teacher' })

    const logoutPromise = auth.logout()

    expect(logoutPromise).toBeInstanceOf(Promise)
    expect(mocks.logout).toHaveBeenCalledWith('access-token')
    expect(auth.accessToken).toBe('')
    expect(auth.user).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()

    resolveLogout({})
    await logoutPromise
  })
})
