import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const listLogsMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('../../../api/adminLogs.js', () => ({
  adminLogsAPI: { listLogs: listLogsMock },
}))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => ({ showToast: vi.fn() }) }))

import AdminLogsView from '../AdminLogsView.vue'

function payload() {
  return {
    items: [
      { ts: '2026-08-22T10:03:00+00:00', level: 'WARNING', logger: 'dai.exam_grading', rid: 'r4', message: 'ExamSubmission 985 转 review_required' },
      { ts: '2026-08-22T10:01:00+00:00', level: 'ERROR', logger: 'dai.ai_client', rid: 'r2', message: 'ai_retries_exhausted', operation: 'rubric_generation', attempts: 3 },
      { ts: '2026-08-22T10:00:00+00:00', level: 'INFO', logger: 'dai.ai_client', rid: 'r1', message: 'ai_chat_completed', completion_tokens: 800, max_tokens: 8000 },
    ],
    total: 3,
    source: 'api',
    rotated: null,
    file: 'dai-api.log',
    file_size: 4096,
  }
}

describe('AdminLogsView', () => {
  beforeEach(() => {
    listLogsMock.mockReset()
    listLogsMock.mockResolvedValue({ data: payload() })
  })

  it('渲染日志表格：时间/级别/来源/内容与结构化附加字段', async () => {
    const wrapper = mount(AdminLogsView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('系统日志')
    expect(wrapper.text()).toContain('ExamSubmission 985 转 review_required')
    expect(wrapper.text()).toContain('ai_retries_exhausted')
    // 附加字段渲染在详情块
    expect(wrapper.text()).toContain('operation=rubric_generation')
    expect(wrapper.text()).toContain('max_tokens=8000')
    // rid 展示
    expect(wrapper.text()).toContain('rid=r2')
    expect(listLogsMock).toHaveBeenCalledWith(expect.objectContaining({ source: 'api', limit: 300 }))
  })

  it('切换到 Worker 来源时按新 source 请求', async () => {
    const wrapper = mount(AdminLogsView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()

    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    await flushPromises()
    expect(listLogsMock).toHaveBeenLastCalledWith(expect.objectContaining({ source: 'worker' }))
  })

  it('加载失败时展示空状态不崩溃', async () => {
    listLogsMock.mockRejectedValue({ response: { data: { detail: { message: '无权限' } } } })
    const wrapper = mount(AdminLogsView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无匹配日志')
  })
})
