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

    <div v-if="!submission" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">加载中...</p>
    </div>

    <template v-else>
      <div class="card mb-4">
        <div class="flex-between mb-4">
          <h3 style="margin:0">提交 #{{ submission.id }}</h3>
          <span class="badge"
            :class="'badge-' + statusBadge(JUDGE_STATUS_MAP, submission.status).color"
            style="font-size:14px;padding:4px 12px">
            {{ statusBadge(JUDGE_STATUS_MAP, submission.status).label }}
          </span>
        </div>
        <div class="grid-2 text-sm text-secondary mb-4">
          <div>状态: <strong>{{ submission.status }}</strong></div>
          <div v-if="submission.score != null">得分: <strong>{{ submission.score }}</strong></div>
          <div v-if="submission.execution_time_ms != null">
            执行时间: <strong>{{ submission.execution_time_ms }}ms</strong>
          </div>
          <div>提交时间: <strong>{{ formatDateTime(submission.created_at) }}</strong></div>
        </div>
      </div>

      <div class="card mb-4" v-if="submission.stdout">
        <h3 style="margin-bottom:8px">标准输出</h3>
        <pre class="output-block">{{ submission.stdout }}</pre>
      </div>

      <div class="card mb-4" v-if="submission.stderr">
        <h3 style="margin-bottom:8px">错误输出</h3>
        <pre class="output-block output-error">{{ submission.stderr }}</pre>
      </div>

      <div class="card" v-if="submission.result_details">
        <h3 style="margin-bottom:12px">测试详情</h3>
        <pre class="output-block">{{ JSON.stringify(submission.result_details, null, 2) }}</pre>
      </div>

      <div v-if="polling" class="text-sm text-secondary mt-4 flex-center gap-2">
        <span>判题进行中，自动刷新中...</span>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
.output-block {
  background: #1e2532; color: #e5e7eb; padding: 16px; border-radius: 6px;
  overflow-x: auto; font-family: var(--font-mono); font-size: 13px; white-space: pre-wrap;
}
.output-error { color: #fca5a5; }
</style>
