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
    generateTestGroups: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

import AIQuestionConfig from '../../../components/ai/AIQuestionConfig.vue'
import AiConfigForm from '../../../components/ai/AiConfigForm.vue'
import { aiGradingAPI } from '../../../api/aiGrading.js'

describe('AIQuestionConfig 真实挂载', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // clearAllMocks 不清除实现：恢复默认配置，避免用例间泄漏
    aiGradingAPI.getConfig.mockResolvedValue({ data: { grading_mode: 'legacy', teacher_constraints: {}, reference_solution: null, test_groups: [], score_cap_rules: [] } })
    aiGradingAPI.updateConfig.mockResolvedValue({ data: { ok: true } })
    aiGradingAPI.listRubrics.mockResolvedValue({ data: { items: [] } })
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

  it('自然语言教师要求保存为 requirements_text', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 9, expanded: true },
    })
    await flushPromises()

    const constraints = wrapper.find('[data-testid="teacher-constraints-input"]')
    await constraints.setValue('  必须正确处理空列表\n禁止使用全局变量  ')
    const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存配置'))
    await saveButton.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.updateConfig).toHaveBeenCalledWith('assignment', 9, expect.objectContaining({
      teacher_constraints: {
        requirements_text: '必须正确处理空列表\n禁止使用全局变量',
      },
    }))
    // 点击「保存配置」成功时通知父组件刷新列表并进入下一题
    expect(wrapper.emitted('saved')).toEqual([[9]])
  })

  it('生成 Rubric 前的内部自动保存不会 emit saved', async () => {
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 10, expanded: true },
    })
    await flushPromises()

    const constraints = wrapper.find('[data-testid="teacher-constraints-input"]')
    await constraints.setValue('必须使用二分查找')
    const generateButton = wrapper.findAll('button').find(button => button.text().includes('AI 生成 Rubric'))
    await generateButton.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.updateConfig).toHaveBeenCalledTimes(1)
    expect(aiGradingAPI.generateRubric).toHaveBeenCalledTimes(1)
    expect(aiGradingAPI.updateConfig.mock.invocationCallOrder[0])
      .toBeLessThan(aiGradingAPI.generateRubric.mock.invocationCallOrder[0])
    expect(wrapper.emitted('saved')).toBeUndefined()
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

  // ══ AI 生成测试组 ══════════════════════════════════════════════════

  const generatedGroups = [
    { id: 'F1', name: '基础', dimension: 'F', max_score: 30, tests: 'def test_f1(): assert True' },
    { id: 'F2', name: '核心', dimension: 'F', max_score: 30, tests: 'def test_f2(): assert True' },
    { id: 'R1', name: '边界', dimension: 'R', max_score: 10, tests: 'def test_r1(): assert True' },
  ]
  const genResponse = (groups = generatedGroups) => ({
    data: {
      test_groups: groups,
      validation: { f_total: 60, r_total: 10, group_count: groups.length, f_group_count: 2, r_group_count: 1 },
      warnings: [], generation_id: 'g-test-1',
    },
  })

  function genBtn(wrapper) {
    // 生成中文本变为「生成中…」，两种状态都需可匹配
    return wrapper.findAll('button').find(
      (b) => b.text().includes('AI 生成测试组') || b.text().includes('生成中…'),
    )
  }

  it('空草稿时点击直接请求生成，不弹覆盖确认；成功整体回填并标记 dirty，不触发 PUT', async () => {
    aiGradingAPI.generateTestGroups.mockResolvedValue(genResponse())
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 20, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()

    expect(aiGradingAPI.generateTestGroups).toHaveBeenCalledTimes(1)
    expect(aiGradingAPI.generateTestGroups).toHaveBeenCalledWith(
      'assignment', 20, expect.objectContaining({ teacher_constraints: {}, reference_solution: null }),
    )
    // 无覆盖确认弹窗
    expect(wrapper.text()).not.toContain('覆盖当前测试组草稿')
    // 整体回填 + 成功提示
    expect(wrapper.text()).toContain('已回填草稿，请检查并保存')
    expect(wrapper.findAll('input[placeholder="ID (如 F1)"]')).toHaveLength(3)
    // dirty → 保存按钮可用；但生成本身不触发 PUT
    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存配置'))
    expect(saveBtn.attributes('disabled')).toBeUndefined()
    expect(aiGradingAPI.updateConfig).not.toHaveBeenCalled()
  })

  it('已有测试组时点击先弹覆盖确认；取消时不请求且草稿不变', async () => {
    aiGradingAPI.getConfig.mockResolvedValue({
      data: {
        grading_mode: 'active', teacher_constraints: {}, reference_solution: null,
        test_groups: [
          { id: 'F1', name: '旧功能', dimension: 'F', max_score: 60, tests: 'def test_old(): pass' },
          { id: 'R1', name: '旧鲁棒', dimension: 'R', max_score: 10, tests: 'def test_old_r(): pass' },
        ],
        score_cap_rules: [],
      },
    })
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 21, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('覆盖当前测试组草稿')
    expect(aiGradingAPI.generateTestGroups).not.toHaveBeenCalled()

    // 默认按钮为取消；点击后不请求、旧草稿保留
    const cancelBtn = wrapper.findAll('button').find((b) => b.text() === '取消')
    await cancelBtn.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.generateTestGroups).not.toHaveBeenCalled()
    const ids = wrapper.findAll('input[placeholder="ID (如 F1)"]').map((i) => i.element.value)
    expect(ids).toEqual(['F1', 'R1'])
  })

  it('确认覆盖后生成并整体替换草稿', async () => {
    aiGradingAPI.getConfig.mockResolvedValue({
      data: {
        grading_mode: 'active', teacher_constraints: {}, reference_solution: null,
        test_groups: [
          { id: 'F1', name: '旧功能', dimension: 'F', max_score: 60, tests: 'def test_old(): pass' },
          { id: 'R1', name: '旧鲁棒', dimension: 'R', max_score: 10, tests: 'def test_old_r(): pass' },
        ],
        score_cap_rules: [],
      },
    })
    aiGradingAPI.generateTestGroups.mockResolvedValue(genResponse())
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 22, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()
    const confirmBtn = wrapper.findAll('button').find((b) => b.text() === '确认生成')
    await confirmBtn.trigger('click')
    await flushPromises()

    expect(aiGradingAPI.generateTestGroups).toHaveBeenCalledTimes(1)
    // 旧组整体被新组替换（2 组 → 3 组）
    expect(wrapper.findAll('input[placeholder="ID (如 F1)"]')).toHaveLength(3)
    expect(wrapper.text()).toContain('已回填草稿，请检查并保存')
    expect(aiGradingAPI.updateConfig).not.toHaveBeenCalled()
  })

  it('失败保留旧草稿并展示后端 message + 逐项 issues', async () => {
    aiGradingAPI.getConfig.mockResolvedValue({
      data: {
        grading_mode: 'active', teacher_constraints: {}, reference_solution: null,
        test_groups: [
          { id: 'F1', name: '旧功能', dimension: 'F', max_score: 60, tests: 'def test_old(): pass' },
          { id: 'R1', name: '旧鲁棒', dimension: 'R', max_score: 10, tests: 'def test_old_r(): pass' },
        ],
        score_cap_rules: [],
      },
    })
    aiGradingAPI.generateTestGroups.mockRejectedValue({
      response: { data: { detail: {
        message: 'AI 生成测试组不合规，请重新生成或手动修改',
        fields: { issues: ['缺少 R 组', 'F1.tests 语法错误: 第 2 行 invalid syntax'] },
      } } },
    })
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 23, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '确认生成').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('AI 生成测试组不合规，请重新生成或手动修改')
    expect(wrapper.text()).toContain('缺少 R 组')
    expect(wrapper.text()).toContain('F1.tests 语法错误')
    // 旧草稿保留
    const ids = wrapper.findAll('input[placeholder="ID (如 F1)"]').map((i) => i.element.value)
    expect(ids).toEqual(['F1', 'R1'])
    // 提供重新生成入口（按钮仍在）
    expect(genBtn(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('生成中按钮禁用并显示「生成中…」，防重复点击', async () => {
    let resolveFn
    aiGradingAPI.generateTestGroups.mockReturnValue(new Promise((r) => { resolveFn = r }))
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 24, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()

    const btn = genBtn(wrapper)
    expect(btn.text()).toContain('生成中…')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(aiGradingAPI.generateTestGroups).toHaveBeenCalledTimes(1)

    // 完成后恢复
    resolveFn(genResponse())
    await flushPromises()
    expect(genBtn(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('生成期间切换题目：迟到响应被丢弃，不回填新题目', async () => {
    let resolveOld
    aiGradingAPI.generateTestGroups.mockReturnValueOnce(new Promise((r) => { resolveOld = r }))
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 25, expanded: true },
    })
    await flushPromises()

    await genBtn(wrapper).trigger('click')
    await flushPromises()
    expect(aiGradingAPI.generateTestGroups).toHaveBeenCalledTimes(1)

    // 切到另一题（新题无测试组）
    await wrapper.setProps({ questionId: 26 })
    await flushPromises()

    // 旧请求此时才返回
    resolveOld(genResponse())
    await flushPromises()

    // 新题配置未被污染
    const ids = wrapper.findAll('input[placeholder="ID (如 F1)"]')
    expect(ids).toHaveLength(0)
    expect(wrapper.text()).not.toContain('已回填草稿，请检查并保存')
  })

  it('shadow/active 且无锁定 Rubric 时显示门禁提示；有锁定 Rubric 时隐藏', async () => {
    aiGradingAPI.getConfig.mockResolvedValue({
      data: {
        grading_mode: 'shadow',
        teacher_constraints: {}, reference_solution: null,
        test_groups: [{ id: 'F1', name: '基础', dimension: 'F', max_score: 60, tests: 'x' },
                       { id: 'R1', name: '边界', dimension: 'R', max_score: 10, tests: 'x' }],
        score_cap_rules: [],
      },
    })
    aiGradingAPI.listRubrics.mockResolvedValue({ data: { items: [] } })
    const wrapper = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 13, expanded: true },
    })
    await flushPromises()
    expect(wrapper.find('.gate-warn').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚无可发布的 Rubric，请先生成并锁定')

    // 存在锁定 Rubric → 提示隐藏
    aiGradingAPI.listRubrics.mockResolvedValueOnce({
      data: { items: [{ id: 1, version: 1, status: 'locked', model_name: 'gpt-4o' }] },
    })
    const wrapper2 = mount(AIQuestionConfig, {
      props: { kind: 'assignment', questionId: 14, expanded: true },
    })
    await flushPromises()
    expect(wrapper2.find('.gate-warn').exists()).toBe(false)
  })
})

// ══ AiConfigForm 纯表单层（草稿模式：无 questionId，不调后端） ════════
describe('AiConfigForm 草稿模式（无 questionId）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const draft = { grading_mode: 'legacy', teacher_constraints: {}, reference_solution: '', test_groups: [], score_cap_rules: [] }

  it('无 questionId 可编辑全部字段，且不调用任何 AI 接口', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    await flushPromises()

    expect(wrapper.text()).toContain('评分模式')
    expect(wrapper.text()).toContain('功能/鲁棒性测试组')

    // 评分模式切 shadow + 添加测试组
    await wrapper.find('select').setValue('shadow')
    await wrapper.findAll('button').find((b) => b.text().includes('添加测试组')).trigger('click')
    await flushPromises()

    // 草稿模式不调后端
    expect(aiGradingAPI.getConfig).not.toHaveBeenCalled()
    expect(aiGradingAPI.updateConfig).not.toHaveBeenCalled()
    expect(aiGradingAPI.generateRubric).not.toHaveBeenCalled()
    // 编辑结果通过 update:modelValue 交给父组件
    const last = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(last.grading_mode).toBe('shadow')
    expect(last.test_groups).toHaveLength(1)
    expect(last.test_groups[0]).toMatchObject({ dimension: 'F', max_score: 0 })
  })

  it('测试组分数合计提供本地校验提示（F=60、R=10）', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('添加测试组')).trigger('click')
    await flushPromises()

    const idInput = wrapper.findAll('input[placeholder="ID (如 F1)"]')[0]
    const nameInput = wrapper.findAll('input[placeholder="名称"]')[0]
    await idInput.setValue('F1')
    await nameInput.setValue('基础')
    await wrapper.findAll('input[placeholder="满分"]')[0].setValue('60')
    await flushPromises()

    expect(wrapper.text()).toContain('F 总计 60/60')
    expect(wrapper.text()).toContain('R 总计 0/10')
  })

  it('教师硬性要求使用自然语言说明、示例和 2000 字限制', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    await flushPromises()

    const constraints = wrapper.find('[data-testid="teacher-constraints-input"]')
    expect(wrapper.text()).toContain('教师硬性要求（可选）')
    expect(wrapper.text()).toContain('此处内容将用于生成评分规则并影响 AI 评分')
    expect(constraints.attributes('placeholder')).toContain('每行填写一条必须满足的规则')
    expect(constraints.attributes('maxlength')).toBe('2000')
  })

  it('自然语言输入 trim 后通过 modelValue 保存为 requirements_text，空输入保存为 {}', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    const constraints = wrapper.find('[data-testid="teacher-constraints-input"]')
    await constraints.setValue('  必须正确处理空列表\n禁止使用全局变量  ')
    await flushPromises()

    let last = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(last.teacher_constraints).toEqual({
      requirements_text: '必须正确处理空列表\n禁止使用全局变量',
    })

    await constraints.setValue('   \n  ')
    await flushPromises()
    last = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(last.teacher_constraints).toEqual({})
  })

  it('requirements_text 格式自动回填自然语言文本框', () => {
    const wrapper = mount(AiConfigForm, {
      props: {
        modelValue: {
          ...draft,
          teacher_constraints: { requirements_text: '必须处理空列表\n时间复杂度不得高于 O(n)' },
        },
      },
    })

    expect(wrapper.find('[data-testid="teacher-constraints-input"]').element.value)
      .toBe('必须处理空列表\n时间复杂度不得高于 O(n)')
  })

  it('旧版 dict 只读展示，编辑其他字段时不覆盖原数据', async () => {
    const legacyConstraints = { required_algorithm: '二分查找', required_complexity: 'O(log n)' }
    const wrapper = mount(AiConfigForm, {
      props: { modelValue: { ...draft, teacher_constraints: legacyConstraints } },
    })

    const constraints = wrapper.find('[data-testid="teacher-constraints-input"]')
    expect(constraints.attributes()).toHaveProperty('readonly')
    expect(wrapper.text()).toContain('旧版结构数据，请重新填写')

    await wrapper.find('select').setValue('shadow')
    const last = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(last.teacher_constraints).toEqual(legacyConstraints)
  })
})
