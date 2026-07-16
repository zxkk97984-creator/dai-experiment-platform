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
    <div class="course-list-page">
      <h1 class="page-title">课程列表</h1>

      <div v-if="loading" class="loading-text">加载中...</div>

      <div v-else-if="courses.length === 0" class="card empty-card">
        <p class="text-secondary">暂无可选课程</p>
      </div>

      <div v-else class="grid-3">
        <div v-for="c in courses" :key="c.id" class="card course-card" @click="goDetail(c.id)">
          <div class="flex-between mb-3">
            <h3 class="course-title" @click.stop="goDetail(c.id)">{{ c.title }}</h3>
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

      <div v-if="total > 20" class="pagination">
        <button :disabled="page <= 1" @click="page--; fetchCourses()">上一页</button>
        <span class="text-sm text-secondary mx-2">第 {{ page }} 页 / 共 {{ Math.ceil(total/20) }} 页</span>
        <button :disabled="page >= Math.ceil(total/20)" @click="page++; fetchCourses()">下一页</button>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Page wrapper ──────────────────────────────────────────────────── */
.course-list-page {
  min-height: 100%;
}

/* ── Page title override ───────────────────────────────────────────── */
.course-list-page :deep(.page-title) {
  color: #D6DEEB;
}

/* ── Loading ───────────────────────────────────────────────────────── */
.loading-text {
  color: #6A7086;
  font-size: var(--text-sm);
}

/* ── Cards ─────────────────────────────────────────────────────────── */
.course-list-page .card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
  box-shadow: none;
}

.course-list-page .card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  border-color: #2A3040;
}

.course-list-page .card.course-card {
  cursor: pointer;
}

.course-list-page .card.course-card:hover {
  border-color: #E0553D;
}

/* Empty state card */
.empty-card {
  text-align: center;
  padding: 48px;
}

/* ── Course title link ─────────────────────────────────────────────── */
.course-title {
  margin: 0;
  font-size: 16px;
  cursor: pointer;
  color: #E0553D;
  font-weight: 500;
  transition: color var(--duration-fast) var(--ease-out);
}

.course-title:hover {
  color: #F07060;
}

/* ── Text overrides ────────────────────────────────────────────────── */
.course-list-page .text-secondary {
  color: #6A7086;
}

/* ── Badges (dark-background adapted) ──────────────────────────────── */
.course-list-page .badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
}

.course-list-page .badge-success {
  background: rgba(15, 123, 94, 0.18);
  color: #3DD68C;
}

.course-list-page .badge-warning {
  background: rgba(181, 118, 14, 0.18);
  color: #F5C842;
}

.course-list-page .badge-neutral {
  background: rgba(106, 112, 134, 0.18);
  color: #8B95A8;
}

.course-list-page .badge-info {
  background: rgba(88, 102, 196, 0.18);
  color: #98A0F0;
}

.course-list-page .badge-danger {
  background: rgba(209, 46, 62, 0.18);
  color: #F07080;
}

/* ── "选课" button ────────────────────────────────────────────────── */
.course-list-page .btn-primary {
  background: #E0553D;
  color: #fff;
  border-color: #E0553D;
  font-weight: 500;
}

.course-list-page .btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}

/* ── Pagination ────────────────────────────────────────────────────── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: var(--space-4);
}

.pagination button {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  color: #D6DEEB;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}

.pagination button:hover:not(:disabled) {
  background: #252A3A;
  border-color: #3A4050;
}

.pagination button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.pagination button:active:not(:disabled) {
  transform: scale(0.985);
}
</style>
