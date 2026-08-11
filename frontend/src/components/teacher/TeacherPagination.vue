<script setup>
import { computed } from 'vue'
import AppIcon from '../ui/AppIcon.vue'

const props = defineProps({
  currentPage: { type: Number, required: true },
  pageCount: { type: Number, required: true },
  total: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  ariaLabel: { type: String, default: '列表分页' },
  totalSuffix: { type: String, default: '条' },
})

const emit = defineEmits(['change'])

const pageItems = computed(() => {
  const count = Math.max(1, props.pageCount)
  if (count <= 7) return Array.from({ length: count }, (_, index) => ({ key: index + 1, value: index + 1, label: index + 1 }))
  const values = props.currentPage <= 4
    ? [1, 2, 3, 4, 5, null, count]
    : props.currentPage >= count - 3
      ? [1, null, count - 4, count - 3, count - 2, count - 1, count]
      : [1, null, props.currentPage - 1, props.currentPage, props.currentPage + 1, null, count]
  return values.map((value, index) => ({ key: `${value}-${index}`, value, label: value ?? '…' }))
})

function change(nextPage) {
  if (!nextPage || nextPage < 1 || nextPage > props.pageCount || nextPage === props.currentPage) return
  emit('change', nextPage)
}
</script>

<template>
  <footer v-if="total > 0" class="teacher-pagination pagination-bar">
    <span>共 {{ total }} {{ totalSuffix }}</span>
    <nav class="teacher-pagination-controls" :aria-label="ariaLabel">
      <button type="button" :disabled="currentPage === 1" aria-label="上一页" @click="change(currentPage - 1)">
        <AppIcon name="back" :size="16" />
      </button>
      <button
        v-for="item in pageItems"
        :key="item.key"
        type="button"
        :class="{ active: item.value === currentPage, ellipsis: item.value === null }"
        :disabled="item.value === null"
        :aria-label="item.value ? `第 ${item.value} 页` : undefined"
        :aria-current="item.value === currentPage ? 'page' : undefined"
        @click="change(item.value)"
      >
        {{ item.label }}
      </button>
      <button type="button" :disabled="currentPage === pageCount" aria-label="下一页" @click="change(currentPage + 1)">
        <AppIcon name="chevron-right" :size="16" />
      </button>
    </nav>
    <span>{{ pageSize }} 条/页</span>
  </footer>
</template>

<style scoped>
.teacher-pagination.pagination-bar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 16px;
  min-height: 64px;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 13px;
}

.teacher-pagination > span:last-child { justify-self: end; }
.teacher-pagination-controls { display: flex; align-items: center; gap: 6px; }
.teacher-pagination-controls button {
  display: grid;
  place-items: center;
  min-width: 34px;
  height: 34px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 7px;
  color: var(--text-secondary);
  background: transparent;
  font-size: 13px;
}
.teacher-pagination-controls button:hover:not(:disabled) { border-color: var(--border); color: var(--ink); background: var(--surface-raised); }
.teacher-pagination-controls button.active { border-color: var(--primary); color: #fff; background: var(--primary); }
.teacher-pagination-controls button.ellipsis { color: var(--text-tertiary); background: transparent; opacity: 1; }
.teacher-pagination-controls button:disabled:not(.ellipsis) { opacity: .35; }

@media (max-width: 720px) {
  .teacher-pagination { grid-template-columns: 1fr auto; gap: 10px; }
  .teacher-pagination-controls { grid-column: 1 / -1; grid-row: 1; justify-content: center; }
  .teacher-pagination-controls button { min-width: 32px; height: 32px; }
}
</style>
