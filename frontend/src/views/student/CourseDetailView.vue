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

<template>
  <AppLayout>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <template v-else-if="course">
      <h1 class="page-title">{{ course.title }}</h1>
      <p class="text-secondary mb-4">{{ course.description || '暂无简介' }}</p>

      <div v-if="chapters.length === 0" class="card" style="text-align:center;padding:32px">
        <p class="text-secondary">暂无章节内容</p>
      </div>

      <div v-for="ch in chapters" :key="ch.id" class="card mb-4">
        <h3 style="font-size:15px;margin-bottom:12px;color:var(--ink)">
          第{{ ch.order_index + 1 }}章 {{ ch.title }}
        </h3>
        <div v-if="ch.lessons && ch.lessons.length">
          <div v-for="l in ch.lessons" :key="l.id"
            class="lesson-item" @click="goLesson(l)">
            <span class="badge badge-neutral text-sm">
              {{ l.content_type === 'markdown' ? '讲义' : l.content_type === 'video' ? '视频' : 'Notebook' }}
            </span>
            <span style="flex:1;margin-left:10px;cursor:pointer;color:var(--accent)">{{ l.title }}</span>
            <span class="text-sm text-secondary">&gt;</span>
          </div>
        </div>
        <p v-else class="text-sm text-secondary">暂无课时</p>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
.lesson-item {
  display: flex; align-items: center; padding: 8px 12px;
  border-radius: var(--radius-md); cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.lesson-item:hover { background: var(--surface-raised); }
</style>
