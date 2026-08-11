<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import TeacherMetricGrid from '../../components/teacher/TeacherMetricGrid.vue'
import TeacherPageHeader from '../../components/teacher/TeacherPageHeader.vue'
import TeacherPagination from '../../components/teacher/TeacherPagination.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { coursesAPI } from '../../api/courses.js'
import EnvironmentProfilePicker from '../../components/common/EnvironmentProfilePicker.vue'
import ConfirmDialog from '../../components/ui/ConfirmDialog.vue'
import { useAppStore } from '../../stores/app.js'
import { formatDateTime } from '../../utils/format.js'
import { useClientPagination } from '../../composables/useClientPagination.js'

const router = useRouter()
const app = useAppStore()
const assignments = ref([])
const loading = ref(true)
// 创建弹窗开关：点「布置作业」弹出完整创建表单，确定后创建并跳转题目编辑页
const createOpen = ref(false)
const form = ref({ title: '', description: '', course_id: '', due_at: '', environment_version_id: null })
// 环境选择（Phase 4）：envOptions 来自共享 Picker 的 loaded 事件；默认 basic（列表第一项）
const envOptions = ref([])
const importPolicy = ref('unrestricted')
const allowedImports = ref([])
// 课程弹窗：courses 为可选课程列表，courseModalOpen 控制弹窗开关，manualCourseId 为弹窗内手输 ID
const courses = ref([])
const query = ref('')
const statusFilter = ref('all')
const courseFilter = ref('all')
const sortOrder = ref('updated')
const courseModalOpen = ref(false)
const manualCourseId = ref('')

// 选中环境的包 import 名（restricted 白名单候选来源）
const selectedEnv = computed(() =>
  envOptions.value.find((o) => o.environment_version_id === form.value.environment_version_id) || null,
)
const envImportCandidates = computed(() => {
  if (!selectedEnv.value) return []
  const seen = new Set()
  const names = []
  for (const p of selectedEnv.value.packages || []) {
    for (const name of p.import_names || []) {
      if (!seen.has(name)) { seen.add(name); names.push(name) }
    }
  }
  return names
})
// allowed imports 与已安装包不匹配 → 黄色警告（教学规则，不强制耦合）
const importMismatchWarning = computed(() => {
  if (importPolicy.value !== 'restricted' || allowedImports.value.length === 0) return ''
  if (!selectedEnv.value) return ''
  const installed = new Set(envImportCandidates.value)
  const missing = allowedImports.value.filter((name) => !installed.has(name))
  return missing.length ? `注意：${missing.join('、')} 未在当前环境安装，学生运行时会提示环境配置问题` : ''
})

async function fetch() {
  loading.value = true
  try { const res = await assignmentsAPI.list(); assignments.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function fetchCourses() {
  try {
    const res = await coursesAPI.list()
    courses.value = res.data.items || res.data
  } catch { /* 课程列表加载失败不阻塞创建，仍可手动输入课程 ID */ }
}

// 展示框显示：已选课程在列表中 → 「课程名（ID: n）」；手输未在列表 → 「课程 ID: n」
const assignmentStatus = (assignment) => assignment.status || 'draft'
const assignmentUpdated = (assignment) => assignment.updated_at || assignment.created_at || ''
const summary = computed(() => ({ total: assignments.value.length, published: assignments.value.filter((item) => assignmentStatus(item) === 'published').length, draft: assignments.value.filter((item) => assignmentStatus(item) === 'draft').length, ended: assignments.value.filter((item) => assignmentStatus(item) === 'ended' || (item.due_at && new Date(item.due_at) < new Date())).length }))
const filteredAssignments = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const result = assignments.value.filter((item) => {
    const course = courses.value.find((candidate) => String(candidate.id) === String(item.course_id))
    const courseTitle = item.course_title || course?.title || ''
    return (!keyword || `${item.title || ''} ${courseTitle}`.toLowerCase().includes(keyword)) && (statusFilter.value === 'all' || assignmentStatus(item) === statusFilter.value) && (courseFilter.value === 'all' || String(item.course_id) === courseFilter.value)
  })
  return [...result].sort((a, b) => sortOrder.value === 'title' ? String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN') : new Date(assignmentUpdated(b) || 0) - new Date(assignmentUpdated(a) || 0))
})
const { page, pageSize, pageCount, pagedItems, goToPage, resetPage } = useClientPagination(filteredAssignments)
const courseName = (assignment) => assignment.course_title || courses.value.find((course) => String(course.id) === String(assignment.course_id))?.title || '未关联课程'
const courseClassLabel = (assignment) => courses.value.find((course) => String(course.id) === String(assignment.course_id))?.teaching_classes?.map((item) => item.name).join('、') || '未设置班级'
const selectedCourse = computed(
  () => courses.value.find((c) => String(c.id) === String(form.value.course_id)) || null,
)

// 打开课程弹窗：手输框预填当前已选 ID，方便修改
function openCourseModal() {
  manualCourseId.value = form.value.course_id ? String(form.value.course_id) : ''
  courseModalOpen.value = true
}

function closeCourseModal() {
  courseModalOpen.value = false
}

// 点击课程列表项 → 回填 ID 并关闭弹窗
function pickCourse(c) {
  form.value.course_id = String(c.id)
  courseModalOpen.value = false
}

// 手输课程 ID 后点「确定」（或回车）→ 回填并关闭弹窗
function confirmManualCourse() {
  const id = manualCourseId.value.trim()
  if (!id) return
  form.value.course_id = id
  courseModalOpen.value = false
}

// 无可用环境时禁止创建（计划 11.1：提示联系管理员）
const canCreate = computed(() => envOptions.value.length > 0)

function onEnvLoaded(options) {
  envOptions.value = options
  // 默认 basic 当前可用版本：列表按档位 slug 排序，第一项即 basic
  if (options.length && !form.value.environment_version_id) {
    form.value.environment_version_id = options[0].environment_version_id
  }
}

function toggleAllowedImport(name) {
  const idx = allowedImports.value.indexOf(name)
  if (idx >= 0) allowedImports.value.splice(idx, 1)
  else allowedImports.value.push(name)
}

// 点「布置作业」：直接弹出完整创建弹窗
function openCreateModal() {
  createOpen.value = true
}

function closeCreateModal() {
  createOpen.value = false
}

// 弹窗点「确定」：校验通过后创建作业，成功即关闭弹窗并跳转题目编辑页；失败保持弹窗打开
async function doCreate() {
  if (!form.value.title.trim()) {
    app.showToast('请输入作业名称', 'error')
    return
  }
  if (!canCreate.value) {
    app.showToast('暂无可用环境，请联系管理员', 'error')
    return
  }
  try {
    const payload = {
      ...form.value,
      course_id: parseInt(form.value.course_id) || undefined,
      due_at: form.value.due_at || null,
      environment_version_id: form.value.environment_version_id,
      import_policy_mode: importPolicy.value,
      allowed_imports: importPolicy.value === 'restricted' ? [...allowedImports.value] : [],
    }
    const res = await assignmentsAPI.create(payload)
    const created = res?.data || {}
    const newId = created.id
    app.showToast('创建成功', 'success')
    createOpen.value = false
    fetch()
    if (newId) router.push(`/teacher/assignments/${newId}/edit`)
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}

async function handlePublish(a) {
  try { await assignmentsAPI.publish(a.id); app.showToast('已发布', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

// ── 删除草稿作业（确认弹窗） ────────────────────────────────────────
const deleteTarget = ref(null)
const deleting = ref(false)

function askDelete(a) { deleteTarget.value = a }

async function confirmDelete() {
  if (deleting.value) return
  deleting.value = true
  try {
    await assignmentsAPI.deleteAssignment(deleteTarget.value.id)
    deleteTarget.value = null
    app.showToast('作业已删除', 'success')
    fetch()
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '删除失败', 'error') }
  finally { deleting.value = false }
}

// ── 取消发布（确认弹窗） ────────────────────────────────────────────
const unpublishTarget = ref(null)
const unpublishing = ref(false)

function askUnpublish(a) { unpublishTarget.value = a }

async function confirmUnpublish() {
  if (unpublishing.value) return
  unpublishing.value = true
  try {
    await assignmentsAPI.unpublishAssignment(unpublishTarget.value.id)
    unpublishTarget.value = null
    app.showToast('已取消发布', 'success')
    fetch()
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '取消发布失败', 'error') }
  finally { unpublishing.value = false }
}

onMounted(() => { fetch(); fetchCourses() })
</script>

<template>
  <AppLayout>
    <div class="page teacher-management-page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <TeacherPageHeader title="作业管理" subtitle="布置作业、编写判题题目与测试用例" action-label="布置作业" @action="openCreateModal" />

      <TeacherMetricGrid aria-label="作业统计" :items="[{ key: 'total', label: '全部作业', icon: 'assignment', tone: 'blue', value: summary.total, unit: '个' }, { key: 'published', label: '已发布', icon: 'send', tone: 'green', value: summary.published, unit: '个' }, { key: 'draft', label: '草稿', icon: 'draft', tone: 'orange', value: summary.draft, unit: '个' }, { key: 'ended', label: '已截止', icon: 'clock', tone: 'purple', value: summary.ended, unit: '个' }]" />
      <section class="data-panel"><div class="filter-bar"><label class="search-control"><AppIcon name="search" :size="18" /><input v-model="query" placeholder="搜索作业名称" @input="resetPage" /></label><select v-model="statusFilter" @change="resetPage"><option value="all">状态：全部</option><option value="published">已发布</option><option value="draft">草稿</option><option value="ended">已截止</option></select><select v-model="courseFilter" @change="resetPage"><option value="all">课程：全部课程</option><option v-for="course in courses" :key="course.id" :value="String(course.id)">{{ course.title }}</option></select><select v-model="sortOrder" @change="resetPage"><option value="updated">排序：最近更新</option><option value="title">排序：作业名称</option></select></div><div v-if="loading" class="loading-list"><span v-for="i in 6" :key="i" class="skeleton"></span></div><div v-else-if="filteredAssignments.length === 0" class="empty-state"><AppIcon name="assignment" :size="32" /><strong>暂无符合条件的作业</strong><p>调整筛选条件，或布置一份新作业。</p></div><div v-else class="table-scroll"><table><thead><tr><th>作业名称</th><th>所属课程 / 班级</th><th>状态</th><th>截止时间</th><th>提交进度</th><th>最近更新</th><th>操作</th></tr></thead><tbody><tr v-for="assignment in pagedItems" :key="assignment.id"><td class="title-cell">{{ assignment.title }}<small>{{ assignment.description || '暂无作业描述' }}</small></td><td>{{ courseName(assignment) }}<small>{{ courseClassLabel(assignment) }}</small></td><td><span class="status-pill" :class="assignmentStatus(assignment)">{{ assignmentStatus(assignment) === 'published' ? '已发布' : assignmentStatus(assignment) === 'draft' ? '草稿' : '已截止' }}</span></td><td>{{ formatDateTime(assignment.due_at) }}</td><td>{{ assignment.submitted_count != null ? `${assignment.submitted_count} / ${assignment.student_count || '—'}` : '—' }}</td><td class="muted-cell">{{ formatDateTime(assignmentUpdated(assignment)) }}</td><td class="actions-cell"><button class="text-action" @click="router.push(`/teacher/assignments/${assignment.id}/edit`)">编辑题目</button><button v-if="assignment.status === 'draft'" class="publish-action" @click="handlePublish(assignment)">发布</button><button v-if="assignment.status === 'draft'" class="delete-action" @click="askDelete(assignment)">删除</button><button v-if="assignment.status === 'published'" class="text-action" @click="askUnpublish(assignment)">取消发布</button></td></tr></tbody></table></div><TeacherPagination v-if="!loading" :current-page="page" :page-count="pageCount" :total="filteredAssignments.length" :page-size="pageSize" aria-label="作业列表分页" @change="goToPage" /></section>

      <!-- ── 创建作业弹窗（点「布置作业」打开：基本信息 + 环境配置，确定后创建并跳转题目编辑页） ── -->
    </div>

    <!-- ── 创建作业弹窗（点「布置作业」打开：基本信息 + 环境配置，确定后创建并跳转题目编辑页） ── -->
    <div v-if="createOpen" class="modal-backdrop create-backdrop" @click.self="closeCreateModal">
      <div class="create-panel create-modal" role="dialog" aria-modal="true" aria-label="创建作业">
        <header class="create-heading">
          <strong>创建作业</strong>
          <button class="create-close" type="button" aria-label="关闭" @click="closeCreateModal">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </button>
        </header>
        <div class="create-modal-body">
          <div class="form-group"><label>作业名称</label><input v-model="form.title" placeholder="输入作业名称" /></div>
          <div class="form-group"><label>描述</label><textarea v-model="form.description" rows="2" placeholder="作业描述（可选）"></textarea></div>
          <div class="grid-2">
            <div class="form-group">
              <label>课程</label>
              <button type="button" class="course-picker" @click="openCourseModal">
                <span v-if="selectedCourse">{{ selectedCourse.title }}（ID: {{ selectedCourse.id }}）</span>
                <span v-else-if="form.course_id">课程 ID: {{ form.course_id }}</span>
                <span v-else class="placeholder">选择课程</span>
                <svg class="picker-chevron" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </button>
              <p v-if="courses.length === 0" class="form-hint">暂无课程，点击上方可手动输入课程 ID</p>
            </div>
            <div class="form-group"><label>截止时间</label><input v-model="form.due_at" type="datetime-local" /></div>
          </div>

          <!-- ── 环境与 import 教学策略（Phase 4：教师选择） ────────── -->
          <div class="grid-2">
            <div class="form-group">
              <EnvironmentProfilePicker v-model="form.environment_version_id" show-memory label="运行环境" @loaded="onEnvLoaded" />
              <p v-if="envOptions.length === 0" class="form-hint env-warn">暂无可用环境，请联系管理员配置后创建作业</p>
              <p v-if="selectedEnv && form.environment_version_id" class="form-hint">
                环境最低内存 {{ selectedEnv.minimum_memory_mb }} MB——题目的内存上限不得低于该值
              </p>
            </div>
            <div class="form-group">
              <label>导入规则</label>
              <select v-model="importPolicy" class="import-policy-select">
                <option value="unrestricted">不限制（学生可导入任何库）</option>
                <option value="restricted">限定白名单（教学规则）</option>
              </select>
              <p class="form-hint">导入检查是教学反馈，不是安全边界；安全由运行容器隔离负责</p>
            </div>
          </div>

          <div v-if="importPolicy === 'restricted'" class="form-group">
            <label>允许导入（白名单）</label>
            <div v-if="envImportCandidates.length" class="import-candidates">
              <label v-for="name in envImportCandidates" :key="name" class="import-chip">
                <input type="checkbox" :checked="allowedImports.includes(name)" @change="toggleAllowedImport(name)" />
                {{ name }}
              </label>
            </div>
            <p v-else class="form-hint">当前环境未提供教学库，可留空白名单（仅允许 Python 标准库）</p>
            <p v-if="importMismatchWarning" class="form-hint env-warn">{{ importMismatchWarning }}</p>
          </div>

          <div class="create-actions">
            <button class="btn-ghost btn-sm" type="button" @click="closeCreateModal">取消</button>
            <button class="btn-primary btn-sm" type="button" :disabled="!canCreate" @click="doCreate">确定</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 课程选择弹窗 ──────────────────────────────────────────────── -->
    <div v-if="courseModalOpen" class="modal-backdrop create-backdrop" @click.self="closeCourseModal">
      <div class="create-panel course-picker-panel" role="dialog" aria-modal="true" aria-label="选择课程">
        <header class="create-heading">
          <strong>选择课程</strong>
          <button class="create-close" type="button" aria-label="关闭" @click="closeCourseModal">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </button>
        </header>
        <div class="course-picker-body">
          <div class="manual-row">
            <input
              v-model="manualCourseId"
              class="course-id-input"
              type="text"
              inputmode="numeric"
              placeholder="输入课程 ID"
              @keyup.enter="confirmManualCourse"
            />
            <button class="btn-primary btn-sm manual-confirm" type="button" :disabled="!manualCourseId.trim()" @click="confirmManualCourse">确定</button>
          </div>
          <div class="course-list">
            <button
              v-for="c in courses"
              :key="c.id"
              type="button"
              class="course-item"
              :class="{ active: String(c.id) === form.course_id }"
              @click="pickCourse(c)"
            >
              {{ c.title }}（ID: {{ c.id }}）
            </button>
            <p v-if="courses.length === 0" class="empty-tip">暂无课程，可直接输入课程 ID</p>
          </div>
          <div class="create-actions">
            <button class="btn-ghost btn-sm" type="button" @click="closeCourseModal">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 删除草稿作业确认 ──────────────────────────────────────────── -->
    <ConfirmDialog
      v-if="deleteTarget"
      title="删除作业"
      :message="`确定删除作业「${deleteTarget.title}」？将同时删除其全部题目，此操作不可恢复。`"
      confirm-text="确认删除"
      :danger="true"
      :busy="deleting"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />

    <!-- ── 取消发布确认 ──────────────────────────────────────────────── -->
    <ConfirmDialog
      v-if="unpublishTarget"
      title="取消发布"
      message="取消发布后学生将立即无法查看该作业，作业将回到草稿状态。确定取消发布？"
      confirm-text="确认取消发布"
      :busy="unpublishing"
      @confirm="confirmUnpublish"
      @cancel="unpublishTarget = null"
    />

  </AppLayout>
</template>

<style scoped>
/* 表格在内容区内自适应，避免页面出现横向滚动 */
.table-scroll{overflow-x:hidden}.table-scroll table{width:100%;min-width:0;table-layout:fixed}.table-scroll th,.table-scroll td{overflow:hidden;text-overflow:ellipsis}.table-scroll th:nth-child(1){width:21%}.table-scroll th:nth-child(2){width:20%}.table-scroll th:nth-child(3){width:10%}.table-scroll th:nth-child(4){width:13%}.table-scroll th:nth-child(5){width:12%}.table-scroll th:nth-child(6){width:12%}.table-scroll th:nth-child(7){width:22%}.table-scroll td{white-space:nowrap}.table-scroll td small{white-space:nowrap}.status-pill{white-space:nowrap;word-break:keep-all;display:inline-flex;min-width:max-content}.actions-cell{overflow:hidden;gap:0}.actions-cell button{padding-left:5px;padding-right:5px;font-size:12px}
.metric-icon :deep(svg){display:block}
@media(max-width:1150px){.table-scroll th:nth-child(4),.table-scroll td:nth-child(4),.table-scroll th:nth-child(5),.table-scroll td:nth-child(5),.table-scroll th:nth-child(6),.table-scroll td:nth-child(6){display:none}.table-scroll th:nth-child(1){width:27%}.table-scroll th:nth-child(2){width:27%}.table-scroll th:nth-child(3){width:14%}.table-scroll th:nth-child(7){width:32%}}
@media(max-width:700px){.table-scroll{overflow-x:auto}.table-scroll table{min-width:780px}.table-scroll th:nth-child(n),.table-scroll td:nth-child(n){display:table-cell}.table-scroll th:nth-child(1){width:25%}.table-scroll th:nth-child(2){width:22%}.table-scroll th:nth-child(3){width:12%}.table-scroll th:nth-child(7){width:24%}}
/* ═══════════════════════════════════════════════════════════════════════
   Teacher Assignment Manage — Code Studio
   page-head + create modal + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; min-width: 0; container-type: inline-size; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 0;
}

/* ── 创建弹窗表单（modal-backdrop 体系内） ─────────────────────────── */
.form-hint { margin: 6px 0 0; font-size: var(--text-sm); color: var(--text-secondary); }
/* 创建弹窗主体：内容不多，不设内部滚动（避免出现多余滚动条） */
.create-modal-body {
  display: flex; flex-direction: column; gap: 4px;
}
.create-modal-body .form-group { margin-bottom: var(--space-3); }
/* ── 环境与 import 策略（Phase 4） ─────────────────────────────── */
.import-policy-select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control, 7px);
  background: var(--surface, #fff);
  color: var(--ink, #223);
  font-family: inherit;
  font-size: var(--text-sm, 13px);
}
.env-warn { color: var(--warning, #b7791f); }
.import-candidates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.import-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-raised, #f4f6f8);
  font-size: var(--text-sm, 13px);
  cursor: pointer;
}
.import-chip input { margin: 0; }

/* ── 课程选择：只读展示框（点击打开弹窗） ─────────────────────────── */
.course-picker {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--ink);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}
.course-picker:hover { border-color: var(--accent); }
.course-picker .placeholder { color: var(--text-secondary); }
.picker-chevron { flex: none; color: var(--text-secondary); }

/* ── 课程选择弹窗（modal-backdrop 体系，--modal-left 相对内容区居中） ── */
.modal-backdrop {
  position: fixed;
  z-index: 40;
  /* left 随侧栏宽度（--modal-left 由 AppLayout 提供），弹窗以内容区为基准居中 */
  inset: 0 0 0 var(--modal-left, 0);
  display: flex;
  justify-content: flex-end;
  background: rgba(15, 23, 42, 0.25);
}
/* 双类选择器压过基础 .modal-backdrop 的 justify-content: flex-end */
.modal-backdrop.create-backdrop {
  justify-content: center;
  align-items: center;
}
.create-panel {
  width: min(480px, calc(100% - 32px));
  padding: 24px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}
.create-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.create-heading strong { font-size: 17px; color: var(--ink); }
.create-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 7px;
  cursor: pointer;
}
.create-close:hover { background: var(--hover-bg, #f1f5f9); color: var(--ink); }
.course-picker-body { display: flex; flex-direction: column; gap: 12px; }
.manual-row { display: flex; gap: 8px; }
.manual-row .course-id-input { flex: 1; }
.manual-confirm { flex: none; }
.course-list {
  max-height: 240px;
  overflow-y: auto;
  display: grid;
  gap: 6px;
}
.course-item {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--ink);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}
.course-item:hover { border-color: var(--primary); }
.course-item.active {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary-dark);
  font-weight: 600;
}
.empty-tip {
  margin: 0;
  padding: 16px 0;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.create-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }

/* ── Table card ────────────────────────────────────────────────────── */
.table-card {
  padding: 0; overflow: hidden;
}
.table-card table { margin: 0; }

/* ── Skeleton ──────────────────────────────────────────────────────── */
.skeleton-row {
  display: flex; gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: none; }
.skel-cell { height: 16px; border-radius: var(--radius-sm); }
.w-15 { width: 15%; }
.w-20 { width: 20%; }
.w-25 { width: 25%; }
.w-35 { width: 35%; }

/* ── Cells ─────────────────────────────────────────────────────────── */
.title-cell { font-weight: 500; color: var(--ink); }

/* ── Actions ───────────────────────────────────────────────────────── */
.actions-cell { display: flex; gap: 8px; }
.btn-publish {
  color: var(--accent);
  border-color: var(--accent);
  background: transparent;
}
.btn-publish:hover {
  background: var(--accent);
  color: var(--surface);
  border-color: var(--accent);
}
/* 删除：红色文字按钮（对齐 AiConfigForm 的 .btn-danger-text 风格） */
.btn-delete-text {
  border: none;
  background: none;
  color: var(--danger, #dc2626);
  cursor: pointer;
}
.btn-delete-text:hover { opacity: 0.85; }

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;margin-bottom:22px}.metric-card{display:flex;align-items:center;gap:18px;min-height:106px;padding:20px;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.metric-icon{display:grid;place-items:center;width:54px;height:54px;border-radius:15px}.metric-icon.blue{color:var(--primary);background:#edf4ff}.metric-icon.green{color:#10a66a;background:#eaf9f2}.metric-icon.orange{color:#ef8b10;background:#fff4e7}.metric-icon.purple{color:#7c4ce0;background:#f3edff}.metric-card span:last-child{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}.metric-card small{width:100%;color:var(--text-secondary);font-size:14px}.metric-card strong{color:var(--ink);font-size:27px;line-height:1}.metric-card em{color:var(--text-secondary);font-size:13px;font-style:normal}.data-panel{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow-card)}.filter-bar{display:grid;grid-template-columns:minmax(220px,1.4fr) repeat(3,minmax(150px,.8fr));gap:14px;padding:18px;border-bottom:1px solid var(--border)}.search-control{display:flex;align-items:center;gap:9px;padding:0 13px;border:1px solid var(--border);border-radius:8px;color:var(--text-tertiary)}.search-control input{min-width:0;padding:0;border:0;box-shadow:none!important}.filter-bar select{height:44px;min-width:0}.table-scroll{overflow-x:auto}.table-scroll table{width:100%;min-width:1000px;margin:0}.table-scroll th{height:44px;background:#f8fafc}.table-scroll td{height:68px;padding:10px 16px}.table-scroll td small{display:block;margin-top:3px;color:var(--text-tertiary);font-size:12px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.status-pill{display:inline-flex;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:600}.status-pill.published{color:#099b61;background:#e9f8f1}.status-pill.draft{color:#ef8b10;background:#fff4e7}.status-pill.ended{color:#7443d5;background:#f1ebfd}.text-action,.publish-action,.delete-action{padding:5px 7px;border:0;background:transparent;color:var(--primary);font-size:13px;white-space:nowrap}.publish-action{color:var(--warning)}.delete-action{color:var(--danger)}.pagination-bar{display:flex;justify-content:space-between;padding:14px 18px;border-top:1px solid var(--border);color:var(--text-secondary);font-size:13px}.active-page{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#fff;background:var(--primary)}.loading-list{display:grid;gap:1px;background:var(--border)}.loading-list .skeleton{height:68px}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}}@media(max-width:700px){.metric-grid{grid-template-columns:1fr 1fr;gap:10px}.filter-bar{grid-template-columns:1fr}.table-scroll table{min-width:900px}}
/* 侧栏展开时以内容容器宽度为准，避免作业列表被固定最小宽度推出可视区 */
.data-panel{min-width:0}
.filter-bar{min-width:0}
.filter-bar select,.search-control{min-width:0}
.search-control input{min-width:0}
.table-scroll{min-width:0;overflow-x:hidden}
.table-scroll table{width:100%;min-width:0!important;table-layout:fixed}
.table-scroll th,.table-scroll td{min-width:0;overflow:hidden;text-overflow:ellipsis}
.table-scroll th:nth-child(1){width:20%}.table-scroll th:nth-child(2){width:17%}.table-scroll th:nth-child(3){width:10%}.table-scroll th:nth-child(4){width:12%}.table-scroll th:nth-child(5){width:10%}.table-scroll th:nth-child(6){width:9%}.table-scroll th:nth-child(7){width:22%}
.table-scroll td{white-space:nowrap}.table-scroll td strong,.table-scroll td small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.actions-cell{display:flex;flex-wrap:wrap;align-items:center;gap:0;white-space:normal}.actions-cell button{flex:0 0 auto;padding:4px 5px;font-size:12px;white-space:nowrap}
@container (max-width:1050px){.filter-bar{grid-template-columns:minmax(0,1.3fr) repeat(3,minmax(0,.7fr))}.table-scroll th:nth-child(1){width:28%}.table-scroll th:nth-child(2){width:25%}.table-scroll th:nth-child(3){width:15%}.table-scroll th:nth-child(7){width:32%}.table-scroll th:nth-child(4),.table-scroll td:nth-child(4),.table-scroll th:nth-child(5),.table-scroll td:nth-child(5),.table-scroll th:nth-child(6),.table-scroll td:nth-child(6){display:none}.table-scroll td:last-child{padding-left:8px;padding-right:8px}.actions-cell button{padding:4px;font-size:12px}}
@container (max-width:760px){.filter-bar{grid-template-columns:1fr;padding:12px}.table-scroll{overflow:visible;padding:12px;background:#f8fafc}.table-scroll table,.table-scroll tbody{display:block;width:100%;min-width:0!important}.table-scroll thead{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.table-scroll tbody{display:grid;gap:12px}.table-scroll tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:hidden;border:1px solid var(--border);border-radius:10px;background:var(--surface)}.table-scroll td,.table-scroll td:nth-child(4),.table-scroll td:nth-child(5),.table-scroll td:nth-child(6){display:flex;width:auto;height:auto;min-height:58px;padding:10px 12px;flex-direction:column;justify-content:center;gap:5px;border-bottom:1px solid var(--border);overflow:visible;white-space:normal}.table-scroll td::before{color:var(--text-tertiary);font-size:11px;font-weight:500}.table-scroll td:nth-child(1)::before{content:'作业名称'}.table-scroll td:nth-child(2)::before{content:'所属课程 / 班级'}.table-scroll td:nth-child(3)::before{content:'状态'}.table-scroll td:nth-child(4)::before{content:'截止时间'}.table-scroll td:nth-child(5)::before{content:'提交进度'}.table-scroll td:nth-child(6)::before{content:'最近更新'}.table-scroll td:nth-child(7)::before{content:'操作'}.table-scroll td:nth-child(1),.table-scroll td:nth-child(2),.table-scroll td:nth-child(7){grid-column:1/-1}.table-scroll td:nth-child(6),.table-scroll td:nth-last-child(-n+2){border-bottom:0}.table-scroll td strong,.table-scroll td small{overflow:visible;white-space:normal}.table-scroll .actions-cell{display:flex;flex-direction:row;align-items:center;justify-content:flex-end;gap:6px}.table-scroll .actions-cell::before{margin-right:auto}.actions-cell button{padding:6px 8px}}
</style>
