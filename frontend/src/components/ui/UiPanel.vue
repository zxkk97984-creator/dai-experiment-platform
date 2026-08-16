<script setup>
// UiPanel：V2 面板原语（映射 dai-ds-v2.css 的 .panel）。
// header / 默认 / footer 三个插槽；compact 模式减小内边距，避免卡中卡。

defineProps({
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <section class="panel ui-panel" :class="{ 'ui-panel--compact': compact }">
    <header v-if="$slots.header" class="panel-head">
      <div class="ph-label">
        <slot name="header" />
      </div>
    </header>
    <div class="panel-body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="panel-foot ui-panel__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
/* 视觉全部来自全局 .panel / .panel-head / .panel-body；
   仅保留插槽组合差异，不新增颜色、圆角或阴影。 */
.ui-panel { display: flex; flex-direction: column; }
.ui-panel--compact .panel-body { padding: 12px 16px; }
.ui-panel--compact .panel-head { padding-block: 10px; }
.ui-panel__footer { padding: 12px 16px; border-top: 1px solid var(--border); }
</style>
