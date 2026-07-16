<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const assignments = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ title: '', description: '', course_id: '', due_at: '' })

async function fetch() {
  loading.value = true
  try { const res = await assignmentsAPI.list(); assignments.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.title) return
  try {
    await assignmentsAPI.create({ ...form.value, course_id: parseInt(form.value.course_id) || undefined })
    app.showToast('创建成功', 'success')
    showCreate.value = false
    fetch()
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}

async function handlePublish(a) {
  try { await assignmentsAPI.publish(a.id); app.showToast('已发布', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="assignment-manage">
      <div class="flex-between mb-4">
        <h1 class="page-title" style="margin-bottom:0">作业管理</h1>
        <button class="btn-primary" @click="showCreate = !showCreate">
          {{ showCreate ? '取消' : '布置作业' }}
        </button>
      </div>

      <div v-if="showCreate" class="card mb-4 create-form">
        <div class="form-group"><label>作业名称</label><input v-model="form.title" placeholder="输入作业名称" /></div>
        <div class="form-group"><label>描述</label><textarea v-model="form.description" rows="2" placeholder="作业描述（可选）"></textarea></div>
        <div class="grid-2">
          <div class="form-group"><label>课程 ID</label><input v-model="form.course_id" type="number" placeholder="课程 ID" /></div>
          <div class="form-group"><label>截止时间</label><input v-model="form.due_at" type="datetime-local" /></div>
        </div>
        <button class="btn-primary" @click="handleCreate">确认创建</button>
      </div>

      <div v-if="loading" class="loading-text">加载中...</div>
      <table v-else-if="assignments.length" class="data-table">
        <thead><tr><th>名称</th><th>状态</th><th>截止</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="a in assignments" :key="a.id">
            <td class="title-cell">{{ a.title }}</td>
            <td><span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">{{ statusBadge(PUBLISH_STATUS_MAP, a.status).label }}</span></td>
            <td class="text-sm date-cell">{{ formatDateTime(a.due_at) }}</td>
            <td class="actions-cell">
              <button class="btn-ghost btn-sm" @click="router.push(`/teacher/assignments/${a.id}/edit`)">编辑题目</button>
              <button v-if="a.status==='draft'" class="btn-ghost btn-sm btn-publish" style="margin-left:6px" @click="handlePublish(a)">发布</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="card empty-card">
        <p class="empty-text">暂无作业</p>
        <p class="empty-hint">点击「布置作业」创建第一个作业</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Loading ── */
.loading-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

/* ── Empty state ── */
.empty-card {
  text-align: center;
  padding: 48px;
}
.empty-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.empty-hint {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  margin-top: 6px;
  opacity: 0.7;
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

th, td {
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}

th {
  font-weight: 600;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  background: var(--surface-raised);
}

tr:last-child td {
  border-bottom: none;
}

tr:hover td {
  background: var(--surface-raised);
}

.title-cell {
  font-weight: 500;
  color: var(--ink);
}

.date-cell {
  color: var(--text-secondary);
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
