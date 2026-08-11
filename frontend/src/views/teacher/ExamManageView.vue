<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import TeacherMetricGrid from '../../components/teacher/TeacherMetricGrid.vue'
import TeacherPageHeader from '../../components/teacher/TeacherPageHeader.vue'
import TeacherPagination from '../../components/teacher/TeacherPagination.vue'
import ExamCreateDialog from '../../components/teacher/exam/ExamCreateDialog.vue'
import { examsAPI } from '../../api/exams.js'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { formatDateTime } from '../../utils/format.js'
import { EXAM_STATUS_MAP, statusBadge } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const exams = ref([])
const courses = ref([])
const loading = ref(true)
const createOpen = ref(false)
const query = ref('')
const statusFilter = ref('all')
const courseFilter = ref('all')
const sortOrder = ref('updated')
const page = ref(1)
const pageSize = ref(10)

const now = () => Date.now()
function displayStatus(exam) {
  if (exam.status === 'draft') return 'draft'
  if (exam.end_at && new Date(exam.end_at).getTime() < now()) return 'ended'
  return 'published'
}
const summary = computed(() => ({
  total: exams.value.length,
  published: exams.value.filter((item) => displayStatus(item) === 'published').length,
  draft: exams.value.filter((item) => displayStatus(item) === 'draft').length,
  ended: exams.value.filter((item) => displayStatus(item) === 'ended').length,
}))
const courseName = (exam) => exam.course_title || courses.value.find((course) => String(course.id) === String(exam.course_id))?.title || `课程 ${exam.course_id}`
const filteredExams = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const result = exams.value.filter((exam) => {
    const matchesQuery = !keyword || exam.title.toLowerCase().includes(keyword) || courseName(exam).toLowerCase().includes(keyword)
    const matchesStatus = statusFilter.value === 'all' || displayStatus(exam) === statusFilter.value
    const matchesCourse = courseFilter.value === 'all' || String(exam.course_id) === courseFilter.value
    return matchesQuery && matchesStatus && matchesCourse
  })
  return [...result].sort((a, b) => sortOrder.value === 'title'
    ? a.title.localeCompare(b.title, 'zh-CN')
    : new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
})
const pageCount = computed(() => Math.max(1, Math.ceil(filteredExams.value.length / pageSize.value)))
const pagedExams = computed(() => filteredExams.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

async function fetchExams() {
  loading.value = true
  try {
    const res = await examsAPI.list({ page_size: 100 })
    exams.value = res.data.items || res.data || []
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}
async function fetchCourses() {
  try {
    const res = await coursesAPI.list()
    courses.value = res.data.items || res.data || []
  } catch { courses.value = [] }
}
function resetPage() { page.value = 1 }
function openCreateModal() { createOpen.value = true }
function closeCreateModal() { createOpen.value = false }
async function handleSave({ title, course_id, duration_minutes, start_at, end_at }) {
  if (!title) return app.showToast('请输入考试名称', 'error')
  if (!Number.isInteger(course_id) || course_id <= 0) return app.showToast('请选择课程', 'error')
  if (!Number.isInteger(duration_minutes) || duration_minutes <= 0) return app.showToast('考试时长必须大于 0 分钟', 'error')
  if (start_at && end_at && new Date(start_at) >= new Date(end_at)) return app.showToast('结束时间必须晚于开始时间', 'error')
  try {
    const res = await examsAPI.create({ title, course_id, duration_minutes, start_at, end_at })
    app.showToast('创建成功', 'success')
    createOpen.value = false
    await fetchExams()
    if (res?.data?.id) router.push(`/teacher/exams/${res.data.id}/edit`)
  } catch (error) { app.showToast(error.response?.data?.detail?.message || '创建失败', 'error') }
}
async function publishExam(id) {
  try { await examsAPI.update(id, { status: 'published' }); app.showToast('已发布', 'success'); await fetchExams() }
  catch (error) { app.showToast(error.response?.data?.detail?.message || '操作失败', 'error') }
}

onMounted(() => { fetchExams(); fetchCourses() })
</script>

<template>
  <AppLayout>
    <main class="exam-page teacher-management-page">
      <TeacherPageHeader title="考试管理" subtitle="创建考试、配置题目、查看成绩与统计" action-label="创建考试" @action="openCreateModal" />

      <TeacherMetricGrid aria-label="考试统计" :items="[
        { key: 'total', label: '全部考试', icon: 'exam', tone: 'blue', value: summary.total },
        { key: 'published', label: '已发布', icon: 'send', tone: 'green', value: summary.published },
        { key: 'draft', label: '草稿', icon: 'draft', tone: 'orange', value: summary.draft },
        { key: 'ended', label: '已结束', icon: 'clock', tone: 'purple', value: summary.ended },
      ]" />

      <section class="data-panel">
        <div class="filter-bar">
          <label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索考试名称或课程" @input="resetPage" /></label>
          <select v-model="statusFilter" aria-label="状态筛选" @change="resetPage"><option value="all">状态：全部</option><option value="published">已发布</option><option value="draft">草稿</option><option value="ended">已结束</option></select>
          <select v-model="courseFilter" aria-label="课程筛选" @change="resetPage"><option value="all">课程：全部课程</option><option v-for="course in courses" :key="course.id" :value="String(course.id)">{{ course.title }}</option></select>
          <select v-model="sortOrder" aria-label="排序"><option value="updated">排序：最近更新</option><option value="title">排序：考试名称</option></select>
        </div>

        <div v-if="loading" class="loading-list"><span v-for="i in 6" :key="i" class="skeleton"></span></div>
        <div v-else-if="filteredExams.length === 0" class="empty-state"><AppIcon name="exam" :size="34" /><strong>暂无符合条件的考试</strong><p>调整筛选条件，或创建一场新考试。</p></div>
        <div v-else class="table-scroll">
          <table class="exam-table">
            <thead><tr><th>考试名称</th><th>所属课程</th><th>状态</th><th>题目数</th><th>时长</th><th>参与人数</th><th>最近更新</th><th>操作</th></tr></thead>
            <tbody><tr v-for="exam in pagedExams" :key="exam.id">
              <td data-label="考试名称"><strong>{{ exam.title }}</strong><small>{{ exam.start_at ? formatDateTime(exam.start_at) + ' 开始' : '未设置考试时间' }}</small></td>
              <td data-label="所属课程"><span>{{ courseName(exam) }}</span><small>课程 ID {{ exam.course_id }}</small></td>
              <td data-label="状态"><span class="status-pill" :class="displayStatus(exam)">{{ statusBadge(EXAM_STATUS_MAP, displayStatus(exam)).label }}</span></td>
              <td data-label="题目数">{{ exam.question_count ?? '—' }}</td>
              <td data-label="时长">{{ exam.duration_minutes }} 分钟</td>
              <td data-label="参与人数">{{ exam.participant_count ?? 0 }}<span v-if="exam.expected_count"> / {{ exam.expected_count }}</span></td>
              <td data-label="最近更新" class="muted-cell">{{ formatDateTime(exam.updated_at || exam.created_at) }}</td>
              <td data-label="操作" class="row-actions">
                <button class="text-action" @click="router.push(`/teacher/exams/${exam.id}/edit`)">编辑题目</button>
                <button class="text-action" @click="router.push(`/teacher/exams/${exam.id}/grades`)">成绩分析</button>
                <button v-if="displayStatus(exam) === 'draft'" class="publish-action" @click="publishExam(exam.id)">发布</button>
              </td>
            </tr></tbody>
          </table>
        </div>

        <TeacherPagination v-if="!loading" :current-page="page" :page-count="pageCount" :total="filteredExams.length" :page-size="pageSize" aria-label="考试列表分页" @change="page = $event" />
      </section>
    </main>

    <ExamCreateDialog :open="createOpen" :courses="courses" @save="handleSave" @close="closeCreateModal" />
  </AppLayout>
</template>

<style scoped>
.exam-page{display:flex;min-width:0;container-type:inline-size;flex-direction:column;gap:22px}.page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.page-head h1{margin:0 0 5px;color:var(--ink);font-size:30px;line-height:1.15;letter-spacing:-.025em}.page-head p{margin:0;color:var(--text-secondary);font-size:14px}.create-button{min-height:48px;padding:0 20px;font-size:15px}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.metric-card{display:flex;align-items:center;gap:18px;min-height:106px;padding:20px;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.metric-icon{display:grid;place-items:center;width:54px;height:54px;border-radius:15px}.metric-icon.blue{color:var(--primary);background:#edf4ff}.metric-icon.green{color:#10a66a;background:#eaf9f2}.metric-icon.orange{color:#ef8b10;background:#fff4e7}.metric-icon.purple{color:#7c4ce0;background:#f3edff}.metric-card span:last-child{display:grid;gap:3px}.metric-card small{color:var(--text-secondary);font-size:14px}.metric-card strong{color:var(--ink);font-size:26px;line-height:1}
.data-panel{min-width:0;overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.filter-bar{display:grid;min-width:0;grid-template-columns:minmax(240px,1.25fr) repeat(3,minmax(150px,.7fr));gap:14px;padding:18px;border-bottom:1px solid var(--border)}.filter-bar select,.search-control{height:44px;min-width:0}.search-control{display:flex;align-items:center;gap:9px;min-width:0;padding:0 13px;border:1px solid var(--border);border-radius:8px;color:var(--text-tertiary);background:#fff}.search-control:focus-within{border-color:var(--primary);box-shadow:var(--shadow-glow-primary)}.search-control input{height:auto;min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{cursor:pointer;color:var(--text-secondary)}
.table-scroll{min-width:0;overflow-x:hidden}.exam-table{width:100%;min-width:0;table-layout:fixed}.exam-table th{height:44px;padding:0 16px;overflow:hidden;text-transform:none;letter-spacing:0;text-overflow:ellipsis;white-space:nowrap;background:#f8fafc}.exam-table th:nth-child(1){width:22%}.exam-table th:nth-child(2){width:19%}.exam-table th:nth-child(3){width:10%}.exam-table th:nth-child(4){width:9%}.exam-table th:nth-child(5){width:11%}.exam-table th:nth-child(6){width:12%}.exam-table th:nth-child(7){width:15%}.exam-table th:nth-child(8){width:22%}.exam-table td{height:68px;min-width:0;padding:10px 16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.exam-table td:first-child{min-width:0}.exam-table td strong,.exam-table td small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.exam-table td strong{color:var(--ink);font-size:14px}.exam-table td small{margin-top:3px;color:var(--text-tertiary);font-size:12px}.muted-cell{color:var(--text-secondary);font-size:13px}.status-pill{display:inline-flex;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:600}.status-pill.published{color:#099b61;background:#e9f8f1}.status-pill.draft{color:#64748b;background:#f1f5f9}.status-pill.ended{color:#7443d5;background:#f1ebfd}.row-actions{display:flex;flex-wrap:wrap;align-items:center;gap:2px;white-space:normal}.row-actions button{padding:5px 7px;border:0;background:transparent;font-size:13px;white-space:nowrap}.text-action{color:var(--primary)}.publish-action{color:#ef8b10}.row-actions button:hover{background:var(--primary-light)}
.pagination-bar{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-top:1px solid var(--border);color:var(--text-secondary);font-size:13px}.pagination{display:flex;gap:0}.pagination button{display:grid;place-items:center;width:62px;height:58px;padding:0;border:1px solid var(--border);color:var(--text-secondary);background:var(--surface);font-size:18px}.pagination button:first-child{border-radius:12px 0 0 12px}.pagination button:last-child{border-radius:0 12px 12px 0}.pagination button+button{border-left:0}.pagination button.active{border-color:#c7d8ef;color:var(--ink);background:var(--surface)}.pagination button:disabled{color:var(--text-tertiary);background:var(--surface)}.pagination-bar>span:last-child{justify-self:end}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:68px;border-radius:0}.empty-state{display:grid;place-items:center;gap:8px}.empty-state strong{color:var(--ink)}.empty-state p{margin:0}
@media(max-width:1200px){.metric-grid{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:720px){.exam-page{gap:16px}.page-head{align-items:stretch;flex-direction:column}.page-head h1{font-size:26px}.metric-grid{grid-template-columns:1fr 1fr;gap:10px}.metric-card{min-height:88px;padding:14px;gap:12px}.metric-icon{width:44px;height:44px}.metric-card strong{font-size:22px}.filter-bar{grid-template-columns:1fr;padding:12px}.pagination-bar{grid-template-columns:1fr auto}.pagination{grid-column:1/-1;grid-row:1;justify-content:center}.pagination-bar>span:last-child{justify-self:end}}
@container (max-width:1050px){.filter-bar{grid-template-columns:minmax(0,1.3fr) repeat(3,minmax(0,.7fr))}.exam-table th:nth-child(1){width:27%}.exam-table th:nth-child(2){width:23%}.exam-table th:nth-child(3){width:14%}.exam-table th:nth-child(5){width:12%}.exam-table th:nth-child(8){width:24%}.exam-table th:nth-child(4),.exam-table td:nth-child(4),.exam-table th:nth-child(6),.exam-table td:nth-child(6),.exam-table th:nth-child(7),.exam-table td:nth-child(7){display:none}.exam-table td:last-child{padding-left:8px;padding-right:8px}.row-actions{gap:0}.row-actions button{padding:4px;font-size:12px}}
@container (max-width:760px){.filter-bar{grid-template-columns:1fr;padding:12px}.table-scroll{overflow:visible;padding:12px;background:#f8fafc}.exam-table,.exam-table tbody{display:block;width:100%}.exam-table thead{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.exam-table tbody{display:grid;gap:12px}.exam-table tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:hidden;border:1px solid var(--border);border-radius:10px;background:var(--surface)}.exam-table td,.exam-table td:nth-child(4),.exam-table td:nth-child(6),.exam-table td:nth-child(7){display:flex;width:auto;height:auto;min-height:58px;padding:10px 12px;flex-direction:column;justify-content:center;gap:5px;border-bottom:1px solid var(--border);overflow:visible;white-space:normal}.exam-table td::before{content:attr(data-label);color:var(--text-tertiary);font-size:11px;font-weight:500}.exam-table td:nth-child(1),.exam-table td:nth-child(2),.exam-table td:nth-child(8){grid-column:1/-1}.exam-table td:nth-child(7),.exam-table td:nth-last-child(-n+2){border-bottom:0}.exam-table td strong,.exam-table td small{overflow:visible;white-space:normal}.exam-table .row-actions{display:flex;flex-direction:row;align-items:center;justify-content:flex-end;gap:6px}.exam-table .row-actions::before{margin-right:auto}.row-actions button{padding:6px 8px}}
</style>
