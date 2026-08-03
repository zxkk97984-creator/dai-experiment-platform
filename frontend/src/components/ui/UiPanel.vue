<script setup>
// UiPanel：单层白卡容器。header / 默认 / footer 三个插槽；
// compact 模式用于密集行列表，避免卡中卡。

defineProps({
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <section class="ui-panel" :class="{ 'ui-panel--compact': compact }">
    <header v-if="$slots.header" class="ui-panel__header">
      <slot name="header" />
    </header>
    <div class="ui-panel__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="ui-panel__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.ui-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
}

.ui-panel__header {
  padding: 16px 20px 0;
}

.ui-panel__body {
  padding: 16px 20px 20px;
  min-width: 0;
}

.ui-panel__footer {
  padding: 0 20px 16px;
  border-top: 1px solid var(--border);
  margin-top: 4px;
}

.ui-panel--compact .ui-panel__header { padding-top: 14px; }
.ui-panel--compact .ui-panel__body { padding: 12px 16px 14px; }
.ui-panel--compact .ui-panel__footer { padding: 0 16px 12px; }
</style>
