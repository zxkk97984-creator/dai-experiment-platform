// TeacherScoreOverview：顶部评分概览卡测试。

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TeacherScoreOverview from '../TeacherScoreOverview.vue'

const baseDetail = {
  functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
  raw_total: 79, score_cap: null, final_score_100: 79, scaled_score: 79,
  mode: 'active', status: 'completed', overrides: [],
}

function mountOverview(detail = baseDetail) {
  return mount(TeacherScoreOverview, { props: { detail } })
}

describe('TeacherScoreOverview', () => {
  it('突出最终得分大数字', () => {
    const wrapper = mountOverview()
    expect(wrapper.get('.score-overview__value').text()).toBe('79')
    expect(wrapper.text()).toContain('最终得分')
  })

  it('F/A/R/Q 四条中文维度，字母为辅助小标签', () => {
    const wrapper = mountOverview()
    const text = wrapper.text()
    expect(text).toContain('功能正确性')
    expect(text).toContain('算法关键步骤')
    expect(text).toContain('鲁棒性与性能')
    expect(text).toContain('代码质量')
    expect(text).toContain('54 / 60')
    expect(text).toContain('13 / 20')
    expect(text).toContain('7 / 10')
    expect(text).toContain('5 / 10')
    // 字母辅助标签存在（F/A/R/Q，按顺序）
    const letters = wrapper.findAll('.score-overview__dim-letter').map((el) => el.text())
    expect(letters).toEqual(['F', 'A', 'R', 'Q'])
  })

  it('review_required 状态徽章', () => {
    const wrapper = mountOverview({
      ...baseDetail, status: 'review_required', needs_teacher_review: true,
    })
    expect(wrapper.text()).toContain('等待教师复核')
    expect(wrapper.find('.ui-status-warning').exists()).toBe(true)
  })

  it('completed + override 显示教师已调整', () => {
    const wrapper = mountOverview({ ...baseDetail, overrides: [{}] })
    expect(wrapper.text()).toContain('教师已调整并生效')
  })

  it('A/Q 未评分时显示占位符', () => {
    const wrapper = mountOverview({
      ...baseDetail, algorithm_score: null, quality_score: null,
    })
    expect(wrapper.text()).toContain('—')
  })

  it('辅助行：原始分/上限/折算（有数据才显示）', () => {
    const wrapper = mountOverview()
    expect(wrapper.text()).toContain('原始 79')
    expect(wrapper.text()).toContain('折算 79')

    const noMeta = mountOverview({ ...baseDetail, raw_total: null, score_cap: null, scaled_score: null })
    expect(noMeta.find('.score-overview__meta').exists()).toBe(false)
  })

  it('cap 存在时显示上限', () => {
    const wrapper = mountOverview({ ...baseDetail, score_cap: 90 })
    expect(wrapper.text()).toContain('上限 90')
  })
})
