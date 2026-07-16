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

      <table v-else class="data-table">
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
              <button class="btn-ghost btn-sm" @click="router.push(`/teacher/courses/${c.id}/manage`)">章节课时</button>
              <button v-if="c.status === 'draft'" class="btn-ghost btn-sm btn-publish" @click="handlePublish(c)">发布</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Create form ── */
.create-form .form-group label {
  color: var(--text-secondary);
}

.create-form input,
.create-form textarea {
  background: var(--surface);
  border-color: var(--border);
  color: var(--ink);
}
.create-form input::placeholder,
.create-form textarea::placeholder {
  color: #a8b0be;
}
.create-form input:focus,
.create-form textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--accent-light);
  outline: none;
}

/* ── Loading skeleton ── */
.loading-card {
  padding: 0;
  overflow: hidden;
}
.skeleton-row {
  display: flex;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child {
  border-bottom: none;
}
.skeleton-cell {
  height: 16px;
  border-radius: 4px;
}

/* ── Empty state ── */
.empty-card {
  text-align: center;
  padding: 48px;
}
.empty-text {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

/* ── Data table ── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.data-table th {
  background: var(--surface-raised);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--ink);
}

.course-row:hover td {
  background: var(--surface-raised);
}
.course-row:last-child td {
  border-bottom: none;
}

/* ── Course link ── */
.course-link {
  color: var(--primary);
  cursor: pointer;
  font-weight: 500;
  transition: color 120ms ease;
}
.course-link:hover {
  color: var(--accent-hover);
}

/* ── Action buttons ── */
.actions-cell {
  display: flex;
  gap: 8px;
}

.btn-publish {
  color: var(--accent);
  border-color: rgba(224, 85, 61, 0.3);
}
.btn-publish:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
</style>
