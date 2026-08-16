/** AiConfigForm 测试组生成按钮——纯表单层：只上抛事件，不调 API */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../../api/aiGrading.js', () => ({
  aiGradingAPI: {
    generateTestGroups: vi.fn(),
  },
}))

import AiConfigForm from '../AiConfigForm.vue'
import { aiGradingAPI } from '../../../api/aiGrading.js'

const draft = { grading_mode: 'legacy', teacher_constraints: {}, reference_solution: '', test_groups: [], score_cap_rules: [] }

function genButton(wrapper) {
  // 生成中文本变为「生成中…」，两种状态都需可匹配
  return wrapper.findAll('button').find(
    (b) => b.text().includes('AI 生成测试组') || b.text().includes('生成中…'),
  )
}

describe('AiConfigForm 测试组生成按钮', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('按钮位于测试组标题栏，紧邻「+ 添加测试组」', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    await flushPromises()

    const btn = genButton(wrapper)
    expect(btn).toBeTruthy()
    expect(btn.text()).toContain('AI 生成测试组')
    // 同一标题栏内还提供「+ 添加测试组」
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('添加测试组'))
    expect(addBtn).toBeTruthy()
    const sectionHeader = wrapper.find('.section-header')
    expect(sectionHeader.element.contains(btn.element)).toBe(true)
    expect(sectionHeader.element.contains(addBtn.element)).toBe(true)
  })

  it('点击按钮上抛 generate-test-groups 事件，不直接调用 API', async () => {
    const wrapper = mount(AiConfigForm, { props: { modelValue: draft } })
    await flushPromises()

    await genButton(wrapper).trigger('click')

    const emitted = wrapper.emitted('generate-test-groups')
    expect(emitted).toBeTruthy()
    expect(emitted).toHaveLength(1)
    expect(aiGradingAPI.generateTestGroups).not.toHaveBeenCalled()
  })

  it('generating=true 时按钮禁用并显示「生成中…」，防重复点击', async () => {
    const wrapper = mount(AiConfigForm, {
      props: { modelValue: draft, generating: true },
    })
    await flushPromises()

    const btn = genButton(wrapper)
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.text()).toContain('生成中…')

    // 禁用状态下点击不再上抛事件
    await btn.trigger('click')
    expect(wrapper.emitted('generate-test-groups')).toBeUndefined()
  })

  it('生成中不禁用「+ 添加测试组」手动编辑能力', async () => {
    const wrapper = mount(AiConfigForm, {
      props: { modelValue: draft, generating: true },
    })
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('添加测试组'))
    expect(addBtn.attributes('disabled')).toBeUndefined()
  })
})
