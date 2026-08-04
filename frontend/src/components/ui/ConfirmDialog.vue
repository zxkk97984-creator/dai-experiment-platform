<script setup>
// ConfirmDialog：共享自定义确认弹窗（视觉对齐 ChapterManageView 的 .confirm-panel）
// 用法：title 必填；确认按钮默认"离开"（danger 时红色），取消默认"取消"。
// 遮罩点击（@click.self）与 Escape 均触发 cancel。

import { onBeforeUnmount, onMounted } from 'vue'

defineProps({
  title: { type: String, required: true },
  message: { type: String, default: '' },
  /** 确认按钮文字，默认"离开" */
  confirmText: { type: String, default: '离开' },
  /** 取消按钮文字，默认"取消" */
  cancelText: { type: String, default: '取消' },
  /** 确认按钮是否使用红色危险样式 */
  danger: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

// 挂载时监听 Escape → cancel；卸载时移除（避免多弹窗叠加时互相干扰）
function onKeydown(e) {
  if (e.key === 'Escape') emit('cancel')
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cancel')">
    <div class="confirm-panel" role="dialog" aria-modal="true" :aria-label="title">
      <h2>{{ title }}</h2>
      <p v-if="message">{{ message }}</p>
      <div class="confirm-actions">
        <button type="button" class="btn-ghost" @click="emit('cancel')">{{ cancelText }}</button>
        <button
          type="button"
          class="btn-primary"
          :class="{ 'btn-danger': danger }"
          @click="emit('confirm')"
        >
          {{ confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 遮罩与面板对齐全局 .modal-backdrop / .confirm-panel 视觉；
   按钮依赖全局 button.btn-primary / .btn-danger / .btn-ghost，此处不复用任何视图 scoped 类 */
.modal-backdrop {
  position: fixed;
  z-index: 60; /* 高于页面级弹窗，确保编辑页守卫弹窗在最上层 */
  /* left 随侧栏宽度（--modal-left 由 AppLayout 提供），相对内容区居中 */
  inset: 0 0 0 var(--modal-left, 0);
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(15, 23, 42, 0.25);
}

.confirm-panel {
  width: min(420px, calc(100% - 32px));
  padding: 24px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}
.confirm-panel h2 {
  margin: 0 0 10px;
  font-size: 17px;
  color: #0f172a;
}
.confirm-panel p {
  margin: 0 0 20px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
