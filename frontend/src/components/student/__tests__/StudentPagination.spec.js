import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StudentPagination from '../StudentPagination.vue'

function mountPagination(props = {}) {
  return mount(StudentPagination, {
    props: {
      currentPage: 1,
      pageCount: 45,
      total: 450,
      pageSize: 10,
      ...props,
    },
  })
}

function pageLabels(wrapper) {
  return wrapper.findAll('.page-number').map((button) => Number(button.text()))
}

describe('StudentPagination', () => {
  it('最多显示三个连续页码，当前页在中间位置', () => {
    expect(pageLabels(mountPagination({ currentPage: 1 }))).toEqual([1, 2, 3])
    expect(pageLabels(mountPagination({ currentPage: 23 }))).toEqual([22, 23, 24])
    expect(pageLabels(mountPagination({ currentPage: 45, pageCount: 45 }))).toEqual([43, 44, 45])
  })

  it('支持回车跳转，非法页码不触发 change', async () => {
    const wrapper = mountPagination({ currentPage: 23 })
    const input = wrapper.get('input[aria-label="跳转页码"]')

    await input.setValue('40')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('change')).toEqual([[40]])

    await input.setValue('999')
    await input.trigger('keydown.enter')
    expect(input.element.value).toBe('23')

    await input.setValue('abc')
    await input.trigger('keydown.enter')
    expect(input.element.value).toBe('23')
    expect(wrapper.emitted('change')).toHaveLength(1)
  })

  it('页码变更后同步输入框', async () => {
    const wrapper = mountPagination({ currentPage: 1 })
    await wrapper.setProps({ currentPage: 2 })
    expect(wrapper.get('input[aria-label="跳转页码"]').element.value).toBe('2')
  })
})
