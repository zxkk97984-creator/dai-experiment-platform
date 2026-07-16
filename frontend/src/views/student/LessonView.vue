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
.lesson-content { line-height: 1.8; }
.lesson-content :deep(h1), .lesson-content :deep(h2), .lesson-content :deep(h3) {
  margin: 20px 0 8px;
  font-family: var(--font-display);
  font-weight: 400;
  letter-spacing: -0.01em;
}
.lesson-content :deep(h1) { font-size: var(--text-2xl); }
.lesson-content :deep(h2) { font-size: var(--text-xl); }
.lesson-content :deep(p) { margin: 8px 0; }
.lesson-content :deep(pre) {
  background: #1B1F2B; color: #D6DEEB;
  padding: var(--space-4); border-radius: var(--radius-md);
  overflow-x: auto; border: 1px solid #2A3040;
  line-height: 1.6;
}
.lesson-content :deep(code) { font-family: var(--font-mono); font-size: var(--text-sm); }
.lesson-content :deep(code:not(pre code)) {
  background: var(--surface-raised); color: var(--danger);
  padding: 1px 6px; border-radius: 3px;
  font-size: 0.82em;
}
</style>
