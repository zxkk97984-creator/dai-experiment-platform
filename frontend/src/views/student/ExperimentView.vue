<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

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
</script>

<template>
  <AppLayout>
    <h1 class="page-title">实验模块</h1>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <div v-else-if="modules.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无实验模块</p>
    </div>
    <div v-else class="grid-2">
      <div v-for="m in modules" :key="m.id" class="card">
        <div class="flex-between mb-3">
          <h3 style="margin:0;font-size:15px">{{ m.name }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">
            {{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}
          </span>
        </div>
        <p class="text-sm text-secondary mb-4">{{ m.description || '暂无描述' }}</p>
        <a v-if="m.entry_url" :href="m.entry_url" target="_blank"
          class="btn-sm btn-primary" style="display:inline-block;text-decoration:none">进入实验</a>
      </div>
    </div>

    <h2 class="mt-4 mb-4" style="font-size:16px">我的实验记录</h2>
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
/* ── Reading Room experiment module ──────────────────────────────── */

.page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: var(--ink);
  margin-bottom: var(--space-8);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

/* ── Cards ──────────────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink);
}

.card:hover {
  border-color: var(--accent);
  box-shadow: 0 0 20px rgba(224, 85, 61, 0.15),
              0 4px 16px rgba(0, 0, 0, 0.06);
}

/* ── Card title ─────────────────────────────────────────────────────── */
h3 {
  color: var(--ink);
}

/* ── Text utilities ─────────────────────────────────────────────────── */
.text-secondary {
  color: var(--text-secondary);
}

/* ── Section header ─────────────────────────────────────────────────── */
h2 {
  color: var(--ink);
}

/* ── Badges (light theme from global CSS) ──────────────────────────── */

/* ── "进入实验" button (accent orange CTA) ──────────────────────────── */
.btn-primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
  box-shadow: 0 0 14px rgba(224, 85, 61, 0.2);
}

/* ── Table ────────────────────────────────────────────────────── */
th {
  background: var(--surface-raised);
  color: var(--text-secondary);
  border-bottom-color: var(--border);
}

td {
  color: var(--ink);
  border-bottom-color: var(--border);
}

tbody tr:hover td {
  background: var(--surface-raised);
}
</style>
