/** 客户端分页 composable：基于内存数据源切片，页码夹在合法范围，数据量变化时自动收敛 */
import { computed, ref, unref, watch } from 'vue'

export function useClientPagination(source, initialPageSize = 10) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  const pageCount = computed(() => Math.max(1, Math.ceil(unref(source).length / pageSize.value)))
  const pagedItems = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return unref(source).slice(start, start + pageSize.value)
  })
  function goToPage(value) {
    page.value = Math.min(Math.max(Number(value) || 1, 1), pageCount.value)
  }
  function resetPage() { page.value = 1 }
  watch(pageCount, (count) => { if (page.value > count) page.value = count })
  return { page, pageSize, pageCount, pagedItems, goToPage, resetPage }
}
