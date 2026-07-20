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
  try {
    const res = await experimentsAPI.listModules()
    modules.value = res.data.items || res.data
  } catch {
    app.showToast('加载实验模块失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.value.name) return
  try {
    await experimentsAPI.createModule(form.value)
    app.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { name: '', description: '', entry_url: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  }
}

async function toggleStatus(m) {
  const newStatus = m.status === 'published' ? 'draft' : 'published'
  try {
    await experimentsAPI.createModule({ ...m, status: newStatus })
    app.showToast(newStatus === 'published' ? '已发布' : '已下架', 'success')
    fetch()
  } catch {
    app.showToast('操作失败', 'error')
  }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title">实验模块管理 🧪</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '创建实验' }}
      </button>
    </div>

    <!-- Create form -->
    <div v-if="showCreate" class="card mb-4">
      <div class="form-group">
        <label>实验名称</label>
        <input v-model="form.name" placeholder="例如：Python 数据分析实验" />
      </div>
      <div class="form-group">
        <label>实验描述</label>
        <textarea v-model="form.description" rows="3" placeholder="实验目标和步骤说明" />
      </div>
      <div class="form-group">
        <label>入口 URL（可选）</label>
        <input v-model="form.entry_url" placeholder="外部实验链接，留空则使用 JupyterLab" />
      </div>
      <button class="btn-primary" @click="handleCreate">确认创建</button>
    </div>

    <!-- Module list -->
    <div v-if="loading" class="text-secondary" style="padding:24px 0">加载中...</div>

    <table v-else-if="modules.length" class="card" style="padding:0">
      <thead>
        <tr><th>名称</th><th>描述</th><th>入口</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="m in modules" :key="m.id">
          <td style="font-weight:500">{{ m.name }}</td>
          <td class="text-sm text-secondary">{{ m.description || '—' }}</td>
          <td class="text-sm text-secondary">
            <code v-if="m.entry_url" style="font-size:11px">{{ m.entry_url }}</code>
            <span v-else>JupyterLab</span>
          </td>
          <td>
            <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">
              {{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}
            </span>
          </td>
          <td>
            <button class="btn-sm" @click="toggleStatus(m)">
              {{ m.status === 'published' ? '下架' : '发布' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty-state">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
        <rect x="8" y="8" width="32" height="32" rx="4"/><path d="M18 20h12M18 26h8"/>
      </svg>
      <p>暂无实验模块，点击"创建实验"开始</p>
    </div>
  </AppLayout>
</template>

<style scoped>
.page-title { font-family: var(--font-display); font-size: var(--text-2xl); font-weight: 600; color: var(--ink); letter-spacing: -0.01em; }
.card { background: var(--surface); border: 1px solid var(--border); }
.text-secondary { color: var(--text-secondary); }
th { background: var(--surface-raised); color: var(--text-secondary); border-bottom-color: var(--border); }
td { color: var(--ink); border-bottom-color: var(--border); }
tbody tr:hover td { background: var(--surface-raised); }
.empty-state { text-align: center; padding: var(--space-12) var(--space-6); color: var(--text-secondary); }
.empty-state p { font-size: var(--text-sm); margin-top: var(--space-3); }
</style>
