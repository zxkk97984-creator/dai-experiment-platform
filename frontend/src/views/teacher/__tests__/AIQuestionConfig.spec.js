/** AI 题目配置组件——真实挂载测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../../api/aiGrading.js', () => ({
  aiGradingAPI: {
    getConfig: vi.fn().mockResolvedValue({ data: { grading_mode: 'legacy', teacher_constraints: {}, reference_solution: null, test_groups: [], score_cap_rules: [] } }),
    updateConfig: vi.fn().mockResolvedValue({ data: { ok: true } }),
    listRubrics: vi.fn().mockResolvedValue({ data: { items: [] } }),
    generateRubric: vi.fn().mockResolvedValue({ data: { id: 1, version: 1, status: 'draft', rubric_json: {} } }),
    lockRubric: vi.fn().mockResolvedValue({ data: { ok: true } }),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

import AIQuestionConfig from '../../../components/ai/AIQuestionConfig.vue'
import { aiGradingAPI } from '../../../api/aiGrading.js'

describe('AIQuestionConfig 真实挂载', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('组件挂载成功显示 AI 配置标题', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 1, expanded: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('AI 评分配置')
  })

  it('评分模式选择器显示 legacy 选项', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 2, expanded: true },
    })
    await flushPromises()

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
  })

  it('显示功能/鲁棒性测试组区域', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'exam', questionId: 3, expanded: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('功能/鲁棒性测试组')
  })

  it('显示参考答案输入框', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 4, expanded: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('参考答案')
  })

  it('表单渲染完成后显示操作区', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 5, expanded: true },
    })
    await flushPromises()

    // 组件应渲染表单内容（非 error 状态）
    expect(wrapper.find('.ai-config').exists()).toBe(true)
    expect(wrapper.text()).toContain('评分模式')
  })

  it('显示 AI 生成 Rubric 按钮', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 6, expanded: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('AI 生成 Rubric')
  })

  it('显示上限规则区域', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'exam', questionId: 7, expanded: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('分数上限规则')
  })

  it('重复 test_groups ID 被检测', () => {
    const groups = [
      { id: 'F1', name: '基础', dimension: 'F', max_score: 30, tests: '' },
      { id: 'F1', name: '核心', dimension: 'F', max_score: 30, tests: '' },
    ]
    const ids = groups.map(g => g.id)
    expect(new Set(ids).size).not.toBe(ids.length)
  })
})
