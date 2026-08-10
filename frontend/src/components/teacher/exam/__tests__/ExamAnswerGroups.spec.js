/** ExamAnswerGroups 答案分组折叠组件契约测试：分组聚合、展开与事件 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExamAnswerGroups from '../ExamAnswerGroups.vue'

const answers = [
  { id: 1, order_index: 0, question_type: 'single_choice', prompt: 'Python 关键字？', points: 10, score: 10, selected_options: ['A'] },
  { id: 2, order_index: 1, question_type: 'single_choice', prompt: '列表类型？', points: 10, score: 0, selected_options: ['B'] },
  { id: 3, order_index: 2, question_type: 'code', prompt: '编写求和函数', points: 20, score: 15, code_answer: 'def add(a, b):\n    return a + b' },
]

function mountGroups(props = {}) {
  return mount(ExamAnswerGroups, { props: { answers, ...props } })
}

describe('ExamAnswerGroups', () => {
  it('按题型分组并展示分组得分', () => {
    const wrapper = mountGroups()
    const headers = wrapper.findAll('.question-group > header')
    expect(headers).toHaveLength(2)
    expect(headers[0].text()).toContain('单选题')
    expect(headers[0].text()).toContain('共2题')
    expect(headers[0].text()).toContain('10 / 20')
    expect(headers[1].text()).toContain('编程题')
    expect(headers[1].text()).toContain('15 / 20')
  })

  it('点击题目行展开作答并上抛 toggle 事件', async () => {
    const wrapper = mountGroups()
    expect(wrapper.text()).not.toContain('学生答案')
    await wrapper.findAll('.question-row > button')[0].trigger('click')
    expect(wrapper.emitted('toggle')[0][0]).toBe(1)
    expect(wrapper.text()).toContain('学生答案')
    expect(wrapper.text()).toContain('A')
  })

  it('编程题渲染代码区块', async () => {
    const wrapper = mountGroups()
    await wrapper.findAll('.question-row > button')[2].trigger('click')
    expect(wrapper.find('pre').text()).toContain('def add(a, b)')
  })

  it('答案为空时展示空态', () => {
    const wrapper = mountGroups({ answers: [] })
    expect(wrapper.text()).toContain('暂无答题明细')
  })
})
