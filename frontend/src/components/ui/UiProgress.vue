<script setup>
// UiProgress：进度条原语。值钳制在 0–100，暴露完整进度条 ARIA 语义。
import { computed } from 'vue'

const props = defineProps({
  /** 0–100 的进度值；越界值自动钳制 */
  value: { type: Number, default: 0 },
})

const safeValue = computed(() => {
  const v = Number(props.value)
  if (Number.isNaN(v)) return 0
  return Math.round(Math.min(100, Math.max(0, v)))
})
</script>

<template>
  <div
    class="ui-progress"
    role="progressbar"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="safeValue"
  >
    <span class="ui-progress__bar" :style="{ width: safeValue + '%' }"></span>
  </div>
</template>

<style scoped>
.ui-progress {
  width: 100%;
  height: 6px;
  background: var(--surface-raised);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.ui-progress__bar {
  display: block;
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-full);
  transition: width var(--duration-normal) var(--ease-out);
}
</style>
