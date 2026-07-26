<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { studioAPI } from '../../api/studio.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
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
    // 分页接口返回 {items: [...], page: ..., total: ...}
    const rawData = chRes.data
    chapters.value = Array.isArray(rawData) ? rawData : (rawData.items || [])
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
    const res = await coursesAPI.createLesson(chId, { ...f, order_index: 0 })
    if (f.content_type === 'notebook') {
      const tmpl = await studioAPI.createTemplate({ name: f.title, lesson_id: res.data.id })
      router.push(`/teacher/courses/${route.params.id}/studio/${tmpl.data.id}`)
      return
    }
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
    <header class="page-head">
        <div>
          <h1 class="page-title">{{ course?.title || '课程详情' }}</h1>
          <p class="page-sub">管理章节与课时安排</p>
        </div>
        <button class="btn-accent" @click="showChForm = !showChForm">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          {{ showChForm ? '取消' : '添加章节' }}
        </button>
    </header>

    <!-- Chapter creation form -->
    <div v-if="showChForm" class="chapter-form">
      <input
        v-model="chForm.title"
        placeholder="章节名称，如：第一章 Python基础"
        class="form-input"
        @keyup.enter="createChapter"
      />
      <button class="btn-accent" @click="createChapter">确认添加</button>
    </div>

<div v-if="loading" class="card" style="padding:48px;text-align:center">
      <div class="skeleton" style="height:22px;width:240px;margin:0 auto 12px"></div>
      <div class="skeleton" style="height:14px;width:360px;margin:0 auto"></div>
    </div>

    <div v-else-if="chapters.length === 0 && !showChForm" class="empty-state">
      <p>📖 暂无章节，点击「添加章节」开始构建课程</p>
    </div>

    <!-- Chapter cards -->
    <div v-for="(ch, chi) in chapters" :key="ch.id" class="chapter-card">
      <div class="chapter-header">
        <div class="chapter-title-row">
          <span class="chapter-num">第{{ chi + 1 }}章</span>
          <h3 class="chapter-name">{{ ch.title }}</h3>
        </div>
        <button class="btn-ghost btn-sm" @click="showLesForm[ch.id] = !showLesForm[ch.id]">
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
            class="form-input"
          />
          <select v-model="lesForm.content_type" class="form-select">
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
            class="form-textarea"
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
/* ── Page head ── */
.page-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  margin-bottom: 24px; gap: 16px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 6px 0 0;
}

.page-title {
  font-family: var(--font-display);
  font-size: 28px; font-weight: 700;
  color: var(--ink); margin: 0;
  letter-spacing: -0.02em;
}

/* ── Accent CTA button ── */
.btn-accent {
  display: inline-flex;
  align-items: center; gap: 6px;
  padding: 8px 16px;
  background: var(--accent);
  color: var(--surface);
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  font-size: var(--text-sm); font-weight: 500;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
  font-family: var(--font-body); line-height: 1.4;
  white-space: nowrap;
}

.btn-accent:hover {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.32);
}

.btn-accent:active {
  background: var(--accent-dark);
}

.btn-accent-sm {
  padding: 6px 14px;
  font-size: 12px;
}

.btn-icon {
  flex-shrink: 0;
}

/* ── Chapter form ── */
.chapter-form {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 20px;
}

.chapter-form .form-input {
  flex: 1;
}

/* ── Form inputs ── */
.form-input {
  padding: 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--ink);
  font-size: 13px;
  font-family: var(--font-body);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.5;
}

.form-input::placeholder {
  color: var(--text-tertiary);
}

.form-input:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-glow-primary);
}

.form-select {
  padding: 8px 32px 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--ink);
  font-size: 13px;
  font-family: var(--font-body);
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2364748B' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.5;
  min-width: 150px;
}

.form-select:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-glow-primary);
}

.form-select option {
  background: var(--surface);
  color: var(--ink);
}

.form-textarea {
  width: 100%;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--ink);
  font-size: 13px;
  font-family: var(--font-mono);
  outline: none;
  resize: vertical;
  transition: border-color 0.15s, box-shadow 0.15s;
  line-height: 1.6;
}

.form-textarea::placeholder {
  color: var(--text-tertiary);
}

.form-textarea:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-glow-primary);
}

.form-file {
  padding: 8px 12px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
  background: var(--surface-raised);
  width: 100%;
  transition: border-color var(--duration-fast);
}

.form-file:hover {
  border-color: var(--primary);
}

.file-name {
  font-size: var(--text-xs);
  color: var(--primary);
  font-weight: 500;
  margin-top: 4px;
  display: inline-block;
}

/* ── Chapter card ── */
.chapter-card {
  background: var(--surface);
  border: 1px solid var(--border);
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
  color: var(--accent);
  background: rgba(249, 115, 22, 0.1);
  padding: 2px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

.chapter-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

/* ── Lesson form ── */
.lesson-form {
  padding: 16px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
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

.lesson-form-row .form-input {
  flex: 1;
}

/* ── Lesson list ── */
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
  background: var(--surface-raised);
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
  color: var(--primary);
  background: var(--accent-light);
}

.icon-video {
  color: var(--accent);
  background: rgba(249, 115, 22, 0.1);
}

.icon-notebook {
  color: var(--info);
  background: var(--info-light);
}

.lesson-title {
  flex: 1;
  font-size: 13px;
  color: var(--ink);
  line-height: 1.4;
}

.lesson-type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  background: var(--surface-raised);
  padding: 2px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

/* ── Empty state ── */
.empty-text {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 0;
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
