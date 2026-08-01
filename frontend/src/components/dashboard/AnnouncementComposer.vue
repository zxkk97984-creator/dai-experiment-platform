<script setup>
// 教师课程公告发布模态：本地校验、提交中禁用、失败保持打开、成功重置并关闭

import { computed, onMounted, reactive, ref, watch } from 'vue'

import { announcementsAPI } from '../../api/announcements.js'

const props = defineProps({
  courses: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'published'])

const form = reactive({
  course_id: null,
  title: '',
  content: '',
  priority: 'normal',
  expires_at: '',
})
const submitting = ref(false)
const error = ref('')
const titleInput = ref(null)
const modalEl = ref(null)

function onTabKeydown(e) {
  // Tab 焦点循环：焦点不逃出模态
  if (e.key !== 'Tab' || !modalEl.value) return
  const focusables = modalEl.value.querySelectorAll(
    'button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
  )
  const list = Array.from(focusables).filter((el) => !el.disabled)
  if (!list.length) return
  const first = list[0]
  const last = list[list.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

const canSubmit = computed(() => {
  return (
    form.course_id != null &&
    form.title.trim().length > 0 &&
    form.content.trim().length > 0 &&
    !submitting.value
  )
})

watch(
  () => props.courses,
  (courses) => {
    if (!form.course_id && courses.length) form.course_id = courses[0].id
  },
  { immediate: true },
)

onMounted(() => {
  titleInput.value?.focus()
})

function close() {
  if (submitting.value) return
  emit('close')
}

function resetForm() {
  Object.assign(form, {
    course_id: props.courses[0]?.id ?? null,
    title: '',
    content: '',
    priority: 'normal',
    expires_at: '',
  })
  error.value = ''
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  error.value = ''
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      priority: form.priority,
      scope: 'course',
      course_id: form.course_id,
    }
    if (form.expires_at) {
      payload.expires_at = new Date(form.expires_at).toISOString()
    }
    const { data } = await announcementsAPI.create(payload)
    resetForm()
    emit('published', data)
  } catch (e) {
    error.value = e.response?.data?.detail?.message || '发布失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="composer-backdrop" @click.self="close">
    <div
      ref="modalEl"
      class="composer-modal"
      role="dialog"
      aria-modal="true"
      aria-label="发布课程公告"
      @keydown.esc="close"
      @keydown="onTabKeydown"
    >
      <div class="composer-head">
        <h2 class="composer-title">发布公告</h2>
        <button type="button" class="close-btn" aria-label="关闭" @click="close">×</button>
      </div>
      <form class="composer-form" @submit.prevent="submit">
        <label class="field">
          <span class="field-label">课程</span>
          <select v-model="form.course_id" required>
            <option v-for="course in courses" :key="course.id" :value="course.id">
              {{ course.title }}
            </option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">标题</span>
          <input
            ref="titleInput"
            v-model="form.title"
            type="text"
            maxlength="120"
            required
            placeholder="请输入公告标题"
          />
        </label>
        <label class="field">
          <span class="field-label">内容</span>
          <textarea
            v-model="form.content"
            rows="4"
            maxlength="2000"
            required
            placeholder="请输入公告内容"
          ></textarea>
        </label>
        <div class="field-row">
          <label class="field">
            <span class="field-label">优先级</span>
            <select v-model="form.priority">
              <option value="normal">普通</option>
              <option value="important">重要</option>
              <option value="urgent">紧急</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">过期时间（可选）</span>
            <input v-model="form.expires_at" type="datetime-local" />
          </label>
        </div>
        <p v-if="error" class="composer-error" role="alert">{{ error }}</p>
        <div class="composer-actions">
          <button type="button" class="cancel-btn" @click="close">取消</button>
          <button type="submit" class="submit-btn" :disabled="!canSubmit">发布</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.composer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.composer-modal {
  width: min(520px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 20px;
}

.composer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.composer-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--ink);
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}
.close-btn:hover { color: var(--ink); background: var(--surface-raised); }

.composer-form { display: flex; flex-direction: column; gap: 14px; }

.field { display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 0; }
.field-row { display: flex; gap: 12px; }

.field-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}

.field input,
.field select,
.field textarea {
  padding: 8px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  width: 100%;
  box-sizing: border-box;
}
.field input:focus-visible,
.field select:focus-visible,
.field textarea:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 1px;
}

.composer-error {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--danger);
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cancel-btn,
.submit-btn {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}

.cancel-btn {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text-secondary);
}
.cancel-btn:hover { background: var(--surface-raised); }

.submit-btn {
  border: none;
  background: var(--primary);
  color: var(--surface);
}
.submit-btn:hover:not(:disabled) { background: var(--primary-dark); }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
