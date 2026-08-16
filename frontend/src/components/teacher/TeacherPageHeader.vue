<script setup>
import AppIcon from '../ui/AppIcon.vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, required: true },
  actionLabel: { type: String, default: '' },
  actionIcon: { type: String, default: 'plus' },
})

defineEmits(['action'])
</script>

<template>
  <header class="page-head teacher-page-header">
    <div class="ph-title">
      <p class="eyebrow">DAI · {{ title }}</p>
      <h1>{{ title }}</h1>
      <p class="lead">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions || actionLabel" class="ph-actions teacher-page-actions">
      <slot name="actions">
        <button class="btn btn-primary btn-lg" type="button" @click="$emit('action')">
          <AppIcon :name="actionIcon" :size="15" />
          {{ actionLabel }}
        </button>
      </slot>
    </div>
  </header>
</template>

<style scoped>
/* 视觉来自全局 .page-head；仅保留组件槽位差异。 */
.teacher-page-header { margin-bottom: 0; }
</style>
