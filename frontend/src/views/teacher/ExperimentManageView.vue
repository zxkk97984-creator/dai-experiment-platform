<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()
const modules = ref([])
const loading = ref(true)
const createOpen = ref(false)
const form = ref({ name: '', description: '', entry_url: '' })
const query = ref('')
const statusFilter = ref('all')
const entryFilter = ref('all')
const sortOrder = ref('updated')
const moduleStatus = (module) => module.status || 'draft'
const moduleUpdated = (module) => module.updated_at || module.created_at || ''
const summary = computed(() => ({ total: modules.value.length, published: modules.value.filter((item) => moduleStatus(item) === 'published').length, draft: modules.value.filter((item) => moduleStatus(item) === 'draft').length, offline: modules.value.filter((item) => moduleStatus(item) === 'offline' || moduleStatus(item) === 'archived').length }))
const filteredModules = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const result = modules.value.filter((item) => (!keyword || `${item.name || ''} ${item.description || ''}`.toLowerCase().includes(keyword)) && (statusFilter.value === 'all' || moduleStatus(item) === statusFilter.value) && (entryFilter.value === 'all' || (entryFilter.value === 'external' ? item.entry_url : !item.entry_url)))
  return [...result].sort((a, b) => sortOrder.value === 'name' ? String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN') : new Date(moduleUpdated(b) || 0) - new Date(moduleUpdated(a) || 0))
})
function formatDate(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date).replaceAll('/', '-') }

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
  createOpen.value = true
}

function closeCreateModal() {
  createOpen.value = false
}

async function handleCreate() {
  const name = form.value.name.trim()
  if (!name) {
    app.showToast('请输入实验名称', 'error')
    return
  }

  try {
    await experimentsAPI.createModule({ ...form.value, name })
    app.showToast('创建成功', 'success')
    createOpen.value = false
    form.value = { name: '', description: '', entry_url: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  }
}

async function toggleStatus(m) {
  const newStatus = m.status === 'published' ? 'draft' : 'published'
  try {
    await experimentsAPI.updateModule(m.id, { status: newStatus })
    app.showToast(newStatus === 'published' ? '已发布' : '已下架', 'success')
    fetch()
  } catch {
    app.showToast('操作失败', 'error')
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
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">实验模块管理</h1>
          <p class="page-sub">创建与维护实验模块，配置 JupyterLab 环境与入口</p>
        </div>
        <div class="page-meta">
          <button class="btn-ghost" @click="goToSubmissions">查看提交</button>
          <button class="btn-primary" @click="openCreateModal">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            创建实验
          </button>
        </div>
      </header>

      <!-- ── Create Modal ──────────────────────────────────────────────── -->
      <div v-if="createOpen" class="modal-backdrop create-backdrop" @click.self="closeCreateModal">
        <div class="create-panel create-modal create-form" role="dialog" aria-modal="true" aria-label="创建实验">
          <header class="create-heading">
            <strong>创建实验</strong>
            <button class="create-close" type="button" aria-label="关闭" @click="closeCreateModal">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            </button>
          </header>
          <div class="create-modal-body">
            <div class="form-group">
              <label>实验名称</label>
              <input v-model="form.name" placeholder="例如：Python 数据分析实验" />
            </div>
            <div class="form-group">
              <label>实验描述</label>
              <textarea v-model="form.description" rows="3" placeholder="实验目标和步骤说明"></textarea>
            </div>
            <div class="form-group">
              <label>入口 URL（可选）</label>
              <input v-model="form.entry_url" placeholder="外部实验链接，留空则使用 JupyterLab" />
            </div>
            <p class="form-hint modal-hint">创建后可在列表中发布或下架实验模块。</p>
            <div class="create-actions">
              <button class="btn-ghost btn-sm" type="button" @click="closeCreateModal">取消</button>
              <button class="btn-primary btn-sm" type="button" @click="handleCreate">确定</button>
            </div>
          </div>
        </div>
      </div>

      <section class="metric-grid"><article v-for="item in [{ key: 'total', label: '全部实验', icon: 'experiment', tone: 'blue' }, { key: 'published', label: '已发布', icon: 'send', tone: 'green' }, { key: 'draft', label: '草稿', icon: 'draft', tone: 'orange' }, { key: 'offline', label: '已下架', icon: 'clock', tone: 'purple' }]" :key="item.key" class="metric-card"><span class="metric-icon" :class="item.tone"><AppIcon :name="item.icon" :size="24" /></span><span><small>{{ item.label }}</small><strong>{{ summary[item.key] }}</strong><em>个</em></span></article></section>
      <section class="data-panel"><div class="filter-bar"><label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索实验名称" /></label><select v-model="statusFilter"><option value="all">状态：全部</option><option value="published">已发布</option><option value="draft">草稿</option><option value="offline">已下架</option></select><select v-model="entryFilter"><option value="all">入口：全部入口</option><option value="jupyter">JupyterLab</option><option value="external">外部入口</option></select><select v-model="sortOrder"><option value="updated">排序：最近更新</option><option value="name">排序：实验名称</option></select></div><div v-if="loading" class="loading-list"><span v-for="i in 6" :key="i" class="skeleton"></span></div><div v-else-if="filteredModules.length === 0" class="empty-state"><p>🧪 暂无符合条件的实验</p></div><div v-else class="table-scroll"><table><thead><tr><th>实验名称</th><th>描述</th><th>入口</th><th>状态</th><th>最近更新</th><th>操作</th></tr></thead><tbody><tr v-for="module in filteredModules" :key="module.id"><td class="title-cell">{{ module.name }}</td><td>{{ module.description || '暂无实验描述' }}</td><td><code v-if="module.entry_url" class="entry-code">{{ module.entry_url }}</code><span v-else>JupyterLab</span></td><td><span class="status-pill" :class="moduleStatus(module)">{{ moduleStatus(module) === 'published' ? '已发布' : moduleStatus(module) === 'draft' ? '草稿' : '已下架' }}</span></td><td class="muted-cell">{{ formatDate(moduleUpdated(module)) }}</td><td class="actions-cell"><button class="text-action">编辑模块</button><button class="text-action" @click="goToSubmissions">查看提交</button><button class="publish-action" @click="toggleStatus(module)">{{ module.status === 'published' ? '下架' : '发布' }}</button></td></tr></tbody></table></div><footer v-if="!loading && filteredModules.length" class="pagination-bar"><span>共 {{ filteredModules.length }} 条</span><span>10 条/页　‹　<span class="active-page">1</span>　2　›</span></footer></section>.
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Teacher Experiment Manage — Code Studio
   page-head + create modal + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 22px; }
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.metric-card{display:flex;align-items:center;gap:18px;min-height:106px;padding:20px;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.metric-icon{display:grid;place-items:center;width:54px;height:54px;border-radius:15px}.metric-icon.blue{color:var(--primary);background:#edf4ff}.metric-icon.green{color:#10a66a;background:#eaf9f2}.metric-icon.orange{color:#ef8b10;background:#fff4e7}.metric-icon.purple{color:#7c4ce0;background:#f1ebfd}.metric-card span:last-child{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}.metric-card small{width:100%;color:var(--text-secondary);font-size:14px}.metric-card strong{color:var(--ink);font-size:27px;line-height:1}.metric-card em{color:var(--text-secondary);font-size:13px;font-style:normal}.data-panel{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.filter-bar{display:grid;grid-template-columns:minmax(220px,1.4fr) repeat(3,minmax(150px,.8fr));gap:14px;padding:18px;border-bottom:1px solid var(--border)}.search-control{display:flex;align-items:center;gap:9px;padding:0 13px;border:1px solid var(--border);border-radius:8px;color:var(--text-tertiary)}.search-control input{min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{height:44px;min-width:0}.table-scroll{overflow-x:auto}.table-scroll table{width:100%;min-width:900px;margin:0}.table-scroll th{height:44px;background:#f8fafc}.table-scroll td{height:68px;padding:10px 16px}.table-scroll td small{display:block;color:var(--text-tertiary);font-size:12px}.status-pill{display:inline-flex;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:600}.status-pill.published{color:#099b61;background:#e9f8f1}.status-pill.draft{color:#ef8b10;background:#fff4e7}.status-pill.offline{color:#7443d5;background:#f1ebfd}.muted-cell{color:var(--text-secondary);font-size:13px}.actions-cell{display:flex;gap:2px;white-space:nowrap}.text-action,.publish-action{padding:5px 7px;border:0;background:transparent;color:var(--primary);font-size:13px}.publish-action{color:var(--warning)}.pagination-bar{display:flex;justify-content:space-between;padding:14px 18px;border-top:1px solid var(--border);color:var(--text-secondary);font-size:13px}.active-page{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#fff;background:var(--primary)}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:68px}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:700px){.page-head{flex-direction:column}.metric-grid{grid-template-columns:1fr 1fr;gap:10px}.filter-bar{grid-template-columns:1fr}.table-scroll table{min-width:820px}}

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 0;
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
  color: var(--text-secondary);
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
  background: rgba(15, 23, 42, 0.28);
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
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
}
.create-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.create-heading strong { font-size: 17px; color: var(--ink); }
.create-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.create-close:hover { background: var(--hover-bg, #f1f5f9); color: var(--ink); }
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
.title-cell { font-weight: 500; color: var(--ink); }
.entry-code {
  font-family: var(--font-mono); font-size: 11px;
  background: var(--surface-sunken);
  padding: 2px 6px; border-radius: var(--radius-sm);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
