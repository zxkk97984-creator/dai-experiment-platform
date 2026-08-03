// TeacherReviewPanel：教师复核卡测试。
// 组件只负责表单/校验/预览/弹窗/草稿，通过 emit('submit') 提交，绝不直接调 API。

import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TeacherReviewPanel from '../TeacherReviewPanel.vue'

const REVIEW_DETAIL = {
  id: 7, mode: 'active', status: 'review_required',
  functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
  raw_total: 79, score_cap: null, final_score_100: 79,
  needs_teacher_review: true, overrides: [],
}

const DONE_DETAIL = {
  ...REVIEW_DETAIL, status: 'completed', needs_teacher_review: false,
  overrides: [{ id: 1, reason: '教师调整', created_at: '2026-08-01T10:00:00',
                original_snapshot: { algorithm_score: 13, quality_score: 5, final_score_100: 79 },
                replacement_snapshot: { algorithm_score: 10, quality_score: 5, final_score_100: 76 } }],
}

function mountPanel(detail = REVIEW_DETAIL, props = {}) {
  return mount(TeacherReviewPanel, {
    props: { detail, teacherId: 1, submitting: false, ...props },
  })
}

beforeEach(() => {
  localStorage.clear()
})

describe('TeacherReviewPanel', () => {
  it('review_required 默认进入编辑模式，纵向表单不换行', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('input#ov-a').exists()).toBe(true)
    expect(wrapper.find('input#ov-q').exists()).toBe(true)
    expect(wrapper.find('textarea#ov-reason').exists()).toBe(true)
    // 范围说明
    expect(wrapper.text()).toContain('范围 0–20')
    expect(wrapper.text()).toContain('范围 0–10')
    expect(wrapper.text()).toContain('当前 13 分')
  })

  it('completed 默认只读，点击"调整评分"进入编辑', async () => {
    const wrapper = mountPanel(DONE_DETAIL)
    expect(wrapper.find('.review-readonly').exists()).toBe(true)
    expect(wrapper.find('input#ov-a').exists()).toBe(false)

    await wrapper.findAll('button').find((b) => b.text().includes('调整评分')).trigger('click')
    expect(wrapper.find('input#ov-a').exists()).toBe(true)
    expect(wrapper.text()).toContain('确认覆盖评分')
  })

  it('总分预览随 A 修改重算（系统自动计算）', async () => {
    const wrapper = mountPanel()
    await wrapper.find('input#ov-a').setValue(10)
    await flushPromises()
    // F=54 R=7 A=10 Q=5 → 76
    expect(wrapper.find('.preview__value').text()).toBe('76')
    expect(wrapper.text()).toContain('系统自动计算')
  })

  it('直接调整总分开关展开总分输入', async () => {
    const wrapper = mountPanel()
    expect(wrapper.find('input#ov-final').exists()).toBe(false)
    await wrapper.find('.final-switch input').setValue(true)
    await flushPromises()
    expect(wrapper.find('input#ov-final').exists()).toBe(true)
    await wrapper.find('input#ov-final').setValue(88)
    await flushPromises()
    expect(wrapper.find('.preview__value').text()).toBe('88')
  })

  it('理由必填（≥3 字）时按钮禁用并说明原因', async () => {
    const wrapper = mountPanel()
    const submit = wrapper.find('.review-submit')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('请至少修改一个评分项')
    expect(wrapper.text()).toContain('将记录在评分历史中')

    await wrapper.find('input#ov-a').setValue(10)
    await wrapper.find('textarea#ov-reason').setValue('好')
    await flushPromises()
    expect(wrapper.find('.review-submit').attributes('disabled')).toBeDefined()

    await wrapper.find('textarea#ov-reason').setValue('调整理由说明')
    await flushPromises()
    expect(wrapper.find('.review-submit').attributes('disabled')).toBeUndefined()
  })

  it('仅修改项进入确认弹窗，确认后 emit 结构化 payload', async () => {
    const wrapper = mountPanel()
    await wrapper.find('input#ov-a').setValue(10)
    await wrapper.find('textarea#ov-reason').setValue('教师复核调整')
    await flushPromises()

    await wrapper.find('.review-submit').trigger('click')
    await flushPromises()

    const dialog = wrapper.find('.confirm-dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('原始得分')
    expect(dialog.text()).toContain('79')
    expect(dialog.text()).toContain('76')
    expect(dialog.text()).toContain('算法关键步骤 13 → 10')
    expect(dialog.text()).toContain('教师复核调整')

    await dialog.findAll('button').find((b) => b.text().includes('确认复核并生效')).trigger('click')
    await flushPromises()

    expect(wrapper.emitted('submit')).toHaveLength(1)
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      algorithm_score: 10, reason: '教师复核调整',
    })
  })

  it('不修改任何项时不能提交（hasChanges 校验）', async () => {
    const wrapper = mountPanel()
    await wrapper.find('textarea#ov-reason').setValue('没有改动的理由')
    await flushPromises()
    expect(wrapper.find('.review-submit').attributes('disabled')).toBeDefined()
  })

  it('本机草稿：24h 内自动恢复并提示', async () => {
    localStorage.setItem('ai_grade_draft_v1_1_7', JSON.stringify({
      version: 1, savedAt: new Date().toISOString(),
      a: 10, q: null, useFinal: false, final: null, reason: '草稿理由',
    }))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('input#ov-a').element.value).toBe('10')
    expect(wrapper.find('textarea#ov-reason').element.value).toBe('草稿理由')
    expect(wrapper.text()).toContain('已恢复本机未提交的调整内容')
  })

  it('草稿过期（>24h）不恢复', async () => {
    const stale = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString()
    localStorage.setItem('ai_grade_draft_v1_1_7', JSON.stringify({
      version: 1, savedAt: stale, a: 10, q: null, useFinal: false, final: null, reason: '旧草稿',
    }))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('textarea#ov-reason').element.value).toBe('')
    expect(wrapper.text()).not.toContain('已恢复本机未提交')
  })

  it('草稿版本不匹配忽略', async () => {
    localStorage.setItem('ai_grade_draft_v1_1_7', JSON.stringify({
      version: 99, savedAt: new Date().toISOString(), a: 10, q: null, useFinal: false, final: null, reason: '旧格式',
    }))

    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('textarea#ov-reason').element.value).toBe('')
  })

  it('clearDraft 清除本机草稿（页面覆盖成功后调用）', async () => {
    localStorage.setItem('ai_grade_draft_v1_1_7', JSON.stringify({
      version: 1, savedAt: new Date().toISOString(), a: 10, q: null, useFinal: false, final: null, reason: 'x',
    }))
    const wrapper = mountPanel()
    await flushPromises()

    wrapper.vm.clearDraft()
    expect(localStorage.getItem('ai_grade_draft_v1_1_7')).toBeNull()
  })

  it('评分历史只显示真实字段：差异、理由、时间', () => {
    const wrapper = mountPanel(DONE_DETAIL)
    const text = wrapper.text()
    expect(text).toContain('评分历史')
    expect(text).toContain('算法关键步骤 13 → 10')
    expect(text).toContain('最终得分 79 → 76')
    expect(text).toContain('教师调整')
    // created_at 存在时显示时间
    expect(text).toContain('8/1')
  })

  it('历史中缺失 created_at/reason 时不渲染假字段', () => {
    const wrapper = mountPanel({
      ...DONE_DETAIL,
      overrides: [{ id: 2, original_snapshot: { algorithm_score: 13 }, replacement_snapshot: { algorithm_score: 10 } }],
    })
    const text = wrapper.text()
    expect(text).toContain('算法关键步骤 13 → 10')
    expect(text).not.toContain('undefined')
  })
})
