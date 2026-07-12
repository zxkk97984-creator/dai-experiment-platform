<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const course = ref(null)
const chapters = ref([])
const loading = ref(true)

async function fetch() {
  loading.value = true
  try {
    const [cRes, chRes] = await Promise.all([
      coursesAPI.get(route.params.id),
      coursesAPI.getChapters(route.params.id),
    ])
    course.value = cRes.data
    chapters.value = chRes.data
  } catch (e) {
    app.showToast('加载课程失败', 'error')
  } finally { loading.value = false }
}

function goLesson(lesson) {
  router.push(`/student/courses/${route.params.id}/lessons/${lesson.id}`)
}

onMounted(fetch)
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
        <h3 style="font-size:15px;margin-bottom:12px;color:#111827">
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
  border-radius: 6px; cursor: pointer; transition: background 0.1s;
}
.lesson-item:hover { background: #f9fafb; }
</style>
