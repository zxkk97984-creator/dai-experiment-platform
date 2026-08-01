<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import StudentAIGradingResult from '../../components/ai/StudentAIGradingResult.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const route = useRoute(); const app = useAppStore()
const exam = ref(null); const questions = ref([]); const submission = ref(null)
const started = ref(false); const submitted = ref(false); const graded = ref(false)
const timeLeft = ref(0); const answers = ref({}); const loading = ref(true)
let timer = null

// ── 防抖保存 ─────────────────────────────────────────────────────────
const DEBOUNCE_MS = 1000   // 1 秒防抖
const FALLBACK_MS = 30000  // 30 秒兜底
const saveTimers = {}       // qId → setTimeout
const pendingSaves = {}     // qId → value（待发送的数据）
let fallbackTimer = null

/** 刷新单个题目的待保存数据，返回 true=成功 */
async function flushSave(qId) {
  if (saveTimers[qId]) { clearTimeout(saveTimers[qId]); delete saveTimers[qId] }
  const value = pendingSaves[qId]
  if (value === undefined) return true  // 无待保存数据，视为成功
  delete pendingSaves[qId]
  try {
    if (typeof value === 'string') {
      await examsAPI.saveAnswer(route.params.id, qId, { code_answer: value })
    } else {
      await examsAPI.saveAnswer(route.params.id, qId, { selected_options: value })
    }
    return true
  } catch (e) {
    // 仅在用户未做新编辑时恢复旧值，避免覆盖新输入
    if (pendingSaves[qId] === undefined) {
      pendingSaves[qId] = value
    }
    const detail = e.response?.data?.detail?.message
    app.showToast(detail || '自动保存失败，请检查网络连接', 'error')
    return false
  }
}

/** 刷新所有待保存答案，返回 { hasFailures } */
async function flushAllSaves() {
  const ids = Object.keys(pendingSaves)
  if (ids.length === 0) return { hasFailures: false }
  const results = await Promise.all(ids.map(id => flushSave(id)))
  return { hasFailures: results.some(r => !r) }
}

/** 防抖保存入口：立即更新本地状态，1 秒后发送到服务端 */
function saveAnswer(qId, value) {
  // 立即更新本地 UI
  answers.value = { ...answers.value, [qId]: value }
  // 记录待保存数据
  pendingSaves[qId] = value
  // 清除已有定时器，重新计时
  if (saveTimers[qId]) clearTimeout(saveTimers[qId])
  saveTimers[qId] = setTimeout(() => flushSave(qId), DEBOUNCE_MS)
}

/** 启动 30 秒兜底定时器 */
function startFallbackTimer() {
  if (fallbackTimer) clearInterval(fallbackTimer)
  fallbackTimer = setInterval(() => flushAllSaves(), FALLBACK_MS)
}

/** 清理所有定时器 */
function cleanupTimers() {
  clearInterval(timer)
  if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null }
  Object.values(saveTimers).forEach(t => clearTimeout(t))
}

// ── 题型标签 ─────────────────────────────────────────────────────────
const typeLabel = (t) => ({ single_choice: '单选题', multi_choice: '多选题', code: '编程题' }[t] || t)
const answeredCount = computed(() => Object.keys(answers.value).filter(k => answers.value[k] !== '' && answers.value[k] != null && (!Array.isArray(answers.value[k]) || answers.value[k].length > 0)).length)
const totalPoints = computed(() => questions.value.reduce((s,q) => s + (q.points||0), 0))
const progressPercent = computed(() => questions.value.length ? Math.round(answeredCount.value / questions.value.length * 100) : 0)
const timeDisplay = computed(() => { const m = Math.floor(timeLeft.value / 60); const s = timeLeft.value % 60; return m + ':' + s.toString().padStart(2, '0') })
const statusText = computed(() => { if (graded.value) return '已评分：' + (submission.value?.score ?? 0) + ' 分'; if (submitted.value) return '已交卷，等待评分'; return '' })
const hasBreakdown = computed(() => (submission.value?.answers || []).some(a => a.grading_breakdown))

// ── 生命周期 ─────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [eRes, qRes] = await Promise.all([examsAPI.get(route.params.id), examsAPI.getQuestions(route.params.id).catch(() => ({ data: { items: [] } }))])
    exam.value = eRes.data; questions.value = qRes.data?.items || qRes.data || []
    try {
      const gRes = await examsAPI.getMyGrade(route.params.id)
      submission.value = gRes.data
      if (gRes.data.status === 'graded') { graded.value = true; submitted.value = true }
      else if (gRes.data.status !== 'started') { submitted.value = true }
      else { started.value = true; timeLeft.value = Math.max(0, Math.floor((new Date(gRes.data.expires_at).getTime() - Date.now()) / 1000)); startTimer(); startFallbackTimer() }
    } catch { /* 首次进入无提交记录，正常情况 */ }
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}
function startTimer() { clearInterval(timer); timer = setInterval(() => { if (timeLeft.value > 0) timeLeft.value-- }, 1000) }
onMounted(load)
onUnmounted(() => cleanupTimers())

// 路由离开前刷新待保存数据
onBeforeRouteLeave(async (_to, _from, next) => {
  if (started.value && !submitted.value) {
    await flushAllSaves()
  }
  next()
})

// 页面关闭/刷新前尝试保存（浏览器尽力而为）
window.addEventListener('beforeunload', () => {
  if (started.value && !submitted.value) {
    flushAllSaves()
  }
})

// ── 操作 ─────────────────────────────────────────────────────────────
async function startExam() {
  try {
    const res = await examsAPI.start(route.params.id)
    submission.value = res.data; started.value = true
    timeLeft.value = Math.max(0, Math.floor((new Date(res.data.expires_at).getTime() - Date.now()) / 1000))
    startTimer(); startFallbackTimer()

    // 开始成功后重新加载题目（此时已获得查看权限）
    try {
      const qRes = await examsAPI.getQuestions(route.params.id)
      questions.value = qRes.data?.items || qRes.data || []
    } catch {
      app.showToast('题目加载失败，请刷新页面', 'error')
    }
  } catch(e) {
    app.showToast(e.response?.data?.detail?.message || '开始失败', 'error')
  }
}

async function submitExam() {
  if (!confirm('确定要交卷吗？交卷后无法修改答案。')) return
  // 交卷前刷新所有待保存数据
  const flushResult = await flushAllSaves()
  if (flushResult.hasFailures) {
    app.showToast('部分答案保存失败，请检查网络后重试交卷', 'error')
    return
  }
  try {
    const res = await examsAPI.submit(route.params.id, {})
    submission.value = res.data; submitted.value = true
    cleanupTimers()
    app.showToast('交卷成功', 'success')
  } catch(e) {
    app.showToast(e.response?.data?.detail?.message || '交卷失败', 'error')
  }
}

function isSelected(qId, optKey) { const ans = answers.value[qId]; return ans && ans.includes(optKey) }
</script>

<template>
  <AppLayout>
    <!-- ── Loading ──────────────────────────────────────────────────────── -->
    <div v-if="loading" class="card" style="padding:48px;text-align:center">
      <div class="skeleton" style="height:22px;width:240px;margin:0 auto 16px"></div>
      <div class="skeleton" style="height:14px;width:360px;margin:0 auto"></div>
    </div>

    <template v-else>
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <div class="exam-header">
        <div class="header-left">
          <h1 class="exam-title">{{ exam?.title }}</h1>
          <p v-if="statusText" class="status-text">{{ statusText }}</p>
        </div>
        <div v-if="started && !submitted" class="header-right">
          <div class="timer-box">
            <span class="timer-label">剩余时间</span>
            <span class="timer-value">{{ timeDisplay }}</span>
          </div>
        </div>
      </div>

      <!-- ── Graded Result ─────────────────────────────────────────────── -->
      <div v-if="graded" class="card result-card">
        <div class="result-score">{{ submission?.score ?? 0 }} <span class="result-unit">/ {{ totalPoints }} 分</span></div>
        <p class="result-text">考试已完成</p>
      </div>

      <!-- ── Active AI 评分逐题明细（仅对学生显示安全信息） ────────────── -->
      <section v-if="graded && hasBreakdown" class="breakdown-section">
        <h3 class="breakdown-title">AI 评分详情</h3>
        <div v-for="(ans, ai) in (submission?.answers || [])" :key="ai">
          <StudentAIGradingResult
            v-if="ans.grading_breakdown"
            :breakdown="ans.grading_breakdown"
            :heading="'第 ' + (ai + 1) + ' 题'"
          />
        </div>
      </section>

      <!-- ── Submitted ─────────────────────────────────────────────────── -->
      <div v-else-if="submitted" class="card result-card">
        <div class="result-icon">&#10003;</div>
        <p class="result-text">已交卷，等待评分...</p>
      </div>

      <!-- ── Start ─────────────────────────────────────────────────────── -->
      <div v-else-if="!started" class="card start-card">
        <div class="start-info">
          <p>考试时长：<strong>{{ exam?.duration_minutes }} 分钟</strong></p>
          <p>题目数量：<strong>{{ questions.length }} 题</strong></p>
          <p>总分：<strong>{{ totalPoints }} 分</strong></p>
        </div>
        <button class="btn-accent start-btn" @click="startExam">开始考试</button>
      </div>

      <!-- ── Exam Body ─────────────────────────────────────────────────── -->
      <div v-else class="exam-body">
        <div class="progress-wrap">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <span class="progress-text">已答 {{ answeredCount }} / {{ questions.length }} 题（{{ progressPercent }}%）</span>
        </div>

        <div v-for="(q,i) in questions" :key="q.id" class="card question-card" :id="'q-' + q.id">
          <div class="question-header">
            <span class="question-num">第 {{ i + 1 }} 题</span>
            <span class="question-type badge" :class="q.question_type === 'single_choice' ? 'badge-primary' : q.question_type === 'multi_choice' ? 'badge-info' : 'badge-neutral'">
              {{ typeLabel(q.question_type) }}
            </span>
            <span class="question-points">{{ q.points }} 分</span>
          </div>
          <p class="question-prompt">{{ q.prompt }}</p>

          <!-- 单选题 -->
          <div v-if="q.question_type === 'single_choice'" class="options-list">
            <label v-for="(opt,k) in q.options" :key="k" class="option-row" :class="{ selected: isSelected(q.id, k) }">
              <input type="radio" :name="'q'+q.id" class="option-radio" :checked="isSelected(q.id, k)" @change="saveAnswer(q.id, [k])" />
              <span class="option-letter">{{ k }}.</span>
              <span class="option-text">{{ opt }}</span>
            </label>
          </div>

          <!-- 多选题 -->
          <div v-else-if="q.question_type === 'multi_choice'" class="options-list">
            <label v-for="(opt,k) in q.options" :key="k" class="option-row" :class="{ selected: isSelected(q.id, k) }">
              <input type="checkbox" class="option-checkbox" :checked="isSelected(q.id, k)" @change="saveAnswer(q.id, isSelected(q.id, k) ? (answers[q.id]||[]).filter(v=>v!==k) : [...(answers[q.id]||[]),k])" />
              <span class="option-letter">{{ k }}.</span>
              <span class="option-text">{{ opt }}</span>
            </label>
          </div>

          <!-- 编程题 -->
          <div v-else class="code-area">
            <textarea :value="answers[q.id] || q.starter_code || ''" @input="saveAnswer(q.id, $event.target.value)" class="code-editor" rows="8" :placeholder="q.starter_code || '在此编写代码...'"></textarea>
          </div>
        </div>

        <div class="submit-area">
          <button class="btn-accent submit-btn" @click="submitExam">交卷</button>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Exam View — Code Studio
   page-head + timer + option cards + code editor + submit
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page Head ─────────────────────────────────────────────────────── */
.exam-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 24px; flex-wrap: wrap; gap: 12px;
}
.exam-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 4px;
}
.status-text {
  font-size: var(--text-sm); color: var(--text-secondary);
}

/* ── Timer ─────────────────────────────────────────────────────────── */
.timer-box {
  display: flex; flex-direction: column; align-items: center;
  background: var(--accent); color: var(--surface);
  padding: 10px 24px; border-radius: var(--radius-lg);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.25);
}
.timer-label { font-size: 11px; opacity: 0.85; }
.timer-value {
  font-family: var(--font-mono); font-size: 24px; font-weight: 700;
  letter-spacing: 0.04em;
}

/* ── Result / Start cards ──────────────────────────────────────────── */
.result-card {
  text-align: center; padding: 48px 24px;
}
.result-score {
  font-size: 36px; font-weight: 700; color: var(--success);
}
.result-unit {
  font-size: 18px; color: var(--text-secondary); font-weight: 400;
}
.result-text {
  color: var(--text-secondary); margin-top: 8px; font-size: var(--text-sm);
}
.result-icon {
  font-size: 48px; color: var(--success); margin-bottom: 8px;
}

.start-card {
  text-align: center; padding: 56px 24px;
}
.start-info { margin-bottom: 24px; line-height: 2.2; color: var(--ink); font-size: 15px; }
.start-info strong { font-weight: 600; color: var(--ink); }
.start-btn {
  padding: 12px 48px; font-size: 16px; font-weight: 600;
}

/* ── Exam body ─────────────────────────────────────────────────────── */
.exam-body { max-width: 800px; }

/* Progress */
.progress-wrap {
  display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
}
.progress-bar {
  flex: 1; height: 6px; background: var(--surface-raised);
  border-radius: var(--radius-full); overflow: hidden;
}
.progress-fill {
  height: 100%; background: var(--accent);
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}
.progress-text {
  font-size: var(--text-xs); color: var(--text-secondary); white-space: nowrap;
}

/* Question card */
.question-card {
  padding: 24px; margin-bottom: 16px;
}
.question-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.question-num {
  font-size: var(--text-sm); font-weight: 600; color: var(--ink);
}
.question-points {
  font-size: var(--text-xs); color: var(--text-secondary); margin-left: auto;
}
.question-prompt {
  font-size: var(--text-sm); color: var(--ink); line-height: 1.7; margin-bottom: 18px;
}

/* Options */
.options-list { display: flex; flex-direction: column; gap: 2px; }
.option-row {
  display: grid; grid-template-columns: auto auto 1fr; align-items: center;
  gap: 10px; padding: 12px 14px; border-radius: var(--radius-md);
  cursor: pointer; border: 1px solid transparent;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.option-row:hover { background: var(--surface-raised); }
.option-row.selected {
  background: var(--primary-light);
  border-color: var(--primary-soft);
}
.option-radio, .option-checkbox {
  width: 16px; height: 16px; margin: 0;
  accent-color: var(--primary); flex-shrink: 0;
}
.option-letter {
  font-weight: 600; font-size: var(--text-sm); color: var(--ink);
  min-width: 20px;
}
.option-text {
  font-size: var(--text-sm); color: var(--ink);
  line-height: 1.5; word-break: break-word;
}

/* Code editor */
.code-area { margin-top: 8px; }
.code-editor {
  width: 100%; background: #0F172A; color: #E2E8F0;
  border: 1px solid #1E293B; border-radius: var(--radius-md);
  padding: 14px;
  font-family: var(--font-mono); font-size: 13px;
  line-height: 1.65; resize: vertical;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.code-editor:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.12);
}

/* Submit */
.submit-area { text-align: center; padding: 32px 0 48px; }
.submit-btn { padding: 12px 56px; font-size: 16px; font-weight: 600; }

/* ── Active AI 评分逐题明细（学生安全展示） ─────────────────────── */
.breakdown-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
}
.breakdown-title {
  margin: 0;
  color: var(--ink);
  font-size: 15px;
  font-weight: 600;
}

@media (max-width: 640px) {
  .exam-header { flex-direction: column; }
  .option-row { padding: 10px 10px; gap: 8px; }
  .question-card { padding: 18px; }
  .exam-title { font-size: 24px; }
}
</style>
