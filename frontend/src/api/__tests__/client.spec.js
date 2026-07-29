import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'


const state = vi.hoisted(() => {
  const auth = {
    isAuthenticated: false,
    accessToken: '',
    setAccessToken: vi.fn(),
    logout: vi.fn(),
  }
  const client = Object.assign(vi.fn(), {
    post: vi.fn(),
    get: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: {
        use: vi.fn((onFulfilled, onRejected) => {
          state.responseRejected = onRejected
        }),
      },
    },
  })
  return {
    auth,
    client,
    axiosPost: vi.fn(),
    routerPush: vi.fn(),
    responseRejected: null,
  }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => state.client),
    post: state.axiosPost,
  },
}))

vi.mock('../../stores/auth.js', () => ({
  useAuthStore: () => state.auth,
}))

vi.mock('../../router/index.js', () => ({
  default: { push: state.routerPush },
}))


describe('认证 401 拦截', () => {
  beforeAll(async () => {
    await import('../client.js')
  })

  beforeEach(() => {
    vi.clearAllMocks()
    state.auth.isAuthenticated = false
  })

  it('未登录请求收到 401 时不调用 logout 形成递归', async () => {
    const error = {
      config: { url: '/courses' },
      response: { status: 401 },
    }

    await expect(state.responseRejected(error)).rejects.toBe(error)

    expect(state.auth.logout).not.toHaveBeenCalled()
    expect(state.routerPush).toHaveBeenCalledWith('/login')
  })

  it('显式跳过刷新流程的认证请求原样返回 401', async () => {
    const error = {
      config: { url: '/auth/logout', skipAuthRefresh: true },
      response: { status: 401 },
    }

    await expect(state.responseRejected(error)).rejects.toBe(error)

    expect(state.auth.logout).not.toHaveBeenCalled()
    expect(state.routerPush).not.toHaveBeenCalled()
  })
})


describe('认证 API', () => {
  beforeAll(async () => {
    const { authAPI } = await import('../auth.js')
    state.authAPI = authAPI
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it.each([
    ['login', ['teacher', 'secret']],
    ['refresh', []],
    ['logout', []],
  ])('%s 请求跳过通用 401 刷新拦截器', async (method, args) => {
    state.authAPI[method](...args)

    expect(state.client.post).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Object),
      { skipAuthRefresh: true },
    )
  })
})
