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
const form = ref({ name: '', description: '' })

async function fetch() {
  loading.value = true
  try { const res = await experimentsAPI.listModules(); modules.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.name) return
  try { await experimentsAPI.createModule(form.value); app.showToast('创建成功', 'success'); showCreate.value = false; form.value = { name: '', description: '' }; fetch() }
  catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}

async function handleUpdate(m) {
  try {
    if (m.status === 'published') {
      await experimentsAPI.unpublishModule(m.id)
      app.showToast('已下架', 'success')
    } else {
      await experimentsAPI.publishModule(m.id)
      app.showToast('已发布', 'success')
    }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '操作失败', 'error')
  }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">实验模块管理</h1>
          <p class="page-sub">配置与维护实验模块、镜像与数据集</p>
        </div>
        <div class="page-meta">
          <button class="btn-primary" @click="showCreate = !showCreate">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            {{ showCreate ? '取消' : '创建模块' }}
          </button>
        </div>
      </header>

      <!-- ── Create Form ───────────────────────────────────────────────── -->
      <div v-if="showCreate" class="card create-form">
        <div class="form-group"><label>模块名称</label><input v-model="form.name" placeholder="输入模块名称" /></div>
        <div class="form-group"><label>描述</label><textarea v-model="form.description" rows="2" placeholder="模块描述"></textarea></div>
        <button class="btn-primary" @click="handleCreate">确认创建</button>
      </div>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 4" :key="i">
          <div class="skeleton skel-cell w-25"></div>
          <div class="skeleton skel-cell w-40"></div>
          <div class="skeleton skel-cell w-15"></div>
          <div class="skeleton skel-cell w-15"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="modules.length === 0" class="empty-state">
        <p>暂无实验模块</p>
      </div>

      <!-- ── Table ──────────────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table class="ds-table">
          <thead>
            <tr><th>名称</th><th>描述</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in modules" :key="m.id">
              <td class="title-cell">{{ m.name }}</td>
              <td class="text-sm text-secondary">{{ m.description || '—' }}</td>
              <td>
                <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">
                  {{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}
                </span>
              </td>
              <td>
                <button class="btn-ghost btn-sm" @click="handleUpdate(m)">
                  {{ m.status === 'published' ? '下架' : '发布' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Admin Experiment Manage — Code Studio
   page-head + create form + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--fg); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--muted); margin: 0;
}

/* ── Create Form ───────────────────────────────────────────────────── */
.create-form {
  padding: 24px;
  display: flex; flex-direction: column; gap: 4px;
}
.create-form .form-group { margin-bottom: var(--space-3); }

/* ── Table card ────────────────────────────────────────────────────── */
.table-card {
  padding: 0; overflow: hidden;
}
.table-card table { margin: 0; }

/* ── Skeleton ──────────────────────────────────────────────────────── */
.skeleton-row {
  display: flex; gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: none; }
.skel-cell { height: 16px; border-radius: var(--radius-sm); }
.w-15 { width: 15%; }
.w-25 { width: 25%; }
.w-40 { width: 40%; }

/* ── Cells ─────────────────────────────────────────────────────────── */
.title-cell { font-weight: 500; color: var(--fg); }

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
