<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const route = useRoute(); const app = useAppStore()
const exam = ref(null); const questions = ref([]); const submission = ref(null)
const started = ref(false); const submitted = ref(false); const graded = ref(false)
const timeLeft = ref(0); const answers = ref({}); const loading = ref(true)
let timer = null

const typeLabel = (t) => ({ single_choice: '单选题', multi_choice: '多选题', code: '编程题' }[t] || t)
const answeredCount = computed(() => Object.keys(answers.value).filter(k => answers.value[k] !== '' && answers.value[k] != null && (!Array.isArray(answers.value[k]) || answers.value[k].length > 0)).length)
const totalPoints = computed(() => questions.value.reduce((s,q) => s + (q.points||0), 0))
const progressPercent = computed(() => questions.value.length ? Math.round(answeredCount.value / questions.value.length * 100) : 0)
const timeDisplay = computed(() => { const m = Math.floor(timeLeft.value / 60); const s = timeLeft.value % 60; return m + ':' + s.toString().padStart(2, '0') })
const statusText = computed(() => { if (graded.value) return '已评分：' + (submission.value?.score ?? 0) + ' 分'; if (submitted.value) return '已交卷，等待评分'; return '' })

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
      else { started.value = true; timeLeft.value = Math.max(0, Math.floor((new Date(gRes.data.expires_at).getTime() - Date.now()) / 1000)); startTimer() }
    } catch {}
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}
function startTimer() { clearInterval(timer); timer = setInterval(() => { if (timeLeft.value > 0) timeLeft.value-- }, 1000) }
onMounted(load); onUnmounted(() => clearInterval(timer))
async function startExam() { try { const res = await examsAPI.start(route.params.id); submission.value = res.data; started.value = true; timeLeft.value = Math.max(0, Math.floor((new Date(res.data.expires_at).getTime() - Date.now()) / 1000)); startTimer() } catch(e) { app.showToast(e.response?.data?.detail?.message || '开始失败', 'error') } }
async function saveAnswer(qId, value) { answers.value = { ...answers.value, [qId]: value }; try { if (typeof value === 'string') await examsAPI.saveAnswer(route.params.id, qId, { code_answer: value }); else await examsAPI.saveAnswer(route.params.id, qId, { selected_options: value }) } catch {} }
async function submitExam() { if (!confirm('确定要交卷吗？交卷后无法修改答案。')) return; try { const res = await examsAPI.submit(route.params.id, {}); submission.value = res.data; submitted.value = true; clearInterval(timer); app.showToast('交卷成功', 'success') } catch(e) { app.showToast(e.response?.data?.detail?.message || '交卷失败', 'error') } }
function isSelected(qId, optKey) { const ans = answers.value[qId]; return ans && ans.includes(optKey) }
</script>
<template>
  <AppLayout>
    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <div class="exam-header">
        <div class="header-left">
          <h1 class="exam-title">{{ exam?.title }}</h1>
          <div v-if="statusText" class="status-text">{{ statusText }}</div>
        </div>
        <div v-if="started && !submitted" class="header-right">
          <div class="timer-box">
            <span class="timer-label">剩余时间</span>
            <span class="timer-value">{{ timeDisplay }}</span>
          </div>
        </div>
      </div>

      <div v-if="graded" class="result-card">
        <div class="result-score">{{ submission?.score ?? 0 }} <span class="result-unit">/ {{ totalPoints }} 分</span></div>
        <p class="result-text">考试已完成</p>
      </div>

      <div v-else-if="submitted" class="result-card">
        <div class="result-icon">&#10003;</div>
        <p class="result-text">已交卷，等待评分...</p>
      </div>

      <div v-else-if="!started" class="start-card">
        <div class="start-info">
          <p>考试时长：<strong>{{ exam?.duration_minutes }} 分钟</strong></p>
          <p>题目数量：<strong>{{ questions.length }} 题</strong></p>
          <p>总分：<strong>{{ totalPoints }} 分</strong></p>
        </div>
        <button class="start-btn" @click="startExam">开始考试</button>
      </div>

      <div v-else class="exam-body">
        <div class="progress-bar-wrap">
          <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPercent + '%' }"></div></div>
          <span class="progress-text">已答 {{ answeredCount }} / {{ questions.length }} 题（{{ progressPercent }}%）</span>
        </div>

        <div v-for="(q,i) in questions" :key="q.id" class="question-card" :id="'q-' + q.id">
          <div class="question-header">
            <span class="question-num">第 {{ i + 1 }} 题</span>
            <span class="question-type">{{ typeLabel(q.question_type) }}</span>
            <span class="question-points">{{ q.points }} 分</span>
          </div>
          <p class="question-prompt">{{ q.prompt }}</p>

          <div v-if="q.question_type === 'single_choice'" class="options-list">
            <label v-for="(opt,k) in q.options" :key="k" class="option-row" :class="{ selected: isSelected(q.id, k) }">
              <input type="radio" :name="'q'+q.id" class="option-radio" :checked="isSelected(q.id, k)" @change="saveAnswer(q.id, [k])" />
              <span class="option-letter">{{ k }}.</span>
              <span class="option-text">{{ opt }}</span>
            </label>
          </div>

          <div v-else-if="q.question_type === 'multi_choice'" class="options-list">
            <label v-for="(opt,k) in q.options" :key="k" class="option-row" :class="{ selected: isSelected(q.id, k) }">
              <input type="checkbox" class="option-checkbox" :checked="isSelected(q.id, k)" @change="saveAnswer(q.id, isSelected(q.id, k) ? (answers[q.id]||[]).filter(v=>v!==k) : [...(answers[q.id]||[]),k])" />
              <span class="option-letter">{{ k }}.</span>
              <span class="option-text">{{ opt }}</span>
            </label>
          </div>

          <div v-else class="code-area">
            <textarea :value="answers[q.id] || q.starter_code || ''" @input="saveAnswer(q.id, $event.target.value)" class="code-editor" rows="8" :placeholder="q.starter_code || '在此编写代码...'"></textarea>
          </div>
        </div>

        <div class="submit-area">
          <button class="submit-btn" @click="submitExam">交卷</button>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
.loading { padding: 48px; text-align: center; color: #6b7280; }

.exam-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.exam-title { font-size: 20px; font-weight: 600; margin: 0 0 4px 0; }
.status-text { font-size: 13px; color: #6b7280; }
.header-right { flex-shrink: 0; }
.timer-box { display: flex; flex-direction: column; align-items: center; background: #f97316; color: #fff; padding: 8px 20px; border-radius: 8px; }
.timer-label { font-size: 11px; opacity: .85; }
.timer-value { font-family: monospace; font-size: 22px; font-weight: 700; }

.result-card { text-align: center; padding: 48px 24px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }
.result-score { font-size: 36px; font-weight: 700; color: #16a34a; }
.result-unit { font-size: 18px; color: #6b7280; font-weight: 400; }
.result-text { color: #6b7280; margin-top: 8px; font-size: 14px; }
.result-icon { font-size: 48px; color: #16a34a; margin-bottom: 8px; }

.start-card { text-align: center; padding: 48px 24px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }
.start-info { margin-bottom: 24px; line-height: 2; color: #374151; font-size: 15px; }
.start-btn { padding: 12px 48px; background: #f97316; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
.start-btn:hover { background: #ea580c; }

.exam-body { max-width: 800px; }

.progress-bar-wrap { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.progress-bar { flex: 1; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: #f97316; border-radius: 3px; transition: width .3s; }
.progress-text { font-size: 12px; color: #6b7280; white-space: nowrap; }

.question-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.question-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.question-num { font-size: 14px; font-weight: 600; color: #374151; }
.question-type { font-size: 11px; padding: 2px 10px; border-radius: 4px; background: #eff6ff; color: #2563eb; font-weight: 500; }
.question-points { font-size: 12px; color: #6b7280; margin-left: auto; }
.question-prompt { font-size: 14px; color: #374151; line-height: 1.7; margin-bottom: 16px; }

.options-list { display: flex; flex-direction: column; gap: 1px; }
.option-row { display: grid; grid-template-columns: auto auto 1fr; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 6px; cursor: pointer; transition: background .15s; border: 1px solid transparent; }
.option-row:hover { background: #f9fafb; }
.option-row.selected { background: #eff6ff; border-color: #93c5fd; }
.option-radio, .option-checkbox { width: 16px; height: 16px; margin: 0; accent-color: #2563eb; flex-shrink: 0; }
.option-letter { font-weight: 600; font-size: 14px; color: #374151; min-width: 20px; }
.option-text { font-size: 14px; color: #374151; line-height: 1.5; word-break: break-word; }

.code-area { margin-top: 8px; }
.code-editor { width: 100%; background: #0f172a; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 6px; padding: 14px; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.6; resize: vertical; box-sizing: border-box; }
.code-editor:focus { outline: none; border-color: #f97316; }

.submit-area { text-align: center; padding: 24px 0 48px; }
.submit-btn { padding: 12px 56px; background: #f97316; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
.submit-btn:hover { background: #ea580c; }

@media (max-width: 640px) {
  .exam-header { flex-direction: column; }
  .option-row { padding: 10px 10px; gap: 8px; }
  .question-card { padding: 14px; }
}
</style>
