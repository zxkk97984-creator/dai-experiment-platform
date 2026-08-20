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
    ensureModuleTemplate: vi.fn(),
    updateModule: vi.fn(),
    publishModule: vi.fn(),
    unpublishModule: vi.fn(),
  },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

vi.mock('../../../stores/auth', () => ({
  useAuthStore: () => ({ isAdmin: false }),
}))

import { experimentsAPI } from '../../../api/experiments.js'

function makeModules(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    name: `实验模块 ${index + 1}`,
    description: `描述 ${index + 1}`,
    status: 'draft',
    template_id: index + 10,
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

async function findCreateButton(wrapper) {
  const button = wrapper.findAll('button').find((item) => item.text().includes('创建实验'))
  expect(button, '页面应有「创建实验」按钮').toBeDefined()
  return button
}

async function openCreateModal(wrapper) {
  const button = await findCreateButton(wrapper)
  await button.trigger('click')
  await flushPromises()
  expect(wrapper.find('.create-panel').exists()).toBe(true)
  return wrapper.get('.create-panel')
}

describe('实验模块管理页 ExperimentManageView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    experimentsAPI.listModules.mockResolvedValue({ data: { items: [] } })
    experimentsAPI.createModule.mockResolvedValue({ data: { id: 11, template_id: 20 } })
    experimentsAPI.ensureModuleTemplate.mockResolvedValue({ data: { id: 11, template_id: 20 } })
    experimentsAPI.updateModule.mockResolvedValue({ data: { id: 1, template_id: 11 } })
  })

  it('点击「创建实验」打开弹窗，填写完整后才创建并进入编辑器', async () => {
    const wrapper = await mountPage()
    await flushPromises()

    const panel = await openCreateModal(wrapper)
    expect(panel.get('.create-heading strong').text()).toBe('创建实验')

    // 基本信息不完整时不允许创建
    await panel.trigger('submit')
    await flushPromises()
    expect(experimentsAPI.createModule).not.toHaveBeenCalled()
    expect(showToastMock).toHaveBeenCalledWith('请输入实验名称', 'error')

    await panel.get('input[type="text"]').setValue('Python 数据分析实验')
    await panel.trigger('submit')
    await flushPromises()
    expect(experimentsAPI.createModule).not.toHaveBeenCalled()
    expect(showToastMock).toHaveBeenCalledWith('请输入实验描述', 'error')

    await panel.get('textarea').setValue('完成数据清洗与可视化')
    await panel.trigger('submit')
    await flushPromises()

    expect(experimentsAPI.createModule).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Python 数据分析实验', description: '完成数据清洗与可视化' }),
    )
    expect(experimentsAPI.ensureModuleTemplate).not.toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/teacher/experiments/11/studio/20')
  })

  it('创建和编辑信息弹窗复用布置作业的标准表单布局', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(1) } })
    const wrapper = await mountPage()
    await flushPromises()

    const createPanel = await openCreateModal(wrapper)
    expect(createPanel.classes()).toContain('create-modal')
    expect(createPanel.find('header.create-heading').exists()).toBe(true)
    expect(createPanel.find('.create-modal-body').exists()).toBe(true)
    expect(createPanel.find('.create-actions').exists()).toBe(true)

    await createPanel.find('.create-close').trigger('click')
    await wrapper.get('[data-action="edit-info"]').trigger('click')
    await flushPromises()

    const editPanel = wrapper.get('.create-panel')
    expect(editPanel.classes()).toContain('create-modal')
    expect(editPanel.find('header.create-heading').exists()).toBe(true)
    expect(editPanel.find('.create-modal-body').exists()).toBe(true)
    expect(editPanel.find('.create-actions').exists()).toBe(true)
  })

  it('点击「编辑模块」直接进入已有实验编辑器', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(3) } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.findAll('[data-action="edit-module"]')[1].trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateModule).not.toHaveBeenCalled()
    expect(experimentsAPI.ensureModuleTemplate).not.toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/teacher/experiments/2/studio/11')
  })

  it('点击实验名称同样直接进入编辑器', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(3) } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[data-action="open-module"]').trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/teacher/experiments/1/studio/10')
  })

  it('编辑信息弹窗可保存修改并刷新列表', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(1) } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[data-action="edit-info"]').trigger('click')
    await flushPromises()

    const panel = wrapper.get('.create-panel')
    await panel.get('input[type="text"]').setValue('改名后的实验')
    const saveButton = wrapper.findAll('button').find((item) => item.text().includes('保存信息'))
    expect(saveButton).toBeDefined()
    await saveButton.trigger('click')
    await flushPromises()

    expect(experimentsAPI.updateModule).toHaveBeenCalledWith(1, expect.objectContaining({ name: '改名后的实验' }))
    expect(showToastMock).toHaveBeenCalledWith('保存成功', 'success')
    expect(wrapper.find('.create-panel').exists()).toBe(false)
  })

  it('编辑没有 Notebook 的历史模块时自动初始化并进入编辑器', async () => {
    const modules = makeModules(1)
    modules[0].template_id = null
    experimentsAPI.listModules.mockResolvedValue({ data: { items: modules } })
    experimentsAPI.ensureModuleTemplate.mockResolvedValue({ data: { id: 1, template_id: 33 } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[data-action="edit-module"]').trigger('click')
    await flushPromises()

    expect(experimentsAPI.ensureModuleTemplate).toHaveBeenCalledWith(1)
    expect(pushMock).toHaveBeenCalledWith('/teacher/experiments/1/studio/33')
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

  it('草稿模块点击「发布」调用 publishModule 并刷新', async () => {
    experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(1) } })
    experimentsAPI.publishModule.mockResolvedValue({ data: { id: 1, status: 'published' } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.find('.publish-action').trigger('click')
    await flushPromises()

    expect(experimentsAPI.publishModule).toHaveBeenCalledWith(1)
    expect(showToastMock).toHaveBeenCalledWith('已发布', 'success')
  })

  it('已发布模块点击「下架」调用 unpublishModule 并刷新', async () => {
    const publishedModules = makeModules(1)
    publishedModules[0].status = 'published'
    experimentsAPI.listModules.mockResolvedValue({ data: { items: publishedModules } })
    experimentsAPI.unpublishModule.mockResolvedValue({ data: { id: 1, status: 'draft' } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.find('.publish-action').trigger('click')
    await flushPromises()

    expect(experimentsAPI.unpublishModule).toHaveBeenCalledWith(1)
    expect(showToastMock).toHaveBeenCalledWith('已下架', 'success')
  })
})
