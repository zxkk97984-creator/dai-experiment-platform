<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const exam = ref(null)
const started = ref(false)
const timeLeft = ref(0)
const answers = ref({})
const submitted = ref(false)
let timer = null

const timeDisplay = computed(() => {
  const m = Math.floor(timeLeft.value / 60)
  const s = timeLeft.value % 60
  return `${m}:${s.toString().padStart(2, '0')}`
})

onMounted(async () => {
  try {
    const res = await examsAPI.get(route.params.id)
    exam.value = res.data
  } catch { app.showToast('加载考试失败', 'error') }
})

onUnmounted(() => { if (timer) clearInterval(timer) })

async function startExam() {
  try {
    await examsAPI.start(route.params.id)
    started.value = true
    timeLeft.value = (exam.value.duration_minutes || 60) * 60
    timer = setInterval(() => {
      if (timeLeft.value > 0) timeLeft.value--
      else { clearInterval(timer); app.showToast('考试时间到', 'warning') }
    }, 1000)
    app.showToast('考试开始', 'success')
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '开始失败', 'error')
  }
}

async function submitExam() {
  try {
    await examsAPI.submit(route.params.id, { answers: answers.value })
    submitted.value = true
    clearInterval(timer)
    app.showToast('交卷成功', 'success')
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '交卷失败', 'error')
  }
}
</script>

<template>
  <AppLayout>
    <div v-if="!exam" class="text-secondary">加载中...</div>
    <template v-else>
      <div class="flex-between mb-4">
        <h1 class="page-title" style="margin-bottom:0">{{ exam.title }}</h1>
        <div v-if="started && !submitted" class="exam-timer">
          {{ timeDisplay }}
        </div>
      </div>

      <div v-if="submitted" class="exam-card exam-submitted">
        <h3>考试已提交</h3>
        <p>请等待教师批阅</p>
      </div>

      <div v-else-if="!started" class="exam-card exam-start-card">
        <p class="exam-duration">时长: {{ exam.duration_minutes }} 分钟</p>
        <button class="btn-primary exam-start-btn" @click="startExam">
          开始考试
        </button>
      </div>

      <div v-else class="exam-card">
        <p class="text-secondary mb-4">考试进行中，请在下方作答</p>
        <textarea v-model="answers.content" rows="12" class="code-editor"
          placeholder="在此作答..."></textarea>
        <button class="btn-primary mt-4" @click="submitExam" style="padding:10px 32px">
          交卷
        </button>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Timer badge ─────────────────────────────────────────────────────── */
.exam-timer {
  background: #1A1E2B;
  border: 2px solid #E0553D;
  color: #E0553D;
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: var(--radius-md);
}

/* ── Dark cards ───────────────────────────────────────────────────────── */
.exam-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.exam-start-card {
  text-align: center;
  padding: 48px;
}

.exam-duration {
  color: #6A7086;
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}

.exam-start-btn {
  padding: 12px 40px !important;
  font-size: 16px !important;
  font-weight: 600 !important;
}

/* ── Submitted state ─────────────────────────────────────────────────── */
.exam-submitted {
  text-align: center;
  padding: 48px;
}
.exam-submitted h3 {
  color: var(--success);
  font-size: var(--text-lg);
  margin-bottom: var(--space-4);
}
.exam-submitted p {
  color: #6A7086;
}

/* ── Answer textarea ─────────────────────────────────────────────────── */
.code-editor {
  width: 100%;
  background: #1A1E2B;
  color: #D6DEEB;
  border: 1px solid #2A3040;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.65;
  resize: vertical;
}
.code-editor:focus {
  outline: none;
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.18);
}
</style>
