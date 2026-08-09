<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import StudentAIGradingResult from '../../components/ai/StudentAIGradingResult.vue'
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

function isResultComplete(result) {
  if (TERMINAL_STATUSES.includes(result.status)) return true
  // graded 可能先于 CodeGrade 明细提交；等明细可见后再停止轮询。
  return result.status === 'graded' && Boolean(result.grading_breakdown)
}

async function fetchResult() {
  try {
    const res = await judgeAPI.getResult(route.params.id)
    submission.value = res.data
    if (isResultComplete(res.data)) {
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
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <h1 class="page-title">判题结果</h1>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="!submission" class="card" style="padding:48px;text-align:center">
        <div class="skeleton" style="height:22px;width:200px;margin:0 auto 12px"></div>
        <div class="skeleton" style="height:14px;width:300px;margin:0 auto"></div>
      </div>

      <template v-else>
        <!-- ── Submission Card ──────────────────────────────────────────── -->
        <div class="card submission-card">
          <div class="flex-between mb-4">
            <h3 class="submission-title">提交 #{{ submission.id }}</h3>
            <span class="badge" :class="'badge-' + statusBadge(JUDGE_STATUS_MAP, submission.status).color">
              {{ statusBadge(JUDGE_STATUS_MAP, submission.status).label }}
            </span>
          </div>
          <div class="submission-meta grid-2">
            <div>状态: <strong>{{ submission.status }}</strong></div>
            <div v-if="submission.score != null">得分: <strong>{{ submission.score }}</strong></div>
            <div v-if="submission.execution_time_ms != null">执行时间: <strong>{{ submission.execution_time_ms }}ms</strong></div>
            <div>提交时间: <strong>{{ formatDateTime(submission.created_at) }}</strong></div>
          </div>
        </div>

        <!-- ── Phase 5：结构化 import 诊断（安全中文文案，不展示裸 traceback） ── -->
        <div v-if="submission.diagnostic" class="card diagnostic-card">
          <span class="diag-icon">⚠</span>
          {{ submission.diagnostic.message }}
        </div>

        <!-- ── Polling ──────────────────────────────────────────────────── -->
        <div v-if="polling" class="polling-hint">
          <span class="spinner-sm"></span>
          <span>判题进行中，自动刷新中...</span>
        </div>

        <!-- ── AI 评分分解（仅 active 模式学生可见） ─────────────────────── -->
        <StudentAIGradingResult
          v-if="submission.grading_breakdown"
          :breakdown="submission.grading_breakdown"
        />

        <!-- ── stdout / stderr ──────────────────────────────────────────── -->
        <div v-if="submission.stdout" class="card output-card">
          <div class="output-label">标准输出</div>
          <pre class="output-block">{{ submission.stdout }}</pre>
        </div>
        <div v-if="submission.stderr" class="card output-card">
          <div class="output-label">标准错误</div>
          <pre class="output-block output-error">{{ submission.stderr }}</pre>
        </div>

      </template>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Submission View — Code Studio
   page-head + submission card + polling + output blocks
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0;
}

/* ── Submission Card ────────────────────────────────────────────────── */
.submission-card { padding: 24px; }
.submission-title { margin: 0; color: var(--ink); font-weight: 600; font-size: 17px; }
.submission-meta { font-size: var(--text-sm); color: var(--text-secondary); }
.submission-meta strong { color: var(--ink); font-weight: 600; }

/* ── Output card ───────────────────────────────────────────────────── */
.output-card { padding: 20px; }
.output-label {
  font-size: var(--text-xs); font-weight: 600;
  color: var(--text-secondary); text-transform: uppercase;
  letter-spacing: 0.05em; margin-bottom: 10px;
}
.output-block {
  background: #0F172A; color: #E2E8F0;
  padding: var(--space-4); border-radius: var(--radius-md);
  overflow-x: auto; font-family: var(--font-mono);
  font-size: var(--text-sm); line-height: 1.7;
  white-space: pre-wrap; border: 1px solid #1E293B;
  margin: 0;
}
.output-error { color: #F5A3AB; }

/* ── Phase 5：结构化诊断（无裸 traceback） ──────────────────────────── */
.diagnostic-card {
  padding: 16px 20px;
  display: flex; align-items: center; gap: 8px;
  background: var(--surface-raised);
  border: 1px dashed var(--warning, #d97706);
  border-radius: var(--radius-md);
  color: var(--warning, #d97706);
  font-size: var(--text-sm); line-height: 1.5;
}
.diag-icon { font-size: 14px; flex-shrink: 0; }

/* ── Polling ────────────────────────────────────────────────────────── */
.polling-hint {
  display: flex; align-items: center; gap: 8px;
  font-size: var(--text-sm); color: var(--text-secondary);
}
.spinner-sm {
  width: 14px; height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
