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
      <h1 class="page-title" style="margin-bottom:0">考试管理 📋</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">{{ showCreate ? '取消' : '创建考试' }}</button>
    </div>

    <div v-if="showCreate" class="card mb-4">
      <div class="grid-2">
        <div class="form-group"><label>考试名称</label><input v-model="form.title" placeholder="输入考试名称" /></div>
        <div class="form-group"><label>课程 ID</label><input v-model="form.course_id" type="number" placeholder="课程 ID" /></div>
        <div class="form-group"><label>时长 (分钟)</label><input v-model.number="form.duration_minutes" type="number" /></div>
        <div class="form-group"><label>开始时间</label><input v-model="form.start_at" type="datetime-local" /></div>
      </div>
      <button class="btn-primary" @click="handleCreate">确认创建</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="exams.length" class="data-table">
      <thead><tr><th>名称</th><th>状态</th><th>时长</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="e in exams" :key="e.id">
          <td>{{ e.title }}</td>
          <td><span class="badge" :class="'badge-' + statusBadge(EXAM_STATUS_MAP, e.status).color">{{ statusBadge(EXAM_STATUS_MAP, e.status).label }}</span></td>
          <td>{{ e.duration_minutes }} 分钟</td>
          <td><button class="btn-ghost btn-sm" @click="router.push(`/teacher/exams/${e.id}/grades`)">查看成绩</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无考试</p></div>
  </AppLayout>
</template>

<style scoped>
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
  background: var(--surface-sunken);
  color: var(--text-secondary);
}

.data-table td {
  border-bottom: 1px solid var(--border);
}

.data-table tbody tr:hover td {
  background: var(--surface-raised);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}
</style>
