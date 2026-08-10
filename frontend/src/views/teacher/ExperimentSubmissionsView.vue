<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { formatDateTime } from '../../utils/format.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()

const submissions = ref([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const summary = reactive({ total: 0, pending: 0, graded: 0 })
const filterOptions = reactive({ courses: [], entries: [] })
const filters = reactive({
  q: '',
  courseId: '',
  entryId: '',
  reviewStatus: '',
  sort: 'submitted_desc',
})

let searchTimer = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const hasFilters = computed(() => Boolean(
  filters.q || filters.courseId || filters.entryId || filters.reviewStatus,
))
const pageNumbers = computed(() => {
  const count = totalPages.value
  if (count <= 5) return Array.from({ length: count }, (_, index) => index + 1)
  const start = Math.max(1, Math.min(page.value - 2, count - 4))
  return Array.from({ length: 5 }, (_, index) => start + index)
})

async function load({ initial = false } = {}) {
  if (initial) loading.value = true
  else refreshing.value = true
  loadError.value = false
  try {
    const params = {
      page: page.value,
      page_size: pageSize,
      sort: filters.sort,
    }
    if (route.query.record_id) params.record_id = route.query.record_id
    if (filters.q.trim()) params.q = filters.q.trim()
    if (filters.courseId) params.course_id = Number(filters.courseId)
    if (filters.entryId) params.entry_id = Number(filters.entryId)
    if (filters.reviewStatus) params.review_status = filters.reviewStatus

    const res = await experimentsAPI.listSubmissions(params)
    submissions.value = res.data?.items || []
    total.value = res.data?.total || 0
    Object.assign(summary, res.data?.summary || { total: 0, pending: 0, graded: 0 })
    filterOptions.courses = res.data?.filter_options?.courses || []
    filterOptions.entries = res.data?.filter_options?.entries || []
  } catch {
    loadError.value = true
    app.showToast('加载提交列表失败', 'error')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function reloadFromFirstPage() {
  page.value = 1
  load()
}

function scheduleSearch() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(reloadFromFirstPage, 300)
}

function viewDetail(subId) {
  const prefix = auth.isAdmin ? '/admin' : '/teacher'
  router.push(`${prefix}/submissions/${subId}`)
}

function goPage(nextPage) {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) return
  page.value = nextPage
  load()
}

function clearFilters() {
  filters.q = ''
  filters.courseId = ''
  filters.entryId = ''
  filters.reviewStatus = ''
  filters.sort = 'submitted_desc'
  window.clearTimeout(searchTimer)
  page.value = 1
  load()
}

function avatarText(submission) {
  const value = submission.student_name || submission.student_username || '学'
  return value.trim().slice(0, 1)
}

watch(() => filters.q, scheduleSearch)
watch(
  () => [filters.courseId, filters.entryId, filters.reviewStatus, filters.sort],
  reloadFromFirstPage,
)

onMounted(() => load({ initial: true }))
onBeforeUnmount(() => window.clearTimeout(searchTimer))
</script>

<template>
  <AppLayout>
    <div class="submissions-page">
      <header class="page-head">
        <h1>提交与评分</h1>
        <p>查看学生实验提交情况，完成评分与反馈</p>
      </header>

      <section class="stats-grid" aria-label="提交统计">
        <article class="stat-card stat-card-primary">
          <span class="stat-icon"><AppIcon name="assignment" :size="22" /></span>
          <span class="stat-copy">
            <span class="stat-label">全部提交</span>
            <strong>{{ summary.total }}</strong>
            <span class="stat-unit">条记录</span>
          </span>
        </article>
        <article class="stat-card stat-card-warning">
          <span class="stat-icon"><AppIcon name="clock" :size="22" /></span>
          <span class="stat-copy">
            <span class="stat-label">待评分</span>
            <strong>{{ summary.pending }}</strong>
            <span class="stat-unit">条记录</span>
          </span>
        </article>
        <article class="stat-card stat-card-success">
          <span class="stat-icon"><AppIcon name="check" :size="22" /></span>
          <span class="stat-copy">
            <span class="stat-label">已评分</span>
            <strong>{{ summary.graded }}</strong>
            <span class="stat-unit">条记录</span>
          </span>
        </article>
      </section>

      <section class="records-panel" aria-label="提交记录">
        <div class="filter-bar">
          <label class="search-control">
            <AppIcon name="search" :size="18" />
            <span class="sr-only">搜索提交记录</span>
            <input v-model="filters.q" type="search" placeholder="搜索学生姓名、账号或实验名称" />
            <button
              v-if="filters.q"
              type="button"
              class="clear-search"
              aria-label="清空搜索"
              @click="filters.q = ''"
            >
              <AppIcon name="close" :size="15" />
            </button>
          </label>

          <label class="select-field">
            <span>课程</span>
            <select v-model="filters.courseId" aria-label="按课程筛选">
              <option value="">全部课程</option>
              <option v-for="course in filterOptions.courses" :key="course.id" :value="String(course.id)">
                {{ course.name }}
              </option>
            </select>
          </label>

          <label class="select-field">
            <span>实验</span>
            <select v-model="filters.entryId" aria-label="按实验筛选">
              <option value="">全部实验</option>
              <option v-for="entry in filterOptions.entries" :key="entry.id" :value="String(entry.id)">
                {{ entry.name }}
              </option>
            </select>
          </label>

          <label class="select-field">
            <span>评分状态</span>
            <select v-model="filters.reviewStatus" aria-label="按评分状态筛选">
              <option value="">全部状态</option>
              <option value="pending">待评分</option>
              <option value="graded">已评分</option>
            </select>
          </label>

          <label class="select-field sort-field">
            <span>排序</span>
            <select v-model="filters.sort" aria-label="提交记录排序">
              <option value="submitted_desc">提交时间（最新）</option>
              <option value="submitted_asc">提交时间（最早）</option>
            </select>
          </label>
        </div>

        <div v-if="loading" class="table-skeleton" aria-label="正在加载提交记录">
          <div v-for="row in 6" :key="row" class="skeleton-row">
            <span class="skeleton skel-wide"></span>
            <span class="skeleton"></span>
            <span class="skeleton skel-wide"></span>
            <span class="skeleton"></span>
            <span class="skeleton"></span>
          </div>
        </div>

        <div v-else-if="loadError" class="state-panel">
          <span class="state-icon state-icon-error"><AppIcon name="warning" :size="24" /></span>
          <strong>提交记录暂时无法加载</strong>
          <p>请检查网络连接后重试。</p>
          <button type="button" class="btn-secondary" @click="load({ initial: true })">重新加载</button>
        </div>

        <div v-else-if="submissions.length === 0" class="state-panel">
          <span class="state-icon"><AppIcon name="assignment" :size="25" /></span>
          <strong>{{ hasFilters ? '没有符合条件的提交' : '暂无提交记录' }}</strong>
          <p>{{ hasFilters ? '调整筛选条件后再试试。' : '学生完成实验提交后，记录会显示在这里。' }}</p>
          <button v-if="hasFilters" type="button" class="btn-secondary" @click="clearFilters">清除筛选</button>
        </div>

        <template v-else>
          <div class="table-wrap" :class="{ refreshing }">
            <table>
              <thead>
                <tr>
                  <th>学生信息</th>
                  <th>所属课程</th>
                  <th>实验名称</th>
                  <th>提交情况</th>
                  <th>提交时间</th>
                  <th>状态</th>
                  <th>得分</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="submission in submissions" :key="submission.id">
                  <td data-label="学生信息">
                    <div class="student-cell">
                      <span class="student-avatar" aria-hidden="true">{{ avatarText(submission) }}</span>
                      <span class="cell-stack">
                        <strong>{{ submission.student_name || '未命名学生' }}</strong>
                        <small>{{ submission.student_username || '—' }}</small>
                      </span>
                    </div>
                  </td>
                  <td data-label="所属课程">
                    <span class="course-name">{{ submission.course_name || '独立实验' }}</span>
                  </td>
                  <td data-label="实验名称">
                    <span class="cell-stack">
                      <strong>{{ submission.entry_name || '未命名实验' }}</strong>
                      <small>{{ submission.entry_type === 'module' ? '实验模块' : 'Notebook 实验' }}</small>
                    </span>
                  </td>
                  <td data-label="提交情况"><span class="attempt-pill">第 {{ submission.attempt_number }} 次提交</span></td>
                  <td data-label="提交时间" class="time-cell">{{ formatDateTime(submission.submitted_at) }}</td>
                  <td data-label="状态">
                    <span class="status-pill" :class="submission.score == null ? 'pending' : 'graded'">
                      {{ submission.score == null ? '待评分' : '已评分' }}
                    </span>
                  </td>
                  <td data-label="得分">
                    <strong v-if="submission.score != null" class="score-value">{{ submission.score }}</strong>
                    <span v-else class="score-empty">—</span>
                  </td>
                  <td data-label="操作">
                    <button
                      type="button"
                      class="row-action"
                      :class="{ primary: submission.score == null }"
                      @click="viewDetail(submission.id)"
                    >
                      {{ submission.score == null ? '去评分' : '查看详情' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="table-footer">
            <span>共 {{ total }} 条记录</span>
            <nav v-if="total > 0" class="pagination" aria-label="提交记录分页">
              <button type="button" aria-label="上一页" :disabled="page === 1" @click="goPage(page - 1)">
                <AppIcon name="back" :size="16" />
              </button>
              <button
                v-for="pageNumber in pageNumbers"
                :key="pageNumber"
                type="button"
                :class="{ active: pageNumber === page }"
                :aria-current="pageNumber === page ? 'page' : undefined"
                @click="goPage(pageNumber)"
              >
                {{ pageNumber }}
              </button>
              <button type="button" aria-label="下一页" :disabled="page === totalPages" @click="goPage(page + 1)">
                <AppIcon name="chevron-right" :size="16" />
              </button>
            </nav>
            <span class="page-size">{{ pageSize }} 条/页</span>
          </footer>
        </template>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
.submissions-page { display: flex; flex-direction: column; gap: 22px; }
.page-head h1 { margin: 0 0 6px; color: var(--ink); font-size: 28px; line-height: 1.2; letter-spacing: -.025em; }
.page-head p { margin: 0; color: var(--text-secondary); font-size: var(--text-sm); }

.stats-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.stat-card {
  min-height: 108px; padding: 22px; display: flex; align-items: center; gap: 18px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.stat-icon {
  width: 52px; height: 52px; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; flex: 0 0 auto;
}
.stat-card-primary .stat-icon { color: var(--primary); background: var(--primary-light); }
.stat-card-warning .stat-icon { color: var(--warning); background: var(--warning-light); }
.stat-card-success .stat-icon { color: var(--success); background: var(--success-light); }
.stat-copy { display: grid; grid-template-columns: auto auto; align-items: baseline; column-gap: 8px; }
.stat-label { grid-column: 1 / -1; margin-bottom: 2px; color: var(--text-secondary); font-size: 13px; }
.stat-copy strong { color: var(--ink); font-size: 30px; line-height: 1; font-weight: 700; }
.stat-card-warning .stat-copy strong { color: var(--warning); }
.stat-card-success .stat-copy strong { color: var(--success); }
.stat-unit { color: var(--text-tertiary); font-size: 12px; }

.records-panel {
  overflow: hidden; background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-card); box-shadow: var(--shadow-card);
}
.filter-bar { display: grid; grid-template-columns: minmax(230px, 1.4fr) repeat(4, minmax(130px, .8fr)); gap: 14px; padding: 20px; }
.search-control { position: relative; display: flex; align-items: center; color: var(--text-secondary); }
.search-control > .app-icon { position: absolute; right: auto; bottom: 12px; left: 13px; pointer-events: none; }
.search-control input { height: 42px; align-self: flex-end; padding: 9px 38px 9px 40px; }
.clear-search {
  position: absolute; right: 9px; display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; padding: 0; border: 0; border-radius: 50%; background: var(--surface-raised);
  color: var(--text-tertiary); cursor: pointer;
}
.select-field { display: flex; flex-direction: column; gap: 5px; }
.select-field > span { color: var(--text-secondary); font-size: 12px; font-weight: 500; }
.select-field select { height: 42px; padding: 8px 32px 8px 11px; cursor: pointer; }

.table-wrap { overflow-x: hidden; border-top: 1px solid var(--border); transition: opacity var(--duration-fast); }
.table-wrap.refreshing { opacity: .55; pointer-events: none; }
table { width: 100%; min-width: 0; table-layout: fixed; }
th { height: 44px; padding: 10px; overflow: hidden; background: #F7F9FC; text-transform: none; letter-spacing: 0; text-overflow: ellipsis; white-space: nowrap; }
td { height: 66px; padding: 10px; overflow: hidden; color: var(--text-secondary); vertical-align: middle; }
th:nth-child(1) { width: 17%; }
th:nth-child(2) { width: 14%; }
th:nth-child(3) { width: 18%; }
th:nth-child(4) { width: 13%; }
th:nth-child(5) { width: 14%; }
th:nth-child(6) { width: 9%; }
th:nth-child(7) { width: 6%; }
th:nth-child(8) { width: 9%; }
tbody tr { transition: background var(--duration-fast); }
tbody tr:hover { background: #FAFCFF; }
.student-cell { display: flex; align-items: center; gap: 10px; }
.student-avatar {
  width: 36px; height: 36px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; flex: 0 0 auto; color: var(--primary); background: var(--primary-light);
  font-size: 14px; font-weight: 600;
}
.cell-stack { display: flex; min-width: 0; flex-direction: column; gap: 1px; }
.cell-stack strong, .course-name { overflow: hidden; color: var(--ink); font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.cell-stack small { overflow: hidden; color: var(--text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.attempt-pill, .status-pill {
  display: inline-flex; align-items: center; width: fit-content; padding: 4px 8px;
  border: 1px solid var(--primary-soft); border-radius: var(--radius-sm); color: var(--primary);
  background: var(--primary-light); font-size: 12px; line-height: 1.2; white-space: nowrap;
}
.status-pill.pending { border-color: var(--warning-soft); color: var(--warning); background: var(--warning-light); }
.status-pill.graded { border-color: var(--success-soft); color: var(--success); background: var(--success-light); }
.time-cell { font-size: 12px; white-space: nowrap; }
.score-value { color: var(--primary); font-size: 14px; }
.score-empty { color: var(--text-tertiary); }
.row-action {
  width: 100%; min-width: 0; padding: 7px 6px; border: 1px solid var(--border-strong); border-radius: var(--radius-control);
  background: var(--surface); color: var(--ink); font-size: 12px; font-weight: 500; cursor: pointer;
}
.row-action:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
.row-action.primary { border-color: var(--primary); color: #fff; background: var(--primary); }
.row-action.primary:hover { border-color: var(--primary-dark); color: #fff; background: var(--primary-dark); }

.table-footer { min-height: 66px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px; padding: 12px 20px; color: var(--text-secondary); font-size: 12px; }
.pagination { display: flex; align-items: center; gap: 6px; }
.pagination button {
  width: 32px; height: 32px; padding: 0; display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid transparent; border-radius: var(--radius-control); background: transparent; color: var(--text-secondary); cursor: pointer;
}
.pagination button:hover:not(:disabled) { border-color: var(--border); background: var(--surface-raised); color: var(--ink); }
.pagination button.active { border-color: var(--primary); background: var(--primary); color: #fff; }
.pagination button:disabled { opacity: .35; cursor: not-allowed; }
.page-size { grid-column: 3; justify-self: end; padding: 6px 10px; border: 1px solid var(--border); border-radius: var(--radius-control); }

.table-skeleton { border-top: 1px solid var(--border); }
.skeleton-row { display: grid; grid-template-columns: 1.4fr 1fr 1.4fr 1fr 1fr; gap: 24px; padding: 20px; border-bottom: 1px solid var(--border); }
.skeleton-row .skeleton { height: 15px; }
.skel-wide { width: 85%; }
.state-panel { min-height: 340px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px; border-top: 1px solid var(--border); text-align: center; }
.state-icon { width: 52px; height: 52px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 14px; border-radius: 50%; color: var(--primary); background: var(--primary-light); }
.state-icon-error { color: var(--danger); background: var(--danger-light); }
.state-panel strong { color: var(--ink); font-size: 15px; }
.state-panel p { margin: 5px 0 16px; color: var(--text-secondary); font-size: 13px; }
.btn-secondary { padding: 8px 16px; border: 1px solid var(--border-strong); border-radius: var(--radius-control); background: var(--surface); color: var(--ink); cursor: pointer; }
.btn-secondary:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

@media (max-width: 1199px) {
  .filter-bar { grid-template-columns: 1.5fr repeat(2, 1fr); }
  .sort-field { grid-column: auto; }
}
@media (max-width: 800px) {
  .submissions-page { gap: 16px; }
  .page-head h1 { font-size: 24px; }
  .stats-grid { grid-template-columns: 1fr; gap: 10px; }
  .stat-card { min-height: 82px; padding: 15px 18px; }
  .stat-icon { width: 44px; height: 44px; }
  .stat-copy strong { font-size: 25px; }
  .filter-bar { grid-template-columns: 1fr; padding: 16px; }
  .table-wrap { overflow: visible; border-top: 0; }
  table, tbody { display: block; width: 100%; }
  thead {
    position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden;
    clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
  }
  tbody { display: grid; gap: 12px; padding: 12px; background: #F7F9FC; }
  tbody tr {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface);
  }
  tbody tr:hover { background: var(--surface); }
  td {
    width: auto !important; height: auto; min-height: 58px; padding: 9px 12px; display: flex;
    flex-direction: column; justify-content: center; gap: 5px; border-bottom: 1px solid var(--border);
  }
  td::before { content: attr(data-label); color: var(--text-tertiary); font-size: 11px; font-weight: 500; }
  td:nth-child(1), td:nth-child(3), td:nth-child(8) { grid-column: 1 / -1; }
  td:nth-last-child(-n + 2) { border-bottom: 0; }
  td:nth-child(7) { border-bottom: 0; }
  .student-cell { align-items: center; }
  .row-action { width: 100%; min-height: 36px; }
  .table-footer { grid-template-columns: 1fr; justify-items: center; }
  .page-size { grid-column: 1; justify-self: center; }
}
</style>
