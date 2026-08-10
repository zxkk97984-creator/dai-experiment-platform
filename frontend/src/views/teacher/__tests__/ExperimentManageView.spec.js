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
  },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

vi.mock('../../../stores/auth', () => ({
  useAuthStore: () => ({ isAdmin: false }),
}))

import { experimentsAPI } from '../../../api/experiments.js'

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
  })

  it('点击「创建实验」打开创建弹窗', async () => {
    const wrapper = await mountPage()
    await flushPromises()

    await openCreateModal(wrapper)

    expect(wrapper.find('[role="dialog"][aria-label="创建实验"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="例如：Python 数据分析实验"]').exists()).toBe(true)
  })

  it('实验名称为空时提示并阻止提交', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    await openCreateModal(wrapper)

    await wrapper.find('.create-form button.btn-primary').trigger('click')

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
    await wrapper.find('input[placeholder="外部实验链接，留空则使用 JupyterLab"]').setValue('https://example.com/lab')
    await wrapper.find('.create-form button.btn-primary').trigger('click')
    await flushPromises()

    expect(experimentsAPI.createModule).toHaveBeenCalledWith({
      name: 'Python 数据分析实验',
      description: '完成数据清洗与可视化',
      entry_url: 'https://example.com/lab',
    })
    expect(wrapper.find('[role="dialog"][aria-label="创建实验"]').exists()).toBe(false)
    expect(experimentsAPI.listModules).toHaveBeenCalledTimes(2)
  })
})
