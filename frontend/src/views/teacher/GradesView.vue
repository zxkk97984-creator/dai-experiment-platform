<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { formatDateTime } from '../../utils/format.js'
import { EXAM_GRADE_STATUS_MAP, statusBadge } from '../../utils/status.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const grades = ref([])
const exam = ref({})
const summary = ref({ expected_count: 0, submitted_count: 0, graded_count: 0, average_score: null, highest_score: null, pass_rate: 0, excellent_rate: 0 })
const distribution = ref([])
const loading = ref(true)
const query = ref('')
const statusFilter = ref('all')
const scoreFilter = ref('all')
const sortOrder = ref('score-desc')
const page = ref(1)
const pageSize = ref(10)

function scoreMatches(score, range) {
  if (range === 'all') return true
  if (score == null) return false
  if (range === 'excellent') return score >= 90
  if (range === 'good') return score >= 80 && score < 90
  if (range === 'pass') return score >= 60 && score < 80
  return score < 60
}
const filteredGrades = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const items = grades.value.filter((item) => {
    const matchesQuery = !keyword || item.student_name?.toLowerCase().includes(keyword) || item.student_number?.toLowerCase().includes(keyword)
    const matchesStatus = statusFilter.value === 'all' || item.status === statusFilter.value
    return matchesQuery && matchesStatus && scoreMatches(item.score, scoreFilter.value)
  })
  return [...items].sort((a, b) => {
    if (sortOrder.value === 'name') return (a.student_name || '').localeCompare(b.student_name || '', 'zh-CN')
    if (sortOrder.value === 'time') return new Date(b.submitted_at || 0) - new Date(a.submitted_at || 0)
    const left = a.score == null ? -1 : a.score
    const right = b.score == null ? -1 : b.score
    return sortOrder.value === 'score-asc' ? left - right : right - left
  })
})
const pageCount = computed(() => Math.max(1, Math.ceil(filteredGrades.value.length / pageSize.value)))
const pagedGrades = computed(() => filteredGrades.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const maxDistribution = computed(() => Math.max(1, ...distribution.value.map((item) => item.count)))
const donutStyle = computed(() => ({ background: `conic-gradient(#2f72f3 0 ${summary.value.pass_rate || 0}%, #58c1b3 ${summary.value.pass_rate || 0}% 100%)` }))

async function load() {
  loading.value = true
  try {
    const res = await examsAPI.getGrades(route.params.id)
    grades.value = res.data.items || []
    exam.value = res.data.exam || {}
    summary.value = { ...summary.value, ...(res.data.summary || {}) }
    distribution.value = res.data.distribution || []
  } catch { app.showToast('加载成绩失败', 'error') }
  finally { loading.value = false }
}
function resetPage() { page.value = 1 }
function viewDetail(item) { if (item.submission_id) router.push(`/teacher/exams/${route.params.id}/grades/${item.submission_id}`) }
function exportGrades() {
  const rows = [['学生姓名', '学号', '状态', '得分', '提交时间'], ...filteredGrades.value.map((item) => [item.student_name, item.student_number, statusBadge(EXAM_GRADE_STATUS_MAP, item.status).label, item.score ?? '', formatDateTime(item.submitted_at, { seconds: true })])]
  const csv = `\ufeff${rows.map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(',')).join('\n')}`
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = `${exam.value.title || '考试'}-成绩.csv`; link.click(); URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <main class="grades-page">
      <button class="back-link" @click="router.push('/teacher/exams')"><AppIcon name="back" :size="17" />返回考试管理</button>
      <header class="page-head"><div><h1>{{ exam.title || '考试成绩' }} · 成绩总览</h1><p>查看本场考试成绩、统计与学生表现</p></div><button class="btn-primary export-button" :disabled="!grades.length" @click="exportGrades"><AppIcon name="download" :size="18" />导出成绩</button></header>

      <section class="summary-grid" aria-label="成绩统计">
        <article v-for="item in [
          { label: '应考人数', value: summary.expected_count, icon: 'user', tone: 'blue' },
          { label: '已交卷', value: summary.submitted_count, icon: 'clipboard', tone: 'green' },
          { label: '平均分', value: summary.average_score ?? '—', icon: 'chart', tone: 'orange' },
          { label: '及格率', value: summary.pass_rate + '%', icon: 'pie', tone: 'purple' },
          { label: '最高分', value: summary.highest_score ?? '—', icon: 'trophy', tone: 'blue' },
        ]" :key="item.label" class="summary-card"><span class="summary-icon" :class="item.tone"><AppIcon :name="item.icon" :size="24" /></span><span><small>{{ item.label }}</small><strong>{{ item.value }}</strong></span></article>
      </section>

      <section class="charts-grid">
        <article class="chart-card"><h2>分数分布</h2><div v-if="distribution.length" class="bar-chart"><div v-for="item in distribution" :key="item.label" class="bar-column"><span class="bar-count">{{ item.count }}</span><span class="bar" :style="{ height: `${Math.max(6, item.count / maxDistribution * 100)}%` }"></span><small>{{ item.label }}</small></div></div><div v-else class="chart-empty">暂无可统计成绩</div></article>
        <article class="chart-card performance-card"><h2>考试表现</h2><div class="performance-body"><div class="donut" :style="donutStyle"><span><strong>{{ summary.pass_rate }}%</strong><small>及格率</small></span></div><div class="performance-stats"><span><small>及格率（≥60分）</small><strong>{{ summary.pass_rate }}%</strong></span><span><small>优秀率（≥90分）</small><strong>{{ summary.excellent_rate }}%</strong></span><p><i class="legend pass"></i>及格 {{ summary.graded_count ? Math.round(summary.graded_count * summary.pass_rate / 100) : 0 }} 人 <i class="legend fail"></i>未及格 {{ summary.graded_count ? summary.graded_count - Math.round(summary.graded_count * summary.pass_rate / 100) : 0 }} 人</p></div></div></article>
      </section>

      <section class="results-panel">
        <div class="filter-bar"><label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索学生姓名或学号" @input="resetPage" /></label><select v-model="statusFilter" @change="resetPage"><option value="all">状态：全部</option><option value="graded">已评分</option><option value="review_required">待复核</option><option value="grading">评分中</option><option value="absent">缺考</option></select><select v-model="scoreFilter" @change="resetPage"><option value="all">分数段：全部</option><option value="excellent">90–100</option><option value="good">80–89</option><option value="pass">60–79</option><option value="fail">0–59</option></select><select v-model="sortOrder"><option value="score-desc">排序：分数从高到低</option><option value="score-asc">排序：分数从低到高</option><option value="time">排序：最近提交</option><option value="name">排序：学生姓名</option></select></div>
        <div v-if="loading" class="loading-list"><span v-for="i in 5" :key="i" class="skeleton"></span></div>
        <div v-else-if="!filteredGrades.length" class="empty-state"><AppIcon name="chart" :size="34" /><strong>暂无符合条件的成绩</strong></div>
        <div v-else class="table-scroll"><table class="grade-table"><thead><tr><th>学生</th><th>学号</th><th>课程</th><th>交卷状态</th><th>得分</th><th>提交时间</th><th>操作</th></tr></thead><tbody><tr v-for="item in pagedGrades" :key="item.id"><td data-label="学生"><span class="student-cell"><i>{{ item.student_name?.slice(0, 1) || '学' }}</i><strong>{{ item.student_name }}</strong></span></td><td data-label="学号">{{ item.student_number }}</td><td data-label="课程">{{ exam.course_title || '—' }}</td><td data-label="交卷状态"><span class="status-pill" :class="item.status">{{ statusBadge(EXAM_GRADE_STATUS_MAP, item.status).label }}</span></td><td data-label="得分"><strong v-if="item.score != null" class="score">{{ item.score }}</strong><span v-else>—</span></td><td data-label="提交时间" class="muted-cell">{{ formatDateTime(item.submitted_at, { seconds: true }) }}</td><td data-label="操作"><button class="detail-action" :disabled="!item.submission_id" @click="viewDetail(item)">查看详情</button></td></tr></tbody></table></div>
        <footer v-if="!loading && filteredGrades.length" class="pagination-bar"><span>共 {{ filteredGrades.length }} 条</span><div class="pagination"><button :disabled="page === 1" @click="page--">‹</button><button v-for="number in pageCount" :key="number" :class="{ active: page === number }" @click="page = number">{{ number }}</button><button :disabled="page === pageCount" @click="page++">›</button></div><span>{{ pageSize }} 条/页</span></footer>
      </section>
    </main>
  </AppLayout>
</template>

<style scoped>
.grades-page{display:flex;min-width:0;container-type:inline-size;flex-direction:column;gap:18px}.back-link{align-self:flex-start;padding:0;border:0;color:var(--primary);background:transparent}.page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.page-head h1{margin:0 0 5px;color:var(--ink);font-size:28px;letter-spacing:-.025em}.page-head p{margin:0;color:var(--text-secondary);font-size:14px}.export-button{min-height:46px;padding:0 19px}
.summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}.summary-card{display:flex;align-items:center;gap:14px;min-height:96px;padding:17px;border:1px solid var(--border);border-radius:12px;background:#fff;box-shadow:var(--shadow-card)}.summary-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px}.summary-icon.blue{color:var(--primary);background:#edf4ff}.summary-icon.green{color:#0aa66a;background:#e8f8f0}.summary-icon.orange{color:#ef8a0b;background:#fff3e4}.summary-icon.purple{color:#7a48dc;background:#f2ebfd}.summary-card span:last-child{display:grid;gap:4px}.summary-card small{color:var(--text-secondary);font-size:13px}.summary-card strong{color:var(--ink);font-size:25px;line-height:1}
.charts-grid{display:grid;grid-template-columns:1.35fr 1fr;gap:14px}.chart-card{min-height:250px;padding:18px 20px;border:1px solid var(--border);border-radius:12px;background:#fff;box-shadow:var(--shadow-card)}.chart-card h2{margin:0;color:var(--ink);font-size:15px}.bar-chart{display:flex;align-items:flex-end;justify-content:space-around;height:190px;padding:25px 22px 0;border-bottom:1px solid var(--border)}.bar-column{display:grid;grid-template-rows:20px 1fr 26px;align-items:end;justify-items:center;width:14%;height:100%}.bar-count{color:var(--text-secondary);font-size:12px}.bar{width:38px;max-height:130px;border-radius:3px 3px 0 0;background:linear-gradient(180deg,#3d7cf5,#2464e7)}.bar-column small{align-self:end;padding-top:7px;color:var(--text-secondary);font-size:12px;white-space:nowrap}.chart-empty{display:grid;place-items:center;height:190px;color:var(--text-tertiary)}.performance-body{display:flex;align-items:center;justify-content:space-around;height:210px;gap:24px}.donut{display:grid;place-items:center;width:150px;height:150px;border-radius:50%;position:relative}.donut::after{content:'';position:absolute;width:104px;height:104px;border-radius:50%;background:#fff}.donut span{z-index:1;display:grid;text-align:center}.donut strong{color:var(--ink);font-size:27px}.donut small{color:var(--text-secondary);font-size:12px}.performance-stats{display:grid;gap:15px;min-width:190px}.performance-stats>span{display:flex;align-items:end;justify-content:space-between;padding-bottom:10px;border-bottom:1px dashed var(--border)}.performance-stats small{color:var(--text-secondary)}.performance-stats strong{color:var(--ink);font-size:24px}.performance-stats p{margin:0;color:var(--text-secondary);font-size:12px}.legend{display:inline-block;width:9px;height:9px;margin-right:4px;border-radius:2px}.legend.pass{background:#2f72f3}.legend.fail{background:#58c1b3}
.results-panel{min-width:0;overflow:hidden;border:1px solid var(--border);border-radius:12px;background:#fff}.filter-bar{display:grid;min-width:0;grid-template-columns:minmax(220px,1.2fr) repeat(3,minmax(150px,.75fr));gap:12px;padding:15px;border-bottom:1px solid var(--border)}.filter-bar select,.search-control{height:42px;min-width:0}.search-control{display:flex;align-items:center;gap:8px;min-width:0;padding:0 12px;border:1px solid var(--border);border-radius:8px;color:var(--text-tertiary)}.search-control input{min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{cursor:pointer}.table-scroll{min-width:0;overflow-x:hidden}.grade-table{width:100%;min-width:0;table-layout:fixed}.grade-table th{height:42px;padding:0 14px;overflow:hidden;text-transform:none;letter-spacing:0;text-overflow:ellipsis;white-space:nowrap}.grade-table th:nth-child(1){width:22%}.grade-table th:nth-child(2){width:13%}.grade-table th:nth-child(3){width:17%}.grade-table th:nth-child(4){width:15%}.grade-table th:nth-child(5){width:10%}.grade-table th:nth-child(6){width:17%}.grade-table th:nth-child(7){width:12%}.grade-table td{height:61px;min-width:0;padding:8px 14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.student-cell{display:flex;align-items:center;min-width:0;gap:10px}.student-cell strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink)}.student-cell i{display:grid;place-items:center;flex:0 0 auto;width:32px;height:32px;border-radius:50%;color:var(--primary);background:var(--primary-light);font-style:normal;font-size:13px}.status-pill{display:inline-flex;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600}.status-pill.graded{color:#07985e;background:#e8f8f0}.status-pill.review_required{color:#dc7c08;background:#fff3df}.status-pill.grading,.status-pill.submitted,.status-pill.started{color:#2563eb;background:#edf4ff}.status-pill.absent{color:#dc3e49;background:#ffedef}.score{color:var(--primary);font-size:17px}.muted-cell{color:var(--text-secondary);font-size:13px}.detail-action{padding:4px;border:0;color:var(--primary);background:transparent;white-space:nowrap}.detail-action:disabled{color:var(--text-tertiary)}.pagination-bar{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:13px 16px;border-top:1px solid var(--border);color:var(--text-secondary);font-size:13px}.pagination{display:flex;gap:6px}.pagination button{width:33px;height:33px;padding:0}.pagination button.active{border-color:var(--primary);color:#fff;background:var(--primary)}.pagination-bar>span:last-child{justify-self:end}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:61px;border-radius:0}.empty-state{display:grid;place-items:center;gap:8px}.empty-state strong{color:var(--ink)}
@media(max-width:1250px){.summary-grid{grid-template-columns:repeat(3,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:900px){.charts-grid{grid-template-columns:1fr}.summary-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:680px){.page-head{align-items:stretch;flex-direction:column}.page-head h1{font-size:24px}.summary-grid{grid-template-columns:1fr 1fr;gap:9px}.summary-card{min-height:82px;padding:12px}.summary-icon{width:42px;height:42px}.summary-card strong{font-size:21px}.filter-bar{grid-template-columns:1fr;padding:12px}.performance-body{flex-direction:column;height:auto;padding-top:18px}.pagination-bar{grid-template-columns:1fr auto}.pagination{grid-column:1/-1;grid-row:1;justify-content:center}}
@container (max-width:1050px){.filter-bar{grid-template-columns:minmax(0,1.2fr) repeat(3,minmax(0,.75fr))}.grade-table th:nth-child(1){width:28%}.grade-table th:nth-child(2){width:17%}.grade-table th:nth-child(4){width:18%}.grade-table th:nth-child(5){width:15%}.grade-table th:nth-child(7){width:22%}.grade-table th:nth-child(3),.grade-table td:nth-child(3),.grade-table th:nth-child(6),.grade-table td:nth-child(6){display:none}}
@container (max-width:760px){.filter-bar{grid-template-columns:1fr;padding:12px}.table-scroll{overflow:visible;padding:12px;background:#f8fafc}.grade-table,.grade-table tbody{display:block;width:100%}.grade-table thead{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.grade-table tbody{display:grid;gap:12px}.grade-table tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:hidden;border:1px solid var(--border);border-radius:10px;background:#fff}.grade-table td,.grade-table td:nth-child(3),.grade-table td:nth-child(6){display:flex;width:auto;height:auto;min-height:58px;padding:10px 12px;flex-direction:column;justify-content:center;gap:5px;border-bottom:1px solid var(--border);overflow:visible;white-space:normal}.grade-table td::before{content:attr(data-label);color:var(--text-tertiary);font-size:11px;font-weight:500}.grade-table td:nth-child(1),.grade-table td:nth-child(3),.grade-table td:nth-child(7){grid-column:1/-1}.grade-table td:nth-child(6),.grade-table td:nth-last-child(-n+2){border-bottom:0}.grade-table .student-cell{align-items:center}.grade-table .detail-action{align-self:flex-end;min-height:34px}.grade-table td strong{overflow:visible;white-space:normal}}
</style>
