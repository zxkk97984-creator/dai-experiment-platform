import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TeacherPagination from '../TeacherPagination.vue'

function mountPagination(props = {}) {
  return mount(TeacherPagination, {
    props: {
      currentPage: 1,
      pageCount: 45,
      total: 450,
      pageSize: 10,
      ...props,
    },
    global: {
      stubs: {
        AppIcon: { template: '<span />' },
      },
    },
  })
}

function pageLabels(wrapper) {
  return wrapper.findAll('.teacher-pagination-controls button')
    .map((button) => button.text().trim())
    .filter(Boolean)
    .map(Number)
}

describe('TeacherPagination', () => {
  it('最多显示三个连续页码，并让当前页尽量居中', async () => {
    const first = mountPagination({ currentPage: 1 })
    expect(pageLabels(first)).toEqual([1, 2, 3])

    const middle = mountPagination({ currentPage: 45, pageCount: 100, total: 1000 })
    expect(pageLabels(middle)).toEqual([44, 45, 46])
    expect(middle.find('.teacher-pagination-controls .active').text()).toBe('45')

    const last = mountPagination({ currentPage: 45, pageCount: 45 })
    expect(pageLabels(last)).toEqual([43, 44, 45])
  })

  it('总页数不超过三页时只显示实际页码', () => {
    expect(pageLabels(mountPagination({ pageCount: 1 }))).toEqual([1])
    expect(pageLabels(mountPagination({ pageCount: 2 }))).toEqual([1, 2])
    expect(pageLabels(mountPagination({ pageCount: 3 }))).toEqual([1, 2, 3])
  })

  it('上一页、下一页和页码按钮会发出目标页码', async () => {
    const wrapper = mountPagination({ currentPage: 45, pageCount: 100, total: 1000 })
    const controls = wrapper.findAll('.teacher-pagination-controls button')

    await controls[0].trigger('click')
    await controls[2].trigger('click')
    await controls[controls.length - 1].trigger('click')

    expect(wrapper.emitted('change')).toEqual([[44], [46]])
  })

  it('按回车跳转到合法页码，并在页码变化后同步输入框', async () => {
    const wrapper = mountPagination({ currentPage: 1 })
    const input = wrapper.get('input[aria-label="跳转页码"]')

    await input.setValue('23')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('change')).toEqual([[23]])

    await wrapper.setProps({ currentPage: 23 })
    expect(input.element.value).toBe('23')
  })

  it('无效页码不跳转，并恢复为当前页', async () => {
    const wrapper = mountPagination({ currentPage: 23 })
    const input = wrapper.get('input[aria-label="跳转页码"]')

    for (const value of ['0', '-1', '46', 'abc', '']) {
      await input.setValue(value)
      await input.trigger('keydown.enter')
      expect(input.element.value).toBe('23')
    }
    expect(wrapper.emitted('change')).toBeUndefined()
  })
})
