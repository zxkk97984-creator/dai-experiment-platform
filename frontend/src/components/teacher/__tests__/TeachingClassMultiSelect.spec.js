import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TeachingClassMultiSelect from '../TeachingClassMultiSelect.vue'

const options = [
  { id: 1, code: 'CS-2601', name: 'Python 程序设计 1 班', student_count: 2 },
  { id: 2, code: 'CS-2602', name: 'Python 程序设计 2 班', student_count: 2 },
]

function mountSelect(modelValue = []) {
  return mount(TeachingClassMultiSelect, {
    props: { modelValue, options },
    global: { stubs: { AppIcon: { template: '<span />' } } },
  })
}

describe('TeachingClassMultiSelect', () => {
  it('展开后展示搜索框、全选和教学班选项', async () => {
    const wrapper = mountSelect()

    await wrapper.get('.teaching-class-trigger').trigger('click')

    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    expect(wrapper.find('.teaching-class-toolbar').text()).toContain('已选 0/2')
    expect(wrapper.findAll('.teaching-class-option')).toHaveLength(2)
  })

  it('支持搜索、选择和移除已选教学班', async () => {
    const wrapper = mountSelect()
    await wrapper.get('.teaching-class-trigger').trigger('click')

    await wrapper.get('input[type="search"]').setValue('2602')
    expect(wrapper.findAll('.teaching-class-option')).toHaveLength(1)
    await wrapper.get('.teaching-class-option').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[2]])

    await wrapper.setProps({ modelValue: [2] })
    expect(wrapper.find('.teaching-class-tag').text()).toContain('Python 程序设计 2 班')
    await wrapper.get('.teaching-class-tag button').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[]])
  })

  it('支持全选和取消全选', async () => {
    const wrapper = mountSelect()
    await wrapper.get('.teaching-class-trigger').trigger('click')

    await wrapper.get('.teaching-class-toolbar button').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[1, 2]])
    await wrapper.setProps({ modelValue: [1, 2] })
    await wrapper.get('.teaching-class-toolbar button').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[]])
  })
})
