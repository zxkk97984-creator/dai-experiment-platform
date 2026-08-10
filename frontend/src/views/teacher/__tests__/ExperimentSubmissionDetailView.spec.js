import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../../api/experiments.js', () => ({
  experimentsAPI: { getSubmission: vi.fn(), updateReview: vi.fn() },
}))

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '21' }, meta: { role: 'teacher' } }),
  useRouter: () => ({ push: routerPush }),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(), push: vi.fn(), replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/submissions/21' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

import { experimentsAPI } from '../../../api/experiments.js'
import ExperimentSubmissionDetailView from '../ExperimentSubmissionDetailView.vue'

const DETAIL = {
  id: 21,
  attempt_number: 2,
  student_name: '张三',
  student_username: '20260001',
  course_name: '机器学习实践',
  entry_name: '数据分析入门',
  submitted_at: '2026-08-07T01:54:33Z',
  score: null,
  feedback: null,
  reviewed_at: null,
  cells_snapshot: {
    markdown: '# 数据分析入门',
    code: 'print("hello")',
    empty: '',
  },
  cell_metadata: {
    markdown: { type: 'markdown', order: 0 },
    code: { type: 'code', order: 1 },
    empty: { type: 'code', order: 2 },
  },
  outputs_snapshot: {
    code: { execution_count: 1, outputs: [{ output_type: 'stream', text: 'hello\n' }] },
  },
}

function mountPage() {
  return mount(ExperimentSubmissionDetailView, {
    global: {
      stubs: {
        AppLayout: { template: '<main><slot /></main>' },
        AppIcon: { template: '<i class="icon-stub" />' },
      },
    },
  })
}

describe('实验提交评分工作台', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    experimentsAPI.getSubmission.mockResolvedValue({ data: DETAIL })
    experimentsAPI.updateReview.mockResolvedValue({ data: { ...DETAIL, score: 90 } })
  })

  it('展示学生上下文、Markdown、代码和执行输出', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('提交详情 / 评分工作台')
    expect(text).toContain('张三')
    expect(text).toContain('20260001')
    expect(text).toContain('机器学习实践')
    expect(wrapper.find('.markdown-body h1').text()).toBe('数据分析入门')
    expect(text).toContain('print("hello")')
    expect(text).toContain('hello')
  })

  it('默认收起空单元格并可展开全部', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.findAll('.snapshot-cell')).toHaveLength(2)
    expect(wrapper.text()).toContain('1 个空单元格已收起')
    await wrapper.find('.snapshot-footer button').trigger('click')
    expect(wrapper.findAll('.snapshot-cell')).toHaveLength(3)
    expect(wrapper.text()).toContain('收起空单元格')
  })

  it('允许只保存教师反馈且不提交空分数', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('#review-feedback').setValue('建议补充结果解释')
    await wrapper.find('.save-button').trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateReview).toHaveBeenCalledWith(21, {
      feedback: '建议补充结果解释',
    })
  })

  it('保存有效分数和反馈后刷新详情', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('#review-score').setValue('92.5')
    await wrapper.find('#review-feedback').setValue('完成度很好')
    await wrapper.find('.save-button').trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateReview).toHaveBeenCalledWith(21, {
      score: 92.5,
      feedback: '完成度很好',
    })
    expect(experimentsAPI.getSubmission).toHaveBeenCalledTimes(2)
  })

  it('拒绝超出范围的分数', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('#review-score').setValue('101')
    await wrapper.find('.save-button').trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateReview).not.toHaveBeenCalled()
  })

  it('返回提交列表并处理加载失败', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.back-button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/teacher/submissions')

    experimentsAPI.getSubmission.mockRejectedValueOnce(new Error('network'))
    const errorWrapper = mountPage()
    await flushPromises()
    expect(errorWrapper.text()).toContain('提交详情暂时无法加载')
  })
})
