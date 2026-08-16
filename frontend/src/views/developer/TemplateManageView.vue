<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { studioAPI } from '../../api/studio.js'
import { useAppStore } from '../../stores/app.js'

const router = useRouter()
const app = useAppStore()
const templates = ref([])
const loading = ref(true)
const showCreate = ref(false)
const newName = ref('')
const newDesc = ref('')
const creating = ref(false)

async function load() {
  loading.value = true
  try { const res = await studioAPI.listTemplates(); templates.value = res.data || [] }
  catch { app.showToast('加载模板失败', 'error') }
  finally { loading.value = false }
}

async function createBlank() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    const res = await studioAPI.createTemplate({ name: newName.value.trim(), description: newDesc.value })
    router.push(`/developer/studio/${res.data.id}`)
  } catch { app.showToast('创建失败', 'error') }
  finally { creating.value = false }
}

async function importTemplate(file) {
  creating.value = true
  try {
    const fd = new FormData()
    fd.append('name', file.name.replace(/\.(ipynb|zip)$/i, ''))
    fd.append('file', file)
    const res = await studioAPI.importNew(fd)
    router.push(`/developer/studio/${res.data.id}`)
  } catch (e) { app.showToast('导入失败: ' + (e.response?.data?.detail?.message || ''), 'error') }
  finally { creating.value = false }
}

function onFileChange(e) { const f = e.target.files[0]; if (f) importTemplate(f) }

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <p class="eyebrow">Developer Workspace</p>
          <h1 class="page-title">实验模板管理</h1>
          <p class="page-sub">创建、编辑、发布独立实验使用的 Notebook 模板</p>
        </div>
        <div class="header-actions">
          <button class="btn-accent" @click="showCreate = !showCreate">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            新建模板
          </button>
          <label class="btn-accent btn-import">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 2v10M4 8l4 4 4-4M2 14h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            导入 .ipynb / .zip
            <input type="file" accept=".ipynb,.zip" class="hidden-input" @change="onFileChange" />
          </label>
        </div>
      </header>

      <!-- ── Create Form ───────────────────────────────────────────────── -->
      <div v-if="showCreate" class="card create-form">
        <input v-model="newName" placeholder="模板名称" class="form-input" @keyup.enter="createBlank" />
        <input v-model="newDesc" placeholder="描述（可选）" class="form-input" />
        <button class="btn-accent" :disabled="creating" @click="createBlank">
          {{ creating ? '创建中...' : '创建空白模板' }}
        </button>
      </div>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 4" :key="i">
          <div class="skeleton skel-cell w-40"></div>
          <div class="skeleton skel-cell w-20"></div>
          <div class="skeleton skel-cell w-15"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="templates.length === 0" class="empty-state">
        <p>📓 暂无模板，点击上方按钮创建或导入</p>
      </div>

      <!-- ── Template List ──────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table class="ds-table">
          <thead>
            <tr><th>模板名称</th><th>状态</th><th>版本</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="tpl in templates" :key="tpl.id">
              <td class="title-cell">{{ tpl.name }}</td>
              <td>
                <span class="badge" :class="tpl.status === 'published' ? 'badge-success' : 'badge-neutral'">
                  {{ tpl.status === 'published' ? '已发布' : '草稿' }}
                </span>
              </td>
              <td class="text-sm text-secondary">rev {{ tpl.draft_revision }}</td>
              <td>
                <button class="btn-accent btn-sm" @click="router.push('/developer/studio/' + tpl.id)">编辑</button>
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
   Developer Template Manage — Code Studio
   page-head + create form + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.eyebrow {
  margin: 0 0 var(--space-2); color: var(--accent);
  font-size: var(--text-xs); font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--fg); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--muted); margin: 0;
}
.header-actions {
  display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center;
}

/* ── Create Form ───────────────────────────────────────────────────── */
.create-form {
  padding: 20px;
  display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center;
}
.form-input {
  padding: 8px 12px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  color: var(--fg); font-size: var(--text-sm); outline: none;
  flex: 1; min-width: 180px;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.form-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }

/* ── Import button ─────────────────────────────────────────────────── */
.btn-import {
  position: relative; cursor: pointer;
}
.hidden-input {
  position: absolute; inset: 0; opacity: 0; cursor: pointer;
}

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
.w-20 { width: 20%; }
.w-40 { width: 40%; }

/* ── Cells ─────────────────────────────────────────────────────────── */
.title-cell { font-weight: 500; color: var(--fg); }

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
  .header-actions { width: 100%; }
}
</style>
