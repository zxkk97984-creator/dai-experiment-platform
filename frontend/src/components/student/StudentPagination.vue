<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  currentPage: { type: Number, required: true },
  pageCount: { type: Number, required: true },
  total: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  ariaLabel: { type: String, default: '列表分页' },
  totalSuffix: { type: String, default: '条' },
})

const emit = defineEmits(['change'])
const jumpPage = ref(String(props.currentPage))

const pageItems = computed(() => {
  const count = Math.max(1, props.pageCount)
  if (count <= 3) return Array.from({ length: count }, (_, index) => index + 1)
  const start = Math.min(Math.max(props.currentPage - 1, 1), count - 2)
  return [start, start + 1, start + 2]
})

watch(() => [props.currentPage, props.pageCount], () => {
  jumpPage.value = String(props.currentPage)
})

function change(nextPage) {
  if (!nextPage || nextPage < 1 || nextPage > props.pageCount || nextPage === props.currentPage) return
  emit('change', nextPage)
}

function jumpToPage() {
  const value = jumpPage.value.trim()
  if (!/^\d+$/.test(value)) {
    jumpPage.value = String(props.currentPage)
    return
  }
  const nextPage = Number(value)
  if (nextPage < 1 || nextPage > props.pageCount) {
    jumpPage.value = String(props.currentPage)
    return
  }
  change(nextPage)
}
</script>

<template>
  <nav v-if="total > 0" class="student-pagination" :aria-label="ariaLabel">
    <span class="pagination-total">共 {{ total }} {{ totalSuffix }}</span>
    <div class="pagination-controls">
      <button type="button" class="page-arrow" :disabled="currentPage === 1" aria-label="上一页" @click="change(currentPage - 1)">
        <span aria-hidden="true">‹</span>
      </button>
      <button
        v-for="pageNumber in pageItems"
        :key="pageNumber"
        type="button"
        class="page-number"
        :class="{ active: pageNumber === currentPage }"
        :aria-label="`第 ${pageNumber} 页`"
        :aria-current="pageNumber === currentPage ? 'page' : undefined"
        @click="change(pageNumber)"
      >
        {{ pageNumber }}
      </button>
      <button type="button" class="page-arrow" :disabled="currentPage === pageCount" aria-label="下一页" @click="change(currentPage + 1)">
        <span aria-hidden="true">›</span>
      </button>
    </div>
    <div class="pagination-jump">
      <label>
        <span>跳转至</span>
        <input v-model="jumpPage" type="text" inputmode="numeric" aria-label="跳转页码" @keydown.enter.prevent="jumpToPage" />
        <span>页</span>
      </label>
      <span class="page-size">{{ pageSize }} 条/页</span>
    </div>
  </nav>
</template>

<style scoped>
.student-pagination {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  min-height: 64px;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 13px;
}
.pagination-controls { display: flex; align-items: center; justify-content: center; gap: 6px; }
.student-pagination button {
  display: grid;
  place-items: center;
  min-width: 34px;
  height: 34px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--muted);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
}
.student-pagination button:hover:not(:disabled) { border-color: var(--border); color: var(--fg); background: var(--surface-subtle); }
.student-pagination button.active { border-color: var(--accent); color: var(--surface); background: var(--accent); }
.student-pagination button:disabled { cursor: not-allowed; opacity: .35; }
.pagination-jump { display: flex; align-items: center; justify-self: end; gap: 14px; white-space: nowrap; }
.pagination-jump label { display: inline-flex; align-items: center; gap: 5px; }
.pagination-jump input { width: 52px; height: 32px; padding: 0 7px; border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--fg); background: var(--surface); text-align: center; font-size: 13px; }
.pagination-jump input:focus { border-color: var(--accent); outline: 0; box-shadow: 0 0 0 3px var(--accent-soft); }
@media (max-width: 720px) {
  .student-pagination { grid-template-columns: 1fr auto; gap: 10px; }
  .pagination-controls { grid-column: 1 / -1; grid-row: 1; }
  .pagination-jump { justify-self: end; gap: 8px; }
}
</style>
