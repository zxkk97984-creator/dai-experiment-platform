import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getTemplate: vi.fn(),
  createTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  bindTemplate: vi.fn(),
  saveDraft: vi.fn(),
  previewRun: vi.fn(),
  previewInterrupt: vi.fn(),
  previewReset: vi.fn(),
  publish: vi.fn(),
  publishModule: vi.fn(),
  getVersions: vi.fn(),
  getVersion: vi.fn(),
  exportDraft: vi.fn(),
  exportVersion: vi.fn(),
}))

vi.mock('../../api/studio.js', () => ({
  studioAPI: mocks,
}))

vi.mock('../../api/experiments.js', () => ({
  experimentsAPI: { publishModule: mocks.publishModule },
}))

import { useStudioStore } from '../studio.js'
import { useAppStore } from '../app.js'

const codeCell = (overrides = {}) => ({
  id: 'cell-abc12345',
  type: 'code',
  source: 'print(3)',
  order: 0,
  student_editable: true,
  source_hidden: false,
  ...overrides,
})

describe('useStudioStore previewRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('草稿未保存（dirty）时先保存草稿，再按 cell.id 发起预览运行', async () => {
    const store = useStudioStore()
    store.templateId = 11
    store.draftRevision = 1
    store.dirty = true
    const cell = codeCell()
    store.cells = [cell]
    mocks.saveDraft.mockResolvedValue({
      data: {
        draft_revision: 2,
        draft_cells: [{ ...cell }],
        status: 'draft',
        name: '222',
      },
    })
    mocks.previewRun.mockResolvedValue({ data: { outputs: [], execution_time_ms: 1 } })

    const result = await store.previewRun(cell.id)

    // 必须先保存：后端 preview_run 只查数据库 draft_cells，未保存时必然 404
    expect(mocks.saveDraft).toHaveBeenCalledTimes(1)
    expect(mocks.previewRun).toHaveBeenCalledTimes(1)
    expect(mocks.previewRun).toHaveBeenCalledWith(11, { cell_id: cell.id })
    expect(result.outputs).toEqual([])
  })

  it('保存失败时中止预览，不发送运行请求', async () => {
    const store = useStudioStore()
    store.templateId = 11
    store.dirty = true
    store.cells = [codeCell()]
    mocks.saveDraft.mockRejectedValue({
      response: { data: { detail: { code: 'SAVE_FAILED' } } },
    })

    const result = await store.previewRun('cell-abc12345')

    expect(result).toBeNull()
    expect(mocks.previewRun).not.toHaveBeenCalled()
  })

  it('草稿已保存（非 dirty）时直接发起预览运行', async () => {
    const store = useStudioStore()
    store.templateId = 11
    store.dirty = false
    store.cells = [codeCell()]
    mocks.previewRun.mockResolvedValue({ data: { outputs: [], execution_time_ms: 2 } })

    await store.previewRun('cell-abc12345')

    expect(mocks.saveDraft).not.toHaveBeenCalled()
    expect(mocks.previewRun).toHaveBeenCalledTimes(1)
  })

  it('未指定 cell_id 时不发送请求并提示', async () => {
    const store = useStudioStore()
    store.templateId = 11
    store.dirty = false
    store.cells = [codeCell()]
    mocks.previewRun.mockResolvedValue({ data: { outputs: [], execution_time_ms: 1 } })

    const result = await store.previewRun(undefined)

    expect(result).toBeNull()
    expect(mocks.previewRun).not.toHaveBeenCalled()
    expect(mocks.saveDraft).not.toHaveBeenCalled()
  })
})

describe('useStudioStore 新增 Cell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  const mk = (id, order) => ({
    id,
    type: 'markdown',
    source: id,
    order,
    student_editable: false,
    source_hidden: false,
  })

  it('在中间 Cell 后新增代码时插入其后，而不是追加到末尾', () => {
    const store = useStudioStore()
    store.cells = [mk('A', 0), mk('B', 1), mk('C', 2)]

    store.addCell('code', 'B')

    const result = store.sortedCells
    expect(result.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
      'C',
    ])
    expect(result.map((cell) => cell.order)).toEqual([0, 1, 2, 3])
    expect(result[2]).toMatchObject({ type: 'code', student_editable: true })
  })

  it('复制中间 Cell 时把副本插入原 Cell 后，而不是追加到末尾', () => {
    const store = useStudioStore()
    store.cells = [mk('A', 0), mk('B', 1), mk('C', 2)]

    store.duplicateCell('B')

    const result = store.sortedCells
    expect(result.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
      'C',
    ])
    expect(result.map((cell) => cell.order)).toEqual([0, 1, 2, 3])
    expect(result[2]).toMatchObject({ type: 'markdown', source: 'B' })
  })

  it('在中间 Cell 后新增讲解时保留讲解类型与只读默认值', () => {
    const store = useStudioStore()
    store.cells = [mk('A', 0), mk('B', 1), mk('C', 2)]

    store.addCell('markdown', 'B')

    const result = store.sortedCells
    expect(result.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
      'C',
    ])
    expect(result[2]).toMatchObject({ type: 'markdown', student_editable: false })
  })

  it('以末尾 Cell 为锚点时追加到末尾', () => {
    const store = useStudioStore()
    store.cells = [mk('A', 0), mk('B', 1), mk('C', 2)]

    store.addCell('code', 'C')

    expect(store.sortedCells.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      'C',
      expect.stringMatching(/^cell-/),
    ])
  })

  it('未提供锚点时保持原有的末尾追加行为', () => {
    const store = useStudioStore()
    store.cells = [mk('A', 0), mk('B', 1)]

    store.addCell('code')

    expect(store.sortedCells.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
    ])
  })

  it('原始数组乱序时仍按 order 找到锚点并插入', () => {
    const store = useStudioStore()
    store.cells = [mk('C', 2), mk('A', 0), mk('B', 1)]

    store.addCell('code', 'B')

    expect(store.sortedCells.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
      'C',
    ])
    expect(store.sortedCells.map((cell) => cell.order)).toEqual([0, 1, 2, 3])
  })

  it('保存草稿时按插入后的顺序提交连续 order，并按响应顺序回填', async () => {
    const store = useStudioStore()
    store.templateId = 20
    store.draftRevision = 1
    store.cells = [mk('A', 0), mk('B', 1), mk('C', 2)]
    store.addCell('markdown', 'B')
    mocks.saveDraft.mockImplementation(async (_templateId, payload) => ({
      data: {
        name: '测试模板',
        status: 'draft',
        draft_revision: 2,
        draft_cells: payload.cells,
      },
    }))

    await store.saveDraft()

    const payload = mocks.saveDraft.mock.calls[0][1]
    expect(payload.cells.map((cell) => cell.id)).toEqual([
      'A',
      'B',
      expect.stringMatching(/^cell-/),
      'C',
    ])
    expect(payload.cells.map((cell) => cell.order)).toEqual([0, 1, 2, 3])
    expect(store.sortedCells.map((cell) => cell.id)).toEqual(payload.cells.map((cell) => cell.id))
  })
})

describe('useStudioStore 排序操作（moveCell / moveCellTo）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  const mk = (id, order) => ({ id, type: 'markdown', source: '', order, student_editable: true, source_hidden: false })
  // 有序数组
  const ordered = () => [mk('A', 0), mk('B', 1), mk('C', 2)]
  // 数组乱序但 order 正确（模拟加载未排序的极端情况）
  const shuffled = () => [mk('C', 2), mk('A', 0), mk('B', 1)]

  it('上移有效：B 上移后到第一位', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCell('B', 'up')
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'A', 'C'])
    expect(store.sortedCells.map(c => c.order)).toEqual([0, 1, 2])
    expect(store.dirty).toBe(true)
  })

  it('下移有效：A 下移后到第二位', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCell('A', 'down')
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'A', 'C'])
    expect(store.dirty).toBe(true)
  })

  it('边界：首位上移、末位下移不生效也不置脏', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.dirty = false
    store.moveCell('A', 'up')
    store.moveCell('C', 'down')
    expect(store.sortedCells.map(c => c.id)).toEqual(['A', 'B', 'C'])
    expect(store.dirty).toBe(false)
  })

  it('数组乱序时移动仍按 order 语义生效', () => {
    const store = useStudioStore()
    store.cells = shuffled()
    store.moveCell('B', 'up')
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'A', 'C'])
    store.moveCell('C', 'up')
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'C', 'A'])
  })

  it('moveCellTo：A 拖到第 3 位', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCellTo('A', 2)
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'C', 'A'])
    expect(store.dirty).toBe(true)
  })

  it('moveCellTo：C 拖到第 1 位', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCellTo('C', 0)
    expect(store.sortedCells.map(c => c.id)).toEqual(['C', 'A', 'B'])
  })

  it('moveCellTo：拖到末尾（index = length）', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCellTo('A', 3)
    expect(store.sortedCells.map(c => c.id)).toEqual(['B', 'C', 'A'])
  })

  it('moveCellTo：原地（idx 或 idx+1）不生效也不置脏', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.dirty = false
    store.moveCellTo('B', 1)
    store.moveCellTo('B', 2)
    expect(store.sortedCells.map(c => c.id)).toEqual(['A', 'B', 'C'])
    expect(store.dirty).toBe(false)
  })

  it('moveCellTo：非法 id / 越界下标直接忽略', () => {
    const store = useStudioStore()
    store.cells = ordered()
    store.moveCellTo('NOPE', 1)
    store.moveCellTo('A', -1)
    store.moveCellTo('A', 99)
    expect(store.sortedCells.map(c => c.id)).toEqual(['A', 'B', 'C'])
  })
})

describe('useStudioStore Phase 4 草稿环境绑定', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('open 回填草稿环境三件套', async () => {
    mocks.getTemplate.mockResolvedValue({
      data: {
        id: 9, name: 'T', status: 'draft', draft_revision: 3, draft_cells: [],
        current_version_id: null, lesson_id: 1, module_id: null, owner_id: 2,
        draft_environment_version_id: 22, draft_import_policy_mode: 'restricted',
        draft_allowed_imports: ['numpy', 'pandas'],
      },
    })
    const store = useStudioStore()
    await store.open(9)
    expect(store.environmentVersionId).toBe(22)
    expect(store.importPolicyMode).toBe('restricted')
    expect(store.allowedImports).toEqual(['numpy', 'pandas'])
  })

  it('saveDraft payload 携带环境三件套，与 cells 同一 revision 提交', async () => {
    const store = useStudioStore()
    store.templateId = 20
    store.draftRevision = 1
    store.cells = [codeCell()]
    store.environmentVersionId = 11
    store.importPolicyMode = 'restricted'
    store.allowedImports = ['pytest']
    mocks.saveDraft.mockResolvedValue({
      data: {
        name: 'T', status: 'draft', draft_revision: 2, draft_cells: [codeCell()],
        draft_environment_version_id: 11, draft_import_policy_mode: 'restricted',
        draft_allowed_imports: ['pytest'],
      },
    })

    await store.saveDraft()

    const payload = mocks.saveDraft.mock.calls[0][1]
    expect(payload.environment_version_id).toBe(11)
    expect(payload.import_policy_mode).toBe('restricted')
    expect(payload.allowed_imports).toEqual(['pytest'])
    expect(payload.draft_revision).toBe(1)
    expect(store.draftRevision).toBe(2)
  })

  it('setEnvironment 修改环境后纳入 dirty，保存后生效', async () => {
    const store = useStudioStore()
    store.dirty = false
    store.setEnvironment(22, 'unrestricted', [])
    expect(store.environmentVersionId).toBe(22)
    expect(store.importPolicyMode).toBe('unrestricted')
    expect(store.dirty).toBe(true)
  })

  it('setImportPolicy 切换 restricted 并写入白名单', async () => {
    const store = useStudioStore()
    store.dirty = false
    store.setImportPolicy('restricted', ['numpy'])
    expect(store.importPolicyMode).toBe('restricted')
    expect(store.allowedImports).toEqual(['numpy'])
    expect(store.dirty).toBe(true)
  })
})

describe('useStudioStore publish（实验模块联动发布）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('课时模板（未绑定模块）：仅发布模板版本，提示已发布版本', async () => {
    const store = useStudioStore()
    store.templateId = 64
    store.moduleId = null
    store.dirty = false
    mocks.publish.mockResolvedValue({ data: { id: 9, version_number: 3 } })
    const app = useAppStore()

    const result = await store.publish()

    expect(mocks.publish).toHaveBeenCalledWith(64)
    expect(mocks.publishModule).not.toHaveBeenCalled()
    expect(app.toastMessage).toBe('已发布版本 3')
    expect(app.toastType).toBe('success')
    expect(result).toEqual({ id: 9, version_number: 3 })
    expect(store.status).toBe('published')
  })

  it('实验模板：模板版本发布成功后显式发布模块，提示实验发布成功', async () => {
    const store = useStudioStore()
    store.templateId = 64
    store.moduleId = 62
    store.dirty = false
    mocks.publish.mockResolvedValue({ data: { id: 9, version_number: 1 } })
    mocks.publishModule.mockResolvedValue({ data: { id: 62, status: 'published' } })
    const app = useAppStore()

    await store.publish()

    expect(mocks.publish).toHaveBeenCalledTimes(1)
    expect(mocks.publish).toHaveBeenCalledWith(64)
    expect(mocks.publishModule).toHaveBeenCalledTimes(1)
    expect(mocks.publishModule).toHaveBeenCalledWith(62)
    expect(app.toastMessage).toBe('实验发布成功')
    expect(app.toastType).toBe('success')
  })

  it('模块发布失败（部分成功）：不提示成功，明确报错，返回版本数据', async () => {
    const store = useStudioStore()
    store.templateId = 64
    store.moduleId = 62
    store.dirty = false
    mocks.publish.mockResolvedValue({ data: { id: 9, version_number: 2 } })
    mocks.publishModule.mockRejectedValue({
      response: { data: { detail: { message: '模板不存在或尚未发布版本' } } },
    })
    const app = useAppStore()

    const result = await store.publish()

    expect(mocks.publishModule).toHaveBeenCalledWith(62)
    // 避免假成功：绝不能出现成功提示
    expect(app.toastMessage).not.toBe('实验发布成功')
    expect(app.toastType).toBe('error')
    expect(app.toastMessage).toContain('实验发布失败')
    expect(app.toastMessage).toContain('模板不存在或尚未发布版本')
    // 模板版本已发布是真实状态：返回版本数据（弹窗关闭），模块发布可回列表重试
    expect(result).toEqual({ id: 9, version_number: 2 })
  })

  it('模板发布失败：不调用模块发布，返回 null', async () => {
    const store = useStudioStore()
    store.templateId = 64
    store.moduleId = 62
    store.dirty = false
    mocks.publish.mockRejectedValue({
      response: { data: { detail: { message: '发布失败' } } },
    })

    const result = await store.publish()

    expect(result).toBeNull()
    expect(mocks.publishModule).not.toHaveBeenCalled()
  })
})
