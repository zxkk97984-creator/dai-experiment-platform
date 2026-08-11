<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import CourseCreateModal from '../../components/teacher/CourseCreateModal.vue'
import TeacherMetricGrid from '../../components/teacher/TeacherMetricGrid.vue'
import TeacherPageHeader from '../../components/teacher/TeacherPageHeader.vue'
import TeacherPagination from '../../components/teacher/TeacherPagination.vue'
import { coursesAPI } from '../../api/courses.js'
import { academicsAPI } from '../../api/academics.js'
import { useAppStore } from '../../stores/app.js'
import { coursePublishMissingMessage } from '../../utils/coursePublish.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const terms = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const serverSummary = ref({ total: 0, published: 0, draft: 0, archived: 0 })
const loading = ref(true)
const showCreate = ref(false)
const query = ref('')
const statusFilter = ref('all')
const termFilter = ref('all')
const sortOrder = ref('updated')

const courseStatus = (course) => course.status || 'draft'
const courseLabel = (status) => ({ published: '已发布', draft: '草稿', archived: '已归档' })[status] || status
const courseUpdated = (course) => course.updated_at || course.created_at || course.updatedAt || ''
const summary = computed(() => serverSummary.value)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const managePath = (course) => `${router.currentRoute?.value?.path?.startsWith('/admin') ? '/admin' : '/teacher'}/courses/${course.id}/manage`
const classLabel = (course) => course.teaching_classes?.map((item) => item.name).join('、') || '未设置班级'

function resetPage() { page.value = 1; fetchCourses() }
function goToPage(next) { page.value = next; fetchCourses() }

async function fetchCourses() {
  loading.value = true
  try {
    const res = await coursesAPI.list({
      page: page.value, page_size: pageSize,
      q: query.value.trim() || undefined,
      status_filter: statusFilter.value === 'all' ? undefined : statusFilter.value,
      academic_term_id: termFilter.value === 'all' ? undefined : Number(termFilter.value),
      sort_by: sortOrder.value,
    })
    courses.value = res.data.items || []
    total.value = res.data.total || 0
    serverSummary.value = res.data.summary || serverSummary.value
  }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}
function handleCourseCreated(course) {
  showCreate.value = false
  if (course?.id) {
    router.push(managePath(course))
    return
  }
  fetchCourses()
}
async function handlePublish(course) {
  const missingMessage = coursePublishMissingMessage(course)
  if (missingMessage) {
    app.showToast(missingMessage, 'error')
    return
  }
  try { await coursesAPI.update(course.id, { status: 'published' }); app.showToast('已发布', 'success'); fetchCourses() }
  catch (err) { app.showToast(err.response?.data?.detail?.message || '操作失败', 'error') }
}
let queryTimer
watch(query, () => { clearTimeout(queryTimer); queryTimer = setTimeout(resetPage, 250) })
onMounted(async () => {
  try { const res = await academicsAPI.listTerms({ page_size: 100 }); terms.value = res.data.items || [] } catch { terms.value = [] }
  fetchCourses()
})
</script>

<template>
  <AppLayout>
    <main class="page teacher-management-page">
      <TeacherPageHeader title="课程管理" subtitle="创建与维护课程，管理章节、课时与教学安排">
        <template #actions><button class="btn-primary teacher-page-action" type="button" @click="showCreate = true"><AppIcon name="plus" :size="18" />创建课程</button></template>
      </TeacherPageHeader>
      <TeacherMetricGrid aria-label="课程统计" :items="[{ key: 'total', label: '全部课程', icon: 'course', tone: 'blue', value: summary.total, unit: '门' }, { key: 'published', label: '已发布', icon: 'send', tone: 'green', value: summary.published, unit: '门' }, { key: 'draft', label: '草稿', icon: 'draft', tone: 'orange', value: summary.draft, unit: '门' }, { key: 'archived', label: '已归档', icon: 'clock', tone: 'purple', value: summary.archived, unit: '门' }]" />
      <section class="data-panel"><div class="filter-bar"><label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索课程名称" /></label><select v-model="statusFilter" aria-label="状态筛选" @change="resetPage"><option value="all">状态：全部</option><option value="published">已发布</option><option value="draft">草稿</option><option value="archived">已归档</option></select><select v-model="termFilter" aria-label="学期筛选" @change="resetPage"><option value="all">学期：全部学期</option><option v-for="term in terms" :key="term.id" :value="String(term.id)">{{ term.name }}</option></select><select v-model="sortOrder" aria-label="排序" @change="resetPage"><option value="updated">排序：最近更新</option><option value="title">排序：课程名称</option></select></div><div v-if="loading" class="loading-list"><span v-for="i in 6" :key="i" class="skeleton"></span></div><div v-else-if="courses.length === 0" class="empty-state"><AppIcon name="course" :size="32" /><strong>暂无符合条件的课程</strong><p>调整筛选条件，或创建一门新课程。</p></div><div v-else class="table-scroll"><table><thead><tr><th>课程名称</th><th>所属学期 / 班级</th><th>状态</th><th>章节 / 课时</th><th>学生人数</th><th>最近更新</th><th>操作</th></tr></thead><tbody><tr v-for="course in courses" :key="course.id"><td><a class="course-link" @click="router.push(managePath(course))">{{ course.title }}</a><small>{{ course.description || '课程教学内容与安排' }}</small></td><td>{{ course.academic_term?.name || '未设置学期' }}<small>{{ classLabel(course) }}</small></td><td><span class="status-pill" :class="courseStatus(course)">{{ courseLabel(courseStatus(course)) }}</span></td><td>{{ course.chapter_count }} 章 / {{ course.lesson_count }} 课时</td><td><span class="icon-value"><AppIcon name="user" :size="14" />{{ course.student_count }}</span></td><td class="muted-cell">{{ formatDateTime(courseUpdated(course)) }}</td><td class="actions-cell"><button class="text-action" @click="router.push(managePath(course))">课程设置</button><button class="text-action" @click="router.push(managePath(course))">章节课时</button><button v-if="course.status === 'draft'" class="publish-action" @click="handlePublish(course)">发布</button></td></tr></tbody></table></div><TeacherPagination v-if="!loading" :current-page="page" :page-count="pageCount" :total="total" :page-size="pageSize" aria-label="课程列表分页" @change="goToPage" /></section>
      <CourseCreateModal v-if="showCreate" :terms="terms" @close="showCreate = false" @created="handleCourseCreated" />
    </main>
  </AppLayout>
</template>

<style scoped>
.page{display:flex;flex-direction:column;gap:22px}.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.page-head h1{margin:0 0 6px;color:var(--ink);font-size:30px}.page-head p{margin:0;color:var(--text-secondary)}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.metric-card{display:flex;align-items:center;gap:18px;min-height:106px;padding:20px;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.metric-icon{display:grid;place-items:center;width:54px;height:54px;border-radius:15px}.metric-icon.blue{color:var(--primary);background:#edf4ff}.metric-icon.green{color:#10a66a;background:#eaf9f2}.metric-icon.orange{color:#ef8b10;background:#fff4e7}.metric-icon.purple{color:#7c4ce0;background:#f3edff}.metric-card span:last-child{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}.metric-card small{width:100%;color:var(--text-secondary);font-size:14px}.metric-card strong{color:var(--ink);font-size:27px;line-height:1}.metric-card em{color:var(--text-secondary);font-size:13px;font-style:normal}.data-panel{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.filter-bar{display:grid;grid-template-columns:minmax(220px,1.4fr) repeat(3,minmax(150px,.8fr));gap:14px;padding:18px;border-bottom:1px solid var(--border)}.search-control{display:flex;align-items:center;gap:9px;padding:0 13px;border:1px solid var(--border);border-radius:8px;color:var(--text-tertiary)}.search-control input{min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{height:44px;min-width:0}.table-scroll{overflow-x:auto}.table-scroll table{width:100%;min-width:900px;margin:0}.table-scroll th{height:44px;background:#f8fafc}.table-scroll td{height:68px;padding:10px 16px}.table-scroll td:first-child{font-weight:600}.table-scroll td small{display:block;margin-top:3px;color:var(--text-tertiary);font-size:12px;font-weight:400;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.status-pill{display:inline-flex;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:600}.status-pill.published{color:#099b61;background:#e9f8f1}.status-pill.draft{color:#ef8b10;background:#fff4e7}.status-pill.archived{color:#7443d5;background:#f1ebfd}.muted-cell{color:var(--text-secondary);font-size:13px}.actions-cell{display:flex;gap:2px;white-space:nowrap}.text-action,.publish-action{padding:5px 7px;border:0;background:transparent;color:var(--primary);font-size:13px}.publish-action{color:var(--warning)}.pagination-bar{display:flex;justify-content:space-between;padding:14px 18px;border-top:1px solid var(--border);color:var(--text-secondary);font-size:13px}.active-page{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#fff;background:var(--primary)}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:68px}.create-form{padding:24px}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:700px){.page-head{flex-direction:column}.metric-grid{grid-template-columns:1fr 1fr;gap:10px}.filter-bar{grid-template-columns:1fr}.metric-card{padding:14px;gap:12px}.table-scroll table{min-width:820px}}
.status-pill{white-space:nowrap}
</style>
