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
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">作业管理</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '布置作业' }}
      </button>
    </div>

    <div v-if="showCreate" class="card mb-4">
      <div class="form-group"><label>作业名称</label><input v-model="form.title" /></div>
      <div class="form-group"><label>描述</label><textarea v-model="form.description" rows="2"></textarea></div>
      <div class="grid-2">
        <div class="form-group"><label>课程 ID</label><input v-model="form.course_id" type="number" /></div>
        <div class="form-group"><label>截止时间</label><input v-model="form.due_at" type="datetime-local" /></div>
      </div>
      <button class="btn-primary" @click="handleCreate">确认创建</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="assignments.length" class="card" style="padding:0">
      <thead><tr><th>名称</th><th>状态</th><th>截止</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="a in assignments" :key="a.id">
          <td>{{ a.title }}</td>
          <td><span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">{{ statusBadge(PUBLISH_STATUS_MAP, a.status).label }}</span></td>
          <td class="text-sm">{{ formatDateTime(a.due_at) }}</td>
          <td>
            <button class="btn-sm" @click="router.push(`/teacher/assignments/${a.id}/edit`)">编辑题目</button>
            <button v-if="a.status==='draft'" class="btn-sm btn-primary" style="margin-left:6px" @click="handlePublish(a)">发布</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无作业</p></div>
  </AppLayout>
</template>
