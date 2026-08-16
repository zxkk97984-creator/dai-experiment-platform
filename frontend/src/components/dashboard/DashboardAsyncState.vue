<script setup>
// 共享异步区域状态：加载 / 可重试错误 / 如实空态；有内容时渲染默认插槽

defineProps({
  loading: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  empty: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '暂无数据' },
  emptyBody: { type: String, default: '' },
})

defineEmits(['retry'])
</script>

<template>
  <div v-if="loading" class="async-state" aria-busy="true">
    <div class="skeleton skeleton-line"></div>
    <div class="skeleton skeleton-line short"></div>
  </div>
  <div v-else-if="error" class="async-state" role="alert">
    <p class="state-title">加载失败</p>
    <button type="button" class="retry-btn" @click="$emit('retry')">重试</button>
  </div>
  <div v-else-if="empty" class="async-state">
    <p class="state-title">{{ emptyTitle }}</p>
    <p v-if="emptyBody" class="state-body">{{ emptyBody }}</p>
  </div>
  <slot v-else />
</template>

<style scoped>
.async-state { padding: 24px 16px; text-align: center; color: var(--muted); font-size: var(--text-base); }
.skeleton { border-radius: var(--radius-sm); background: var(--surface-subtle); margin: 8px auto; }
.skeleton-line { width: 80%; height: 14px; }
.skeleton-line.short { width: 55%; height: 12px; }
.state-title { margin: 0 0 8px; font-weight: 600; color: var(--muted); }
.state-body { margin: 0; font-size: var(--text-sm); color: var(--faint); }
.retry-btn { margin-top: 8px; height: 28px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface); color: var(--fg); font-size: var(--text-base); cursor: pointer; }
.retry-btn:hover { border-color: var(--fg); }
</style>
