/** createLatestRequestGuard 请求序号守卫测试：只接受最新请求，invalidate 后旧 token 失效 */
import { describe, it, expect } from 'vitest'
import { createLatestRequestGuard } from '../latestRequest.js'

describe('createLatestRequestGuard', () => {
  it('接受最新请求 token，拒绝旧 token', () => {
    const guard = createLatestRequestGuard()
    const first = guard.begin()
    const second = guard.begin()
    expect(guard.isLatest(first)).toBe(false)
    expect(guard.isLatest(second)).toBe(true)
  })

  it('invalidate 后所有旧 token 失效', () => {
    const guard = createLatestRequestGuard()
    const token = guard.begin()
    expect(guard.isLatest(token)).toBe(true)
    guard.invalidate()
    expect(guard.isLatest(token)).toBe(false)
  })

  it('新请求使上一个 token 立即失效', () => {
    const guard = createLatestRequestGuard()
    const first = guard.begin()
    expect(guard.isLatest(first)).toBe(true)
    const second = guard.begin()
    expect(guard.isLatest(first)).toBe(false)
    expect(guard.isLatest(second)).toBe(true)
  })
})
