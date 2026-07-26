<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { judgeAPI } from '../../api/judge.js'
import { useAppStore } from '../../stores/app.js'
import { sanitizeHtml } from '../../utils/sanitize.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const assignment = ref(null)
const questions = ref([])
const activeQ = ref(0)
const code = ref('')
const submitting = ref(false)
const testing = ref(false)
const bottomTab = ref('self-test')
const showProblem = ref(true)
const customInput = ref('')
const testResult = ref(null)

const MAX_POLL_COUNT = 120

const lineCount = computed(() => {
  let count = 1
  const s = code.value || ''
  for (let i = 0; i < s.length; i++) {
    if (s[i] === '\n') count++
  }
  return count
})

const lineNumbers = computed(() => {
  const nums = []
  for (let i = 1; i <= lineCount.value; i++) nums.push(i)
  return nums.join('\n')
})

const descriptionHtml = computed(() => {
  const desc = questions.value[activeQ.value]?.description
  if (!desc) return ''
  return sanitizeHtml(desc.replace(/\n/g, '<br>'))
})

const publicCasesPretty = computed(() => {
  const cases = questions.value[activeQ.value]?.public_cases
  if (!cases?.length) return ''
  return JSON.stringify(cases, null, 2)
})

const TERMINAL_STATUSES = ['accepted', 'wrong_answer', 'runtime_error', 'time_limit_exceeded', 'system_error']

const TEST_STATUS_ICON = { queued: '⏳', running: '🔄', accepted: '✓', wrong_answer: '✗', runtime_error: '✗', time_limit_exceeded: '⏱', system_error: '✗', no_public_cases: '—' }
const TEST_STATUS_LABEL = { queued: '排队等待判题...', running: '正在判题中...', accepted: '全部测试通过', wrong_answer: '答案错误', runtime_error: '运行错误', time_limit_exceeded: '执行超时', system_error: '系统错误', no_public_cases: '无公开样例' }
const TEST_STATUS_CLASS = { queued: 'muted', running: 'muted', accepted: 'success', wrong_answer: 'error', runtime_error: 'error', time_limit_exceeded: 'warning', system_error: 'error', no_public_cases: 'muted' }

const SUBMIT_STATUS_LABEL = { queued: '⏳ 排队等待判题...', running: '🔄 正在判题中...', accepted: '✓ 全部通过', wrong_answer: '✗ 答案错误', runtime_error: '✗ 运行错误', time_limit_exceeded: '⏱ 执行超时', system_error: '⚠ 系统错误' }

const submitResult = ref(null)
const submitPolling = ref(false)
const completedQuestions = ref(new Set())

let pollTimer = null
let pollCount = 0

onMounted(async () => {
  const results = await Promise.allSettled([
    assignmentsAPI.get(route.params.id),
    assignmentsAPI.getQuestions(route.params.id),
    judgeAPI.list(),
  ])
  if (results[0].status === 'fulfilled') {
    assignment.value = results[0].value.data
  } else {
    app.showToast('加载作业失败', 'error')
  }
  if (results[1].status === 'fulfilled') {
    const qData = results[1].value.data
    questions.value = qData.items || qData || []
  }
  if (results[2].status === 'fulfilled') {
    const subs = results[2].value.data.items || results[2].value.data || []
    for (const s of subs) {
      if (s.status === 'accepted') completedQuestions.value.add(s.question_id)
    }
  }
  if (!assignment.value && questions.value.length === 0) {
    app.showToast('加载作业失败', 'error')
  }
  if (questions.value.length > 0) {
    code.value = questions.value[0].starter_code || ''
  }
})

const currentCompleted = computed(() => {
  const qid = questions.value[activeQ.value]?.id
  return qid != null && completedQuestions.value.has(qid)
})

onUnmounted(() => { stopPolling(); stopSubmitPolling() })

function selectQuestion(idx) {
  stopPolling()
  stopSubmitPolling()
  activeQ.value = idx
  code.value = questions.value[idx]?.starter_code || ''
  testResult.value = null
  submitResult.value = null
  submitPolling.value = false
  bottomTab.value = 'self-test'
}

function syncScroll() {
  const editor = document.getElementById('code-editor')
  const gutter = document.getElementById('code-gutter')
  if (editor && gutter) gutter.scrollTop = editor.scrollTop
}

// ── Self-test ─────────────────────────────────────────────────────────
async function handleSelfTest() {
  const q = questions.value[activeQ.value]
  if (!q) return
  testing.value = true
  testResult.value = null
  try {
    const res = await judgeAPI.sampleRun(q.id, {
      question_id: q.id,
      code: code.value,
      input: customInput.value,
    })
    const submissionId = res.data.id
    if (submissionId != null) {
      pollResult(submissionId)
    } else {
      app.showToast('自测请求未返回有效ID', 'error')
      testing.value = false
    }
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '自测请求失败'
    app.showToast(msg, 'error')
    testing.value = false
  }
}

function pollResult(submissionId) {
  stopPolling()
  pollCount = 0
  let failCount = 0
  pollTimer = setInterval(async () => {
    pollCount++
    try {
      const res = await judgeAPI.getResult(submissionId)
      testResult.value = res.data
      failCount = 0
      if (TERMINAL_STATUSES.includes(res.data.status)) {
        stopPolling()
        testing.value = false
      }
    } catch {
      failCount++
      if (failCount >= 5) {
        stopPolling()
        testing.value = false
        app.showToast('判题服务无响应，请重试', 'error')
      }
    }
    if (pollCount >= MAX_POLL_COUNT) {
      stopPolling()
      testing.value = false
      app.showToast('判题超时，请重试', 'error')
    }
  }, 1000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// ── Submit ────────────────────────────────────────────────────────────
async function handleSubmit() {
  const q = questions.value[activeQ.value]
  if (!q) return
  submitting.value = true
  submitResult.value = null
  bottomTab.value = 'submit'
  const submittingQId = q.id
  try {
    const res = await judgeAPI.submit({ question_id: q.id, code: code.value })
    if (res.data.id != null) {
      pollSubmitResult(res.data.id, submittingQId)
    } else {
      app.showToast('提交未返回有效ID', 'error')
      submitting.value = false
    }
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '提交失败'
    app.showToast(msg, 'error')
    submitting.value = false
  }
}

let submitPollTimer = null
let submitPollCount = 0

// Resizable editor
const editorHeight = ref(300)
let editorDragStartY = 0
let editorDragStartH = 0
let editorDragging = false

function onEditorDragStart(e) {
  e.preventDefault()
  editorDragging = true
  editorDragStartY = e.clientY
  const el = document.getElementById('code-editor')
  editorDragStartH = el?.offsetHeight || editorHeight.value
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'ns-resize'
  document.addEventListener('mousemove', onEditorDragMove)
  document.addEventListener('mouseup', onEditorDragEnd)
}

function onEditorDragMove(e) {
  if (!editorDragging) return
  const delta = e.clientY - editorDragStartY
  if (Math.abs(delta) < 5) return
  e.preventDefault()
  editorHeight.value = Math.max(120, editorDragStartH + delta)
}

function onEditorDragEnd() {
  editorDragging = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  document.removeEventListener('mousemove', onEditorDragMove)
  document.removeEventListener('mouseup', onEditorDragEnd)
}

function pollSubmitResult(submissionId, questionId) {
  stopSubmitPolling()
  submitPolling.value = true
  submitPollCount = 0
  submitPollTimer = setInterval(async () => {
    submitPollCount++
    try {
      const res = await judgeAPI.getResult(submissionId)
      submitResult.value = res.data
      if (TERMINAL_STATUSES.includes(res.data.status)) {
        stopSubmitPolling()
        submitting.value = false
        submitPolling.value = false
        if (res.data.status === 'accepted' && questionId != null) {
          completedQuestions.value.add(questionId)
        }
      }
    } catch { /* ignore */ }
    if (submitPollCount >= MAX_POLL_COUNT) {
      stopSubmitPolling()
      submitting.value = false
      submitPolling.value = false
      app.showToast('判题超时，请重试', 'error')
    }
  }, 1000)
}

function stopSubmitPolling() {
  if (submitPollTimer) { clearInterval(submitPollTimer); submitPollTimer = null }
}
</script>

<template>
  <AppLayout>
    <div v-if="!assignment" class="empty-state">
      <p class="skeleton" style="width:240px;height:28px;margin:0 auto 12px"></p>
      <p class="skeleton" style="width:360px;height:14px;margin:0 auto"></p>
    </div>

    <template v-else>
      <!-- ── Header ──────────────────────────────────────────────────── -->
      <div class="editor-header">
        <button class="btn-ghost btn-sm back-btn" @click="router.push(`/student/courses/${assignment.course_id}`)">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 3L5 8l5 5"/>
          </svg>
          返回
        </button>
        <div class="header-info">
          <h1 class="assignment-title">{{ assignment.title }}</h1>
          <span class="question-nav" v-if="questions.length > 1">
            <button
              v-for="(q, i) in questions"
              :key="q.id"
              class="q-dot"
              :class="{ active: i === activeQ, done: completedQuestions.has(q.id) }"
              @click="selectQuestion(i)"
              :title="q.title"
            >{{ i + 1 }}</button>
          </span>
        </div>
      </div>

      <!-- ── Problem Description ─────────────────────────────────────── -->
      <div class="problem-card" :class="{ collapsed: !showProblem }">
        <div class="problem-header" @click="showProblem = !showProblem">
          <div class="problem-label">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 3h12v10H2z"/><path d="M5 6h6M5 9h4"/>
            </svg>
            题目描述
          </div>
          <button class="btn-ghost btn-sm collapse-btn" :title="showProblem ? '收起' : '展开'">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path :d="showProblem ? 'M3 9l4-4 4 4' : 'M3 5l4 4 4-4'"/>
            </svg>
          </button>
        </div>
        <transition name="problem-collapse">
          <div v-if="showProblem" class="problem-body">
            <div class="problem-desc" v-if="descriptionHtml"
              v-html="descriptionHtml"></div>
            <div class="problem-meta" v-if="questions[activeQ]">
              <div class="meta-item" v-if="questions[activeQ]?.signature || questions[activeQ]?.function_name">
                <span class="meta-label">函数签名</span>
                <code class="meta-code">{{ questions[activeQ]?.signature || questions[activeQ]?.function_name }}</code>
              </div>
              <div class="meta-item" v-if="questions[activeQ]?.public_cases?.length">
                <span class="meta-label">公开样例</span>
                <code class="meta-code pre">{{ publicCasesPretty }}</code>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <div v-if="questions.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
          <rect x="8" y="8" width="32" height="32" rx="4"/>
          <path d="M18 20h12M18 26h8"/>
        </svg>
        <p>暂无题目</p>
      </div>

      <!-- ── Code Editor ─────────────────────────────────────────────── -->
      <div class="editor-panel" v-if="questions.length > 0">
        <!-- File tab bar -->
        <div class="file-tabs">
          <div class="file-tab active">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" class="file-icon">
              <path d="M3.5 1.5h3l3 3v6.5H3.5V1.5z" stroke="currentColor" stroke-width="0.8" fill="none"/>
              <path d="M6.5 1.5V4a.5.5 0 00.5.5h2.5" stroke="currentColor" stroke-width="0.8" fill="none"/>
            </svg>
            {{ questions[activeQ]?.title || 'solution' }}.py
            <span class="file-close">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
                <path d="M2 2l6 6M8 2l-6 6"/>
              </svg>
            </span>
          </div>
        </div>

        <!-- Editor body -->
        <div class="editor-body" :style="{ height: editorHeight + 'px' }">
          <div class="editor-gutter" id="code-gutter">
            <pre>{{ lineNumbers }}</pre>
          </div>
          <textarea
            id="code-editor"
            class="editor-textarea"
            :class="{ completed: currentCompleted }"
            v-model="code"
            @scroll="syncScroll"
            @keydown.tab.prevent="code += '    '"
            spellcheck="false"
            :placeholder="currentCompleted ? '该题目已完成' : '# 在这里编写 Python 代码...'"
            :disabled="currentCompleted"
          ></textarea>
        </div>

        <!-- Editor resize handle -->
        <div class="editor-resize-handle" @mousedown="onEditorDragStart">
          <div class="editor-resize-grip"></div>
        </div>

        <!-- Bottom action tabs -->
        <div class="bottom-section">
          <div class="bottom-tabs">
            <button
              class="bottom-tab"
              :class="{ active: bottomTab === 'self-test' }"
              @click="bottomTab = 'self-test'"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4.5 2L1 7l3.5 5"/><path d="M9.5 2L13 7l-3.5 5"/><path d="M8 1l-2 12"/>
              </svg>
              自测
            </button>
            <button
              class="bottom-tab"
              :class="{ active: bottomTab === 'submit' }"
              @click="bottomTab = 'submit'"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
                <path d="M7 1v8M3 5l4 4 4-4"/><path d="M2 11v1.5h10V11"/>
              </svg>
              提交
            </button>
          </div>

          <!-- Self-test content -->
          <transition name="tab-fade">
            <div v-if="bottomTab === 'self-test'" class="tab-content" key="self-test">
              <div class="self-test-input-group">
                <label class="input-label">自定义输入</label>
                <textarea
                  v-model="customInput"
                  class="custom-input"
                  rows="3"
                  placeholder="输入测试数据（可选）例如: [1, 2, 3, 4, 5]"
                  spellcheck="false"
                ></textarea>
              </div>

              <!-- Terminal output -->
              <div class="terminal-panel" v-if="testResult || testing">
                <div class="terminal-header">
                  <span class="terminal-dot red"></span>
                  <span class="terminal-dot yellow"></span>
                  <span class="terminal-dot green"></span>
                  <span class="terminal-title">运行输出</span>
                </div>
                <div class="terminal-body">
                  <div v-if="testing" class="terminal-line muted">
                    <span class="prompt">$</span> 运行测试中...
                  </div>
                  <template v-else>
                    <div class="terminal-line muted">
                      <span class="prompt">$</span> pytest test_{{ questions[activeQ]?.function_name || 'solution' }}.py
                    </div>
                    <div
                      v-if="testResult?.status && TEST_STATUS_LABEL[testResult.status]"
                      class="terminal-line"
                      :class="TEST_STATUS_CLASS[testResult.status] || 'error'"
                    >
                      <span class="check">{{ TEST_STATUS_ICON[testResult.status] || '✗' }}</span>
                      {{ TEST_STATUS_LABEL[testResult.status] }}
                      <span v-if="testResult.execution_time_ms != null" class="time">({{ testResult.execution_time_ms }}ms)</span>
                    </div>
                  </template>
                </div>
              </div>
            </div>

            <!-- Submit content -->
            <div v-else class="tab-content submit-tab" key="submit">
              <div v-if="!submitResult && !submitPolling" class="submit-hint">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="8" cy="8" r="7"/><path d="M8 5v3M8 11.5v.01"/>
                </svg>
                <span>提交后不可修改，建议先通过自测验证代码正确性</span>
              </div>
              <!-- Submit result -->
              <div v-if="submitPolling || submitResult" class="submit-result-card" :class="{
                'result-pass': submitResult?.status === 'accepted',
                'result-fail': submitResult && submitResult.status !== 'accepted'
              }">
                <div v-if="submitPolling" class="result-status">
                  <span class="spinner-sm"></span> 判题中...
                </div>
                <template v-else>
                  <div class="result-status">
                    <span>{{ SUBMIT_STATUS_LABEL[submitResult?.status] || '✗ ' + submitResult?.status }}</span>
                  </div>
                  <div class="result-meta">
                    <span v-if="submitResult?.execution_time_ms != null">{{ submitResult.execution_time_ms }}ms</span>
                  </div>
                </template>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- ── Action Buttons ───────────────────────────────────────────── -->
      <div class="action-bar" v-if="questions.length > 0">
        <div v-if="currentCompleted" class="completed-badge">✓ 已完成</div>
        <template v-else>
        <button
          class="btn-self-test"
          :disabled="testing || submitting"
          @click="handleSelfTest"
        >
          <svg v-if="!testing" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 2.5L1.5 8 5 13.5"/><path d="M11 2.5l3.5 5.5L11 13.5"/><path d="M9 1.5l-2 13"/>
          </svg>
          <span v-if="testing" class="spinner-sm"></span>
          {{ testing ? '运行中...' : '自测' }}
        </button>
        <button
          class="btn-submit-code"
          :disabled="testing || submitting"
          @click="handleSubmit"
        >
          <svg v-if="!submitting" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M8 1.5v9M3.5 6.5L8 11l4.5-4.5"/><path d="M2.5 13.5v1.5h11V13.5"/>
          </svg>
          <span v-if="submitting" class="spinner-sm"></span>
          {{ submitting ? '提交中...' : '提交代码' }}
        </button>
        </template>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Assignment Detail — IDE-style code workspace
   Design: "Precision Instrument" palette
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Editor Header ───────────────────────────────────────────────────── */
.editor-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.back-btn:hover { color: var(--text); }

.header-info {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
}

.assignment-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.question-nav { display: flex; gap: 4px; flex-shrink: 0; }

.q-dot {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all var(--duration-fast) var(--ease-out);
}
.q-dot:hover { border-color: var(--primary); color: var(--primary); }
.q-dot.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.q-dot.done {
  background: var(--success-light);
  border-color: var(--success);
  color: var(--success);
}

/* ── Problem Card ────────────────────────────────────────────────────── */
.problem-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
  transition: border-color var(--duration-normal) var(--ease-out);
}
.problem-card:hover { border-color: var(--border); }

.problem-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  cursor: pointer;
  user-select: none;
}
.problem-header:hover { background: var(--surface-raised); }
.problem-header:first-child { border-radius: var(--radius-lg) var(--radius-lg) 0 0; }

.problem-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.01em;
}
.problem-label svg { color: var(--text-secondary); }

.collapse-btn {
  color: var(--text-secondary);
  padding: 2px 6px;
  width: auto;
}

.problem-body {
  padding: 0 var(--space-5) var(--space-5);
  border-top: 1px solid var(--border);
}

.problem-desc {
  font-size: var(--text-sm);
  line-height: 1.75;
  color: var(--text);
  padding-top: var(--space-4);
}
.problem-desc :deep(strong) { color: var(--ink); font-weight: 600; }
.problem-desc :deep(code) {
  background: var(--surface-raised);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--danger);
}

.problem-meta { margin-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }

.meta-item { display: flex; flex-direction: column; gap: 4px; }

.meta-label {
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.meta-code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  background: var(--surface-raised);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  color: var(--text);
  line-height: 1.55;
}
.meta-code.pre { white-space: pre; overflow-x: auto; }

/* Collapse transition */
.problem-collapse-enter-active,
.problem-collapse-leave-active {
  transition: all var(--duration-slow) var(--ease-out);
  overflow: hidden;
}
.problem-collapse-enter-from,
.problem-collapse-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.problem-collapse-enter-to,
.problem-collapse-leave-from {
  opacity: 1;
  max-height: 800px;
}

/* ── Editor Panel ────────────────────────────────────────────────────── */
.editor-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--duration-normal) var(--ease-out);
  box-shadow: var(--shadow-sm);
}
.editor-panel:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* File tabs */
.file-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px var(--space-3) 0;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}

.file-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--surface-raised);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  border: 1px solid transparent;
  cursor: default;
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-out);
}
.file-tab.active {
  background: var(--surface);
  color: var(--ink);
  border-color: var(--border);
  border-bottom-color: var(--surface);
  margin-bottom: -1px;
}

.file-icon { color: var(--primary); flex-shrink: 0; }

.file-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  cursor: pointer;
  margin-left: 2px;
  color: var(--text-secondary);
  opacity: 0.5;
  transition: all var(--duration-fast);
}
.file-close:hover { opacity: 1; background: var(--border); }

/* Editor body */
.editor-body {
  display: flex;
  position: relative;
  min-height: 120px;
  height: 300px;
}

/* Editor resize handle */
.editor-resize-handle {
  height: 4px;
  background: var(--border);
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  position: relative;
}
.editor-resize-handle::before {
  content: '';
  position: absolute;
  inset: -4px 0;
}
.editor-resize-handle:hover,
.editor-resize-handle:active {
  background: var(--border-strong);
}
.editor-resize-grip {
  width: 48px;
  height: 3px;
  border-radius: 2px;
  background: var(--surface);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.editor-resize-handle:hover .editor-resize-grip,
.editor-resize-handle:active .editor-resize-grip {
  opacity: 0.8;
}

.editor-gutter {
  flex-shrink: 0;
  width: 48px;
  background: #0F172A;
  border-right: 1px solid #1E293B;
  padding: var(--space-3) 0;
  overflow: hidden;
  user-select: none;
}
.editor-gutter pre {
  padding: 0 var(--space-2);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  color: #4A5568;
  text-align: right;
  margin: 0;
}

.editor-textarea {
  flex: 1;
  background: #0F172A;
  color: #E2E8F0;
  border: none;
  border-radius: 0;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  resize: none;
  tab-size: 4;
  overflow: auto;
  transition: none;
  box-shadow: none;
}
.editor-textarea:focus {
  outline: none;
  border: none;
  box-shadow: none;
  background: #0F172A;
}
.editor-textarea::placeholder { color: #4E5670; }
.editor-textarea.completed { opacity: 0.6; cursor: not-allowed; }
.editor-textarea.completed::placeholder { color: var(--success); }

.completed-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 24px; font-size: var(--text-sm); font-weight: 600;
  color: var(--success); background: var(--success-light);
  border: 1px solid var(--success); border-radius: var(--radius-md);
}

/* ── Bottom Section ──────────────────────────────────────────────────── */
.bottom-section {
  border-top: 1px solid var(--border);
}

.bottom-tabs {
  display: flex;
  gap: 0;
  padding: 0 var(--space-3);
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
}

.bottom-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  letter-spacing: 0.02em;
}
.bottom-tab:hover { color: var(--text); background: var(--border); }
.bottom-tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  background: transparent;
}

.tab-content {
  padding: var(--space-4);
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}
.tab-fade-enter-from,
.tab-fade-leave-to { opacity: 0; }

/* Self-test tab */
.self-test-input-group { margin-bottom: var(--space-4); }

.input-label {
  display: block;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 5px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.custom-input {
  width: 100%;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text);
  resize: vertical;
  line-height: 1.55;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.custom-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--accent-light);
}
.custom-input::placeholder { color: #b0b8c4; }

/* ── Terminal Panel ──────────────────────────────────────────────────── */
.terminal-panel {
  background: #0F172A;
  border: 1px solid #1E293B;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #1E293B;
  border-bottom: 1px solid #1E293B;
  user-select: none;
}

.terminal-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.terminal-dot.red    { background: #E05555; }
.terminal-dot.yellow { background: #D8A723; }
.terminal-dot.green  { background: #3DA069; }

.terminal-title {
  margin-left: 8px;
  font-size: var(--text-xs);
  font-weight: 500;
  color: #6A7086;
  letter-spacing: 0.03em;
}

.terminal-body {
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  min-height: 48px;
  max-height: 220px;
  overflow-y: auto;
}

.terminal-line {
  white-space: pre-wrap;
  word-break: break-all;
}
.terminal-line + .terminal-line { margin-top: 2px; }

.terminal-line .prompt  { color: #3DA069; margin-right: 6px; }
.terminal-line .check   { color: #3DA069; margin-right: 4px; }
.terminal-line .cross   { color: #E05555; margin-right: 4px; }
.terminal-line .time    { color: #6A7086; margin-left: 8px; font-size: 11px; }

.terminal-line.muted   { color: #6A7086; }
.terminal-line.success { color: #A3D9B8; }
.terminal-line.error   { color: #EEA3A3; }
.terminal-line.warning { color: #E0C56A; }
.terminal-line.stdout  { color: #C5CDE0; }
.terminal-line.stderr  { color: #EEA3A3; }

/* ── Submit Tab ──────────────────────────────────────────────────────── */
.submit-tab { padding: var(--space-5) var(--space-4); }

.submit-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--warning-light);
  border: 1px solid var(--warning);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--warning);
  line-height: 1.6;
}
.submit-hint svg { flex-shrink: 0; margin-top: 1px; color: var(--warning); }

/* ── Submit result card ───────────────────── */
.submit-result-card {
  padding: var(--space-4); border-radius: var(--radius-md);
  border: 1px solid var(--border);
}
.submit-result-card.result-pass { background: var(--success-light); border-color: var(--success); }
.submit-result-card.result-fail { background: var(--danger-light);  border-color: var(--danger); }

.result-status {
  font-size: var(--text-md); font-weight: 600; margin-bottom: var(--space-2);
  display: flex; align-items: center; gap: var(--space-2);
}
.result-pass .result-status { color: var(--success); }
.result-fail .result-status { color: var(--danger); }

.result-meta {
  font-size: var(--text-sm); color: var(--text-secondary);
  display: flex; gap: var(--space-4);
}

/* ── Action Bar ──────────────────────────────────────────────────────── */
.action-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
  padding-bottom: var(--space-2);
}

.btn-self-test {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--primary);
  background: var(--surface);
  border: 1px solid var(--primary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  letter-spacing: 0.02em;
}
.btn-self-test:hover {
  background: var(--accent-light);
  border-color: var(--accent-hover);
  color: var(--accent-hover);
}
.btn-self-test:disabled { opacity: 0.45; cursor: not-allowed; }

.btn-submit-code {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 24px;
  font-size: var(--text-sm);
  font-weight: 500;
  color: #fff;
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  letter-spacing: 0.02em;
}
.btn-submit-code:hover {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
}
.btn-submit-code:disabled { opacity: 0.45; cursor: not-allowed; }

/* ── Spinner ─────────────────────────────────────────────────────────── */
.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.25);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.btn-self-test .spinner-sm {
  border-color: rgba(37, 99, 235, 0.2);
  border-top-color: var(--primary);
}

/* ── Responsive ──────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .editor-body { min-height: 120px; }
  .editor-textarea { font-size: 12px; }
  .editor-gutter pre { font-size: 12px; }
  .editor-gutter { width: 36px; }
  .action-bar { flex-direction: column; gap: var(--space-2); }
  .btn-self-test,
  .btn-submit-code { width: 100%; justify-content: center; }
}
</style>
