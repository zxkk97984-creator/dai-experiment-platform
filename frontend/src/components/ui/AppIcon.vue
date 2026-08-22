<script setup>
// AppIcon：语义图标原语。图标数据来自 ./icon-map.js（本地打包的 Iconify 数据），
// 运行时不依赖 Iconify API。禁止用 emoji、自制 SVG 或 CSS 图案代替真实图标。

import { computed } from 'vue'
import { Icon } from '@iconify/vue'

import { ICONS } from './icon-map.js'

const props = defineProps({
  /** 语义键，如 home / course / python */
  name: { type: String, required: true },
  /** 数字（px）或字符串（如 '1.25em'） */
  size: { type: [Number, String], default: 20 },
  /** 提供时图标作为图像暴露给辅助技术 */
  label: { type: String, default: null },
})

const icon = computed(() => ICONS[props.name] || null)

if (import.meta.env.DEV && !icon.value) {
  console.warn(`[AppIcon] 未知图标语义键: ${props.name}`)
}
</script>

<template>
  <Icon
    v-if="icon"
    :icon="icon.data"
    :data-set="icon.set"
    :data-icon="name"
    :width="size"
    :height="size"
    class="app-icon"
    :aria-hidden="label ? 'false' : 'true'"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
  />
</template>

<style>
/* 全局 img,svg{max-width:100%} 在 grid/flex 容器里会把按属性定宽的图标压缩成几像素，
   图标始终由 size 属性显式定宽，这里解除该钳制。 */
.app-icon {
  max-width: none;
}
</style>
