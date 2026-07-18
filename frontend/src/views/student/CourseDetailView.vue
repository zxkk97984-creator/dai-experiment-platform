<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { assignmentsAPI } from '../../api/assignments.js'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const course = ref(null)
const chapters = ref([])
const assignments = ref([])
const exams = ref([])
const loading = ref(true)
const enrolling = ref(false)
const enrolled = ref(false)
const fetchError = ref(false)

const courseId = computed(() => route.params.id)

const completedLessonIds = computed(() => {
  // 从 localStorage 读取已完成的课时 ID 集合
  try {
    const raw = localStorage.getItem(`course_${courseId.value}_completed`)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
})

const totalLessons = computed(() => {
  let count = 0
  for (const ch of chapters.value) {
    if (ch.lessons) count += ch.lessons.length
  }
  return count
})

const progressPercent = computed(() => {
  if (totalLessons.value === 0) return 0
  return Math.round((completedLessonIds.value.length / totalLessons.value) * 100)
})

async function fetchAll() {
  loading.value = true
  try {
    const [cRes, chRes, aRes, eRes] = await Promise.all([
      coursesAPI.get(courseId.value),
      coursesAPI.getChapters(courseId.value),
      assignmentsAPI.list({ course_id: courseId.value }),
      examsAPI.list({ course_id: courseId.value }),
    ])
    course.value = cRes.data
    chapters.value = chRes.data.items || chRes.data || []
    assignments.value = (aRes.data.items || aRes.data || [])
    exams.value = (eRes.data.items || eRes.data || [])
    enrolled.value = true
  } catch (e) {
    if (e.response?.status === 403) enrolled.value = false
    else { fetchError.value = true; app.showToast('加载课程失败', 'error') }
  } finally { loading.value = false }
}

async function handleEnroll() {
  enrolling.value = true
  try {
    await coursesAPI.enroll(courseId.value)
    app.showToast('选课成功', 'success')
    enrolled.value = true
    await fetchAll()
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '选课失败'
    app.showToast(msg, 'error')
  } finally { enrolling.value = false }
}

function goLesson(lesson) {
  router.push(`/student/courses/${courseId.value}/lessons/${lesson.id}`)
}

function goAssignment(id) {
  router.push(`/student/assignments/${id}`)
}

function goExam(id) {
  router.push(`/student/exams/${id}`)
}

function goBack() {
  router.push('/student/courses')
}

onMounted(fetchAll)
</script>

<template>
  <AppLayout>
    <!-- Loading state -->
    <div v-if="loading" class="course-loading">
      <div class="skeleton" style="height:28px;width:240px;margin-bottom:12px"></div>
      <div class="skeleton" style="height:14px;width:360px;margin-bottom:24px"></div>
      <div class="skeleton" style="height:120px;width:100%;margin-bottom:16px"></div>
      <div v-for="i in 3" :key="i" class="skeleton" style="height:48px;width:100%;margin-bottom:8px"></div>
    </div>

    <!-- Error: fetch failed -->
    <div v-else-if="fetchError" class="empty-state">
      <p>加载课程失败</p>
      <button class="btn-primary" @click="fetchAll" style="margin-top:12px">重新加载</button>
    </div>

    <!-- Error: not enrolled -->
    <div v-else-if="!course && !enrolled" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
        <rect x="4" y="8" width="40" height="32" rx="4"/>
        <path d="M16 22h16M16 28h12"/>
      </svg>
      <p>你还未选这门课</p>
      <button class="btn-primary" :disabled="enrolling" @click="handleEnroll" style="margin-top:12px">
        {{ enrolling ? '选课中...' : '立即选课' }}
      </button>
    </div>

    <!-- Error: course not found -->
    <div v-else-if="!course" class="empty-state">
      <p>课程不存在</p>
      <button class="btn-primary" @click="goBack" style="margin-top:12px">返回课程列表</button>
    </div>

    <!-- Course portal -->
    <template v-else>
      <!-- Back -->
      <button class="btn-ghost btn-sm back-link" @click="goBack">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3L5 8l5 5"/></svg>
        返回课程列表
      </button>

      <!-- Info card -->
      <div class="course-hero">
        <h1 class="course-hero-title">{{ course.title }}</h1>
        <p class="course-hero-desc" v-if="course.description">{{ course.description }}</p>
        <div class="course-hero-stats">
          <div class="hero-stat">
            <span class="hero-stat-value">{{ chapters.length }}</span>
            <span class="hero-stat-label">章节</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-value">{{ totalLessons }}</span>
            <span class="hero-stat-label">课时</span>
          </div>
        </div>
        <!-- Progress bar -->
        <div class="progress-wrap" v-if="totalLessons > 0">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <span class="progress-text">{{ progressPercent }}% 完成</span>
        </div>
      </div>

      <!-- Assignments quick entry -->
      <div class="quick-section" v-if="assignments.length > 0">
        <h2 class="quick-section-title">作业</h2>
        <div class="quick-list">
          <div v-for="a in assignments" :key="a.id" class="quick-item" @click="goAssignment(a.id)">
            <span class="quick-item-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h7l4 4v7H2V3z"/><path d="M9 3v4h4"/></svg>
            </span>
            <span class="quick-item-title">{{ a.title }}</span>
          </div>
        </div>
      </div>

      <!-- Exams quick entry -->
      <div class="quick-section" v-if="exams.length > 0">
        <h2 class="quick-section-title">考试</h2>
        <div class="quick-list">
          <div v-for="e in exams" :key="e.id" class="quick-item" @click="goExam(e.id)">
            <span class="quick-item-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="12" height="12" rx="2"/><path d="M5 7l2 2 4-4"/></svg>
            </span>
            <span class="quick-item-title">{{ e.title }}</span>
            <span class="quick-item-meta" v-if="e.duration_minutes">{{ e.duration_minutes }} 分钟</span>
          </div>
        </div>
      </div>

      <!-- Chapter outline -->
      <div class="chapter-outline" v-if="chapters.length > 0">
        <div v-for="ch in chapters" :key="ch.id" class="chapter-card">
          <h3 class="chapter-title">第{{ ch.order_index + 1 }}章  {{ ch.title }}</h3>
          <div v-if="ch.lessons && ch.lessons.length" class="lesson-list">
            <div v-for="l in ch.lessons" :key="l.id" class="lesson-item" @click="goLesson(l)">
              <span class="lesson-type-icon">
                <template v-if="l.content_type === 'markdown'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h10v8H2z"/><path d="M4 6h6M4 9h4"/></svg>
                </template>
                <template v-else-if="l.content_type === 'video'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="7" r="5"/><path d="M6 5v4l3-2z"/></svg>
                </template>
                <template v-else>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="10" height="10" rx="1"/><path d="M5 6h4M5 9h2"/></svg>
                </template>
              </span>
              <span class="lesson-title">{{ l.title }}</span>
              <span v-if="completedLessonIds.includes(l.id)" class="lesson-check">✓</span>
            </div>
          </div>
          <p v-else class="lesson-empty">暂无课时</p>
        </div>
      </div>

    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Back link ─────────────────────────────── */
.back-link {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-5);
}
.back-link:hover { color: var(--text); }

/* ── Hero card ─────────────────────────────── */
.course-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  margin-bottom: var(--space-5);
  transition: border-color var(--duration-normal) var(--ease-out);
}
.course-hero:hover { border-color: #cfd5e0; }

.course-hero-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: var(--ink);
  letter-spacing: -0.01em;
  margin: 0 0 var(--space-2);
  line-height: 1.2;
}

.course-hero-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--space-5);
  line-height: 1.6;
}

.course-hero-stats { display: flex; gap: var(--space-6); margin-bottom: var(--space-4); }
.hero-stat { display: flex; flex-direction: column; }
.hero-stat-value { font-family: var(--font-display); font-size: 22px; color: var(--ink); }
.hero-stat-label { font-size: var(--text-xs); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }

/* Progress bar */
.progress-wrap { display: flex; align-items: center; gap: var(--space-3); }
.progress-bar {
  flex: 1; height: 6px; background: #E4E8F0;
  border-radius: 3px; overflow: hidden;
}
.progress-fill {
  height: 100%; background: var(--accent);
  border-radius: 3px; transition: width var(--duration-slow) var(--ease-out);
}
.progress-text {
  font-size: var(--text-xs); color: var(--text-secondary);
  white-space: nowrap; font-weight: 500;
}

/* ── Quick sections (assignments & exams) ─── */
.quick-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6);
  margin-bottom: var(--space-4);
  transition: border-color var(--duration-normal) var(--ease-out);
}
.quick-section:hover { border-color: #cfd5e0; }

.quick-section-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 400;
  color: var(--ink);
  margin: 0 0 var(--space-3);
  letter-spacing: -0.01em;
}

.quick-list { display: flex; flex-direction: column; gap: 2px; }
.quick-item {
  display: flex; align-items: center; gap: var(--space-3);
  padding: 8px 10px; border-radius: var(--radius-md);
  cursor: pointer; transition: background var(--duration-fast) var(--ease-out);
}
.quick-item:hover { background: var(--surface-raised); }

.quick-item-icon { color: var(--text-secondary); flex-shrink: 0; display: flex; }
.quick-item-title { flex: 1; font-size: var(--text-sm); font-weight: 500; color: var(--text); }
.quick-item-meta { font-size: var(--text-xs); color: var(--text-secondary); }

/* ── Chapter outline ───────────────────────── */
.chapter-outline { display: flex; flex-direction: column; gap: var(--space-4); }
.chapter-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6);
  transition: border-color var(--duration-normal) var(--ease-out);
}
.chapter-card:hover { border-color: #cfd5e0; }

.chapter-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 var(--space-3);
  letter-spacing: 0.01em;
}

.lesson-list { display: flex; flex-direction: column; gap: 2px; }
.lesson-item {
  display: flex; align-items: center; gap: var(--space-2);
  padding: 7px 10px; border-radius: var(--radius-md);
  cursor: pointer; transition: background var(--duration-fast) var(--ease-out);
}
.lesson-item:hover { background: var(--surface-raised); }

.lesson-type-icon { color: var(--text-secondary); flex-shrink: 0; display: flex; }
.lesson-title { flex: 1; font-size: var(--text-sm); color: var(--text); }
.lesson-check { color: var(--success); font-size: var(--text-xs); font-weight: 600; }
.lesson-empty { font-size: var(--text-xs); color: var(--text-secondary); padding: var(--space-2) 0; margin: 0; }

/* ── Loading ───────────────────────────────── */
.course-loading { padding: var(--space-2) 0; }

/* ── Empty state ───────────────────────────── */
.empty-state {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state p { font-size: var(--text-sm); margin-bottom: var(--space-3); }
</style>
