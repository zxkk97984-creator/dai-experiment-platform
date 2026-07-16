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
    <h1 class="page-title">我的作业</h1>
    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="assignments.length === 0" class="empty-card">
      <p class="empty-text">暂无作业</p>
    </div>
    <div v-else class="grid-2">
      <div v-for="a in assignments" :key="a.id" class="assignment-card"
        @click="router.push(`/student/assignments/${a.id}`)">
        <div class="flex-between mb-3">
          <h3 class="assignment-title">{{ a.title }}</h3>
          <span class="badge badge-dark" :class="'badge-dark-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">
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
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.assignment-card:hover {
  border-color: #E0553D;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

/* ── Title ─────────────────────────────────────────────────────────── */
.assignment-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #E0553D;
  line-height: 1.3;
  transition: color var(--duration-fast) var(--ease-out);
}
.assignment-card:hover .assignment-title {
  color: #F0705A;
}

/* ── Due date ──────────────────────────────────────────────────────── */
.assignment-due {
  font-size: var(--text-sm);
  color: #6A7086;
  margin: 0;
}

/* ── Empty state ───────────────────────────────────────────────────── */
.empty-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: 48px;
  text-align: center;
}
.empty-text {
  color: #6A7086;
  font-size: var(--text-sm);
  margin: 0;
}

/* ── Loading ───────────────────────────────────────────────────────── */
.loading-state {
  color: #6A7086;
  font-size: var(--text-sm);
}

/* ── Badges (dark-card compatible) ──────────────────────────────────── */
.badge-dark {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.07);
  color: #8891A4;
}
.badge-dark-success { background: rgba(15, 123, 94, 0.18);  color: #34D399; }
.badge-dark-warning { background: rgba(181, 118, 14, 0.18); color: #FBBF24; }
.badge-dark-danger  { background: rgba(209, 46, 62, 0.18);  color: #F87171; }
.badge-dark-info    { background: rgba(88, 102, 196, 0.18);  color: #A5B4FC; }
.badge-dark-neutral { background: rgba(255, 255, 255, 0.06); color: #8891A4; }
</style>
