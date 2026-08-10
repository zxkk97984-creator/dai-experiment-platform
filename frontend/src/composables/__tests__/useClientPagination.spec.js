/** useClientPagination 客户端分页 composable 测试：分页切片、边界、页码复位与越界收敛 */
import { describe, it, expect } from 'vitest'
import { nextTick, ref } from 'vue'
import { useClientPagination } from '../useClientPagination.js'

describe('useClientPagination', () => {
  it('按每页 10 条切片并计算页数', () => {
    const source = ref(Array.from({ length: 12 }, (_, i) => i + 1))
    const { page, pageCount, pagedItems } = useClientPagination(source)

    expect(page.value).toBe(1)
    expect(pageCount.value).toBe(2)
    expect(pagedItems.value).toHaveLength(10)
  })

  it('goToPage 跳转并夹在合法范围', () => {
    const source = ref(Array.from({ length: 12 }, (_, i) => i + 1))
    const { page, pageCount, pagedItems, goToPage } = useClientPagination(source)

    goToPage(2)
    expect(page.value).toBe(2)
    expect(pagedItems.value).toEqual([11, 12])

    goToPage(99)
    expect(page.value).toBe(pageCount.value)
    goToPage(0)
    expect(page.value).toBe(1)
    goToPage('abc')
    expect(page.value).toBe(1)
  })

  it('空数据时页数为 1 且切片为空', () => {
    const source = ref([])
    const { page, pageCount, pagedItems, goToPage } = useClientPagination(source)

    expect(pageCount.value).toBe(1)
    expect(pagedItems.value).toEqual([])
    goToPage(2)
    expect(page.value).toBe(1)
  })

  it('数据量减少时当前页自动收敛到最后一页', async () => {
    const source = ref(Array.from({ length: 12 }, (_, i) => i + 1))
    const { page, pageCount, goToPage } = useClientPagination(source)

    goToPage(2)
    source.value = [1, 2, 3]
    await nextTick()
    expect(pageCount.value).toBe(1)
    expect(page.value).toBe(1)
  })

  it('resetPage 回到第 1 页', () => {
    const source = ref(Array.from({ length: 12 }, (_, i) => i + 1))
    const { page, goToPage, resetPage } = useClientPagination(source)

    goToPage(2)
    resetPage()
    expect(page.value).toBe(1)
  })

  it('支持自定义每页条数', () => {
    const source = ref(Array.from({ length: 25 }, (_, i) => i + 1))
    const { pageCount, pageSize } = useClientPagination(source, 20)

    expect(pageSize.value).toBe(20)
    expect(pageCount.value).toBe(2)
  })
})
