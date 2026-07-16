<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, EXAM_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const exams = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await examsAPI.list()
    exams.value = res.data.items || res.data
  } catch { app.showToast('加载考试列表失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <h1 class="page-title">考试中心</h1>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <div v-else-if="exams.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无考试</p>
    </div>
    <div v-else class="grid-2">
      <div v-for="e in exams" :key="e.id" class="card"
        style="cursor:pointer" @click="router.push(`/student/exams/${e.id}`)">
        <div class="flex-between mb-3">
          <h3 style="margin:0;font-size:15px;color:var(--accent)">{{ e.title }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(EXAM_STATUS_MAP, e.status).color">
            {{ statusBadge(EXAM_STATUS_MAP, e.status).label }}
          </span>
        </div>
        <p class="text-sm text-secondary">时长: {{ e.duration_minutes }} 分钟</p>
        <p class="text-sm text-secondary">开始: {{ formatDateTime(e.start_at) }}</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Pythonista dark theme ───────────────────────────────────────────── */

.page-title {
  color: #D6DEEB;
}

/* Card overrides */
.card {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #D6DEEB;
  transition: border-color 200ms ease, box-shadow 200ms ease;
}
.card:hover {
  border-color: #E0553D;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

/* Muted text */
.text-secondary {
  color: #6A7086;
}

/* Title links in accent orange */
h3 {
  color: #E0553D;
}

/* Dark bg badges — luminous on dark surfaces */
.badge {
  font-weight: 500;
}
.badge-success  { background: rgba(15, 123, 94, 0.18);  color: #2EE6A8; }
.badge-warning  { background: rgba(181, 118, 14, 0.18); color: #F5C842; }
.badge-danger   { background: rgba(209, 46, 62, 0.18);  color: #FF6B7A; }
.badge-info     { background: rgba(88, 102, 196, 0.18);  color: #9DA8F0; }
.badge-neutral  { background: rgba(106, 112, 134, 0.15); color: #8B93A8; }
</style>
