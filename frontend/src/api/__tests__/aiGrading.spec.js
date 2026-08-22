// aiGradingAPI 接口契约：长耗时 AI 生成接口的超时配置（避免后端完成前 axios 先中断）
import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
}))

vi.mock('../client.js', () => ({ default: client }))

import { aiGradingAPI } from '../aiGrading.js'

describe('aiGradingAPI 长耗时生成接口超时', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('generateRubric 单独配置 200 秒超时（后端 ai_timeout_seconds 上限 180s）', () => {
    aiGradingAPI.generateRubric('exam', 42)

    const [path, body, config] = client.post.mock.calls[0]
    expect(path).toBe('/ai-grading/questions/exam/42/rubrics/generate')
    expect(body).toBeNull()
    expect(config.timeout).toBe(200000)
  })

  it('generateTestGroups 单独配置 300 秒超时（两次 DeepSeek 调用 + Docker 预检）', () => {
    aiGradingAPI.generateTestGroups('assignment', 7, { teacher_constraints: {} })

    const config = client.post.mock.calls[0][2]
    expect(config.timeout).toBe(300000)
  })
})
