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
  color: var(--ink);
}

/* ── Loading ───────────────────────────────────────────────────────── */
.loading-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

/* ── Cards ─────────────────────────────────────────────────────────── */
.course-list-page .card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
  box-shadow: none;
}

.course-list-page .card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  border-color: var(--border);
}

.course-list-page .card.course-card {
  cursor: pointer;
}

.course-list-page .card.course-card:hover {
  border-color: var(--accent);
  box-shadow: 0 0 20px rgba(224, 85, 61, 0.15),
              0 4px 12px rgba(0, 0, 0, 0.06);
}

/* Empty state card */
.empty-card {
  text-align: center;
  padding: 48px;
}

/* ── Course title link (Prussian blue) ──────────────────────────────── */
.course-title {
  margin: 0;
  font-size: 16px;
  cursor: pointer;
  color: var(--primary);
  font-weight: 500;
  transition: color var(--duration-fast) var(--ease-out);
}

.course-title:hover {
  color: var(--accent-hover);
}

/* ── Text overrides ────────────────────────────────────────────────── */
.course-list-page .text-secondary {
  color: var(--text-secondary);
}

/* ── Badges (light theme from global CSS) ──────────────────────────── */

/* ── "选课" button (accent orange CTA) ──────────────────────────────── */
.course-list-page .btn-primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
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
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}

.pagination button:hover:not(:disabled) {
  background: var(--surface-raised);
  border-color: var(--border);
}

.pagination button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.pagination button:active:not(:disabled) {
  transform: scale(0.985);
}
</style>
