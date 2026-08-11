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
  <header class="teacher-page-header">
    <div class="teacher-page-heading">
      <h1>{{ title }}</h1>
      <p>{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions || actionLabel" class="teacher-page-actions">
      <slot name="actions">
        <button class="btn-primary teacher-page-action" type="button" @click="$emit('action')">
          <AppIcon :name="actionIcon" :size="18" />
          {{ actionLabel }}
        </button>
      </slot>
    </div>
  </header>
</template>

<style scoped>
.teacher-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.teacher-page-heading { min-width: 0; }

h1 {
  margin: 0 0 6px;
  color: var(--ink);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -.025em;
  line-height: 1.15;
}

p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.55;
}

.teacher-page-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex: 0 0 auto;
}

.teacher-page-action {
  min-height: 46px;
  padding: 0 18px;
  font-size: 14px;
}

@media (max-width: 720px) {
  .teacher-page-header { align-items: stretch; flex-direction: column; gap: 14px; }
  h1 { font-size: 26px; }
  .teacher-page-actions { justify-content: stretch; }
  .teacher-page-actions :deep(button) { flex: 1; }
}
</style>
