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
              <button class="btn-sm btn-action" @click="router.push(`/teacher/assignments/${a.id}/edit`)">编辑题目</button>
              <button v-if="a.status==='draft'" class="btn-sm btn-publish" style="margin-left:6px" @click="handlePublish(a)">发布</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-card">
        <p class="empty-text">暂无作业</p>
        <p class="empty-hint">点击「布置作业」创建第一个作业</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   Pythonista Dark Admin — Assignment Management
   ═══════════════════════════════════════════════════════════ */

.assignment-manage {
  color: #D6DEEB;
}

/* ── Page title ─────────────────────────────────────────── */
.page-title {
  color: #D6DEEB;
}

/* ── Loading ────────────────────────────────────────────── */
.loading-text {
  color: #6A7086;
  font-size: var(--text-sm);
}

/* ── Cards ──────────────────────────────────────────────── */
.card,
.empty-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}
.card:hover,
.empty-card:hover {
  box-shadow: none;
  border-color: #2A3040;
}

.empty-card {
  text-align: center;
  padding: 48px;
}
.empty-text {
  color: #6A7086;
  font-size: var(--text-sm);
}
.empty-hint {
  color: #4A5066;
  font-size: var(--text-xs);
  margin-top: 6px;
}

/* ── Create form card ───────────────────────────────────── */
.create-form {
  /* inherits .card */
}

/* ── Form labels ────────────────────────────────────────── */
.form-group label {
  color: #6A7086;
}

/* ── Inputs ─────────────────────────────────────────────── */
input,
textarea,
select {
  background: #151821;
  border-color: #2A3040;
  color: #D6DEEB;
}
input::placeholder,
textarea::placeholder {
  color: #4A5066;
}
input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.18);
}

/* ── Secondary text ─────────────────────────────────────── */
.text-secondary {
  color: #6A7086;
}

/* ── Buttons: base override for dark bg ─────────────────── */
button {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #8A90A8;
}
button:hover {
  background: #222738;
  border-color: #3A4050;
}

/* Primary buttons keep their accent styling */
button.btn-primary {
  background: #E0553D;
  color: #fff;
  border-color: #E0553D;
}
button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}

/* ── Small action buttons ───────────────────────────────── */
button.btn-sm {
  padding: 4px 10px;
  font-size: var(--text-xs);
  border-radius: var(--radius-sm);
}

.btn-action {
  background: transparent;
  border-color: #2A3040;
  color: #8A90A8;
}
.btn-action:hover {
  background: rgba(224, 85, 61, 0.08);
  border-color: #E0553D;
  color: #E0553D;
}

.btn-publish {
  background: rgba(224, 85, 61, 0.12);
  border-color: #E0553D;
  color: #E0553D;
}
.btn-publish:hover {
  background: #E0553D;
  color: #fff;
}

/* ── Data table ─────────────────────────────────────────── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  overflow: hidden;
}

th,
td {
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid #2A3040;
}

th {
  font-weight: 600;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6A7086;
  background: #11141D;
}

tr:last-child td {
  border-bottom: none;
}

tr:hover td {
  background: rgba(224, 85, 61, 0.04);
}

.title-cell {
  font-weight: 500;
  color: #D6DEEB;
}

.date-cell {
  color: #8A90A8;
}

/* ── Badges on dark background ──────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
}

.badge-success {
  background: rgba(15, 123, 94, 0.15);
  color: #3EC99E;
}

.badge-warning {
  background: rgba(181, 118, 14, 0.15);
  color: #E5A820;
}

.badge-danger {
  background: rgba(209, 46, 62, 0.15);
  color: #F05060;
}

.badge-info {
  background: rgba(88, 102, 196, 0.15);
  color: #8898E8;
}

.badge-neutral {
  background: rgba(106, 112, 134, 0.15);
  color: #8A90A8;
}

/* ── Grid ───────────────────────────────────────────────── */
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

/* ── Flex utilities ─────────────────────────────────────── */
.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ── Spacing ────────────────────────────────────────────── */
.mb-4 {
  margin-bottom: var(--space-4);
}
.mb-3 {
  margin-bottom: var(--space-3);
}

.text-sm {
  font-size: var(--text-sm);
}
</style>
