<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { judgeAPI } from '../../api/judge.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, JUDGE_STATUS_MAP } from '../../utils/status.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const assignment = ref(null)
const questions = ref([])
const activeQ = ref(0)
const code = ref('')
const submitting = ref(false)
const testing = ref(false)
const bottomTab = ref('self-test') // 'self-test' | 'submit'
const showProblem = ref(true)
const customInput = ref('')
const testResult = ref(null)
const lineCount = computed(() => {
  const lines = (code.value || '').split('\n')
  return Math.max(lines.length, 1)
})

const TERMINAL_STATUSES = ['accepted', 'wrong_answer', 'runtime_error', 'time_limit_exceeded', 'system_error']

let pollTimer = null

onMounted(async () => {
  try {
    const [aRes, qRes] = await Promise.all([
      assignmentsAPI.get(route.params.id),
      assignmentsAPI.getQuestions(route.params.id),
    ])
    assignment.value = aRes.data
    questions.value = qRes.data.items || qRes.data || []
    if (questions.value.length > 0) {
      code.value = questions.value[0].starter_code || ''
    }
  } catch { app.showToast('加载作业失败', 'error') }
})

onUnmounted(() => { stopPolling() })

function selectQuestion(idx) {
  activeQ.value = idx
  code.value = questions.value[idx]?.starter_code || ''
  testResult.value = null
  bottomTab.value = 'self-test'
}

function handleCodeInput(e) {
  code.value = e.target.value
}

// ── Line numbers ──────────────────────────────────────────────────────
function lineNumbers() {
  const len = lineCount.value
  return Array.from({ length: len }, (_, i) => i + 1).join('\n')
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
    const res = await judgeAPI.sampleRun(q.id, { question_id: q.id, code: code.value })
    const submissionId = res.data.id
    pollResult(submissionId)
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '自测请求失败'
    app.showToast(msg, 'error')
    testing.value = false
  }
}

function pollResult(submissionId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await judgeAPI.getResult(submissionId)
      testResult.value = res.data
      if (TERMINAL_STATUSES.includes(res.data.status)) {
        stopPolling()
        testing.value = false
      }
    } catch { /* ignore poll errors */ }
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
  try {
    const res = await judgeAPI.submit({ question_id: q.id, code: code.value })
    app.showToast('提交成功', 'success')
    router.push(`/student/submissions/${res.data.id}`)
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '提交失败'
    app.showToast(msg, 'error')
  } finally { submitting.value = false }
}

// ── Computed helpers for test result display ──────────────────────────
const resultStatus = computed(() => {
  if (!testResult.value) return null
  return statusBadge(JUDGE_STATUS_MAP, testResult.value.status)
})

const isTerminal = computed(() => {
  if (!testResult.value) return false
  return TERMINAL_STATUSES.includes(testResult.value.status)
})
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
              :class="{ active: i === activeQ }"
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
            <div class="problem-desc" v-if="questions[activeQ]?.description"
              v-html="questions[activeQ]?.description.replace(/\n/g, '<br>')"></div>
            <div class="problem-meta" v-if="questions[activeQ]">
              <div class="meta-item" v-if="questions[activeQ]?.signature || questions[activeQ]?.function_name">
                <span class="meta-label">函数签名</span>
                <code class="meta-code">{{ questions[activeQ]?.signature || questions[activeQ]?.function_name }}</code>
              </div>
              <div class="meta-item" v-if="questions[activeQ]?.public_cases?.length">
                <span class="meta-label">公开样例</span>
                <code class="meta-code pre">{{ JSON.stringify(questions[activeQ].public_cases, null, 2) }}</code>
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
        <div class="editor-body">
          <div class="editor-gutter" id="code-gutter">
            <pre>{{ lineNumbers() }}</pre>
          </div>
          <textarea
            id="code-editor"
            class="editor-textarea"
            v-model="code"
            @scroll="syncScroll"
            @keydown.tab.prevent="code += '    '"
            spellcheck="false"
            placeholder="# 在这里编写 Python 代码..."
            :rows="Math.max(lineCount, 12)"
          ></textarea>
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
                    <div v-if="testResult?.status === 'accepted'" class="terminal-line success">
                      <span class="check">✓</span> 全部测试通过
                      <span v-if="testResult.execution_time_ms != null" class="time">({{ testResult.execution_time_ms }}ms)</span>
                    </div>
                    <div v-else-if="testResult?.status === 'wrong_answer'" class="terminal-line error">
                      <span class="cross">✗</span> 测试未通过 — 答案错误
                    </div>
                    <div v-else-if="testResult?.status === 'runtime_error'" class="terminal-line error">
                      <span class="cross">✗</span> 运行错误
                    </div>
                    <div v-else-if="testResult?.status === 'time_limit_exceeded'" class="terminal-line warning">
                      <span class="cross">⏱</span> 执行超时
                    </div>
                    <div v-else-if="testResult?.status === 'system_error'" class="terminal-line error">
                      <span class="cross">✗</span> 系统错误
                    </div>
                    <div v-if="testResult?.stdout" class="terminal-line stdout">{{ testResult.stdout }}</div>
                    <div v-if="testResult?.stderr" class="terminal-line stderr">{{ testResult.stderr }}</div>
                    <div v-if="testResult?.score != null" class="terminal-line muted">
                      <span class="prompt">score</span> {{ testResult.score }} / 100
                    </div>
                  </template>
                </div>
              </div>
            </div>

            <!-- Submit content -->
            <div v-if="bottomTab === 'submit'" class="tab-content submit-tab" key="submit">
              <div class="submit-hint">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="8" cy="8" r="7"/><path d="M8 5v3M8 11.5v.01"/>
                </svg>
                <span>提交后不可修改，建议先通过自测验证代码正确性</span>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- ── Action Buttons ───────────────────────────────────────────── -->
      <div class="action-bar" v-if="questions.length > 0">
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
  font-weight: 400;
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
  box-shadow: 0 0 0 3px rgba(26,92,138,0.1);
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
  background: #E0E3EA;
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
  min-height: 280px;
}

.editor-gutter {
  flex-shrink: 0;
  width: 48px;
  background: #1E2230;
  border-right: 1px solid #2A3040;
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
  background: #1A1E2B;
  color: #D6DEEB;
  border: none;
  border-radius: 0;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  resize: none;
  min-height: 280px;
  tab-size: 4;
  overflow: auto;
  transition: none;
  box-shadow: none;
}
.editor-textarea:focus {
  outline: none;
  border: none;
  box-shadow: none;
  background: #181C28;
}
.editor-textarea::placeholder { color: #4E5670; }

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
  background: #0F1118;
  border: 1px solid #1F2330;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #161922;
  border-bottom: 1px solid #1F2330;
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
  background: var(--cta-hover);
  border-color: var(--cta-hover);
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
  border-color: rgba(26,92,138,0.2);
  border-top-color: var(--primary);
}

/* ── Responsive ──────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .editor-body { min-height: 200px; }
  .editor-textarea { min-height: 200px; font-size: 12px; }
  .editor-gutter pre { font-size: 12px; }
  .editor-gutter { width: 36px; }
  .action-bar { flex-direction: column; gap: var(--space-2); }
  .btn-self-test,
  .btn-submit-code { width: 100%; justify-content: center; }
}
</style>
