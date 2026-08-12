import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FillBlankEditor from '../FillBlankEditor.vue'

describe('FillBlankEditor', () => {
  it('插入稳定占位符并创建对应答案配置', async () => {
    const wrapper = mount(FillBlankEditor, { props: { prompt: 'Python 的作者是 ', modelValue: [] } })
    await wrapper.get('.fill-toolbar button').trigger('click')

    expect(wrapper.emitted('update:prompt').at(-1)[0]).toBe('Python 的作者是 [[blank:blank1]]')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([
      { id: 'blank1', accepted_answers: [''], case_sensitive: false },
    ])
  })

  it('安全预览题干，不使用 HTML 注入', () => {
    const wrapper = mount(FillBlankEditor, {
      props: {
        prompt: '<img src=x onerror=alert(1)> [[blank:name]]',
        modelValue: [{ id: 'name', accepted_answers: ['Guido'], case_sensitive: false }],
      },
    })
    expect(wrapper.find('.preview img').exists()).toBe(false)
    expect(wrapper.find('.preview input[aria-label="name"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })
})
