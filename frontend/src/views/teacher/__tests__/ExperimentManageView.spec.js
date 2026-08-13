import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const showToastMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('../../../api/experiments', () => ({
  experimentsAPI: {
    listModules: vi.fn(),
    createModule: vi.fn(),
    updateModule: vi.fn(),
    publishModule: vi.fn(),
    unpublishModule: vi.fn(),
  },
}))

vi.mock('../../../api/studio', () => ({
  studioAPI: {
    listTemplates: vi.fn(),
  },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

vi.mock('../../../stores/auth', () => ({
  useAuthStore: () => ({ isAdmin: false }),
}))

import { experimentsAPI } from '../../../api/experiments.js'
import { studioAPI } from '../../../api/studio.js'

function makeModules(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    name: `实验模块 ${index + 1}`,
    description: `描述 ${index + 1}`,
    status: index % 2 === 0 ? 'draft' : 'published',
    template_id: null,
    updated_at: '2026-08-01T08:00:00Z',
  }))
}

async function mountPage() {
  const mod = await import('../ExperimentManageView.vue')
  return mount(mod.default, {
    global: {
      stubs: { AppLayout: { template: '<div><slot /></div>' } },
    },
  })
}

async function openCreateModal(wrapper) {
  const button = wrapper.findAll('button').find((item) => item.text().includes('创建实验'))
  expect(button, '页面应有「创建实验」按钮').toBeDefined()
  await button.trigger('click')
}

describe('实验模块管理页 ExperimentManageView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    experimentsAPI.listModules.mockResolvedValue({ data: { items: [] } })
    studioAPI.listTemplates.mockResolvedValue({ data: { items: [{ id: 1, name: '数据分析模板' }] } })
  })

  it('点击「创建实验」打开创建弹窗（含模板选择，无 entry_url）', async () => {
    const wrapper = await mountPage()
    await flushPromises()

    await openCreateModal(wrapper)

    expect(wrapper.find('[role="dialog"][aria-label="创建实验"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="例如：Python 数据分析实验"]').exists()).toBe(true)
    expect(wrapper.find('select[name="module-template"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="外部实验链接，留空则使用 JupyterLab"]').exists()).toBe(false)
  })

  it('实验名称为空时提示并阻止提交', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await openCreateModal(wrapper)

    await wrapper.find('[data-action="save-module"]').trigger('click')

    expect(experimentsAPI.createModule).not.toHaveBeenCalled()
    expect(showToastMock).toHaveBeenCalledWith('请输入实验名称', 'error')
  })

  it('确认创建后关闭弹窗并刷新列表', async () => {
    experimentsAPI.createModule.mockResolvedValue({ data: { id: 8 } })
    const wrapper = await mountPage()
    await flushPromises()
    await openCreateModal(wrapper)

    await wrapper.find('input[placeholder="例如：Python 数据分析实验"]').setValue('Python 数据分析实验')
    await wrapper.find('textarea[placeholder="实验目标和步骤说明"]').setValue('完成数据清洗与可视化')
    await wrapper.find('select[name="module-template"]').setValue(1)
    await wrapper.find('[data-action="save-module"]').trigger('click')
    await flushPromises()

    expect(experimentsAPI.createModule).toHaveBeenCalledWith({
      name: 'Python 数据分析实验',
      description: '完成数据清洗与可视化',
      template_id: 1,
    })
    expect(wrapper.find('[role="dialog"][aria-label="创建实验"]').exists()).toBe(false)
    expect(experimentsAPI.listModules).toHaveBeenCalledTimes(2)
  })

  it('12 个模块分两页展示：第 1 页 10 行，点「第 2 页」后 2 行', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(12) } })
    const wrapper = await mountPage()
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
    expect(wrapper.find('footer.pagination-bar').text()).toContain('共 12 条')

    await wrapper.get('[aria-label="第 2 页"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('点击「编辑模块」回填表单并保存修改', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(3) } })
    experimentsAPI.updateModule.mockResolvedValue({ data: { id: 1 } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.findAll('[data-action="edit-module"]')[0].trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain('编辑实验')
    expect(wrapper.find('[name="module-name"]').element.value).toBe('实验模块 1')

    await wrapper.get('[name="module-name"]').setValue('新名称')
    await wrapper.get('[data-action="save-module"]').trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateModule).toHaveBeenCalledWith(1, expect.objectContaining({ name: '新名称' }))
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(experimentsAPI.listModules).toHaveBeenCalledTimes(2)
  })

  it('发布/下架只走专用门禁端点', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(2) } })
    experimentsAPI.publishModule.mockResolvedValue({ data: { id: 1 } })
    experimentsAPI.unpublishModule.mockResolvedValue({ data: { id: 2 } })
    const wrapper = await mountPage()
    await flushPromises()

    // 第 1 行是 draft → 「发布」调 publishModule
    await wrapper.findAll('.publish-action')[0].trigger('click')
    await flushPromises()
    expect(experimentsAPI.publishModule).toHaveBeenCalledWith(1)
    expect(showToastMock).toHaveBeenCalledWith('已发布', 'success')

    // 第 2 行是 published → 「下架」调 unpublishModule
    await wrapper.findAll('.publish-action')[1].trigger('click')
    await flushPromises()
    expect(experimentsAPI.unpublishModule).toHaveBeenCalledWith(2)
    expect(showToastMock).toHaveBeenCalledWith('已下架', 'success')
  })
})
