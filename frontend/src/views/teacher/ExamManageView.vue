<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, EXAM_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const exams = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ title: '', course_id: '', duration_minutes: 60, start_at: '', end_at: '' })

async function fetch() {
  loading.value = true
  try { const res = await examsAPI.list(); exams.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.title) return
  try {
    await examsAPI.create({ ...form.value, course_id: parseInt(form.value.course_id) || undefined })
    app.showToast('创建成功', 'success'); showCreate.value = false; fetch()
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">考试管理</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">{{ showCreate ? '取消' : '创建考试' }}</button>
    </div>

    <div v-if="showCreate" class="card mb-4">
      <div class="grid-2">
        <div class="form-group"><label>考试名称</label><input v-model="form.title" /></div>
        <div class="form-group"><label>课程 ID</label><input v-model="form.course_id" type="number" /></div>
        <div class="form-group"><label>时长 (分钟)</label><input v-model.number="form.duration_minutes" type="number" /></div>
        <div class="form-group"><label>开始时间</label><input v-model="form.start_at" type="datetime-local" /></div>
      </div>
      <button class="btn-primary" @click="handleCreate">确认创建</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="exams.length" class="card" style="padding:0">
      <thead><tr><th>名称</th><th>状态</th><th>时长</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="e in exams" :key="e.id">
          <td>{{ e.title }}</td>
          <td><span class="badge" :class="'badge-' + statusBadge(EXAM_STATUS_MAP, e.status).color">{{ statusBadge(EXAM_STATUS_MAP, e.status).label }}</span></td>
          <td>{{ e.duration_minutes }} 分钟</td>
          <td><button class="btn-sm" @click="router.push(`/teacher/exams/${e.id}/grades`)">查看成绩</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无考试</p></div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   ExamManageView — Dark Admin Theme
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page title ─────────────────────────────────────────────────────── */
.page-title {
  color: #D6DEEB;
}

/* ── Cards ──────────────────────────────────────────────────────────── */
.card {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #D6DEEB;
}
.card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  border-color: #3A4050;
}

/* ── Table ──────────────────────────────────────────────────────────── */
table {
  color: #D6DEEB;
}
th {
  background: #151821;
  color: #8891A4;
  border-bottom-color: #2A3040;
}
td {
  border-bottom-color: #2A3040;
}
tbody tr:hover td {
  background: #1F2433;
}

/* ── Inputs ─────────────────────────────────────────────────────────── */
input {
  background: #151821;
  border-color: #2A3040;
  color: #D6DEEB;
}
input:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.15);
  outline: none;
}
input::placeholder {
  color: #5F6B7A;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
button {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #D6DEEB;
}
button:hover {
  background: #252B3A;
  border-color: #3A4050;
}

button.btn-primary {
  background: #E0553D;
  border-color: #E0553D;
  color: #fff;
}
button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}
button.btn-primary:focus-visible {
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.25);
}

button.btn-sm {
  background: #252B3A;
  border-color: #2A3040;
  color: #D6DEEB;
}
button.btn-sm:hover {
  background: #E0553D;
  border-color: #E0553D;
  color: #fff;
}

/* ── Form labels ────────────────────────────────────────────────────── */
.form-group label {
  color: #8891A4;
}

/* ── Badges — dark-context adjustments ──────────────────────────────── */
.badge-success { background: rgba(15, 123, 94, 0.18); color: #34D399; }
.badge-warning { background: rgba(181, 118, 14, 0.18); color: #FBBF24; }
.badge-danger  { background: rgba(209, 46, 62, 0.18);  color: #F87171; }
.badge-info    { background: rgba(88, 102, 196, 0.18);  color: #A5B4FC; }
.badge-neutral { background: #1F2433; color: #8891A4; }

/* ── Type utilities ─────────────────────────────────────────────────── */
.text-secondary {
  color: #8891A4;
}

/* ── Focus ring ─────────────────────────────────────────────────────── */
:focus-visible {
  outline-color: #E0553D;
}
</style>
