<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const course = ref(null)
const chapters = ref([])
const loading = ref(true)
const showChForm = ref(false)
const showLesForm = ref({})
const chForm = ref({ title: '' })
const lesForm = ref({ title: '', content_type: 'markdown', content: '' })

async function fetch() {
  loading.value = true
  try {
    const [cRes, chRes] = await Promise.all([
      coursesAPI.get(route.params.id),
      coursesAPI.getChapters(route.params.id),
    ])
    course.value = cRes.data
    chapters.value = chRes.data
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function createChapter() {
  if (!chForm.value.title) return
  try {
    await coursesAPI.createChapter(route.params.id, {
      title: chForm.value.title,
      order_index: chapters.value.length,
    })
    chForm.value.title = ''
    showChForm.value = false
    fetch()
    app.showToast('章节已创建', 'success')
  } catch { app.showToast('创建失败', 'error') }
}

async function createLesson(chId) {
  const f = lesForm.value
  if (!f.title) return
  try {
    await coursesAPI.createLesson(chId, { ...f, order_index: 0 })
    lesForm.value = { title: '', content_type: 'markdown', content: '' }
    showLesForm.value[chId] = false
    fetch()
    app.showToast('课时已创建', 'success')
  } catch { app.showToast('创建失败', 'error') }
}

function typeLabel(ct) {
  const map = { markdown: '讲义', video: '视频', notebook: 'Notebook' }
  return map[ct] || ct
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="page-header">
      <h1 class="page-title">{{ course?.title || '课程详情' }}</h1>
      <button class="btn-accent" @click="showChForm = !showChForm">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" class="btn-icon">
          <path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        {{ showChForm ? '取消' : '添加章节' }}
      </button>
    </div>

    <!-- Chapter creation form -->
    <div v-if="showChForm" class="chapter-form">
      <input
        v-model="chForm.title"
        placeholder="章节名称，如：第一章 Python基础"
        class="dark-input"
        @keyup.enter="createChapter"
      />
      <button class="btn-accent" @click="createChapter">确认添加</button>
    </div>

    <div v-if="loading" class="loading-text">加载中...</div>

    <!-- Chapter cards -->
    <div v-for="(ch, chi) in chapters" :key="ch.id" class="chapter-card">
      <div class="chapter-header">
        <div class="chapter-title-row">
          <span class="chapter-num">第{{ chi + 1 }}章</span>
          <h3 class="chapter-name">{{ ch.title }}</h3>
        </div>
        <button class="btn-ghost" @click="showLesForm[ch.id] = !showLesForm[ch.id]">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" class="btn-icon">
            <path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          添加课时
        </button>
      </div>

      <!-- Lesson creation form -->
      <div v-if="showLesForm[ch.id]" class="lesson-form">
        <div class="lesson-form-row">
          <input
            v-model="lesForm.title"
            placeholder="课时名称"
            class="dark-input"
          />
          <select v-model="lesForm.content_type" class="dark-select">
            <option value="markdown">Markdown 讲义</option>
            <option value="video">视频</option>
            <option value="notebook">Notebook</option>
          </select>
        </div>
        <div v-if="lesForm.content_type === 'markdown'" class="lesson-form-row">
          <textarea
            v-model="lesForm.content"
            rows="4"
            placeholder="Markdown 内容"
            class="dark-textarea"
          ></textarea>
        </div>
        <button class="btn-accent btn-accent-sm" @click="createLesson(ch.id)">确认添加</button>
      </div>

      <!-- Lesson list -->
      <div v-if="ch.lessons && ch.lessons.length" class="lesson-list">
        <div
          v-for="l in ch.lessons"
          :key="l.id"
          class="lesson-item"
        >
          <span class="lesson-type-icon" :class="'icon-' + l.content_type">
            <!-- Markdown icon -->
            <svg v-if="l.content_type === 'markdown'" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 2.5v11h2.5V10h1.25l2.5 3.5H12V2.5h-2.5V7h-1.25l-2.5-3.5H2V2.5h2.5" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
              <path d="M2 13.5h2.5M5.75 10H7l2.5 3.5M9.5 2.5H12M9.5 7H12" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.5"/>
            </svg>
            <!-- Video icon -->
            <svg v-else-if="l.content_type === 'video'" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1.5" y="3" width="13" height="10" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
              <path d="M6.5 6.5l4 2-4 2v-4z" fill="currentColor"/>
            </svg>
            <!-- Notebook icon -->
            <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="3" y="1.5" width="10" height="13" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
              <path d="M6 5h4M6 7.5h4M6 10h3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              <path d="M3 4l-1.5 1v7l1.5 1" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" opacity="0.5"/>
            </svg>
          </span>
          <span class="lesson-title">{{ l.title }}</span>
          <span class="lesson-type-badge">{{ typeLabel(l.content_type) }}</span>
        </div>
      </div>
      <p v-else class="empty-text">暂无课时</p>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Chapter & Lesson Management — Pythonista Dark Admin
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page header ────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 400;
  color: #D6DEEB;
  margin: 0;
  letter-spacing: -0.3px;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.btn-accent {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #E0553D;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
  font-family: var(--font-body);
  line-height: 1.4;
}

.btn-accent:hover {
  background: #C94A33;
}

.btn-accent:active {
  background: #B33E2A;
}

.btn-accent-sm {
  padding: 6px 14px;
  font-size: 12px;
}

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: transparent;
  color: #6A7086;
  border: 1px solid #2A3040;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  font-family: var(--font-body);
  line-height: 1.4;
}

.btn-ghost:hover {
  color: #D6DEEB;
  border-color: #3A4050;
  background: rgba(255,255,255,0.03);
}

.btn-icon {
  flex-shrink: 0;
}

/* ── Chapter form (inline create) ──────────────────────────────────── */
.chapter-form {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px;
  background: #151821;
  border: 1px solid #2A3040;
  border-radius: 8px;
  margin-bottom: 20px;
}

.chapter-form .dark-input {
  flex: 1;
}

/* ── Dark inputs ───────────────────────────────────────────────────── */
.dark-input {
  padding: 8px 12px;
  background: #11141D;
  border: 1px solid #2A3040;
  border-radius: 6px;
  color: #D6DEEB;
  font-size: 13px;
  font-family: var(--font-body);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.5;
}

.dark-input::placeholder {
  color: #4A5060;
}

.dark-input:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 2px rgba(224,85,61,0.15);
}

.dark-select {
  padding: 8px 32px 8px 12px;
  background: #11141D;
  border: 1px solid #2A3040;
  border-radius: 6px;
  color: #D6DEEB;
  font-size: 13px;
  font-family: var(--font-body);
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%236A7086' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.5;
  min-width: 150px;
}

.dark-select:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 2px rgba(224,85,61,0.15);
}

.dark-select option {
  background: #1A1E2B;
  color: #D6DEEB;
}

.dark-textarea {
  width: 100%;
  padding: 10px 12px;
  background: #11141D;
  border: 1px solid #2A3040;
  border-radius: 6px;
  color: #D6DEEB;
  font-size: 13px;
  font-family: var(--font-mono);
  outline: none;
  resize: vertical;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.6;
}

.dark-textarea::placeholder {
  color: #4A5060;
}

.dark-textarea:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 2px rgba(224,85,61,0.15);
}

/* ── Chapter card ──────────────────────────────────────────────────── */
.chapter-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

.chapter-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.chapter-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.chapter-num {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: #E0553D;
  background: rgba(224,85,61,0.1);
  padding: 2px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

.chapter-name {
  font-size: 15px;
  font-weight: 600;
  color: #D6DEEB;
  margin: 0;
}

/* ── Lesson form (inline) ──────────────────────────────────────────── */
.lesson-form {
  padding: 16px;
  background: #151821;
  border: 1px solid #2A3040;
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.lesson-form-row {
  display: flex;
  gap: 10px;
}

.lesson-form-row .dark-input {
  flex: 1;
}

/* ── Lesson list ───────────────────────────────────────────────────── */
.lesson-list {
  display: flex;
  flex-direction: column;
}

.lesson-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  transition: background 0.12s;
  cursor: default;
}

.lesson-item:hover {
  background: rgba(224,85,61,0.06);
}

.lesson-type-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 5px;
  flex-shrink: 0;
}

.icon-markdown {
  color: #5A9FD4;
  background: rgba(90,159,212,0.1);
}

.icon-video {
  color: #E0553D;
  background: rgba(224,85,61,0.1);
}

.icon-notebook {
  color: #7E8CE0;
  background: rgba(126,140,224,0.1);
}

.lesson-title {
  flex: 1;
  font-size: 13px;
  color: #D6DEEB;
  line-height: 1.4;
}

.lesson-type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6A7086;
  background: rgba(106,112,134,0.12);
  padding: 2px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

/* ── Empty state ───────────────────────────────────────────────────── */
.empty-text {
  font-size: 13px;
  color: #6A7086;
  padding: 8px 0;
}

.loading-text {
  font-size: 13px;
  color: #6A7086;
  padding: 24px 0;
}
</style>
