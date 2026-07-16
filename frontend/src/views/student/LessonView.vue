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
    <div v-if="loading" class="text-secondary">加载中...</div>
    <template v-else-if="lesson">
      <h1 class="page-title">{{ lesson.title }}</h1>
      <div class="card">
        <div v-if="lesson.content_type === 'markdown'" class="lesson-content"
          v-html="lesson.content || '暂无内容'"></div>
        <div v-else-if="lesson.content_type === 'video'">
          <p class="text-secondary mb-4">视频课时</p>
          <a v-if="lesson.video_url" :href="lesson.video_url" target="_blank"
            class="btn-primary" style="display:inline-block;padding:8px 16px;text-decoration:none;">打开视频</a>
        </div>
        <div v-else>
          <p class="text-secondary">{{ lesson.content || '暂无内容' }}</p>
        </div>
      </div>
    </template>
    <div v-else class="card" style="text-align:center;padding:32px">
      <p class="text-secondary">课时不存在</p>
    </div>
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
