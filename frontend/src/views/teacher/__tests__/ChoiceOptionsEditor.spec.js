import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ChoiceOptionsEditor from '../../../components/teacher/exam/ChoiceOptionsEditor.vue'

function mountEditor(type = 'multi_choice', value = null) {
  let wrapper
  const modelValue = value || {
    options: [{ key: 'A', text: '甲', correct: true }, { key: 'B', text: '乙', correct: false }],
    scoring_mode: 'all_or_nothing',
  }
  wrapper = mount(ChoiceOptionsEditor, {
    props: {
      questionType: type,
      modelValue,
      'onUpdate:modelValue': (next) => wrapper.setProps({ modelValue: next }),
    },
  })
  return wrapper
}

describe('ChoiceOptionsEditor', () => {
  it('自由添加选项并在 Z 后使用 AA 标识', async () => {
    const options = Array.from({ length: 26 }, (_, index) => ({
      key: String.fromCharCode(65 + index), text: `选项${index + 1}`, correct: index === 0,
    }))
    const wrapper = mountEditor('multi_choice', { options, scoring_mode: 'all_or_nothing' })

    await wrapper.findAll('button').find((button) => button.text().includes('添加选项')).trigger('click')

    expect(wrapper.findAll('input[aria-label="选项标识"]')).toHaveLength(27)
    expect(wrapper.findAll('input[aria-label="选项标识"]')[26].element.value).toBe('AA')
  })

  it('单选题切换正确答案时保持唯一', async () => {
    const wrapper = mountEditor('single_choice')
    const answers = wrapper.findAll('input[type="radio"]')

    await answers[1].setValue(true)

    expect(wrapper.props('modelValue').options.map((row) => row.correct)).toEqual([false, true])
    expect(wrapper.vm.validate()).toBe('')
  })

  it('多选题允许多个答案和部分得分模式', async () => {
    const wrapper = mountEditor()
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    await wrapper.find('.scoring-box select').setValue('partial_no_wrong')

    expect(wrapper.props('modelValue').options.map((row) => row.correct)).toEqual([true, true])
    expect(wrapper.props('modelValue').scoring_mode).toBe('partial_no_wrong')
    expect(wrapper.text()).toContain('任一错误项，本题计 0 分')
  })

  it('正确 JSON 与旧版 correct_answer 格式均可回填', async () => {
    const wrapper = mountEditor()
    await wrapper.find('.json-toggle').trigger('click')
    await wrapper.find('.json-panel textarea').setValue(JSON.stringify({
      options: { X: '一', Y: '二', Z: '三' },
      correct_answer: { correct: ['X', 'Z'], scoring_mode: 'partial_no_wrong' },
    }))
    await wrapper.findAll('button').find((button) => button.text() === '识别并导入').trigger('click')

    expect(wrapper.props('modelValue')).toEqual({
      options: [
        { key: 'X', text: '一', correct: true },
        { key: 'Y', text: '二', correct: false },
        { key: 'Z', text: '三', correct: true },
      ],
      scoring_mode: 'partial_no_wrong',
    })
  })

  it('错误 JSON 显示原因且不覆盖当前内容', async () => {
    const wrapper = mountEditor()
    const before = JSON.parse(JSON.stringify(wrapper.props('modelValue')))
    await wrapper.find('.json-toggle').trigger('click')
    await wrapper.find('.json-panel textarea').setValue('{"options":{"A":"甲"},"correct":["A"]}')
    await wrapper.findAll('button').find((button) => button.text() === '识别并导入').trigger('click')

    expect(wrapper.text()).toContain('至少需要两个选项')
    expect(wrapper.props('modelValue')).toEqual(before)
  })
})
