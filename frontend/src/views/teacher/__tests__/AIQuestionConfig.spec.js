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

  it('以 expanded=true 首次挂载时立即加载已有配置和 Rubric', async () => {
    mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 12, expanded: true },
    })
    await flushPromises()

    expect(aiGradingAPI.getConfig).toHaveBeenCalledWith('assignment', 12)
    expect(aiGradingAPI.listRubrics).toHaveBeenCalledWith('assignment', 12)
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

  it('添加上限规则时提供后端必填的描述字段', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 8, expanded: true },
    })
    await flushPromises()

    const addButton = wrapper.findAll('button').find(button => button.text().includes('添加上限'))
    await addButton.trigger('click')

    expect(wrapper.find('input[placeholder="描述（必填）"]').exists()).toBe(true)
  })

  it('教师约束 JSON 非法时阻止保存并显示错误', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 9, expanded: true },
    })
    await flushPromises()

    const constraints = wrapper.find('textarea[placeholder^="{"]')
    await constraints.setValue('{invalid')
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.updateConfig).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('教师约束 JSON 格式错误')
  })

  it('有未保存配置时先保存再生成 Rubric', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 10, expanded: true },
    })
    await flushPromises()

    const constraints = wrapper.find('textarea[placeholder^="{"]')
    await constraints.setValue('{"required_algorithm":"binary search"}')
    const generateButton = wrapper.findAll('button').find(button => button.text().includes('AI 生成 Rubric'))
    await generateButton.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.updateConfig).toHaveBeenCalledTimes(1)
    expect(aiGradingAPI.generateRubric).toHaveBeenCalledTimes(1)
    expect(aiGradingAPI.updateConfig.mock.invocationCallOrder[0])
      .toBeLessThan(aiGradingAPI.generateRubric.mock.invocationCallOrder[0])
  })

  it('后端拒绝重复测试组 ID 时显示真实接口错误', async () => {
    aiGradingAPI.getConfig.mockResolvedValueOnce({
      data: {
        grading_mode: 'active',
        teacher_constraints: {},
        reference_solution: null,
        test_groups: [
          { id: 'F1', name: '基础', dimension: 'F', max_score: 30, tests: 'def test_1(): pass' },
          { id: 'F2', name: '核心', dimension: 'F', max_score: 30, tests: 'def test_2(): pass' },
          { id: 'R1', name: '边界', dimension: 'R', max_score: 10, tests: 'def test_3(): pass' },
        ],
        score_cap_rules: [],
      },
    })
    aiGradingAPI.updateConfig.mockRejectedValueOnce({
      response: { data: { detail: { message: '测试组 ID 必须唯一' } } },
    })
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 11, expanded: true },
    })
    await flushPromises()

    const ids = wrapper.findAll('input[placeholder="ID (如 F1)"]')
    await ids[1].setValue('F1')
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.updateConfig).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('测试组 ID 必须唯一')
  })
})
