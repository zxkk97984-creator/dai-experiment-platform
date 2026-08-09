// usersAPI 学生候选接口：路径与查询参数契约
import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('../client.js', () => ({ default: client }))

import { usersAPI } from '../users.js'

describe('usersAPI 学生候选', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('listStudents 调用 GET /users/students 并传递查询参数', () => {
    usersAPI.listStudents({ q: '张三', page: 1, page_size: 20 })

    expect(client.get).toHaveBeenCalledWith('/users/students', {
      params: { q: '张三', page: 1, page_size: 20 },
    })
  })

  it('listStudents 无参数时只传空 params', () => {
    usersAPI.listStudents()

    expect(client.get).toHaveBeenCalledWith('/users/students', { params: undefined })
  })
})
