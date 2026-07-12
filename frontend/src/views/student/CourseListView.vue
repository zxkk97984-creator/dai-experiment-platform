<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'
import { formatDate } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const loading = ref(true)
const total = ref(0)
const page = ref(1)

async function fetchCourses() {
  loading.value = true
  try {
    const res = await coursesAPI.list({ page: page.value, page_size: 20 })
    courses.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    app.showToast('加载课程列表失败', 'error')
  } finally { loading.value = false }
}

async function handleEnroll(course) {
  try {
    await coursesAPI.enroll(course.id)
    app.showToast('选课成功', 'success')
    fetchCourses()
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '选课失败'
    app.showToast(msg, 'error')
  }
}

function goDetail(id) { router.push(`/student/courses/${id}`) }

onMounted(fetchCourses)
</script>

<template>
  <AppLayout>
    <h1 class="page-title">课程列表</h1>

    <div v-if="loading" class="text-secondary">加载中...</div>

    <div v-else-if="courses.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无可选课程</p>
    </div>

    <div v-else class="grid-3">
      <div v-for="c in courses" :key="c.id" class="card course-card" @click="goDetail(c.id)">
        <div class="flex-between mb-3">
          <h3 style="margin:0;font-size:16px;cursor:pointer;color:var(--accent)">{{ c.title }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, c.status).color">
            {{ statusBadge(PUBLISH_STATUS_MAP, c.status).label }}
          </span>
        </div>
        <p class="text-secondary text-sm mb-4">{{ c.description || '暂无简介' }}</p>
        <div class="flex-between">
          <span class="text-sm text-secondary">{{ formatDate(c.created_at) }}</span>
          <button class="btn-sm btn-primary" @click.stop="handleEnroll(c)">选课</button>
        </div>
      </div>
    </div>

    <div v-if="total > 20" class="flex-center mt-4" style="justify-content:center">
      <button :disabled="page <= 1" @click="page--; fetchCourses()">上一页</button>
      <span class="text-sm text-secondary mx-2">第 {{ page }} 页 / 共 {{ Math.ceil(total/20) }} 页</span>
      <button :disabled="page >= Math.ceil(total/20)" @click="page++; fetchCourses()">下一页</button>
    </div>
  </AppLayout>
</template>

<style scoped>
.course-card { cursor: pointer; transition: border-color 0.15s; }
.course-card:hover { border-color: var(--accent); }
</style>
