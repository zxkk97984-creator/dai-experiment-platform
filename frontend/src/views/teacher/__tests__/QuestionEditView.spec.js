/** 题目编辑页 QuestionEditView（IDE 风格布局重构）
 *
 * 覆盖：
 * - 布局：作业默认环境卡（draft 可编辑 / published 禁用）、保存作业环境设置
 * - 创建题目：函数签名自动解析函数名；inherit（环境 null）与 override（指定版本）payload 正确
 * - restricted 白名单随 payload 提交；内存低于环境最低值显示警告卡 + 「使用推荐值」按钮
 * - 表格化公开样例：添加/行内编辑/批量导入/分页，保存后序列化为原 JSON 数组格式
 * - 私有测试可视化表格保存为 pytest 代码（hidden_tests 契约不变）
 * - 运行测试调用 sample-run（后端仅学生可用，教师端 403 如实展示）
 * - 编辑已有题目回填并调用 updateQuestion
 * - 学生代码模板为深色 CodeMirror（固定高度，不随代码行数增长）
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  useRouter: () => ({ push: vi.fn() }),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    beforeResolve: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/assignments/7/edit' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/assignments', () => ({
  assignmentsAPI: {
    get: vi.fn(),
    getQuestions: vi.fn(),
    createQuestion: vi.fn(),
    updateQuestion: vi.fn(),
    update: vi.fn(),
    publish: vi.fn(),
  },
}))

vi.mock('../../../api/environments', () => ({
  environmentsAPI: { listAvailable: vi.fn() },
}))

vi.mock('../../../api/judge', () => ({
  judgeAPI: { sampleRun: vi.fn() },
}))

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

const appStore = { showToast: vi.fn() }
vi.mock('../../../stores/app', () => ({
  useAppStore: () => appStore,
}))

import { assignmentsAPI } from '../../../api/assignments.js'
import { environmentsAPI } from '../../../api/environments.js'
import { judgeAPI } from '../../../api/judge.js'
import { aiGradingAPI } from '../../../api/aiGrading.js'

const envOptions = [
  {
    profile_id: 1, environment_version_id: 11, slug: 'basic', display_name: 'Python 基础',
    version_number: 1, packages: [{ pip_name: 'pytest', locked_version: '8.3.4', import_names: ['pytest'] }],
    minimum_memory_mb: 256,
  },
  {
    profile_id: 2, environment_version_id: 22, slug: 'data', display_name: '数据分析',
    version_number: 1, packages: [{ pip_name: 'numpy', locked_version: '2.1.3', import_names: ['numpy'] }],
    minimum_memory_mb: 768,
  },
]

const assignmentDraft = {
  id: 7, title: '环境作业', status: 'draft', course_id: 1,
  environment_version_id: 11, import_policy_mode: 'unrestricted', allowed_imports: [],
  published_at: null, due_at: null,
}

// jsdom 未实现 scrollTo（页面编辑状态切换时调用），静默掉避免噪音
beforeAll(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})

// CodeMirror 在 jsdom 中需要 Range 测量 polyfill（与 CodeCell.spec 同款模式）
const originalRangeGetClientRects = Range.prototype.getClientRects
beforeAll(() => {
  if (!originalRangeGetClientRects) {
    Object.defineProperty(Range.prototype, 'getClientRects', {
      configurable: true,
      value: () => [],
    })
  }
})
afterAll(() => {
  if (!originalRangeGetClientRects) {
    delete Range.prototype.getClientRects
  }
})

const wrappers = []
afterEach(() => {
  for (const wrapper of wrappers.splice(0)) wrapper.unmount()
})

async function mountPage() {
  const mod = await import('../QuestionEditView.vue')
  const wrapper = mount(mod.default, {
    global: {
      stubs: {
        AppLayout: { template: '<div><slot /></div>' },
        AIQuestionConfig: {
          name: 'AIQuestionConfig',
          props: ['kind', 'questionId', 'expanded'],
          template: '<div class="ai-config-stub" />',
        },
      },
    },
  })
  wrappers.push(wrapper)
  return wrapper
}

async function clickBtn(wrapper, text) {
  const btn = wrapper.findAll('button').find((b) => b.text().includes(text))
  expect(btn, `按钮「${text}」应存在`).toBeTruthy()
  await btn.trigger('click')
}

/** 进入新建题目表单（添加题目 → 填标题与签名 → 自动解析函数名） */
async function startNewQuestion(wrapper, title = '新题', signature = 'def add(a: int, b: int) -> int') {
  await clickBtn(wrapper, '添加题目')
  await wrapper.find('input[placeholder="如: 两数之和"]').setValue(title)
  await wrapper.find('input[placeholder^="def add"]').setValue(signature)
  await flushPromises()
}

describe('题目编辑页 QuestionEditView（IDE 布局重构）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    appStore.showToast.mockClear()
    assignmentsAPI.get.mockResolvedValue({ data: assignmentDraft })
    assignmentsAPI.getQuestions.mockResolvedValue({ data: { items: [] } })
    environmentsAPI.listAvailable.mockResolvedValue({ data: envOptions })
  })

  it('加载后展示作业默认环境并默认选中', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('作业默认环境')
    expect(wrapper.text()).toContain('环境最低内存 256 MB')
  })

  it('已发布作业的环境卡禁用且显示提示', async () => {
    assignmentsAPI.get.mockResolvedValue({ data: { ...assignmentDraft, status: 'published' } })
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('环境已锁定')
    // 已发布时作业环境选择器禁用
    expect(wrapper.find('.env-picker-select').attributes('disabled')).toBeDefined()
  })

  it('编辑页展示首次发布时间，延后已发布作业截止时间可直接保存', async () => {
    const published = {
      ...assignmentDraft,
      status: 'published',
      published_at: '2026-08-01T01:00:00Z',
      due_at: '2099-10-01T12:00:00Z',
    }
    assignmentsAPI.get.mockResolvedValue({ data: published })
    assignmentsAPI.update.mockResolvedValue({ data: { ...published, due_at: '2099-11-01T12:00:00Z' } })
    const wrapper = await mountPage()
    await flushPromises()

    expect(wrapper.find('.qe-schedule-card').text()).toContain('首次发布时间')
    await wrapper.find('#assignment-due-at').setValue('2099-11-01T20:00')
    await clickBtn(wrapper, '保存时间设置')
    await flushPromises()

    expect(assignmentsAPI.update).toHaveBeenCalledWith('7', {
      due_at: new Date('2099-11-01T20:00').toISOString(),
    })
    expect(wrapper.find('.confirm-panel').exists()).toBe(false)
  })

  it('编辑页提前截止时间时要求二次确认', async () => {
    const published = {
      ...assignmentDraft,
      status: 'published',
      published_at: '2026-08-01T01:00:00Z',
      due_at: '2099-12-01T12:00:00Z',
    }
    assignmentsAPI.get.mockResolvedValue({ data: published })
    assignmentsAPI.update.mockResolvedValue({ data: published })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.find('#assignment-due-at').setValue('2099-11-01T20:00')
    await clickBtn(wrapper, '保存时间设置')
    await flushPromises()
    expect(assignmentsAPI.update).not.toHaveBeenCalled()
    expect(wrapper.find('.confirm-panel').text()).toContain('缩短学生作答时间')

    await clickBtn(wrapper.find('.confirm-panel'), '确认保存')
    await flushPromises()
    expect(assignmentsAPI.update).toHaveBeenCalledWith('7', {
      due_at: new Date('2099-11-01T20:00').toISOString(),
    })
  })

  it('保存作业环境设置调用 update，payload 携带环境与策略', async () => {
    assignmentsAPI.update.mockResolvedValue({ data: assignmentDraft })
    const wrapper = await mountPage()
    await flushPromises()
    await clickBtn(wrapper, '保存作业环境设置')
    await flushPromises()
    expect(assignmentsAPI.update).toHaveBeenCalledWith('7', {
      environment_version_id: 11,
      import_policy_mode: 'unrestricted',
      allowed_imports: [],
    })
  })

  it('创建题目默认继承作业：签名自动解析函数名，环境 null', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '继承题')
    // 签名解析出函数名提示
    expect(wrapper.text()).toContain('已识别函数名「add」')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()

    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      function_name: 'add',
      environment_version_id: null,
      import_policy_mode: 'inherit',
      allowed_imports: [],
    }))
  })

  it('签名无法解析时提示且阻止提交', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '坏签名', 'hello world')
    expect(wrapper.text()).toContain('未识别到 def 签名')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).not.toHaveBeenCalled()
    expect(appStore.showToast).toHaveBeenCalledWith('请填写标题和函数名', 'error')
  })

  it('题目覆盖环境 + 自定义白名单：payload 携带指定版本与策略', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '覆盖题')

    // 覆盖环境 → 选 data（22）
    // 页面共 3 个 .import-policy-select：[0] 作业导入规则、[1] 题目环境模式、[2] 题目导入规则
    await wrapper.findAll('.import-policy-select')[1].setValue('override')
    await flushPromises()
    const envSelect = wrapper.findAll('.env-picker-select').at(-1)
    await envSelect.setValue('22')
    await flushPromises()
    // 自定义白名单 → 勾选 numpy
    await wrapper.findAll('.import-policy-select')[2].setValue('restricted')
    await flushPromises()
    await wrapper.find('.import-chip input').setValue(true)
    await flushPromises()

    await clickBtn(wrapper, '保存题目')
    await flushPromises()

    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      environment_version_id: 22,
      import_policy_mode: 'restricted',
      allowed_imports: ['numpy'],
    }))
  })

  it('题目内存低于环境最低值显示警告卡，「使用推荐值」一键恢复', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '内存题')
    const memInputs = wrapper.findAll('input[type="number"]')
    await memInputs[1].setValue(128)  // 内存限制 128 < 环境最低 256
    await flushPromises()
    expect(wrapper.text()).toContain('内存上限 128 MB 低于环境最低内存 256 MB')
    // 警告卡片 + 推荐按钮
    expect(wrapper.find('.qe-warn-card').exists()).toBe(true)
    await clickBtn(wrapper, '使用推荐值')
    await flushPromises()
    expect(memInputs[1].element.value).toBe('256')
    expect(wrapper.find('.qe-warn-card').exists()).toBe(false)
  })

  it('编辑已有题目回填并调用 updateQuestion', async () => {
    assignmentsAPI.getQuestions.mockResolvedValue({
      data: {
        items: [{
          id: 55, assignment_id: 7, title: '旧题', function_name: 'old', hidden_tests: 'x',
          time_limit_ms: 10000, memory_limit_mb: 512, grading_mode: 'legacy',
          environment_version_id: 22, import_policy_mode: 'restricted', allowed_imports: ['numpy'],
        }],
      },
    })
    assignmentsAPI.updateQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.find('.qe-list-actions button').trigger('click')  // 列表「编辑」按钮
    await flushPromises()
    expect(wrapper.find('input[placeholder="如: 两数之和"]').element.value).toBe('旧题')
    // 回填后更新标题并保存
    await wrapper.find('input[placeholder="如: 两数之和"]').setValue('新题')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()

    expect(assignmentsAPI.updateQuestion).toHaveBeenCalledWith('7', 55, expect.objectContaining({
      title: '新题',
      environment_version_id: 22,
      import_policy_mode: 'restricted',
      allowed_imports: ['numpy'],
    }))
  })

  it('表格化公开样例：添加/行内编辑后序列化为原 JSON 数组格式', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '求和题')

    // 添加样例 → 行内编辑（2 个参数）
    await clickBtn(wrapper, '+ 添加样例')
    await clickBtn(wrapper, '+ 参数')
    await clickBtn(wrapper, '+ 参数')
    const argInputs = wrapper.findAll('.qe-cases__input--arg')
    await argInputs[0].setValue('1')
    await argInputs[1].setValue('2')
    await wrapper.find('input[placeholder="如 3、ok 或 [1,2]"]').setValue('3')
    await wrapper.find('input[placeholder="说明（可选）"]').setValue('正数相加')
    await wrapper.find('.qe-cases__op--save').trigger('click')
    await flushPromises()

    // 表格展示行
    expect(wrapper.text()).toContain('正数相加')

    // 保存后 public_cases 仍为原 JSON 数组格式
    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      public_cases: [{ args: [1, 2], expected: 3, desc: '正数相加' }],
    }))
  })

  it('批量导入公开样例并分页（每页 10 条，内部滚动不撑高页面）', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '分页题')

    await clickBtn(wrapper, '批量导入')
    const cases = Array.from({ length: 12 }, (_, i) => ({ args: [i], expected: i + 1 }))
    await wrapper.find('.qe-cases__import-ta').setValue(JSON.stringify(cases))
    await clickBtn(wrapper, '导入追加')
    await flushPromises()

    // 导入后跳到末页（新数据可见）
    expect(wrapper.text()).toContain('共 12 条 / 显示 11–12')
    // 上一页回到第一页
    await wrapper.findAll('.qe-cases__pager-btn')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('显示 1–10')
    // 表格区域有固定可视高度（内部滚动）
    expect(wrapper.find('.qe-cases__table-wrap').exists()).toBe(true)
  })

  it('私有测试可视化表格：保存为 pytest 代码（hidden_tests 契约不变）', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '私有题')

    await clickBtn(wrapper, '私有测试')
    await clickBtn(wrapper, '+ 添加用例')
    await clickBtn(wrapper, '+ 参数')
    await wrapper.findAll('.qe-cases__input--arg')[0].setValue('3')
    await wrapper.find('input[placeholder="如 3、ok 或 [1,2]"]').setValue('6')
    await wrapper.find('.qe-cases__op--save').trigger('click')
    await flushPromises()

    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      hidden_tests: expect.stringContaining('def test_case_1()'),
    }))
    const payload = assignmentsAPI.createQuestion.mock.calls[0][1]
    expect(payload.hidden_tests).toContain('assert add(3) == 6')
  })

  it('私有测试回填：已有 pytest 代码解析为可视化表格（同块多断言拆分为多行）', async () => {
    assignmentsAPI.getQuestions.mockResolvedValue({
      data: {
        items: [{
          id: 55, assignment_id: 7, title: '旧题', function_name: 'add', hidden_tests:
            'def test_add():\n    assert add(1, 2) == 3\n    assert add(-1, 1) == 0',
          time_limit_ms: 10000, memory_limit_mb: 512, grading_mode: 'legacy',
          environment_version_id: null, import_policy_mode: 'inherit', allowed_imports: [],
        }],
      },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('.qe-list-actions button').trigger('click')
    await flushPromises()

    await clickBtn(wrapper, '私有测试')
    // 解析成功进入可视化模式：两条用例拆成两行，参数无括号残留
    expect(wrapper.text()).toContain('共 2 条 / 显示 1–2')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).not.toContain('2)')
  })

  it('运行测试调用 sample-run；教师端 403 时如实展示后端错误', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    judgeAPI.sampleRun.mockRejectedValue({
      response: { data: { detail: { message: '只有学生可以使用 sample-run' } } },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '运行题')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()

    await clickBtn(wrapper, '▶ 运行测试')
    await flushPromises()
    expect(judgeAPI.sampleRun).toHaveBeenCalledWith(99, { question_id: 99, code: '' })
    expect(wrapper.text()).toContain('只有学生可以使用 sample-run')
  })

  it('学生代码模板：深色 CodeMirror 编辑器，固定高度不随代码增长', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '代码题')

    // 等待 CodeMirror 动态加载完成
    await vi.waitFor(() => {
      expect(wrapper.find('.qe-code .cm-content').exists()).toBe(true)
    }, { timeout: 5000 })

    // 固定高度（默认 380px，长代码内部滚动）
    expect(wrapper.find('.qe-code').attributes('style')).toContain('380px')
    expect(wrapper.find('.qe-code .cm-editor').exists()).toBe(true)
  })

  // ══ 右侧栏：发布设置 → AI 评分配置 ════════════════════════════════
  it('右侧栏两个 tab：运行设置 | AI 评分配置（发布设置已移除）', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('运行设置')
    expect(wrapper.text()).toContain('AI 评分配置')
    expect(wrapper.text()).not.toContain('发布设置')
    expect(wrapper.text()).not.toContain('前往作业管理')
  })

  it('新建题目（无 id）时 AI 评分配置 tab 直接渲染草稿表单，可编辑', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    // 不再显示「请先保存题目后再配置 AI 评分」
    expect(wrapper.text()).not.toContain('请先保存题目后再配置 AI 评分')
    // 草稿表单渲染且可编辑
    const draft = wrapper.find('.qe-ai-draft')
    expect(draft.exists()).toBe(true)
    expect(draft.text()).toContain('评分模式')
    await draft.find('select').setValue('shadow')
    await flushPromises()
    expect(draft.find('select').element.value).toBe('shadow')
    // 草稿模式无 rubric 区，提示保存题目后可生成 Rubric
    expect(draft.text()).toContain('保存题目后可生成 Rubric')
    expect(draft.text()).not.toContain('AI 生成 Rubric')
  })

  it('草稿模式点击「AI 生成测试组」提示先保存题目（无 questionId 不请求）', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    const draft = wrapper.find('.qe-ai-draft')
    const genBtn = draft.findAll('button').find((b) => b.text().includes('AI 生成测试组'))
    await genBtn.trigger('click')
    await flushPromises()
    expect(draft.text()).toContain('请先保存题目后再生成测试组')
    expect(aiGradingAPI.generateTestGroups).not.toHaveBeenCalled()
  })

  it('新建题草稿选 shadow/active 时显示 Rubric 门禁前置提示', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    // legacy 默认无提示
    expect(wrapper.find('.qe-ai-draft .qe-warn-card').exists()).toBe(false)
    await wrapper.find('.qe-ai-draft select').setValue('shadow')
    await flushPromises()
    expect(wrapper.find('.qe-ai-draft .qe-warn-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚无可发布的 Rubric，请先保存题目后生成并锁定')
  })

  it('发布前当前题 shadow/active 时提示 Rubric 门禁（toast + 确认弹窗）', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    assignmentsAPI.publish.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '门禁题')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    await wrapper.find('.qe-ai-draft select').setValue('shadow')
    await clickBtn(wrapper, '发布作业')
    await flushPromises()
    // toast 前置提示
    expect(appStore.showToast).toHaveBeenCalledWith(expect.stringContaining('Rubric 未生成并锁定'), 'error')
    // 确认弹窗 message 同样拼接门禁提示
    expect(wrapper.text()).toContain('若 Rubric 未生成并锁定，发布将被后端拒绝')
  })

  it('编辑已有题目时 AI 评分配置 tab 内嵌 AIQuestionConfig（kind=assignment）', async () => {
    assignmentsAPI.getQuestions.mockResolvedValue({
      data: {
        items: [{
          id: 55, assignment_id: 7, title: '旧题', function_name: 'old', hidden_tests: '',
          time_limit_ms: 10000, memory_limit_mb: 512, grading_mode: 'legacy',
          environment_version_id: null, import_policy_mode: 'inherit', allowed_imports: [],
        }],
      },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('.qe-list-actions button').trigger('click')  // 列表「编辑」按钮
    await flushPromises()
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    const cfg = wrapper.findComponent({ name: 'AIQuestionConfig' })
    expect(cfg.exists()).toBe(true)
    expect(cfg.props('kind')).toBe('assignment')
    expect(cfg.props('questionId')).toBe(55)
    expect(cfg.props('expanded')).toBe(true)
  })

  it('新建题保存时 AI 草稿字段随 payload 提交（新建默认显式传 legacy）', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, 'AI 草稿题')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()

    const draft = wrapper.find('.qe-ai-draft')
    await draft.find('select').setValue('shadow')
    await draft.find('[data-testid="teacher-constraints-input"]')
      .setValue('  必须正确处理空列表\n禁止使用全局变量  ')
    await clickBtn(wrapper, '+ 添加测试组')
    await flushPromises()
    await wrapper.findAll('input[placeholder="ID (如 F1)"]')[0].setValue('F1')
    await wrapper.findAll('input[placeholder="名称"]')[0].setValue('基础')
    await wrapper.findAll('input[placeholder="满分"]')[0].setValue('60')

    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      grading_mode: 'shadow',
      teacher_constraints: {
        requirements_text: '必须正确处理空列表\n禁止使用全局变量',
      },
      reference_solution: null,
      test_groups: [expect.objectContaining({ id: 'F1', name: '基础', dimension: 'F', max_score: 60 })],
      score_cap_rules: [],
    }))
  })

  it('新建题未碰 AI tab 时保存，payload 显式传 legacy（不依赖后端默认 active）', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '默认题')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      grading_mode: 'legacy',
      teacher_constraints: {},
      test_groups: [],
      score_cap_rules: [],
    }))
  })

  it('创建成功拿到 id 后 AI tab 切持久化模式，修改过的草稿经 PUT 落库', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '持久化题')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    await wrapper.find('.qe-ai-draft select').setValue('shadow')

    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    // 草稿经独立接口落库到新题目（create 链路不接收 AI 字段）
    expect(aiGradingAPI.updateConfig).toHaveBeenCalledWith('assignment', 99, expect.objectContaining({ grading_mode: 'shadow' }))
    // AI tab 切持久化模式：AIQuestionConfig 挂载且指向新 id
    const cfg = wrapper.findComponent({ name: 'AIQuestionConfig' })
    expect(cfg.exists()).toBe(true)
    expect(cfg.props('questionId')).toBe(99)
  })

  it('草稿模式教师要求仅含空白时提交空 dict', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '空约束题')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    await wrapper.find('.qe-ai-draft [data-testid="teacher-constraints-input"]').setValue('  \n  ')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalledWith('7', expect.objectContaining({
      teacher_constraints: {},
    }))
  })

  it('新建题 AI 草稿未保存时切换题目：提示已丢弃且草稿重置', async () => {
    assignmentsAPI.getQuestions.mockResolvedValue({
      data: {
        items: [{
          id: 55, assignment_id: 7, title: '旧题', function_name: 'old', hidden_tests: '',
          time_limit_ms: 10000, memory_limit_mb: 512, grading_mode: 'legacy',
          environment_version_id: null, import_policy_mode: 'inherit', allowed_imports: [],
        }],
      },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '草稿切题')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    await wrapper.find('.qe-ai-draft select').setValue('shadow')

    await wrapper.find('.qe-list-actions button').trigger('click')  // 切换到已有题
    await flushPromises()
    expect(appStore.showToast).toHaveBeenCalledWith(expect.stringContaining('AI 配置草稿未保存'), 'error')

    // 再次新建：草稿已重置为默认 legacy
    await clickBtn(wrapper, '添加题目')
    await clickBtn(wrapper, 'AI 评分配置')
    await flushPromises()
    expect(wrapper.find('.qe-ai-draft select').element.value).toBe('legacy')
  })

  it('列表行「🤖 AI 配置」收敛：选中该题并打开右侧 AI tab（无双实例）', async () => {
    assignmentsAPI.getQuestions.mockResolvedValue({
      data: {
        items: [{
          id: 55, assignment_id: 7, title: '旧题', function_name: 'old', hidden_tests: '',
          time_limit_ms: 10000, memory_limit_mb: 512, grading_mode: 'legacy',
          environment_version_id: null, import_policy_mode: 'inherit', allowed_imports: [],
        }],
      },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await clickBtn(wrapper, '🤖 AI 配置')
    await flushPromises()
    // 该题被选中（编辑态）且右侧栏切到 AI tab
    expect(wrapper.find('.qe-list-row--active').exists()).toBe(true)
    expect(wrapper.find('.qe-side-tab.active').text()).toContain('AI 评分配置')
    // 列表行内不再挂载 AIQuestionConfig，仅右侧栏一个实例
    expect(wrapper.find('.qe-list-row .ai-config-stub').exists()).toBe(false)
    expect(wrapper.find('.qe-side .ai-config-stub').exists()).toBe(true)
  })

  // ══ 右上角「🚀 发布作业」 ═════════════════════════════════════════
  it('右上角发布作业：确认后先保存当前题目，再调用 publish 接口', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    assignmentsAPI.publish.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '发布题')
    await clickBtn(wrapper, '发布作业')
    await flushPromises()
    // 确认弹窗 → 确认发布
    await clickBtn(wrapper, '确认发布')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalled()
    expect(assignmentsAPI.publish).toHaveBeenCalledWith('7')
    expect(appStore.showToast).toHaveBeenCalledWith('作业已发布', 'success')
  })

  it('发布作业：题目保存失败时停止，不调用 publish', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '坏签名题', 'hello world')  // 签名无法解析 → 保存失败
    await clickBtn(wrapper, '发布作业')
    await flushPromises()
    await clickBtn(wrapper, '确认发布')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).not.toHaveBeenCalled()
    expect(assignmentsAPI.publish).not.toHaveBeenCalled()
  })

  it('发布作业：接口失败时明确提示题目已保存为草稿，但发布失败', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({ data: { id: 99 } })
    assignmentsAPI.publish.mockRejectedValue({
      response: { data: { detail: { message: '存在未配置 AI 评分的 legacy 题目' } } },
    })
    const wrapper = await mountPage()
    await flushPromises()
    await startNewQuestion(wrapper, '发布失败题')
    await clickBtn(wrapper, '发布作业')
    await flushPromises()
    await clickBtn(wrapper, '确认发布')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalled()
    expect(assignmentsAPI.publish).toHaveBeenCalledWith('7')
    expect(appStore.showToast).toHaveBeenCalledWith(expect.stringContaining('题目已保存为草稿，但发布失败'), 'error')
    expect(appStore.showToast).toHaveBeenCalledWith(expect.stringContaining('存在未配置 AI 评分的 legacy 题目'), 'error')
  })

  it('作业已发布时右上角按钮显示已发布并禁用', async () => {
    assignmentsAPI.get.mockResolvedValue({ data: { ...assignmentDraft, status: 'published' } })
    const wrapper = await mountPage()
    await flushPromises()
    const btn = wrapper.findAll('.qe-topbar-right button').find((b) => b.text().includes('已发布'))
    expect(btn).toBeTruthy()
    expect(btn.attributes('disabled')).toBeDefined()
    await btn.trigger('click')
    await flushPromises()
    expect(assignmentsAPI.publish).not.toHaveBeenCalled()
  })

  // ══ 底部操作栏精简 ═══════════════════════════════════════════════
  it('底部操作栏精简：只剩取消与保存题目（保存草稿/发布题目已移除）', async () => {
    assignmentsAPI.createQuestion.mockResolvedValue({})
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存草稿')
    expect(wrapper.text()).not.toContain('发布题目')
    await startNewQuestion(wrapper, '精简题')
    await clickBtn(wrapper, '保存题目')
    await flushPromises()
    expect(assignmentsAPI.createQuestion).toHaveBeenCalled()
    expect(wrapper.text()).toContain('取消')
  })
})
