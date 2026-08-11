<script setup>
import AppIcon from '../ui/AppIcon.vue'

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  titleId: { type: String, required: true },
  busy: { type: Boolean, default: false },
  panelClass: { type: String, default: '' },
  bodyClass: { type: String, default: '' },
  actionsClass: { type: String, default: '' },
})

const emit = defineEmits(['close', 'submit'])

function requestClose() {
  if (!props.busy) emit('close')
}
</script>

<template>
  <div class="course-form-backdrop" @click.self="requestClose">
    <form
      :class="['course-form-panel', panelClass]"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      @submit.prevent="$emit('submit')"
    >
      <header class="course-form-heading panel-header">
        <div>
          <h2 :id="titleId">{{ title }}</h2>
          <p v-if="description">{{ description }}</p>
        </div>
        <button
          class="course-form-close icon-button"
          type="button"
          aria-label="关闭"
          :disabled="busy"
          @click="requestClose"
        >
          <AppIcon name="close" :size="17" />
        </button>
      </header>

      <div :class="['course-form-body', bodyClass]">
        <slot />
      </div>

      <footer :class="['course-form-actions', actionsClass]">
        <slot name="actions" />
      </footer>
    </form>
  </div>
</template>

<style scoped>
.course-form-backdrop {
  position: fixed;
  inset: 0 0 0 var(--modal-left, 0);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow-y: auto;
  background: rgba(15, 23, 42, 0.44);
}

.course-form-panel {
  width: min(760px, 100%);
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface, #fff);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.2);
}

.course-form-heading {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: 0;
  padding: 24px 26px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--surface, #fff);
}

.course-form-heading h2 {
  margin: 0 0 5px;
  color: var(--ink);
  font-size: 20px;
  line-height: 1.3;
}

.course-form-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.course-form-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
}

.course-form-close:hover:not(:disabled) {
  border-color: transparent;
  background: var(--surface-raised);
  color: var(--ink);
}

.course-form-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 22px 26px;
  overflow-y: auto;
}

.course-form-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin: 0;
  padding: 16px 26px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface, #fff);
}

.course-form-actions :deep(button) { min-height: 40px; padding: 0 16px; }

@media (max-width: 640px) {
  .course-form-backdrop { align-items: flex-end; padding: 0; }
  .course-form-panel { width: 100%; max-height: 92vh; border-radius: 16px 16px 0 0; }
  .course-form-heading,
  .course-form-body,
  .course-form-actions { padding-left: 18px; padding-right: 18px; }
}
</style>
