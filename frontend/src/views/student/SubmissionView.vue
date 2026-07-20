<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { judgeAPI } from '../../api/judge.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, JUDGE_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const route = useRoute()
const app = useAppStore()
const submission = ref(null)
const polling = ref(true)
let timer = null

const TERMINAL_STATUSES = ['accepted', 'wrong_answer', 'runtime_error', 'time_limit_exceeded', 'system_error']

async function fetchResult() {
  try {
    const res = await judgeAPI.getResult(route.params.id)
    submission.value = res.data
    if (TERMINAL_STATUSES.includes(res.data.status)) {
      polling.value = false
    }
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchResult()
  timer = setInterval(() => { if (polling.value) fetchResult() }, 1500)
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <AppLayout>
    <h1 class="page-title">判题结果 ✅</h1>

    <div v-if="!submission" class="card submission-card" style="text-align:center;padding:48px">
      <p class="text-secondary">加载中...</p>
    </div>

    <template v-else>
      <div class="card submission-card mb-4">
        <div class="flex-between mb-4">
          <h3 class="submission-title">提交 #{{ submission.id }}</h3>
          <span class="badge"
            :class="'badge-' + statusBadge(JUDGE_STATUS_MAP, submission.status).color">
            {{ statusBadge(JUDGE_STATUS_MAP, submission.status).label }}
          </span>
        </div>
        <div class="submission-meta grid-2 text-sm mb-4">
          <div>状态: <strong>{{ submission.status }}</strong></div>
          <div v-if="submission.score != null">得分: <strong>{{ submission.score }}</strong></div>
          <div v-if="submission.execution_time_ms != null">
            执行时间: <strong>{{ submission.execution_time_ms }}ms</strong>
          </div>
          <div>提交时间: <strong>{{ formatDateTime(submission.created_at) }}</strong></div>
        </div>
      </div>


      <div v-if="polling" class="polling-text text-sm mt-4 flex-center gap-2">
        <span>判题进行中，自动刷新中...</span>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Card ────────────────────────────────────────────────── */
.submission-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.submission-title {
  margin: 0;
  color: var(--ink);
  font-weight: 600;
}

.submission-meta {
  color: var(--text-secondary);
}
.submission-meta strong {
  color: var(--ink);
}

/* ── Terminal output blocks (code — keep dark) ──────────────────────── */
.output-block {
  background: #0F172A;
  color: #E2E8F0;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.65;
  white-space: pre-wrap;
  border: 1px solid #1E293B;
}
.output-error { color: #F5A3AB; }

/* ── Polling text ──────────────────────────────────────────────────── */
.polling-text {
  color: var(--text-secondary);
}

/* ── Badges (light theme from global CSS) ──────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
}
</style>
