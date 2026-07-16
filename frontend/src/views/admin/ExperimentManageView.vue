<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const app = useAppStore()
const modules = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ name: '', description: '', entry_url: '' })

async function fetch() {
  loading.value = true
  try { const res = await experimentsAPI.listModules(); modules.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.name) return
  try { await experimentsAPI.createModule(form.value); app.showToast('创建成功', 'success'); showCreate.value = false; form.value = { name: '', description: '', entry_url: '' }; fetch() }
  catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}

async function handleUpdate(m) {
  const newStatus = m.status === 'published' ? 'draft' : 'published'
  try { await experimentsAPI.createModule({ ...m, status: newStatus }); app.showToast('状态已更新', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">实验模块管理</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">{{ showCreate ? '取消' : '创建模块' }}</button>
    </div>

    <div v-if="showCreate" class="card mb-4">
      <div class="form-group"><label>模块名称</label><input v-model="form.name" /></div>
      <div class="form-group"><label>描述</label><textarea v-model="form.description" rows="2"></textarea></div>
      <div class="form-group"><label>入口 URL</label><input v-model="form.entry_url" /></div>
      <button class="btn-primary" @click="handleCreate">确认创建</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="modules.length" class="card" style="padding:0">
      <thead><tr><th>名称</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="m in modules" :key="m.id">
          <td>{{ m.name }}</td>
          <td class="text-sm text-secondary">{{ m.description || '-' }}</td>
          <td><span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">{{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}</span></td>
          <td><button class="btn-sm" @click="handleUpdate(m)">{{ m.status === 'published' ? '下架' : '发布' }}</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无实验模块</p></div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   ExperimentManageView — Pythonista Dark Theme
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
  background: #11141D;
  color: #6A7086;
  border-bottom-color: #2A3040;
}
td {
  border-bottom-color: #2A3040;
}
tbody tr:hover td {
  background: rgba(224, 85, 61, 0.08);
}

/* ── Inputs ─────────────────────────────────────────────────────────── */
input,
textarea {
  background: #151821;
  border-color: #2A3040;
  color: #D6DEEB;
}
input:focus,
textarea:focus {
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.15);
  outline: none;
}
input::placeholder,
textarea::placeholder {
  color: #6A7086;
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

/* Action button — ghost dark */
button.btn-sm {
  background: transparent;
  border-color: #2A3040;
  color: #6A7086;
}
button.btn-sm:hover {
  background: rgba(224, 85, 61, 0.12);
  border-color: #E0553D;
  color: #E0553D;
}

/* ── Form labels ────────────────────────────────────────────────────── */
.form-group label {
  color: #6A7086;
}

/* ── Badges — dark-context adjustments ──────────────────────────────── */
.badge-success { background: rgba(15, 123, 94, 0.18); color: #34D399; }
.badge-warning { background: rgba(181, 118, 14, 0.18); color: #FBBF24; }
.badge-danger  { background: rgba(209, 46, 62, 0.18);  color: #F87171; }
.badge-info    { background: rgba(88, 102, 196, 0.18);  color: #A5B4FC; }
.badge-neutral { background: #1F2433; color: #6A7086; }

/* ── Type utilities ─────────────────────────────────────────────────── */
.text-secondary {
  color: #6A7086;
}

/* ── Focus ring ─────────────────────────────────────────────────────── */
:focus-visible {
  outline-color: #E0553D;
}
</style>
