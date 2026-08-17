import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TeacherExamPaper from '../TeacherExamPaper.vue'

function question(overrides = {}) {
  return {
    id: 1, exam_id: 9, question_type: 'single_choice', prompt: 'Python 关键字是？', points: 10,
    order_index: 0, options: { A: 'def', B: 'class' }, correct_answer: { correct: ['B'] },
    ...overrides,
  }
}

describe('TeacherExamPaper', () => {
  it('以试卷版式展示选项对照、标准答案和学生答案', () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question()],
        answers: [{ id: 11, question_id: 1, selected_options: ['A'], score: 0, grading_status: 'completed' }],
        editable: true,
      },
    })
    expect(wrapper.text()).toContain('一、单选题')
    expect(wrapper.text()).toContain('Python 关键字是？')
    expect(wrapper.text()).toContain('标准答案')
    expect(wrapper.text()).toContain('学生作答')
    expect(wrapper.find('.option-row.correct').text()).toContain('B')
    expect(wrapper.find('.option-row.wrong').text()).toContain('A')
  })

  it('得分不能超过本题满分，合法改分会向上抛事件', async () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question({ points: 20 })],
        answers: [{ id: 11, question_id: 1, selected_options: ['A'], score: 12, grading_status: 'completed' }],
        editable: true,
      },
    })
    const input = wrapper.find('input[type="text"]')
    await input.setValue('25')
    await input.trigger('change')
    expect(wrapper.emitted('save-score')).toBeUndefined()
    expect(input.element.value).toBe('12')

    await input.setValue('18.5')
    await input.trigger('change')
    expect(wrapper.emitted('save-score')[0]).toEqual([{ answerId: 11, questionId: 1, score: 18.5 }])
  })

  it('不可编辑状态时得分输入禁用', () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question()],
        answers: [{ id: 11, question_id: 1, selected_options: ['B'], score: 10, grading_status: 'completed' }],
        editable: false,
      },
    })
    expect(wrapper.find('input[type="text"]').attributes('disabled')).toBeDefined()
  })

  it('填空题在题干中展示学生填写并列出标准答案', () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question({
          id: 3, question_type: 'fill_blank', prompt: '定义函数使用 [[blank:b1]] 关键字。', points: 20, order_index: 2,
          options: null, correct_answer: { blanks: [{ id: 'b1', accepted_answers: ['def'] }] },
        })],
        answers: [{ id: 13, question_id: 3, text_answers: { b1: 'def' }, score: 20, grading_status: 'completed' }],
        editable: true,
      },
    })
    expect(wrapper.text()).toContain('定义函数使用')
    expect(wrapper.text()).toContain('def')
    expect(wrapper.text()).toContain('标准答案')
    expect(wrapper.text()).toContain('第1空：def')
  })

  it('没有答题记录的题目也可以输入得分，并以 questionId 上抛', async () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question({ points: 20 })],
        answers: [],
        editable: true,
      },
    })
    const input = wrapper.find('input[type="text"]')
    expect(input.attributes('disabled')).toBeUndefined()
    await input.setValue('15')
    await input.trigger('change')
    expect(wrapper.emitted('save-score')[0]).toEqual([{ answerId: null, questionId: 1, score: 15 }])
  })

  it('编程题展示学生代码与参考答案', () => {
    const wrapper = mount(TeacherExamPaper, {
      props: {
        questions: [question({
          id: 2, question_type: 'code', prompt: '实现正数求和函数', points: 20, order_index: 1,
          reference_solution: 'def f(values):\n    return sum(v for v in values if v > 0)',
        })],
        answers: [{ id: 12, question_id: 2, code_answer: 'def f(values): return sum(values)', score: 17.93, grading_status: 'completed' }],
        editable: true,
      },
    })
    expect(wrapper.text()).toContain('学生代码')
    expect(wrapper.text()).toContain('参考答案')
    expect(wrapper.text()).toContain('return sum(v for v in values if v > 0)')
  })
})
