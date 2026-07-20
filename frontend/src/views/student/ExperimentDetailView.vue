<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { jupyterAPI } from '../../api/jupyter.js'
import { useAppStore } from '../../stores/app.js'
import { sanitizeHtml } from '../../utils/sanitize.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const module_ = ref(null)
const iframeUrl = ref('')
const loading = ref(true)
const jupyterLoading = ref(false)
const jupyterError = ref('')

// Resizable Jupyter frame
const frameHeight = ref(500)
const isDragging = ref(false)
const frameRef = ref(null)
let dragStartY = 0
let dragStartHeight = 0
let dragStarted = false

function onDragStart(e) {
  e.preventDefault()
  isDragging.value = true
  dragStarted = false
  dragStartY = e.clientY
  dragStartHeight = frameRef.value?.offsetHeight || frameHeight.value
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'ns-resize'
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e) {
  if (!isDragging.value) return
  const delta = e.clientY - dragStartY
  if (!dragStarted && Math.abs(delta) < 5) return
  dragStarted = true
  e.preventDefault()
  frameHeight.value = Math.max(200, dragStartHeight + delta)
}

function onDragEnd() {
  isDragging.value = false
  dragStarted = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
}

onMounted(async () => {
  try {
    const res = await experimentsAPI.getModule(route.params.id)
    module_.value = res.data
  } catch {
    app.showToast('加载实验失败', 'error')
  } finally { loading.value = false }

  // Load JupyterLab in parallel
  jupyterLoading.value = true
  try {
    const jRes = await jupyterAPI.getEntry()
    iframeUrl.value = jRes.data.iframe_url
  } catch {
    jupyterError.value = 'JupyterLab 暂时不可用'
  } finally { jupyterLoading.value = false }
})

function goBack() {
  router.push('/student/experiments')
}
</script>

<template>
  <AppLayout>
    <!-- Back -->
    <button class="btn-ghost btn-sm back-btn" @click="goBack">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 3L5 8l5 5"/>
      </svg>
      返回实验列表
    </button>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <p class="skeleton" style="width:240px;height:28px;margin:0 auto 12px"></p>
      <p class="skeleton" style="width:360px;height:14px;margin:0 auto"></p>
    </div>

    <!-- Error -->
    <div v-else-if="!module_" class="empty-state">
      <p>实验不存在</p>
      <button class="btn-primary" @click="goBack" style="margin-top:12px">返回</button>
    </div>

    <template v-else>
      <!-- Experiment header -->
      <div class="experiment-hero">
        <h1 class="experiment-title">{{ module_.name }}</h1>
        <p class="experiment-desc" v-if="module_.description" v-html="sanitizeHtml(module_.description.replace(/\n/g, '<br>'))"></p>
        <div class="experiment-meta">
          <span class="badge" :class="'badge-' + (module_.status === 'published' ? 'success' : 'neutral')">
            {{ module_.status === 'published' ? '已发布' : module_.status }}
          </span>
        </div>
      </div>

      <!-- JupyterLab workspace -->
      <div class="workspace-section">
        <div class="workspace-header">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="8" height="8" rx="1.5"/><path d="M5.5 3v8M3 5.5h8"/>
          </svg>
          JupyterLab 实验环境
        </div>

        <div v-if="jupyterLoading" class="jupyter-placeholder">
          <span class="spinner"></span>
          <p>正在连接实验环境...</p>
        </div>
        <div v-else-if="jupyterError" class="jupyter-placeholder">
          <p class="text-secondary">{{ jupyterError }}</p>
          <button class="btn-primary" @click="goBack" style="margin-top:8px">返回</button>
        </div>
        <template v-else>
          <div class="jupyter-frame" ref="frameRef" :style="{ height: frameHeight + 'px' }">
            <iframe :src="iframeUrl" frameborder="0" style="width:100%;height:100%;border:none" />
          </div>
          <div class="resize-handle" @mousedown="onDragStart">
            <div class="resize-grip"></div>
          </div>
        </template>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* Back */
.back-btn {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-5);
}
.back-btn:hover { color: var(--text); }

/* Loading */
.loading-state { padding: var(--space-4) 0; text-align: center; }

/* Hero */
.experiment-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  margin-bottom: var(--space-4);
}
.experiment-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 var(--space-3);
  letter-spacing: -0.01em;
}
.experiment-desc {
  font-size: var(--text-sm);
  color: var(--text);
  line-height: 1.75;
  margin-bottom: var(--space-4);
}
.experiment-meta { display: flex; gap: var(--space-2); }

/* Workspace */
.workspace-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.workspace-header {
  display: flex; align-items: center; gap: 8px;
  padding: var(--space-3) var(--space-5);
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text);
}
/* Resize handle — bottom edge, like browser devtools panel resizer */
.resize-handle {
  height: 4px;
  background: var(--border);
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  position: relative;
}
/* Invisible larger hit area */
.resize-handle::before {
  content: '';
  position: absolute;
  inset: -4px 0;
}
.resize-handle:hover,
.resize-handle:active {
  background: var(--border-strong);
}
.resize-grip {
  width: 48px;
  height: 3px;
  border-radius: 2px;
  background: var(--surface);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.resize-handle:hover .resize-grip,
.resize-handle:active .resize-grip {
  opacity: 0.8;
}

/* Prevent text selection while dragging */
.resize-handle:active *,
.resize-handle:active + * {
  user-select: none;
}

.jupyter-frame {
  height: 500px;
  min-height: 200px;
}
.jupyter-placeholder {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.jupyter-placeholder p { font-size: var(--text-sm); }

/* Spinner */
.spinner {
  width: 24px; height: 24px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Shared */
.text-secondary { color: var(--text-secondary); }
.btn-primary {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.btn-primary:hover { background: var(--accent-dark); border-color: var(--accent-dark); }
.empty-state {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state p { font-size: var(--text-sm); margin-bottom: var(--space-3); }
</style>
