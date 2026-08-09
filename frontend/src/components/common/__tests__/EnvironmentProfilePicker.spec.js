/** EnvironmentProfilePicker 共享组件测试：加载 available 环境、默认选中、emit、空态提示 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../../api/environments', () => ({
  environmentsAPI: { listAvailable: vi.fn() },
}))

import { environmentsAPI } from '../../../api/environments.js'
import EnvironmentProfilePicker from '../EnvironmentProfilePicker.vue'

const availableOptions = [
  {
    profile_id: 1,
    environment_version_id: 10,
    slug: 'basic',
    display_name: 'Python 基础',
    description: '基础环境',
    version_number: 1,
    packages: [
      { pip_name: 'pytest', locked_version: '8.3.4', import_names: ['pytest'] },
    ],
    minimum_memory_mb: 256,
  },
  {
    profile_id: 2,
    environment_version_id: 20,
    slug: 'data',
    display_name: '数据分析',
    description: '数据分析环境',
    version_number: 2,
    packages: [
      { pip_name: 'numpy', locked_version: '2.1.3', import_names: ['numpy'] },
      { pip_name: 'pandas', locked_version: '2.2.3', import_names: ['pandas'] },
    ],
    minimum_memory_mb: 768,
  },
]

function mountPicker(modelValue = null) {
  return mount(EnvironmentProfilePicker, {
    props: { modelValue },
    global: { stubs: { transition: false } },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('EnvironmentProfilePicker 教师环境选择', () => {
  it('挂载时加载 available 环境列表', async () => {
    environmentsAPI.listAvailable.mockResolvedValue({ data: availableOptions })
    mountPicker()
    expect(environmentsAPI.listAvailable).toHaveBeenCalledTimes(1)
    await flushPromises()
  })

  it('渲染档位名 + 版本号 + 包摘要的选项', async () => {
    environmentsAPI.listAvailable.mockResolvedValue({ data: availableOptions })
    const wrapper = mountPicker()
    await flushPromises()
    const options = wrapper.findAll('option')
    // 第一个是占位选项，后两个是环境选项
    expect(options.length).toBe(3)
    expect(options[1].text()).toContain('Python 基础')
    expect(options[1].text()).toContain('v1')
    expect(options[1].text()).toContain('pytest')
    expect(options[2].text()).toContain('数据分析')
    expect(options[2].text()).toContain('v2')
    expect(options[2].text()).toContain('numpy')
    expect(options[2].text()).toContain('pandas')
  })

  it('默认选中 modelValue 对应的环境', async () => {
    environmentsAPI.listAvailable.mockResolvedValue({ data: availableOptions })
    const wrapper = mountPicker(20)
    await flushPromises()
    expect(wrapper.find('select').element.value).toBe('20')
  })

  it('选择后 emit update:modelValue', async () => {
    environmentsAPI.listAvailable.mockResolvedValue({ data: availableOptions })
    const wrapper = mountPicker()
    await flushPromises()
    await wrapper.find('select').setValue('20')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([20])
  })

  it('无可用环境时显示提示且禁用选择', async () => {
    environmentsAPI.listAvailable.mockResolvedValue({ data: [] })
    const wrapper = mountPicker()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无可用环境')
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
  })

  it('加载失败时显示错误提示', async () => {
    environmentsAPI.listAvailable.mockRejectedValue(new Error('network'))
    const wrapper = mountPicker()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
  })
})
