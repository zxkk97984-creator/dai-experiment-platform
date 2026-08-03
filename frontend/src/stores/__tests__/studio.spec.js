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
  getVersions: vi.fn(),
  getVersion: vi.fn(),
  exportDraft: vi.fn(),
  exportVersion: vi.fn(),
}))

vi.mock('../../api/studio.js', () => ({
  studioAPI: mocks,
}))

import { useStudioStore } from '../studio.js'

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
