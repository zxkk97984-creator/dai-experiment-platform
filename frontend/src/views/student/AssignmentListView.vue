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

onMounted(async () => {
  try {
    const res = await assignmentsAPI.list()
    assignments.value = res.data.items || res.data
  } catch { app.showToast('加载作业列表失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <h1 class="page-title">我的作业 📝</h1>
    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="assignments.length === 0" class="empty-card">
      <p class="empty-text">暂无作业</p>
    </div>
    <div v-else class="grid-2">
      <div v-for="a in assignments" :key="a.id" class="assignment-card"
        @click="router.push(`/student/assignments/${a.id}`)">
        <div class="flex-between mb-3">
          <h3 class="assignment-title">{{ a.title }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">
            {{ statusBadge(PUBLISH_STATUS_MAP, a.status).label }}
          </span>
        </div>
        <p class="assignment-due">截止: {{ formatDateTime(a.due_at) }}</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Card ──────────────────────────────────────────────────────────── */
.assignment-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.assignment-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

/* ── Title (link — Prussian blue) ───────────────────────────────────── */
.assignment-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--primary);
  line-height: 1.3;
  transition: color var(--duration-fast) var(--ease-out);
}
.assignment-card:hover .assignment-title {
  color: var(--accent-hover);
}

/* ── Due date ──────────────────────────────────────────────────────── */
.assignment-due {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

/* ── Empty state ───────────────────────────────────────────────────── */
.empty-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 48px;
  text-align: center;
}
.empty-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin: 0;
}

/* ── Loading ───────────────────────────────────────────────────────── */
.loading-state {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

/* ── Badges (light theme from global CSS) ──────────────────────────── */
.badge {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
  display: inline-flex;
  align-items: center;
}
</style>
