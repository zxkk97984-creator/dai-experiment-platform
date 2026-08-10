<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import ExamAnswerGroups from '../../components/teacher/exam/ExamAnswerGroups.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { formatDateTime } from '../../utils/format.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const loading = ref(true)
const payload = ref({ exam: {}, student: {}, submission: {}, analysis: {}, answers: [] })
const totalScore = computed(() => Number(payload.value.submission.score || 0))
const totalPossible = computed(() => payload.value.answers.reduce((sum, answer) => sum + Number(answer.points || 0), 0) || 100)
const scorePercent = computed(() => Math.min(100, Math.round(totalScore.value * 100 / totalPossible.value)))
const accuracy = computed(() => payload.value.analysis.question_count ? Math.round(payload.value.analysis.correct_count * 100 / payload.value.analysis.question_count) : 0)
const rankPercent = computed(() => Math.min(99, Math.max(1, scorePercent.value)))

function printReport() { window.print() }
async function load() {
  loading.value = true
  try {
    const res = await examsAPI.getGradeDetail(route.params.id, route.params.submissionId)
    payload.value = res.data
  } catch { app.showToast('加载成绩详情失败', 'error') }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <main v-if="!loading" class="detail-page">
      <button class="back-link" @click="router.push(`/teacher/exams/${route.params.id}/grades`)"><AppIcon name="back" :size="17" />返回成绩总览</button>
      <header class="page-head"><div><h1>学生成绩详情</h1><p>考试名称：{{ payload.exam.title }}</p></div></header>

      <section class="identity-card">
        <div class="identity-item student"><span class="avatar">{{ payload.student.name?.slice(0, 1) || '学' }}</span><span><small>学生姓名</small><strong>{{ payload.student.name }}</strong></span></div>
        <div class="identity-item"><span class="identity-icon blue"><AppIcon name="user" :size="21" /></span><span><small>学号</small><strong>{{ payload.student.number }}</strong></span></div>
        <div class="identity-item"><span class="identity-icon purple"><AppIcon name="exam" :size="21" /></span><span><small>考试名称</small><strong>{{ payload.exam.title }}</strong></span></div>
        <div class="identity-item"><span class="identity-icon green"><AppIcon name="course" :size="21" /></span><span><small>所属课程</small><strong>{{ payload.exam.course_title }}</strong></span></div>
        <div class="identity-item"><span class="identity-icon orange"><AppIcon name="clock" :size="21" /></span><span><small>提交时间</small><strong>{{ formatDateTime(payload.submission.submitted_at) }}</strong></span></div>
        <div class="final-score"><small>总分</small><strong>{{ payload.submission.score ?? '—' }}<em> 分</em></strong><span class="complete-pill">已完成</span></div>
      </section>

      <section class="content-grid">
        <article class="question-panel"><h2>题目得分明细</h2><ExamAnswerGroups :answers="payload.answers" /></article>

        <aside class="analysis-column"><article class="analysis-card"><h2>成绩分析</h2><div class="analysis-grid"><span><i class="analysis-icon blue"><AppIcon name="clipboard" :size="20" /></i><small>客观题得分</small><strong>{{ payload.analysis.objective_score }} <em>/ {{ payload.analysis.objective_total }}</em></strong></span><span><i class="analysis-icon green"><AppIcon name="code" :size="20" /></i><small>编程题得分</small><strong>{{ payload.analysis.code_score }} <em>/ {{ payload.analysis.code_total }}</em></strong></span><span><i class="analysis-icon purple"><AppIcon name="pie" :size="20" /></i><small>正确率</small><strong>{{ accuracy }}%</strong></span><span><i class="analysis-icon slate"><AppIcon name="clock" :size="20" /></i><small>用时</small><strong>{{ payload.submission.elapsed_minutes ?? '—' }} <em>分钟</em></strong></span><span><i class="analysis-icon purple"><AppIcon name="user" :size="20" /></i><small>成绩水平</small><strong>{{ scorePercent >= 90 ? '优秀' : scorePercent >= 60 ? '合格' : '待提升' }}</strong></span><span><i class="analysis-icon blue"><AppIcon name="trophy" :size="20" /></i><small>超过参考</small><strong>{{ rankPercent }}%</strong></span></div></article>

          <article class="teacher-card"><h2>评阅说明</h2><p v-if="payload.submission.review_reason">{{ payload.submission.review_reason }}</p><p v-else>系统已完成本次考试评分。可展开左侧题目查看学生作答与逐题得分。</p></article>

          <article class="ability-card"><h2>能力维度分析</h2><div class="score-ring" :style="{ background: `conic-gradient(#2f72f3 0 ${scorePercent}%, #e8eef8 ${scorePercent}% 100%)` }"><span><strong>{{ payload.submission.score ?? '—' }}</strong><small>总分</small></span></div><div class="dimension-list"><span><small>基础知识</small><strong>{{ payload.analysis.objective_score }} / {{ payload.analysis.objective_total }}</strong><i><b :style="{ width: `${payload.analysis.objective_total ? payload.analysis.objective_score / payload.analysis.objective_total * 100 : 0}%` }"></b></i></span><span><small>程序设计能力</small><strong>{{ payload.analysis.code_score }} / {{ payload.analysis.code_total }}</strong><i><b :style="{ width: `${payload.analysis.code_total ? payload.analysis.code_score / payload.analysis.code_total * 100 : 0}%` }"></b></i></span><span><small>总体完成度</small><strong>{{ scorePercent }}%</strong><i><b :style="{ width: `${scorePercent}%` }"></b></i></span></div></article>
        </aside>
      </section>

      <footer class="action-footer"><button @click="printReport"><AppIcon name="clipboard" :size="18" />打印 / 保存 PDF</button><button class="btn-primary" @click="router.push(`/teacher/exams/${route.params.id}/grades`)">返回成绩总览</button></footer>
    </main>
    <main v-else class="detail-loading"><span v-for="i in 6" :key="i" class="skeleton"></span></main>
  </AppLayout>
</template>

<style scoped>
.detail-page{display:flex;flex-direction:column;gap:15px;padding-bottom:78px}.back-link{align-self:flex-start;padding:0;border:0;color:var(--primary);background:transparent}.page-head h1{margin:0 0 4px;color:var(--ink);font-size:28px;letter-spacing:-.025em}.page-head p{margin:0;color:var(--text-secondary);font-size:14px}
.identity-card{display:grid;grid-template-columns:1.1fr repeat(4,1fr) 1.05fr;align-items:center;min-height:88px;padding:13px 17px;border:1px solid var(--border);border-radius:12px;background:#fff}.identity-item{display:flex;align-items:center;gap:10px;min-width:0;padding:0 12px}.identity-item.student{padding-left:0}.avatar,.identity-icon{display:grid;place-items:center;flex:none;width:42px;height:42px;border-radius:50%}.avatar{color:#fff;background:linear-gradient(135deg,#7a9cf4,#4e6ed0)}.identity-icon{border-radius:12px}.identity-icon.blue{color:var(--primary);background:#edf4ff}.identity-icon.purple{color:#7c4ce0;background:#f2ebfd}.identity-icon.green{color:#0aa568;background:#e8f8f0}.identity-icon.orange{color:#ef8a0b;background:#fff3e4}.identity-item span:last-child{min-width:0}.identity-item small,.identity-item strong{display:block}.identity-item small{color:var(--text-secondary);font-size:12px}.identity-item strong{overflow:hidden;margin-top:3px;color:var(--ink);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.final-score{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding-left:18px;border-left:1px solid var(--border)}.final-score small{color:var(--text-secondary);font-size:12px}.final-score strong{color:var(--primary);font-size:26px;line-height:1}.final-score em{font-size:12px;font-style:normal}.complete-pill{grid-column:2;grid-row:1/3;align-self:center;padding:4px 9px;border-radius:999px;color:#07985e;background:#e8f8f0;font-size:11px}
.content-grid{display:grid;grid-template-columns:1.12fr .88fr;gap:15px}.question-panel,.analysis-card,.teacher-card,.ability-card{border:1px solid var(--border);border-radius:12px;background:#fff;box-shadow:var(--shadow-card)}.question-panel{overflow:hidden}.question-panel>h2,.analysis-card>h2,.teacher-card h2,.ability-card h2{margin:0;color:var(--ink);font-size:15px}.question-panel>h2{padding:16px 18px}.question-group{margin:0 14px 12px;border:1px solid var(--border);border-radius:8px;overflow:hidden}.question-group>header{display:flex;justify-content:space-between;padding:10px 12px;background:#f4f7fb;color:var(--ink);font-size:13px}.question-group>header span{font-weight:600}.question-row{border-top:1px solid var(--border)}.question-row:first-of-type{border-top:0}.question-row>button{display:grid;grid-template-columns:25px 1fr 65px 78px 18px;align-items:center;gap:8px;width:100%;padding:9px 10px;border:0;border-radius:0;background:#fff;text-align:left}.question-row>button:hover{background:#f8fafc}.question-number{display:grid;place-items:center;width:22px;height:22px;border-radius:6px;color:var(--primary);background:var(--primary-light);font-size:11px}.question-prompt{overflow:hidden;color:var(--text-secondary);font-size:12px;text-overflow:ellipsis;white-space:nowrap}.question-row>button strong{color:var(--ink);font-size:12px;text-align:right}.answer-state{font-size:11px;text-align:center}.answer-state.correct{color:#07985e}.answer-state.partial{color:#e68309}.answer-state.wrong{color:#dc3e49}.answer-state.pending{color:#64748b}.answer-detail{padding:12px 16px;border-top:1px dashed var(--border);background:#f8fafc}.answer-detail small{display:block;margin-bottom:5px;color:var(--text-secondary)}.answer-detail p{margin:0;color:var(--ink);font-size:13px}.answer-detail pre{max-height:230px;margin:0;overflow:auto;padding:12px;border-radius:8px;color:#dce7f7;background:#142034;font-family:var(--font-mono);font-size:12px;white-space:pre-wrap}.error-note{margin-top:8px!important;color:var(--danger)!important}
.analysis-column{display:flex;flex-direction:column;gap:12px}.analysis-card,.teacher-card,.ability-card{padding:16px}.analysis-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:13px}.analysis-grid>span{display:grid;grid-template-columns:34px 1fr;align-items:center;padding:10px;border:1px solid var(--border);border-radius:9px}.analysis-icon{grid-row:1/3;display:grid;place-items:center;width:30px;height:30px;border-radius:9px;font-style:normal}.analysis-icon.blue{color:var(--primary);background:#edf4ff}.analysis-icon.green{color:#0aa568;background:#e8f8f0}.analysis-icon.purple{color:#7c4ce0;background:#f2ebfd}.analysis-icon.slate{color:#64748b;background:#f1f5f9}.analysis-grid small{color:var(--text-secondary);font-size:11px}.analysis-grid strong{color:var(--ink);font-size:17px}.analysis-grid em{color:var(--text-secondary);font-size:11px;font-style:normal}.teacher-card p{margin:9px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.7}.ability-card{display:grid;grid-template-columns:126px 1fr;gap:8px 20px}.ability-card h2{grid-column:1/-1}.score-ring{display:grid;place-items:center;width:116px;height:116px;margin-top:10px;border-radius:50%;position:relative}.score-ring::after{content:'';position:absolute;width:82px;height:82px;border-radius:50%;background:#fff}.score-ring span{z-index:1;display:grid;text-align:center}.score-ring strong{color:var(--ink);font-size:24px}.score-ring small{color:var(--text-secondary);font-size:11px}.dimension-list{display:grid;align-content:center;gap:11px}.dimension-list span{display:grid;grid-template-columns:1fr auto;gap:5px}.dimension-list small{color:var(--text-secondary)}.dimension-list strong{color:var(--ink);font-size:12px}.dimension-list i{grid-column:1/-1;height:5px;overflow:hidden;border-radius:999px;background:#edf1f7}.dimension-list b{display:block;height:100%;border-radius:inherit;background:var(--primary)}
.action-footer{position:fixed;z-index:5;right:0;bottom:0;left:var(--sidebar-width,260px);display:flex;justify-content:center;gap:12px;padding:12px;border-top:1px solid var(--border);background:rgba(255,255,255,.96);backdrop-filter:blur(8px)}.action-footer button{min-width:145px}.detail-loading{display:grid;gap:14px}.detail-loading .skeleton{height:90px}
@media(max-width:1250px){.identity-card{grid-template-columns:repeat(3,1fr);gap:14px}.final-score{border-left:0}.content-grid{grid-template-columns:1fr}.analysis-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.identity-card{grid-template-columns:1fr 1fr}.analysis-grid{grid-template-columns:1fr 1fr}.ability-card{grid-template-columns:1fr}.ability-card h2{grid-column:auto}.score-ring{justify-self:center}.question-row>button{grid-template-columns:25px 1fr 55px 18px}.answer-state{display:none}.action-footer{left:0;overflow:auto;justify-content:flex-start}.action-footer button{min-width:130px}}@media print{.back-link,.action-footer{display:none}.detail-page{padding:0}.content-grid{grid-template-columns:1fr}.question-row .answer-detail{display:block!important}}
</style>
