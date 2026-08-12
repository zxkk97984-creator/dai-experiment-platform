<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import ConfirmDialog from '../../components/ui/ConfirmDialog.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const exams = ref([])
const loading = ref(true)
const waitingExam = ref(null)

const statusMeta = {
  scheduled: { label: '未完成 · 未开始', tone: 'scheduled', action: '查看时间安排' },
  ready: { label: '未完成 · 可开始', tone: 'ready', action: '进入考试' },
  in_progress: { label: '未完成 · 进行中', tone: 'progress', action: '继续答题' },
  submitted: { label: '已完成', tone: 'done', action: '查看提交状态', hint: '等待评分' },
  grading: { label: '已完成', tone: 'done', action: '查看提交状态', hint: '评分中' },
  review_required: { label: '已完成', tone: 'done', action: '查看提交状态', hint: '待教师复核' },
  graded: { label: '已完成', tone: 'done', action: '查看结果', hint: '评分完成' },
  missed: { label: '未完成 · 缺考', tone: 'missed', action: '已错过最晚进入时间' },
}

const totalText = computed(() => `共 ${exams.value.length} 场考试`)
const metaFor = (exam) => statusMeta[exam.student_status] || statusMeta.scheduled

onMounted(async () => {
  try {
    const res = await examsAPI.list()
    exams.value = res.data.items || res.data || []
  } catch {
    app.showToast('考试列表加载失败，请稍后重试', 'error')
  } finally {
    loading.value = false
  }
})

function openExam(exam) {
  if (exam.student_status === 'scheduled') {
    waitingExam.value = exam
    return
  }
  if (exam.student_status === 'missed') return
  router.push(`/student/exams/${exam.id}`)
}
</script>

<template>
  <AppLayout>
    <main class="exam-center">
      <header class="page-head">
        <div>
          <p class="eyebrow">ASSESSMENTS</p>
          <h1>考试中心</h1>
          <p class="subtitle">按服务器时间开放考试，进行中的作答可随时继续</p>
        </div>
        <div class="count-pill"><span></span>{{ totalText }}</div>
      </header>

      <div v-if="loading" class="exam-grid" aria-label="正在加载考试">
        <div v-for="i in 4" :key="i" class="exam-card skeleton-card">
          <div class="skeleton line wide"></div>
          <div class="skeleton line"></div>
          <div class="skeleton line short"></div>
        </div>
      </div>

      <section v-else-if="exams.length === 0" class="empty-card">
        <div class="empty-icon">✓</div>
        <h2>当前没有考试安排</h2>
        <p>教师发布考试后会显示在这里。</p>
      </section>

      <section v-else class="exam-grid" aria-label="考试列表">
        <article
          v-for="exam in exams"
          :key="exam.id"
          class="exam-card"
          :class="[`is-${metaFor(exam).tone}`, { disabled: exam.student_status === 'missed' }]"
        >
          <div class="card-top">
            <span class="status-dot"></span>
            <span class="status-label">{{ metaFor(exam).label }}</span>
            <span v-if="metaFor(exam).hint" class="status-hint">{{ metaFor(exam).hint }}</span>
          </div>
          <h2>{{ exam.title }}</h2>
          <dl>
            <div><dt>考试时长</dt><dd>{{ exam.duration_minutes }} 分钟</dd></div>
            <div><dt>开始时间</dt><dd>{{ formatDateTime(exam.start_at) }}</dd></div>
            <div><dt>最晚进入</dt><dd>{{ formatDateTime(exam.end_at) }}</dd></div>
          </dl>
          <button
            type="button"
            class="card-action"
            :disabled="exam.student_status === 'missed'"
            @click="openExam(exam)"
          >
            {{ metaFor(exam).action }} <span v-if="exam.student_status !== 'missed'">→</span>
          </button>
        </article>
      </section>
    </main>

    <ConfirmDialog
      v-if="waitingExam"
      title="考试尚未开始"
      :message="`本场考试将于 ${formatDateTime(waitingExam.start_at)} 开放。系统以服务器时间为准，请到时再进入。`"
      confirm-text="知道了"
      cancel-text="返回列表"
      @confirm="waitingExam = null"
      @cancel="waitingExam = null"
    />
  </AppLayout>
</template>

<style scoped>
.exam-center { display: flex; flex-direction: column; gap: 26px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.eyebrow { margin: 0 0 8px; color: var(--primary); font: 700 11px/1 var(--font-mono); letter-spacing: .16em; }
h1 { margin: 0; color: var(--ink); font-size: 30px; letter-spacing: -.035em; }
.subtitle { margin: 8px 0 0; color: var(--text-secondary); font-size: 14px; }
.count-pill { display: inline-flex; align-items: center; gap: 9px; padding: 9px 14px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); color: var(--text-secondary); font-size: 13px; }
.count-pill span { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px rgba(16,185,129,.12); }
.exam-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.exam-card { min-height: 252px; padding: 24px; border: 1px solid var(--border); border-radius: 16px; background: var(--surface); box-shadow: 0 8px 24px rgba(15,23,42,.035); transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease; }
.exam-card:not(.disabled):hover { transform: translateY(-2px); border-color: #bfd2ef; box-shadow: 0 12px 28px rgba(30,64,175,.08); }
.card-top { display: flex; align-items: center; gap: 8px; min-height: 24px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
.status-label { font-size: 12px; font-weight: 700; color: #64748b; }
.status-hint { margin-left: auto; padding: 3px 8px; border-radius: 999px; background: #f1f5f9; color: #64748b; font-size: 11px; }
.is-ready .status-dot { background: #16a34a; box-shadow: 0 0 0 4px rgba(22,163,74,.12); }
.is-ready .status-label { color: #15803d; }
.is-progress .status-dot { background: #f97316; box-shadow: 0 0 0 4px rgba(249,115,22,.12); }
.is-progress .status-label { color: #c2410c; }
.is-done .status-dot { background: #2563eb; }
.is-done .status-label { color: #1d4ed8; }
.is-missed { background: #f8fafc; }
.is-missed .status-dot { background: #ef4444; }
.exam-card h2 { margin: 18px 0 20px; color: var(--ink); font-size: 18px; line-height: 1.45; }
dl { display: grid; gap: 9px; margin: 0; padding: 15px 0; border-block: 1px solid var(--border); }
dl div { display: flex; justify-content: space-between; gap: 16px; font-size: 12px; }
dt { color: var(--text-secondary); } dd { margin: 0; color: var(--ink); font-weight: 500; text-align: right; }
.card-action { width: 100%; margin-top: 16px; padding: 7px 0; border: 0; background: transparent; color: var(--primary); font-weight: 650; text-align: left; cursor: pointer; }
.card-action span { float: right; }
.card-action:disabled { color: #94a3b8; cursor: not-allowed; }
.empty-card { padding: 72px 24px; border: 1px dashed var(--border); border-radius: 16px; text-align: center; background: var(--surface); }
.empty-icon { display: grid; place-items: center; width: 46px; height: 46px; margin: 0 auto 14px; border-radius: 14px; background: #ecfdf5; color: #16a34a; font-size: 22px; }
.empty-card h2 { margin: 0 0 7px; font-size: 17px; }.empty-card p { margin: 0; color: var(--text-secondary); font-size: 13px; }
.skeleton-card { pointer-events: none; }.line { height: 13px; width: 55%; margin: 18px 0; }.line.wide { width: 80%; }.line.short { width: 38%; }
@media (max-width: 760px) { .exam-grid { grid-template-columns: 1fr; }.page-head { flex-direction: column; }h1 { font-size: 26px; }.exam-card { min-height: 0; } }
</style>
