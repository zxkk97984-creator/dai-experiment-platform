<script setup>
// 构建任务 tab：任务列表 + 2 秒轮询 + 脱敏日志（<pre> 纯文本）+ 失败重试
import { ref, onMounted, computed, watch, onBeforeUnmount } from 'vue'
import { environmentsAPI } from '../../../api/environments.js'
import { useAppStore } from '../../../stores/app.js'
import { statusBadge } from '../../../utils/status.js'

const app = useAppStore()
const builds = ref([])
const loading = ref(true)
const activeLog = ref(null)   // 当前查看日志的任务
const logText = ref('')
const logLoading = ref(false)

const BUILD_STATUS_MAP = {
  queued: { label: '排队中', color: 'info' },
  building: { label: '构建中', color: 'warning' },
  succeeded: { label: '成功', color: 'success' },
  failed: { label: '失败', color: 'danger' },
  timed_out: { label: '超时', color: 'danger' },
}

const hasActive = computed(() =>
  builds.value.some((b) => b.status === 'queued' || b.status === 'building'),
)

function fmtTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 19)
}

async function fetchBuilds() {
  try {
    const res = await environmentsAPI.listBuilds(100)
    builds.value = res.data || []
  } catch {
    app.showToast('加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function openLog(job) {
  activeLog.value = job
  logText.value = ''
  logLoading.value = true
  try {
    const res = await environmentsAPI.getBuildLog(job.id)
    logText.value = res.data?.log_text || ''
  } catch {
    logText.value = '日志加载失败'
  } finally {
    logLoading.value = false
  }
}

function closeLog() {
  activeLog.value = null
  logText.value = ''
}

async function handleRetry(job) {
  try {
    await environmentsAPI.retryBuild(job.id)
    app.showToast('已重新入队', 'success')
    fetchBuilds()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '重试失败', 'error')
  }
}

// 有进行中任务时每 2 秒轮询；组件卸载后停止 timer
let timer = null
function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
watch(hasActive, (active) => {
  stopPolling()
  if (active) timer = setInterval(fetchBuilds, 2000)
})

onMounted(fetchBuilds)
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="panel">
    <div class="panel-bar">
      <p class="panel-hint">
        构建任务由单并发 Builder Worker 执行；queued/building 每 2 秒自动刷新。
      </p>
      <button class="btn-ghost" @click="fetchBuilds">刷新</button>
    </div>

    <div v-if="loading" class="card table-card">
      <div class="skeleton-row" v-for="i in 4" :key="i">
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-20"></div>
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-20"></div>
        <div class="skeleton skel-cell w-20"></div>
      </div>
    </div>
    <div v-else-if="builds.length === 0" class="empty-state">
      <p>🛠 暂无构建任务</p>
    </div>
    <div v-else class="card table-card">
      <table>
        <thead>
          <tr><th>任务 ID</th><th>档位版本</th><th>状态</th><th>尝试</th><th>开始 / 结束</th><th>镜像</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="job in builds" :key="job.id">
            <td class="mono">{{ job.id }}</td>
            <td>
              {{ job.profile_display_name || `版本 #${job.environment_version_id}` }}
              <span v-if="job.version_number" class="vnum">v{{ job.version_number }}</span>
            </td>
            <td>
              <span class="badge" :class="'badge-' + statusBadge(BUILD_STATUS_MAP, job.status).color">
                {{ statusBadge(BUILD_STATUS_MAP, job.status).label }}
              </span>
            </td>
            <td class="mono">{{ job.attempt_number }}</td>
            <td class="text-secondary text-sm">
              {{ fmtTime(job.started_at) }}<br />{{ fmtTime(job.finished_at) }}
            </td>
            <td>
              <span v-if="job.image_digest_short" class="mono digest-short" :title="job.image_digest_short">
                {{ job.image_digest_short }}
              </span>
              <span v-else class="text-tertiary text-sm">—</span>
            </td>
            <td class="actions-cell">
              <button class="btn-ghost btn-sm log-btn" @click="openLog(job)">日志</button>
              <button
                v-if="job.status === 'failed' || job.status === 'timed_out'"
                class="btn-sm retry-btn"
                @click="handleRetry(job)"
              >重试</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 日志弹层：<pre> 纯文本，禁止 v-html ──────────────────────── -->
    <div v-if="activeLog" class="log-overlay" @click.self="closeLog">
      <div class="log-dialog">
        <div class="log-head">
          <h3>构建日志 #{{ activeLog.id }}</h3>
          <button class="btn-ghost btn-sm" @click="closeLog">关闭</button>
        </div>
        <pre v-if="logLoading" class="log-text">加载中…</pre>
        <pre v-else class="log-text">{{ logText }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.panel-hint { margin: 0; font-size: var(--text-xs); color: var(--muted); }
.mono { font-family: var(--font-mono, ui-monospace, monospace); font-size: 12px; }
.vnum {
  display: inline-block; margin-left: 6px; padding: 1px 6px;
  font-size: 11px; border-radius: var(--radius-sm);
  background: var(--accent-soft); color: var(--accent);
}
.digest-short { color: var(--muted); }
.actions-cell {
  display: table-cell;
  vertical-align: middle;
  white-space: nowrap;
}
.actions-cell button + button { margin-left: 8px; }

.log-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: oklch(0.2 0.01 150 / 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.log-dialog {
  width: min(880px, 92vw); max-height: 80vh;
  display: flex; flex-direction: column;
  background: var(--surface, var(--surface));
  border-radius: var(--radius-card, 12px);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}
.log-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border, var(--border));
}
.log-head h3 { margin: 0; font-size: 15px; }
.log-text {
  margin: 0; padding: 16px 18px;
  overflow: auto; white-space: pre-wrap; word-break: break-all;
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 12px; line-height: 1.6;
  background: var(--fg); color: var(--border-strong);
}
</style>
