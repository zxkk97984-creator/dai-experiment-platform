<script setup>
// UiStatusPill：V2 状态徽标原语（映射 .badge + dot）。
// 语义色调收敛为 V2：success / warning / danger / info / neutral / accent；
// 旧 purple/submitted 一律并入 info，禁止紫色。

import { computed } from 'vue'

const TONES = ['success', 'warning', 'danger', 'info', 'neutral', 'accent']

const LEGACY_TONES = {
  pending: 'warning',
  progress: 'info',
  submitted: 'info',
}

const props = defineProps({
  /** 语义色调：支持 success/warning/danger/info/neutral/accent 及旧兼容键 */
  tone: { type: String, default: 'neutral' },
  /** 展示文本 */
  label: { type: String, required: true },
})

const toneClass = computed(() => {
  const tone = LEGACY_TONES[props.tone] || props.tone
  return TONES.includes(tone) ? tone : 'neutral'
})
</script>

<template>
  <span class="badge ui-status" :class="[`badge-${toneClass}`, `ui-status-${props.tone}`, `ui-status-${toneClass}`]">
    <span class="dot" aria-hidden="true"></span>
    {{ label }}
  </span>
</template>

<style scoped>
/* 视觉来自全局 .badge 系列；不新增颜色。 */
.ui-status { gap: 6px; }
</style>
