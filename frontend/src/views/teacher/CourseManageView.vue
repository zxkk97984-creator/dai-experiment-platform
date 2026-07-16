<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ title: '', description: '' })
const creating = ref(false)

async function fetch() {
  loading.value = true
  try { const res = await coursesAPI.list(); courses.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.title) return
  creating.value = true
  try {
    await coursesAPI.create(form.value)
    app.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { title: '', description: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  } finally { creating.value = false }
}

async function handlePublish(c) {
  try { await coursesAPI.update(c.id, { status: 'published' }); app.showToast('已发布', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="course-manage-page">
      <div class="flex-between mb-4">
        <h1 class="page-title" style="margin-bottom:0">课程管理</h1>
        <button class="btn-primary" @click="showCreate = !showCreate">
          {{ showCreate ? '取消' : '创建课程' }}
        </button>
      </div>

      <div v-if="showCreate" class="card create-form mb-4">
        <div class="form-group">
          <label>课程名称</label>
          <input v-model="form.title" placeholder="输入课程名称" />
        </div>
        <div class="form-group">
          <label>课程简介</label>
          <textarea v-model="form.description" rows="3" placeholder="输入课程简介"></textarea>
        </div>
        <button class="btn-primary" :disabled="creating" @click="handleCreate">
          {{ creating ? '创建中...' : '确认创建' }}
        </button>
      </div>

      <div v-if="loading" class="card loading-card">
        <div class="skeleton-row" v-for="i in 3" :key="i">
          <div class="skeleton skeleton-cell" style="width:40%" />
          <div class="skeleton skeleton-cell" style="width:15%" />
          <div class="skeleton skeleton-cell" style="width:30%" />
        </div>
      </div>

      <div v-else-if="courses.length === 0" class="card empty-card">
        <p class="empty-text">暂无课程，点击上方按钮创建第一个课程</p>
      </div>

      <table v-else class="card course-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in courses" :key="c.id" class="course-row">
            <td>
              <a class="course-link" @click="router.push(`/teacher/courses/${c.id}/manage`)">{{ c.title }}</a>
            </td>
            <td>
              <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, c.status).color">
                {{ statusBadge(PUBLISH_STATUS_MAP, c.status).label }}
              </span>
            </td>
            <td class="actions-cell">
              <button class="btn-ghost-dark" @click="router.push(`/teacher/courses/${c.id}/manage`)">章节课时</button>
              <button v-if="c.status === 'draft'" class="btn-ghost-dark btn-publish" @click="handlePublish(c)">发布</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Pythonista Dark Admin — Course Management
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page wrapper ──────────────────────────────────────────────────── */
.course-manage-page {
  color: #D6DEEB;
}

.course-manage-page .page-title {
  color: #D6DEEB;
}

/* ── Cards ─────────────────────────────────────────────────────────── */
.course-manage-page .card {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #D6DEEB;
}
.course-manage-page .card:hover {
  border-color: #3A4050;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

/* ── Create form ───────────────────────────────────────────────────── */
.create-form .form-group label {
  color: #6A7086;
}

.create-form input,
.create-form textarea {
  background: #151821;
  border-color: #2A3040;
  color: #D6DEEB;
}
.create-form input::placeholder,
.create-form textarea::placeholder {
  color: #4A5066;
}
.create-form input:focus,
.create-form textarea:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.15);
  outline: none;
}

/* ── Loading skeleton ──────────────────────────────────────────────── */
.loading-card {
  padding: 0;
  overflow: hidden;
}
.skeleton-row {
  display: flex;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid #2A3040;
}
.skeleton-row:last-child {
  border-bottom: none;
}
.skeleton-cell {
  height: 16px;
  border-radius: 4px;
}
.course-manage-page .skeleton {
  background: linear-gradient(90deg, #1E2332 25%, #252B3A 50%, #1E2332 75%);
  background-size: 200% 100%;
  animation: shimmer-dark 1.5s infinite;
}
@keyframes shimmer-dark {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Empty state ───────────────────────────────────────────────────── */
.empty-card {
  text-align: center;
  padding: 48px;
}
.empty-text {
  color: #6A7086;
  font-size: 0.875rem;
}

/* ── Table ─────────────────────────────────────────────────────────── */
.course-table {
  padding: 0;
  overflow: hidden;
}

.course-table thead {
  background: #11141D;
}
.course-table th {
  background: #11141D;
  color: #6A7086;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 12px 16px;
  border-bottom: 1px solid #2A3040;
}

.course-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #2A3040;
  color: #D6DEEB;
}

.course-row:hover {
  background: rgba(224, 85, 61, 0.06);
}
.course-row:last-child td {
  border-bottom: none;
}

/* ── Course link ───────────────────────────────────────────────────── */
.course-link {
  color: #D6DEEB;
  cursor: pointer;
  font-weight: 500;
  transition: color 120ms ease;
}
.course-link:hover {
  color: #E0553D;
}

/* ── Action buttons (ghost on dark) ────────────────────────────────── */
.actions-cell {
  display: flex;
  gap: 8px;
}

.btn-ghost-dark {
  background: transparent;
  border: 1px solid #2A3040;
  color: #6A7086;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease,
              border-color 120ms ease,
              color 120ms ease;
}
.btn-ghost-dark:hover {
  background: rgba(224, 85, 61, 0.08);
  border-color: #E0553D;
  color: #E0553D;
}

.btn-ghost-dark.btn-publish {
  color: #E0553D;
  border-color: rgba(224, 85, 61, 0.3);
}
.btn-ghost-dark.btn-publish:hover {
  background: #E0553D;
  color: #fff;
  border-color: #E0553D;
}
</style>
