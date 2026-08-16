<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import TeacherMetricGrid from '../../components/teacher/TeacherMetricGrid.vue'
import TeacherPageHeader from '../../components/teacher/TeacherPageHeader.vue'
import TeacherPagination from '../../components/teacher/TeacherPagination.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import { formatDateTime } from '../../utils/format.js'
import { useClientPagination } from '../../composables/useClientPagination.js'

const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()
const modules = ref([])
const loading = ref(true)
const createOpen = ref(false)
const editingId = ref(null)
const form = ref({ name: '', description: '' })
const query = ref('')
const statusFilter = ref('all')
const sortOrder = ref('updated')
const moduleStatus = (module) => module.status || 'draft'
const moduleUpdated = (module) => module.updated_at || module.created_at || ''
const summary = computed(() => ({ total: modules.value.length, published: modules.value.filter((item) => moduleStatus(item) === 'published').length, draft: modules.value.filter((item) => moduleStatus(item) === 'draft').length, offline: modules.value.filter((item) => moduleStatus(item) === 'offline' || moduleStatus(item) === 'archived').length }))
const filteredModules = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const result = modules.value.filter((item) => (!keyword || `${item.name || ''} ${item.description || ''}`.toLowerCase().includes(keyword)) && (statusFilter.value === 'all' || moduleStatus(item) === statusFilter.value))
  return [...result].sort((a, b) => sortOrder.value === 'name' ? String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN') : new Date(moduleUpdated(b) || 0) - new Date(moduleUpdated(a) || 0))
})
const { page, pageSize, pageCount, pagedItems, goToPage, resetPage } = useClientPagination(filteredModules)

async function fetch() {
  loading.value = true
  try {
    const res = await experimentsAPI.listModules()
    modules.value = res.data.items || res.data
  } catch {
    app.showToast('加载实验模块失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  editingId.value = null
  form.value = { name: '', description: '' }
  createOpen.value = true
}

function openEditModal(module) {
  editingId.value = module.id
  form.value = { name: module.name || '', description: module.description || '' }
  createOpen.value = true
}

function closeCreateModal() {
  createOpen.value = false
}

async function saveModule() {
  const name = form.value.name.trim()
  if (!name) {
    app.showToast('请输入实验名称', 'error')
    return
  }
  const payload = { ...form.value, name }
  try {
    if (editingId.value) {
      await experimentsAPI.updateModule(editingId.value, payload)
      app.showToast('修改成功', 'success')
    } else {
      await experimentsAPI.createModule(payload)
      app.showToast('创建成功', 'success')
    }
    createOpen.value = false
    form.value = { name: '', description: '' }
    editingId.value = null
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || (editingId.value ? '修改失败' : '创建失败'), 'error')
  }
}

async function toggleStatus(m) {
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

function goToSubmissions() {
  const prefix = auth.isAdmin ? '/admin' : '/teacher'
  router.push(`${prefix}/submissions`)
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="page teacher-management-page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <TeacherPageHeader title="实验模块管理" subtitle="创建与维护实验模块，配置 JupyterLab 环境与入口">
        <template #actions>
          <button class="btn-ghost teacher-page-action" @click="goToSubmissions"><AppIcon name="clipboard" :size="18" />查看提交</button>
          <button class="btn-primary teacher-page-action" @click="openCreateModal"><AppIcon name="plus" :size="18" />创建实验</button>
        </template>
      </TeacherPageHeader>

      <!-- ── Create Modal ──────────────────────────────────────────────── -->
      <div v-if="createOpen" class="modal-backdrop create-backdrop" @click.self="closeCreateModal">
        <div class="create-panel create-modal create-form" role="dialog" aria-modal="true" :aria-label="editingId ? '编辑实验' : '创建实验'">
          <header class="create-heading">
            <strong>{{ editingId ? '编辑实验' : '创建实验' }}</strong>
            <button class="create-close" type="button" aria-label="关闭" @click="closeCreateModal">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            </button>
          </header>
          <div class="create-modal-body">
            <div class="form-group">
              <label>实验名称</label>
              <input v-model="form.name" name="module-name" placeholder="例如：Python 数据分析实验" />
            </div>
            <div class="form-group">
              <label>实验描述</label>
              <textarea v-model="form.description" name="module-description" rows="3" placeholder="实验目标和步骤说明"></textarea>
            </div>
            <p class="form-hint modal-hint">创建后可在列表中发布或下架实验模块。发布时要求已绑定可用模板。</p>
            <div class="create-actions">
              <button class="btn-ghost btn-sm" type="button" @click="closeCreateModal">取消</button>
              <button class="btn-primary btn-sm" type="button" data-action="save-module" @click="saveModule">{{ editingId ? '保存' : '确定' }}</button>
            </div>
          </div>
        </div>
      </div>

      <TeacherMetricGrid aria-label="实验统计" :items="[{ key: 'total', label: '全部实验', icon: 'experiment', tone: 'blue', value: summary.total, unit: '个' }, { key: 'published', label: '已发布', icon: 'send', tone: 'green', value: summary.published, unit: '个' }, { key: 'draft', label: '草稿', icon: 'draft', tone: 'orange', value: summary.draft, unit: '个' }, { key: 'offline', label: '已下架', icon: 'clock', tone: 'purple', value: summary.offline, unit: '个' }]" />
      <section class="table-wrap data-panel"><div class="toolbar filter-bar"><label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索实验名称" @input="resetPage" /></label><select v-model="statusFilter" @change="resetPage"><option value="all">状态：全部</option><option value="published">已发布</option><option value="draft">草稿</option><option value="offline">已下架</option></select><select v-model="sortOrder" @change="resetPage"><option value="updated">排序：最近更新</option><option value="name">排序：实验名称</option></select></div><div v-if="loading" class="loading-list"><span v-for="i in 6" :key="i" class="skeleton"></span></div><div v-else-if="filteredModules.length === 0" class="empty-state"><AppIcon name="experiment" :size="32" /><strong>暂无符合条件的实验</strong><p>调整筛选条件，或创建一个新实验。</p></div><div v-else class="table-scroll"><table class="ds-table"><thead><tr><th>实验名称</th><th>描述</th><th>状态</th><th>最近更新</th><th>操作</th></tr></thead><tbody><tr v-for="module in pagedItems" :key="module.id"><td class="title-cell">{{ module.name }}</td><td>{{ module.description || '暂无实验描述' }}</td><td><span class="status-pill" :class="moduleStatus(module)">{{ moduleStatus(module) === 'published' ? '已发布' : moduleStatus(module) === 'draft' ? '草稿' : '已下架' }}</span></td><td class="muted-cell">{{ formatDateTime(moduleUpdated(module)) }}</td><td class="actions-cell"><button class="text-action" data-action="edit-module" @click="openEditModal(module)">编辑模块</button><button class="text-action" @click="goToSubmissions">查看提交</button><button class="publish-action" @click="toggleStatus(module)">{{ module.status === 'published' ? '下架' : '发布' }}</button></td></tr></tbody></table></div><TeacherPagination v-if="!loading" :current-page="page" :page-count="pageCount" :total="filteredModules.length" :page-size="pageSize" aria-label="实验列表分页" @change="goToPage" /></section>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Teacher Experiment Manage — Code Studio
   page-head + create modal + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 22px; }
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.metric-card{display:flex;align-items:center;gap:18px;min-height:106px;padding:20px;border:1px solid var(--border);border-radius: var(--radius-lg);background:var(--surface);box-shadow:none}.metric-icon{display:grid;place-items:center;width:54px;height:54px;border-radius:15px}.metric-icon.blue{color:var(--accent);background:var(--accent-soft)}.metric-icon.green{color:var(--success);background:var(--success-bg)}.metric-icon.orange{color:var(--warning);background:var(--warning-bg)}.metric-icon.purple{color:var(--info);background:var(--info-bg)}.metric-card span:last-child{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}.metric-card small{width:100%;color:var(--muted);font-size:14px}.metric-card strong{color:var(--fg);font-size:27px;line-height:1}.metric-card em{color:var(--muted);font-size:13px;font-style:normal}.data-panel{overflow:hidden;border:1px solid var(--border);border-radius: var(--radius-lg);background:var(--surface);box-shadow:none}.filter-bar{display:grid;grid-template-columns:minmax(220px,1.4fr) repeat(3,minmax(150px,.8fr));gap:14px;padding:18px;border-bottom:1px solid var(--border)}.search-control{display:flex;align-items:center;gap:9px;padding:0 13px;border:1px solid var(--border);border-radius: var(--radius-md);color:var(--faint)}.search-control input{min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{height:44px;min-width:0}.table-scroll{overflow-x:auto}.table-scroll table{width:100%;min-width:900px;margin:0}.table-scroll th{height:44px;background:var(--surface-subtle)}.table-scroll td{height:68px;padding:10px 16px}.table-scroll td small{display:block;color:var(--faint);font-size:12px}.status-pill{display:inline-flex;padding:4px 11px;border-radius: var(--radius-full);font-size:12px;font-weight:600}.status-pill.published{color:var(--success);background:var(--success-bg)}.status-pill.draft{color:var(--warning);background:var(--warning-bg)}.status-pill.offline{color:var(--info);background:var(--info-bg)}.muted-cell{color:var(--muted);font-size:13px}.actions-cell{display:table-cell;vertical-align:middle;white-space:nowrap}.actions-cell button{display:inline-flex;align-items:center}.actions-cell button+button{margin-left:2px}.text-action,.publish-action{padding:5px 7px;border:0;background:transparent;color:var(--accent);font-size:13px}.publish-action{color:var(--warning)}.pagination-bar{display:flex;justify-content:space-between;padding:14px 18px;border-top:1px solid var(--border);color:var(--muted);font-size:13px}.active-page{display:inline-grid;place-items:center;width:30px;height:30px;border-radius: var(--radius-md);color:var(--surface);background:var(--accent)}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:68px}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:700px){.page-head{flex-direction:column}.metric-grid{grid-template-columns:1fr 1fr;gap:10px}.filter-bar{grid-template-columns:1fr}.table-scroll table{min-width:820px}}

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
.create-modal {
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}
.create-modal-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.create-modal-body .form-group { margin-bottom: var(--space-3); }
.form-hint {
  margin: 6px 0 0;
  font-size: var(--text-sm);
  color: var(--muted);
}
.modal-hint { margin-top: 2px; }

/* ── Modal ────────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed;
  z-index: 50;
  inset: 0 0 0 var(--modal-left, 0);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  background: oklch(0.2 0.01 150 / 0.28);
  backdrop-filter: blur(2px);
}
.modal-backdrop.create-backdrop {
  justify-content: center;
}
.create-panel {
  width: min(620px, calc(100vw - 32px));
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.create-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.create-heading strong { font-size: 17px; color: var(--fg); }
.create-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.create-close:hover { background: var(--hover-bg, var(--surface-subtle)); color: var(--fg); }
.create-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }

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
.w-30 { width: 30%; }
.w-35 { width: 35%; }

/* ── Cells ─────────────────────────────────────────────────────────── */
.title-cell { font-weight: 500; color: var(--fg); }
.entry-code {
  font-family: var(--font-mono); font-size: 11px;
  background: var(--surface-sunken);
  padding: 2px 6px; border-radius: var(--radius-sm);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}

/* 实验列表列宽固定，状态标签和时间等紧凑字段不能被拆成竖排。 */
.table-scroll table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
}
.table-scroll th {
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}
.table-scroll td {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}
.table-scroll th:nth-child(1) { width: 22%; }
.table-scroll th:nth-child(2) { width: 28%; }
.table-scroll th:nth-child(3) { width: 12%; }
.table-scroll th:nth-child(4) { width: 12%; }
.table-scroll th:nth-child(5) { width: 26%; }
.table-scroll td:nth-child(3),
.table-scroll td:nth-child(4) { white-space: nowrap; }
.table-scroll .status-pill {
  display: inline-flex;
  min-width: max-content;
  white-space: nowrap;
  word-break: keep-all;
}
.table-scroll td:last-child {
  display: table-cell;
  white-space: nowrap;
}
.table-scroll td:last-child button {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
</style>
