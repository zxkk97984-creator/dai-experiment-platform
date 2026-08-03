<script setup>
// UiStatusPill：状态胶囊原语。语义色调映射，未知色调回退 neutral。
import { computed } from 'vue'

const TONES = ['pending', 'progress', 'submitted', 'success', 'warning', 'danger', 'neutral']

const props = defineProps({
  /** 语义色调：pending / progress / submitted / success / warning / danger / neutral */
  tone: { type: String, default: 'neutral' },
  /** 展示文本 */
  label: { type: String, required: true },
})

const toneClass = computed(() => (TONES.includes(props.tone) ? props.tone : 'neutral'))
</script>

<template>
  <span class="ui-status" :class="`ui-status-${toneClass}`">{{ label }}</span>
</template>

<style scoped>
.ui-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 500;
  line-height: 1.5;
  white-space: nowrap;
  border: 1px solid transparent;
}

/* 语义色调 */
.ui-status-pending   { background: var(--surface-raised); color: var(--text-secondary); border-color: var(--border); }
.ui-status-progress  { background: var(--primary-light);   color: var(--primary);        border-color: var(--primary-soft); }
.ui-status-submitted { background: var(--purple-light);    color: var(--purple);         border-color: rgba(119, 88, 232, 0.22); }
.ui-status-success   { background: var(--success-light);   color: var(--success);        border-color: rgba(18, 168, 100, 0.22); }
.ui-status-warning   { background: var(--warning-light);   color: var(--warning);        border-color: rgba(245, 138, 7, 0.22); }
.ui-status-danger    { background: var(--danger-light);    color: var(--danger);         border-color: rgba(240, 68, 56, 0.22); }
.ui-status-neutral   { background: var(--surface-raised);  color: var(--text-secondary); border-color: var(--border); }
</style>
