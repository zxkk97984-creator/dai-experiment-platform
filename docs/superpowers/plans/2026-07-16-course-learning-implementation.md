# 课程学习流前端实现计划 — 课程详情页 + 课时阅读页

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写学生端 CourseDetailView（课程门户）和 LessonView（课时阅读页），Pythonista 技术文档风格。

**Architecture:** 两个独立 Vue SFC 页面，各自用 AppLayout 包裹。CourseDetailView 聚合课程/章节/作业/考试四路数据；LessonView 根据 content_type 三模式渲染（markdown/video/notebook），顶部面包屑+下拉导航，底部前后课时切换。

**Tech Stack:** Vue 3 Composition API, Pinia (app store), axios (client), existing design tokens (style.css)

## Global Constraints

- 使用项目已有 CSS tokens（`--ink`, `--paper`, `--surface`, `--primary`, `--accent`, `--border`, `--font-display`, `--font-body`, `--font-mono` 等）
- 代码块暗色底 `#1A1E2B`，字体 `IBM Plex Mono`，13px
- 暖黄引用块使用 `--warning-light` (`#FDF0D5`) 底色 + `--warning` 左边框
- 进度条使用 `--accent` (`#E0553D`) 镉橙
- 课程标题使用 `DM Serif Display`
- 所有文案使用中文，不道歉（错误信息说发生了什么和怎么修）
- 保持与现有路由 `/student/courses/:id` 和 `/student/courses/:id/lessons/:lid` 兼容

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/views/student/CourseDetailView.vue` | 重写 | 课程门户：信息卡片 + 作业/考试入口 + 章节目录 |
| `frontend/src/views/student/LessonView.vue` | 重写 | 课时阅读：面包屑导航 + Markdown 渲染 + 视频/Notebook 模式 + 底部导航 |

---

### Task 1: 重写 CourseDetailView — 脚本与数据获取

**Files:**
- Modify: `frontend/src/views/student/CourseDetailView.vue` (script section)

**Interfaces:**
- Consumes: `coursesAPI.get(id)`, `coursesAPI.getChapters(id)`, `coursesAPI.enroll(id)`, `assignmentsAPI.list({course_id})`, `examsAPI.list({course_id})`
- Produces: reactive refs `course`, `chapters`, `assignments`, `exams`, `loading`, `enrolling`, `enrolled`

- [ ] **Step 1: 重写 script setup 部分**

替换现有 script 为完整的数据获取逻辑：

```javascript
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
    chapters.value = chRes.data
    assignments.value = (aRes.data.items || aRes.data || [])
    exams.value = (eRes.data.items || eRes.data || [])
    enrolled.value = true
  } catch (e) {
    if (e.response?.status === 403) enrolled.value = false
    else app.showToast('加载课程失败', 'error')
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
```

- [ ] **Step 2: 验证变量和函数签名**

检查确认：
- `courseId` computed 返回 `route.params.id`
- `totalLessons` 遍历所有章节的 lessons 数组累加
- `fetchAll` 并行请求 4 个 API
- `handleEnroll` 调用 enroll API 后重新拉数据
- 所有导航函数使用 router.push

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/student/CourseDetailView.vue
git commit -m "feat(CourseDetailView): rewrite data fetching with multi-API aggregation"
```

---

### Task 2: 重写 CourseDetailView — 模板与渲染

**Files:**
- Modify: `frontend/src/views/student/CourseDetailView.vue` (template section)

**Interfaces:**
- Consumes: All refs from Task 1 (`course`, `chapters`, `assignments`, `exams`, `loading`, `enrolling`, `enrolled`, `completedLessonIds`, `totalLessons`, `progressPercent`) and functions (`goLesson`, `goAssignment`, `goExam`, `goBack`, `handleEnroll`)

- [ ] **Step 1: 写完整模板**

替换现有 `<template>` 为：

```html
<template>
  <AppLayout>
    <!-- Loading state -->
    <div v-if="loading" class="course-loading">
      <div class="skeleton" style="height:28px;width:240px;margin-bottom:12px"></div>
      <div class="skeleton" style="height:14px;width:360px;margin-bottom:24px"></div>
      <div class="skeleton" style="height:120px;width:100%;margin-bottom:16px"></div>
      <div v-for="i in 3" :key="i" class="skeleton" style="height:48px;width:100%;margin-bottom:8px"></div>
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
            <span class="badge badge-neutral text-xs">{{ a.status }}</span>
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

      <!-- Empty chapters -->
      <div v-else class="empty-state">
        <p>教师正在准备课程内容...</p>
      </div>
    </template>
  </AppLayout>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/student/CourseDetailView.vue
git commit -m "feat(CourseDetailView): course portal template with info card, quick entries, chapter outline"
```

---

### Task 3: 重写 CourseDetailView — 样式

**Files:**
- Modify: `frontend/src/views/student/CourseDetailView.vue` (style section)

- [ ] **Step 1: 替换现有 `<style scoped>` 为完整样式**

```css
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/student/CourseDetailView.vue
git commit -m "style(CourseDetailView): Pythonista course portal styling — hero card, progress bar, chapter outline"
```

---

### Task 4: 重写 LessonView — 脚本与数据获取

**Files:**
- Modify: `frontend/src/views/student/LessonView.vue` (script + template + style — 全量重写)

- [ ] **Step 1: 重写 script — LessonView 完整脚本**

```javascript
<script setup>
import { ref, computed, onMounted, watch } from 'vue'
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
const currentChapterIndex = ref(0)

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
    currentChapterIndex.value = i
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

function closeDropdown() {
  dropdownOpen.value = false
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/student/LessonView.vue
git commit -m "feat(LessonView): rewrite data fetching, navigation logic, and progress tracking"
```

---

### Task 5: 重写 LessonView — 模板

**Files:**
- Modify: `frontend/src/views/student/LessonView.vue` (template section — 替换现有 template)

- [ ] **Step 1: 写 LessonView 完整模板**

```html
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/student/LessonView.vue
git commit -m "feat(LessonView): template with breadcrumb, dropdown, content modes, and bottom nav"
```

---

### Task 6: 重写 LessonView — 样式

**Files:**
- Modify: `frontend/src/views/student/LessonView.vue` (style section — 替换现有 `<style scoped>`)

- [ ] **Step 1: 写完整 Pythonista 样式**

```css
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/student/LessonView.vue
git commit -m "style(LessonView): Pythonista lesson styling — markdown rendering, code blocks, warm callouts, bottom nav"
```

---

### Task 7: 构建验证

**Files:**
- None (验证 only)

- [ ] **Step 1: 运行前端构建确认无编译错误**

```bash
cd frontend && npm run build
```

期望输出：`✓ built in ...`，无 error

- [ ] **Step 2: 提交（如有修改）**

```bash
git add -A
git commit -m "chore: build verification after CourseDetailView and LessonView rewrite"
```

---

## Self-Review 检查清单

| 检查项 | 状态 |
|--------|------|
| Spec 覆盖：课程信息卡片 | ✅ Task 2 (hero card template) + Task 3 (hero styles) |
| Spec 覆盖：作业/考试快捷入口 | ✅ Task 2 (quick sections) + Task 3 (quick-section styles) |
| Spec 覆盖：章节目录 | ✅ Task 2 (chapter outline) + Task 3 (chapter-card styles) |
| Spec 覆盖：面包屑导航 | ✅ Task 5 (breadcrumb template) + Task 6 (breadcrumb styles) |
| Spec 覆盖：Markdown 渲染 | ✅ Task 5 (v-html) + Task 6 (:deep() styles) |
| Spec 覆盖：视频/Notebook 模式 | ✅ Task 5 (video/notebook sections) + Task 6 (video/notebook styles) |
| Spec 覆盖：底部前后导航 | ✅ Task 5 (lesson-nav) + Task 6 (nav-btn styles) |
| Spec 覆盖：章节下拉选单 | ✅ Task 5 (dropdown-menu) + Task 6 (dropdown styles) |
| Spec 覆盖：加载/空/错误状态 | ✅ Task 2 + Task 5 (loading, empty-state, 条件渲染) |
| Spec 覆盖：进度条 | ✅ Task 2 (progress bar template) + Task 3 (progress-bar styles) |
| Spec 覆盖：Pythonista 暗色代码块 | ✅ Task 6 (pre code 样式 #1A1E2B) |
| Spec 覆盖：暖黄引用块 | ✅ Task 6 (blockquote 样式) |
| 无 TBD/TODO | ✅ |
| 接口一致性 | ✅ lessonId computed, flatLessons computed, goLesson(id) 签名一致 |
