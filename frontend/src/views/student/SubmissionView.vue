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
    <h1 class="page-title">判题结果</h1>

    <div v-if="!submission" class="card dark-card" style="text-align:center;padding:48px">
      <p style="color:#6A7086">加载中...</p>
    </div>

    <template v-else>
      <div class="card dark-card mb-4">
        <div class="flex-between mb-4">
          <h3 style="margin:0;color:#D6DEEB">提交 #{{ submission.id }}</h3>
          <span class="status-badge"
            :class="'status-badge--' + statusBadge(JUDGE_STATUS_MAP, submission.status).color">
            {{ statusBadge(JUDGE_STATUS_MAP, submission.status).label }}
          </span>
        </div>
        <div class="grid-2 text-sm mb-4" style="color:#6A7086">
          <div>状态: <strong style="color:#D6DEEB">{{ submission.status }}</strong></div>
          <div v-if="submission.score != null">得分: <strong style="color:#D6DEEB">{{ submission.score }}</strong></div>
          <div v-if="submission.execution_time_ms != null">
            执行时间: <strong style="color:#D6DEEB">{{ submission.execution_time_ms }}ms</strong>
          </div>
          <div>提交时间: <strong style="color:#D6DEEB">{{ formatDateTime(submission.created_at) }}</strong></div>
        </div>
      </div>

      <div class="card dark-card mb-4" v-if="submission.stdout">
        <h3 style="margin-bottom:8px;color:#D6DEEB">标准输出</h3>
        <pre class="output-block">{{ submission.stdout }}</pre>
      </div>

      <div class="card dark-card mb-4" v-if="submission.stderr">
        <h3 style="margin-bottom:8px;color:#D6DEEB">错误输出</h3>
        <pre class="output-block output-error">{{ submission.stderr }}</pre>
      </div>

      <div class="card dark-card" v-if="submission.result_details">
        <h3 style="margin-bottom:12px;color:#D6DEEB">测试详情</h3>
        <pre class="output-block">{{ JSON.stringify(submission.result_details, null, 2) }}</pre>
      </div>

      <div v-if="polling" class="text-sm mt-4 flex-center gap-2" style="color:#6A7086">
        <span>判题进行中，自动刷新中...</span>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Dark card overrides ─────────────────────────────────────────────── */
.dark-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

/* ── Terminal output blocks ──────────────────────────────────────────── */
.output-block {
  background: #0F1118;
  color: #D6DEEB;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.65;
  white-space: pre-wrap;
  border: 1px solid #2A3040;
}
.output-error { color: #F5A3AB; }

/* ── Dark-adapted status badges ──────────────────────────────────────── */
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.6;
}
.status-badge--success {
  background: rgba(15, 123, 94, 0.15);
  color: #2EE6A8;
  border: 1px solid rgba(15, 123, 94, 0.25);
}
.status-badge--info {
  background: rgba(88, 102, 196, 0.15);
  color: #8794E8;
  border: 1px solid rgba(88, 102, 196, 0.25);
}
.status-badge--warning {
  background: rgba(181, 118, 14, 0.15);
  color: #F0B94D;
  border: 1px solid rgba(181, 118, 14, 0.25);
}
.status-badge--danger {
  background: rgba(209, 46, 62, 0.15);
  color: #F57A89;
  border: 1px solid rgba(209, 46, 62, 0.25);
}
.status-badge--neutral {
  background: rgba(95, 107, 122, 0.15);
  color: #8A96A8;
  border: 1px solid rgba(95, 107, 122, 0.25);
}
</style>
