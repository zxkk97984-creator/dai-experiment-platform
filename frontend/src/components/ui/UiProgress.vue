<script setup>
// UiProgress：V2 进度条原语（6px / 3px 圆角 / accent 填充）。
// 值钳制在 0–100，保留完整 progressbar ARIA 语义。
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
    class="score-bar ui-progress"
    role="progressbar"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="safeValue"
  >
    <i class="ui-progress__bar" :style="{ width: safeValue + '%' }"></i>
  </div>
</template>

<style scoped>
/* 视觉来自全局 .score-bar；仅保留 ARIA 组件结构。 */
.ui-progress { display: block; }
</style>
