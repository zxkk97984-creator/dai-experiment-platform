<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()

const modules = ref([])
const records = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [mRes, rRes] = await Promise.all([
      experimentsAPI.listModules(),
      experimentsAPI.listRecords(),
    ])
    modules.value = mRes.data.items || mRes.data
    records.value = rRes.data.items || rRes.data
  } catch { app.showToast('加载实验失败', 'error') }
  finally { loading.value = false }
})

function enterExperiment(m) {
  router.push(`/student/experiments/${m.id}`)
}
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">实验模块 🧪</h1>
    </div>

    <div v-if="loading" class="text-secondary" style="padding:24px 0">加载中...</div>

    <div v-else-if="modules.length === 0" class="empty-state">
      <p>暂无实验模块</p>
    </div>

    <div v-else class="grid-2">
      <div v-for="m in modules" :key="m.id" class="card" style="cursor:pointer" @click="enterExperiment(m)">
        <div class="flex-between mb-3">
          <h3 style="margin:0;font-size:15px">{{ m.name }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">
            {{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}
          </span>
        </div>
        <p class="text-sm text-secondary mb-4">{{ m.description || '暂无描述' }}</p>
        <button class="btn-primary" style="display:inline-flex;align-items:center;gap:6px">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="8" height="8" rx="1.5"/><path d="M5.5 3v8M3 5.5h8"/>
          </svg>
          进入实验
        </button>
      </div>
    </div>

    <h2 class="mt-4 mb-4" style="font-size:16px;font-weight:600">我的实验记录</h2>
    <div v-if="records.length === 0" class="text-sm text-secondary">暂无记录</div>
    <table v-else class="card" style="padding:0">
      <thead><tr><th>模块</th><th>状态</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in records" :key="r.id">
          <td>{{ r.module_id }}</td>
          <td><span class="badge badge-info">{{ r.status }}</span></td>
          <td class="text-sm text-secondary">{{ r.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </AppLayout>
</template>

<style scoped>
.page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink);
  transition: all var(--duration-fast) var(--ease-out);
}
.card:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow-md);
}
h3 { color: var(--ink); font-weight: 600; }
.text-secondary { color: var(--text-secondary); }
.btn-primary {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.btn-primary:hover {
  background: var(--accent-dark); border-color: var(--accent-dark);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.32);
}
.empty-state {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state p { font-size: var(--text-sm); }
th { background: var(--surface-raised); color: var(--text-secondary); border-bottom-color: var(--border); }
td { color: var(--ink); border-bottom-color: var(--border); }
tbody tr:hover td { background: var(--surface-raised); }
</style>
