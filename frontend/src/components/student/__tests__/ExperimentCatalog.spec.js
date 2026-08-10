/** ExperimentCatalog 实验目录展示组件契约测试：props 渲染与事件上抛 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExperimentCatalog from '../ExperimentCatalog.vue'

function makeProps(overrides = {}) {
  return {
    items: [
      { id: 1, name: 'Python 数据分析实验', learning_status: 'not_started', last_learning_at: null },
      { id: 2, name: '机器学习入门', learning_status: 'graded', last_learning_at: '2026-08-01T08:00:00Z' },
    ],
    loading: false,
    failed: false,
    total: 2,
    page: 1,
    pageCount: 1,
    activeStatus: '',
    query: '',
    sortBy: 'default',
    summary: { total: 2, not_started: 1, started: 0, submitted: 0, graded: 1 },
    ...overrides,
  }
}

function mountCatalog(props = makeProps()) {
  return mount(ExperimentCatalog, {
    props,
    global: { stubs: { UiStatusPill: { template: '<span class="pill-stub" />' } } },
  })
}

describe('ExperimentCatalog', () => {
  it('加载中渲染骨架屏', () => {
    const wrapper = mountCatalog(makeProps({ loading: true }))
    expect(wrapper.find('[aria-label="正在加载实验模块"]').exists()).toBe(true)
  })

  it('加载失败渲染重试并上抛 retry 事件', async () => {
    const wrapper = mountCatalog(makeProps({ failed: true }))
    expect(wrapper.text()).toContain('实验模块加载失败')
    await wrapper.get('.retry-button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('空数据时区分筛选态与无数据态文案', () => {
    const empty = mountCatalog(makeProps({ items: [], total: 0, query: '不存在' }))
    expect(empty.text()).toContain('没有找到匹配的实验模块')
    const plain = mountCatalog(makeProps({ items: [], total: 0 }))
    expect(plain.text()).toContain('暂无可学习的实验模块')
  })

  it('渲染行数与操作按钮，点击上抛 open 事件携带模块', async () => {
    const wrapper = mountCatalog()
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    await wrapper.findAll('.enter-button')[0].trigger('click')
    expect(wrapper.emitted('open')[0][0]).toEqual({ id: 1, name: 'Python 数据分析实验', learning_status: 'not_started', last_learning_at: null })
  })

  it('状态 tab 跟随 activeStatus prop 并上抛 select-status', async () => {
    const wrapper = mountCatalog(makeProps({ activeStatus: 'graded' }))
    const gradedTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('已评分'))
    expect(gradedTab.attributes('aria-selected')).toBe('true')
    await gradedTab.trigger('click')
    expect(wrapper.emitted('select-status')[0][0]).toBe('graded')
  })

  it('搜索输入与排序选择上抛更新事件', async () => {
    const wrapper = mountCatalog()
    await wrapper.find('input[type="search"]').setValue('Python')
    expect(wrapper.emitted('update:query')[0][0]).toBe('Python')
    await wrapper.find('select').setValue('name_asc')
    expect(wrapper.emitted('update:sort-by')[0][0]).toBe('name_asc')
  })

  it('分页按钮上抛 page 事件', async () => {
    const wrapper = mountCatalog(makeProps({ total: 12, page: 1, pageCount: 2 }))
    await wrapper.get('[aria-label="第 2 页"]').trigger('click')
    expect(wrapper.emitted('page')[0][0]).toBe(2)
  })
})
