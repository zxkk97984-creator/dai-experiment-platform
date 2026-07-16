<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const chapters = ref([])
const course = ref(null)
const lesson = ref(null)
const loading = ref(true)
const dropdownOpen = ref(false)

const courseId = computed(() => route.params.id)
const lessonId = computed(() => route.params.lid)

// 扁平的课时导航数组 [{ lesson, chapterTitle, chapterIndex }]
const flatLessons = computed(() => {
  const result = []
  for (let i = 0; i < chapters.value.length; i++) {
    const ch = chapters.value[i]
    if (ch.lessons) {
      for (const l of ch.lessons) {
        result.push({ lesson: l, chapterTitle: ch.title, chapterIndex: i })
      }
    }
  }
  return result
})

const currentIndex = computed(() => {
  return flatLessons.value.findIndex(f => f.lesson.id == lessonId.value)
})

const prevLesson = computed(() => {
  if (currentIndex.value <= 0) return null
  return flatLessons.value[currentIndex.value - 1]
})

const nextLesson = computed(() => {
  if (currentIndex.value >= flatLessons.value.length - 1) return null
  return flatLessons.value[currentIndex.value + 1]
})

const currentChapterTitle = computed(() => {
  if (currentIndex.value < 0) return ''
  return flatLessons.value[currentIndex.value]?.chapterTitle || ''
})

function findLesson() {
  for (let i = 0; i < chapters.value.length; i++) {
    const ch = chapters.value[i]
    if (ch.lessons) {
      const found = ch.lessons.find(l => l.id == lessonId.value)
      if (found) { lesson.value = found; return }
    }
  }
  lesson.value = null
}

function markComplete() {
  if (!lesson.value) return
  try {
    const key = `course_${courseId.value}_completed`
    const raw = localStorage.getItem(key)
    const ids = raw ? JSON.parse(raw) : []
    if (!ids.includes(lesson.value.id)) {
      ids.push(lesson.value.id)
      localStorage.setItem(key, JSON.stringify(ids))
    }
  } catch { /* ignore */ }
}

async function fetchData() {
  loading.value = true
  try {
    const [chRes, cRes] = await Promise.all([
      coursesAPI.getChapters(courseId.value),
      coursesAPI.get(courseId.value),
    ])
    chapters.value = chRes.data
    course.value = cRes.data
    findLesson()
    if (lesson.value) markComplete()
  } catch {
    app.showToast('加载课时失败', 'error')
  } finally { loading.value = false }
}

function goLesson(lessonId) {
  dropdownOpen.value = false
  router.push(`/student/courses/${courseId.value}/lessons/${lessonId}`)
}

function goPrev() {
  if (prevLesson.value) goLesson(prevLesson.value.lesson.id)
}

function goNext() {
  if (nextLesson.value) goLesson(nextLesson.value.lesson.id)
}

function goCourse() {
  router.push(`/student/courses/${courseId.value}`)
}

function goJupyter() {
  router.push('/student/jupyter')
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

// 点击外部关闭下拉
function onDocClick(e) {
  const el = document.getElementById('chapter-dropdown')
  if (el && !el.contains(e.target)) dropdownOpen.value = false
}

onMounted(async () => {
  await fetchData()
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})

// 路由参数变化时重新查找
watch(lessonId, async () => {
  if (chapters.value.length === 0) {
    await fetchData()
  } else {
    findLesson()
    if (lesson.value) markComplete()
  }
})
</script>

<template>
  <AppLayout>
    <!-- Loading -->
    <div v-if="loading" class="lesson-loading">
      <div class="skeleton" style="height:22px;width:360px;margin-bottom:16px"></div>
      <div class="skeleton" style="height:14px;width:100%;margin-bottom:8px" v-for="i in 8" :key="i"></div>
    </div>

    <!-- Not found -->
    <div v-else-if="!lesson" class="empty-state">
      <p>课时不存在</p>
      <button class="btn-primary" @click="goCourse" style="margin-top:12px">返回课程</button>
    </div>

    <!-- Lesson content -->
    <template v-else>
      <!-- Breadcrumb -->
      <div class="breadcrumb-row">
        <div class="breadcrumb">
          <button class="breadcrumb-link" @click="goCourse">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3L5 8l5 5"/></svg>
            {{ course?.title || '返回课程' }}
          </button>
          <span class="breadcrumb-sep">›</span>
          <span class="breadcrumb-current">{{ currentChapterTitle }}</span>
          <span class="breadcrumb-sep">›</span>
          <span class="breadcrumb-current">{{ lesson.title }}</span>
        </div>

        <!-- Chapter dropdown -->
        <div class="dropdown-wrap" id="chapter-dropdown">
          <button class="btn-ghost btn-sm dropdown-trigger" @click.stop="toggleDropdown">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="10" height="10" rx="1"/><path d="M5 6h4M5 9h2"/></svg>
            快速跳转
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 3.5l3 3 3-3"/></svg>
          </button>
          <transition name="dropdown-fade">
            <div v-if="dropdownOpen" class="dropdown-menu">
              <div v-for="ch in chapters" :key="ch.id" class="dropdown-group">
                <div class="dropdown-chapter">第{{ ch.order_index + 1 }}章  {{ ch.title }}</div>
                <div
                  v-for="l in ch.lessons" :key="l.id"
                  class="dropdown-item"
                  :class="{ active: l.id == lesson.id }"
                  @click.stop="goLesson(l.id)"
                >
                  <span class="dropdown-item-icon">
                    <template v-if="l.content_type === 'markdown'">📖</template>
                    <template v-else-if="l.content_type === 'video'">🎥</template>
                    <template v-else>📓</template>
                  </span>
                  {{ l.title }}
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <hr class="lesson-divider" />

      <!-- Content: markdown -->
      <div v-if="lesson.content_type === 'markdown'" class="lesson-content"
        v-html="lesson.content || '<p class=\'text-secondary\'>暂无内容</p>'"></div>

      <!-- Content: video -->
      <div v-else-if="lesson.content_type === 'video'" class="lesson-video">
        <div v-if="lesson.video_url" class="video-wrapper">
          <div class="video-placeholder">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
              <circle cx="24" cy="24" r="20"/><path d="M20 16v16l12-8z"/>
            </svg>
            <p class="text-sm text-secondary" style="margin-top:12px">视频课时：{{ lesson.title }}</p>
            <a :href="lesson.video_url" target="_blank" class="btn-primary" style="margin-top:12px;display:inline-flex;align-items:center;gap:6px">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="7" r="5"/><path d="M6 5v4l3-2z"/></svg>
              打开视频
            </a>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>视频暂不可用</p>
        </div>
      </div>

      <!-- Content: notebook -->
      <div v-else class="lesson-notebook">
        <div class="notebook-card">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="1" opacity="0.4">
            <rect x="6" y="6" width="28" height="28" rx="2"/><path d="M14 14h12M14 20h8M14 26h6"/>
          </svg>
          <h3>{{ lesson.title }}</h3>
          <p class="text-sm text-secondary" v-if="lesson.content">{{ lesson.content }}</p>
          <button class="btn-primary" @click="goJupyter" style="margin-top:12px;display:inline-flex;align-items:center;gap:6px">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="10" height="10" rx="1"/><path d="M5 6h4M5 9h2"/></svg>
            在 JupyterLab 中打开
          </button>
        </div>
      </div>

      <hr class="lesson-divider" />

      <!-- Bottom navigation -->
      <div class="lesson-nav">
        <button
          v-if="prevLesson"
          class="nav-btn nav-prev"
          @click="goPrev"
          :title="prevLesson.lesson.title"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3L4 7l5 5"/></svg>
          <span class="nav-label">上一课</span>
          <span class="nav-title">{{ prevLesson.lesson.title }}</span>
        </button>
        <div v-else class="nav-btn nav-prev disabled">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3L4 7l5 5"/></svg>
          <span class="nav-label">上一课</span>
        </div>

        <button
          v-if="nextLesson"
          class="nav-btn nav-next"
          @click="goNext"
          :title="nextLesson.lesson.title"
        >
          <span class="nav-title">{{ nextLesson.lesson.title }}</span>
          <span class="nav-label">下一课</span>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3l5 4-5 5"/></svg>
        </button>
        <div v-else class="nav-btn nav-next disabled">
          <span class="nav-label">下一课</span>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3l5 4-5 5"/></svg>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Loading ───────────────────────────────── */
.lesson-loading { padding: var(--space-4) 0; }

/* ── Breadcrumb ────────────────────────────── */
.breadcrumb-row {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: var(--space-4); margin-bottom: var(--space-4);
}

.breadcrumb {
  display: flex; align-items: center; gap: var(--space-2);
  flex-wrap: wrap; min-width: 0;
}

.breadcrumb-link {
  display: inline-flex; align-items: center; gap: 4px;
  background: none; border: none; padding: 2px 4px;
  color: var(--text-secondary); font-size: var(--text-sm); font-weight: 400;
  cursor: pointer; border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}
.breadcrumb-link:hover { color: var(--primary); }

.breadcrumb-sep { color: #c8ced9; font-size: var(--text-sm); }

.breadcrumb-current {
  font-size: var(--text-sm); color: var(--text);
  font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── Dropdown ──────────────────────────────── */
.dropdown-wrap { position: relative; flex-shrink: 0; }

.dropdown-trigger {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--text-xs); white-space: nowrap;
}

.dropdown-menu {
  position: absolute; right: 0; top: 100%; z-index: 50;
  margin-top: 4px; min-width: 280px; max-height: 420px; overflow-y: auto;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
  padding: var(--space-2);
}

.dropdown-group { margin-bottom: var(--space-1); }
.dropdown-chapter {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-secondary);
  padding: 6px 10px 4px; text-transform: uppercase; letter-spacing: 0.04em;
}

.dropdown-item {
  display: flex; align-items: center; gap: var(--space-2);
  padding: 7px 10px; border-radius: var(--radius-md);
  font-size: var(--text-sm); color: var(--text); cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.dropdown-item:hover { background: var(--surface-raised); }
.dropdown-item.active { background: var(--accent-light); color: var(--primary); font-weight: 500; }
.dropdown-item-icon { font-size: 12px; flex-shrink: 0; }

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: all var(--duration-fast) var(--ease-out);
}
.dropdown-fade-enter-from,
.dropdown-fade-leave-to { opacity: 0; transform: translateY(-4px); }

/* ── Divider ───────────────────────────────── */
.lesson-divider {
  border: none; border-top: 1px solid var(--border);
  margin: var(--space-5) 0;
}

/* ── Markdown content (Pythonista) ─────────── */
.lesson-content { line-height: 1.8; }

.lesson-content :deep(h1) {
  font-family: var(--font-display);
  font-size: var(--text-2xl); font-weight: 400;
  color: var(--ink); margin: 28px 0 12px; letter-spacing: -0.01em; line-height: 1.25;
}
.lesson-content :deep(h2) {
  font-family: var(--font-display);
  font-size: var(--text-xl); font-weight: 400;
  color: var(--ink); margin: 24px 0 10px; padding-top: var(--space-5);
  border-top: 1px solid var(--border); letter-spacing: -0.01em; line-height: 1.3;
}
.lesson-content :deep(h3) {
  font-size: var(--text-md); font-weight: 600;
  color: var(--ink); margin: 20px 0 8px; line-height: 1.4;
}
.lesson-content :deep(p) {
  margin: 10px 0; color: var(--text); font-size: var(--text-sm);
}
.lesson-content :deep(a) {
  color: var(--primary); text-decoration: none;
}
.lesson-content :deep(a:hover) { color: var(--accent-hover); text-decoration: underline; }

/* Inline code */
.lesson-content :deep(code:not(pre code)) {
  font-family: var(--font-mono); font-size: 0.85em;
  background: var(--surface-raised); color: var(--danger);
  padding: 1px 6px; border-radius: 3px;
}

/* Code block — Pythonista signature */
.lesson-content :deep(pre) {
  background: #1A1E2B; color: #D6DEEB;
  padding: var(--space-4); border-radius: var(--radius-md);
  overflow-x: auto; border: 1px solid #2A3040;
  margin: 14px 0; line-height: 1.7;
}
.lesson-content :deep(pre code) {
  font-family: var(--font-mono); font-size: 13px;
  background: none; color: inherit; padding: 0;
}

/* Tables */
.lesson-content :deep(table) {
  width: 100%; border-collapse: collapse; margin: 12px 0;
  font-size: var(--text-sm);
}
.lesson-content :deep(th) {
  text-align: left; padding: 8px 12px; border-bottom: 2px solid var(--border);
  font-size: var(--text-xs); font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-secondary); background: var(--surface-raised);
}
.lesson-content :deep(td) {
  padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text);
}

/* Blockquote — warm yellow callout */
.lesson-content :deep(blockquote) {
  background: var(--warning-light); border-left: 3px solid var(--warning);
  padding: var(--space-3) var(--space-4); margin: 12px 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: var(--text-sm); color: #7C5E0A; line-height: 1.65;
}
.lesson-content :deep(blockquote p) { margin: 4px 0; color: inherit; }

/* Images */
.lesson-content :deep(img) {
  max-width: 100%; border-radius: var(--radius-md);
  margin: var(--space-3) 0;
}

/* Lists */
.lesson-content :deep(ul), .lesson-content :deep(ol) {
  margin: 8px 0; padding-left: var(--space-6);
  font-size: var(--text-sm); color: var(--text);
}
.lesson-content :deep(li) { margin: 4px 0; }

/* ── Video mode ────────────────────────────── */
.lesson-video { margin: var(--space-6) 0; }
.video-wrapper {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); overflow: hidden;
}
.video-placeholder {
  text-align: center; padding: var(--space-12) var(--space-6);
  display: flex; flex-direction: column; align-items: center;
}

/* ── Notebook mode ─────────────────────────── */
.lesson-notebook { margin: var(--space-6) 0; }
.notebook-card {
  text-align: center; padding: var(--space-10) var(--space-6);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); display: flex;
  flex-direction: column; align-items: center; gap: var(--space-2);
}
.notebook-card h3 {
  font-family: var(--font-display); font-size: var(--text-xl);
  font-weight: 400; color: var(--ink); margin: 0; letter-spacing: -0.01em;
}

/* ── Bottom navigation ─────────────────────── */
.lesson-nav {
  display: flex; justify-content: space-between; align-items: stretch;
  gap: var(--space-4); margin-bottom: var(--space-4);
}

.nav-btn {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-4); border: 1px solid var(--border);
  border-radius: var(--radius-md); background: var(--surface);
  cursor: pointer; transition: all var(--duration-fast) var(--ease-out);
  flex: 1; max-width: 48%; color: var(--text); text-align: left;
}
.nav-btn:hover {
  border-color: var(--primary); background: var(--surface-raised);
}
.nav-btn.disabled {
  opacity: 0.35; cursor: not-allowed; pointer-events: none;
}

.nav-prev { justify-content: flex-start; }
.nav-next { justify-content: flex-end; }

.nav-label {
  font-size: var(--text-xs); color: var(--text-secondary);
  font-weight: 500; white-space: nowrap;
}

.nav-title {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--text); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}

/* ── Empty state ───────────────────────────── */
.empty-state {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state p { font-size: var(--text-sm); margin-bottom: var(--space-3); }

/* ── Responsive ────────────────────────────── */
@media (max-width: 768px) {
  .breadcrumb-row { flex-direction: column; }
  .dropdown-menu { left: 0; right: auto; min-width: auto; width: 100%; }
  .lesson-nav { flex-direction: column; }
  .nav-btn { max-width: 100%; }
  .nav-title { display: none; }
}
</style>
