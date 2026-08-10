<template>
  <AppLayout>
    <main class="ai-grading-review">
      <header class="page-heading">
        <div>
          <h1>AI 评分复核</h1>
          <p>查看自动评分结果，及时处理需要教师复核的记录</p>
        </div>
      </header>

      <section class="summary-grid" aria-label="评分汇总">
        <article class="summary-card">
          <span class="summary-icon total-icon"><AppIcon name="assignment" :size="24" /></span>
          <div><span>全部评分</span><strong>{{ summary.total }}</strong><small>条记录</small></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon review-icon"><AppIcon name="clock" :size="24" /></span>
          <div><span>需复核</span><strong class="warning-number">{{ summary.review }}</strong><small>条记录</small></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon complete-icon"><AppIcon name="check" :size="26" /></span>
          <div><span>已完成</span><strong class="success-number">{{ summary.completed }}</strong><small>条记录</small></div>
        </article>
      </section>

      <section class="records-panel">
        <form class="filter-bar" @submit.prevent="applyFilters">
          <label class="search-field">
            <span class="visually-hidden">搜索学生</span>
            <AppIcon name="search" :size="22" />
            <input v-model="filterStudent" placeholder="搜索学生 ID 或姓名" />
            <button v-if="filterStudent" class="clear-button" type="button" aria-label="清空搜索" @click="clearSearch">
              <AppIcon name="close" :size="16" />
            </button>
          </label>

          <label class="filter-field">
            <span>评分类型</span>
            <select v-model="filterKind" @change="applyFilters">
              <option value="">全部类型</option>
              <option value="assignment">作业</option>
              <option value="exam">考试</option>
            </select>
          </label>

          <label class="filter-field status-filter">
            <span>评分状态</span>
            <select v-model="filterStatus" @change="applyFilters">
              <option value="">全部状态</option>
              <option value="pending">等待中</option>
              <option value="queued">排队中</option>
              <option value="running">评分中</option>
              <option value="completed">已完成</option>
              <option value="review_required">需复核</option>
              <option value="system_error">系统错误</option>
            </select>
          </label>

          <button class="query-button" type="submit">查询</button>
        </form>

        <div v-if="loading" class="table-skeleton" aria-label="正在加载评分记录">
          <div v-for="row in 5" :key="row" class="skeleton-row"><span v-for="cell in 7" :key="cell" /></div>
        </div>

        <div v-else-if="error" class="state-panel error-state" role="alert">
          <span class="state-icon">!</span>
          <strong>评分记录加载失败</strong>
          <p>{{ error }}</p>
          <button type="button" @click="load">重新加载</button>
        </div>

        <template v-else-if="items.length">
          <div class="table-wrap">
            <table class="grade-table">
              <thead>
                <tr>
                  <th>学生信息</th>
                  <th>评分记录</th>
                  <th>分项得分</th>
                  <th>原始分</th>
                  <th>最终得分</th>
                  <th>评分状态</th>
                  <th>复核状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id">
                  <td data-label="学生信息">
                    <div class="student-cell">
                      <span class="avatar">{{ studentInitial(item) }}</span>
                      <div><strong>{{ item.student_name || '未知学生' }}</strong><small>学生 ID：{{ item.student_id ?? '-' }}</small></div>
                    </div>
                  </td>
                  <td data-label="评分记录">
                    <div class="record-cell">
                      <strong>#{{ item.id }} · {{ item.submission_id ? '作业' : '考试' }}</strong>
                      <small>{{ modeMap[item.mode] || item.mode || '-' }}<template v-if="item.created_at"> · {{ formatDateTime(item.created_at) }}</template></small>
                    </div>
                  </td>
                  <td data-label="分项得分">
                    <div class="score-parts">
                      <span><small>F</small>{{ displayScore(item.functional_score) }}</span>
                      <span><small>A</small>{{ displayScore(item.algorithm_score) }}</span>
                      <span><small>R</small>{{ displayScore(item.robustness_score) }}</span>
                      <span><small>Q</small>{{ displayScore(item.quality_score) }}</span>
                    </div>
                  </td>
                  <td data-label="原始分"><span class="raw-score">{{ displayScore(item.raw_total) }}</span><small v-if="item.score_cap != null" class="score-cap">上限 {{ item.score_cap }}</small></td>
                  <td data-label="最终得分"><strong class="final-score">{{ displayScore(item.final_score_100) }}</strong></td>
                  <td data-label="评分状态"><span :class="['status-badge', `status-${item.status}`]">{{ statusMap[item.status] || item.status }}</span></td>
                  <td data-label="复核状态"><span :class="['review-badge', { required: item.needs_teacher_review }]">{{ item.needs_teacher_review ? '需复核' : '无需复核' }}</span></td>
                  <td data-label="操作"><router-link class="row-action" :to="`${basePath}/${item.id}`">查看详情</router-link></td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="pagination-bar">
            <span>共 {{ total }} 条记录</span>
            <nav v-if="totalPages > 1" class="pagination" aria-label="评分记录分页">
              <button type="button" :disabled="page === 1" aria-label="上一页" @click="goToPage(page - 1)">‹</button>
              <button v-for="pageItem in pageItems" :key="pageItem.key" type="button" :class="{ active: pageItem.value === page }" :disabled="pageItem.value === null" @click="pageItem.value && goToPage(pageItem.value)">{{ pageItem.label }}</button>
              <button type="button" :disabled="page === totalPages" aria-label="下一页" @click="goToPage(page + 1)">›</button>
            </nav>
            <span>{{ pageSize }} 条/页</span>
          </footer>
        </template>

        <div v-else class="state-panel empty-state">
          <span class="empty-icon"><AppIcon name="assignment" :size="30" /></span>
          <strong>{{ hasFilters ? '没有符合筛选条件的记录' : '暂无 AI 评分记录' }}</strong>
          <p>{{ hasFilters ? '可以调整搜索关键词或筛选条件后再试。' : '产生自动评分结果后，记录会显示在这里。' }}</p>
          <button v-if="hasFilters" type="button" @click="resetFilters">清除筛选</button>
        </div>
      </section>
    </main>
  </AppLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { useAuthStore } from '../../stores/auth.js'
import { aiGradingAPI } from '../../api/aiGrading.js'
import { createLatestRequestGuard } from '../../utils/latestRequest.js'
import { formatDateTime } from '../../utils/format.js'

const auth = useAuthStore()
const basePath = computed(() => auth.isAdmin ? '/admin/ai-grading' : '/teacher/ai-grading')
const items = ref([])
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const filterKind = ref('')
const filterStatus = ref('')
const filterStudent = ref('')
const summary = reactive({ total: 0, review: 0, completed: 0 })

const statusMap = {
  pending: '等待中', queued: '排队中', running: '评分中', completed: '已完成',
  review_required: '需复核', system_error: '系统错误',
}
const modeMap = { active: '正式评分', shadow: '影子评分', legacy: '传统评分' }
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const hasFilters = computed(() => Boolean(filterKind.value || filterStatus.value || filterStudent.value.trim()))
const pageItems = computed(() => {
  const count = totalPages.value
  if (count <= 7) return Array.from({ length: count }, (_, index) => ({ key: index + 1, value: index + 1, label: index + 1 }))
  const values = page.value <= 4
    ? [1, 2, 3, 4, 5, null, count]
    : page.value >= count - 3
      ? [1, null, count - 4, count - 3, count - 2, count - 1, count]
      : [1, null, page.value - 1, page.value, page.value + 1, null, count]
  return values.map((value, index) => ({ key: `${value}-${index}`, value, label: value ?? '…' }))
})

function buildParams() {
  const params = { page: page.value, page_size: pageSize }
  if (filterKind.value) params.kind = filterKind.value
  if (filterStatus.value) params.status = filterStatus.value
  const studentFilter = filterStudent.value.trim()
  if (studentFilter) {
    if (/^\d+$/.test(studentFilter)) params.student_id = Number(studentFilter)
    else params.student_name = studentFilter
  }
  return params
}

const requestGuard = createLatestRequestGuard()

async function load() {
  const token = requestGuard.begin()
  loading.value = true
  error.value = ''
  try {
    const res = await aiGradingAPI.listGrades(buildParams())
    if (!requestGuard.isLatest(token)) return
    items.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    if (!requestGuard.isLatest(token)) return
    error.value = e.response?.data?.detail?.message || e.message || '加载失败，请稍后重试'
  } finally {
    if (requestGuard.isLatest(token)) loading.value = false
  }
}

async function loadSummary() {
  try {
    const [all, review, completed] = await Promise.all([
      aiGradingAPI.listGrades({ page: 1, page_size: 1 }),
      aiGradingAPI.listGrades({ page: 1, page_size: 1, status: 'review_required' }),
      aiGradingAPI.listGrades({ page: 1, page_size: 1, status: 'completed' }),
    ])
    summary.total = all.data.total || 0
    summary.review = review.data.total || 0
    summary.completed = completed.data.total || 0
  } catch {
    summary.total = total.value
  }
}

function applyFilters() { page.value = 1; load() }
function clearSearch() { filterStudent.value = ''; applyFilters() }
function resetFilters() { filterStudent.value = ''; filterKind.value = ''; filterStatus.value = ''; applyFilters() }
function goToPage(nextPage) { if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) return; page.value = nextPage; load() }
function studentInitial(item) { return (item.student_name || String(item.student_id ?? '学')).trim().slice(0, 1) }
function displayScore(value) { return value == null ? '—' : value }

onMounted(() => { load(); loadSummary() })
onBeforeUnmount(() => requestGuard.invalidate())
</script>

<style scoped>
.ai-grading-review { min-width: 0; display: flex; flex-direction: column; gap: 22px; padding: 0; color: var(--ink); }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin: 0; }
.page-heading h1 { margin: 0 0 6px; font-size: 28px; line-height: 1.2; letter-spacing: -.025em; font-weight: 700; }
.page-heading p { margin: 0; color: var(--text-secondary); font-size: var(--text-sm); }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 0; }
.summary-card { min-height: 108px; padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: var(--shadow-card); display: flex; align-items: center; gap: 18px; }
.summary-icon { width: 52px; height: 52px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; }
.total-icon { color: var(--primary); background: var(--primary-light); }
.review-icon { color: var(--warning); background: var(--warning-light); }
.complete-icon { color: var(--success); background: var(--success-light); }
.summary-card div { line-height: 1; }
.summary-card div > span { display: block; margin-bottom: 2px; color: var(--text-secondary); font-size: 13px; }
.summary-card strong { font-size: 30px; line-height: 1; color: var(--ink); }
.summary-card small { margin-left: 8px; color: var(--text-tertiary); font-size: 12px; }
.summary-card .warning-number { color: var(--warning); }
.summary-card .success-number { color: var(--success); }
.records-panel { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: var(--shadow-card); }
.filter-bar { display: grid; grid-template-columns: minmax(230px, 1.4fr) repeat(2, minmax(130px, .8fr)) 96px; align-items: end; gap: 14px; padding: 20px; border-bottom: 1px solid var(--border); }
.search-field { position: relative; height: 42px; border: 1px solid var(--border); border-radius: var(--radius-control); display: flex; align-items: center; gap: 11px; padding: 0 15px; color: var(--text-secondary); background: var(--surface); }
.search-field:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 12%, transparent); }
.search-field input { min-width: 0; width: 100%; height: 100%; border: 0; outline: 0; color: var(--ink); background: transparent; font: inherit; }
.search-field input:focus { border-color: transparent; box-shadow: none; }
.search-field input::placeholder { color: var(--text-secondary); opacity: .75; }
.clear-button { width: 26px; height: 26px; padding: 0; border: 0; border-radius: 50%; background: var(--bg); color: var(--text-secondary); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
.filter-field { display: grid; gap: 5px; color: var(--text-secondary); font-size: 12px; }
.filter-field select { width: 100%; height: 42px; padding: 8px 32px 8px 11px; border: 1px solid var(--border); border-radius: var(--radius-control); outline: 0; background: var(--surface); color: var(--ink); font: inherit; }
.filter-field select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 12%, transparent); }
.query-button, .state-panel button { height: 42px; border: 0; border-radius: var(--radius-control); background: var(--primary); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }
.query-button:hover, .state-panel button:hover { filter: brightness(.96); }
.table-wrap { width: 100%; overflow-x: hidden; }
.grade-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.grade-table th { height: 44px; padding: 0 10px; overflow: hidden; background: var(--bg); color: var(--text-secondary); text-align: left; text-overflow: ellipsis; font-size: 13px; font-weight: 600; white-space: nowrap; }
.grade-table th:nth-child(1) { width: 17%; }.grade-table th:nth-child(2) { width: 17%; }.grade-table th:nth-child(3) { width: 18%; }.grade-table th:nth-child(4) { width: 8%; }.grade-table th:nth-child(5) { width: 9%; }.grade-table th:nth-child(6) { width: 11%; }.grade-table th:nth-child(7) { width: 10%; }.grade-table th:nth-child(8) { width: 10%; }
.grade-table td { height: 66px; padding: 10px; overflow: hidden; border-top: 1px solid var(--border); vertical-align: middle; font-size: 14px; }
.grade-table tbody tr { transition: background .18s ease; }.grade-table tbody tr:hover { background: color-mix(in srgb, var(--primary) 2.5%, var(--surface)); }
.student-cell { display: flex; align-items: center; gap: 10px; min-width: 0; }.avatar { width: 36px; height: 36px; flex: 0 0 auto; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: var(--primary-light); color: var(--primary); font-size: 16px; font-weight: 700; }
.student-cell div, .record-cell { min-width: 0; display: grid; gap: 5px; }.student-cell strong, .record-cell strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.student-cell small, .record-cell small, .score-cap { color: var(--text-secondary); font-size: 12px; }
.score-parts { display: grid; grid-template-columns: repeat(4, minmax(28px, 1fr)); gap: 5px; }.score-parts span { padding: 5px 3px; border-radius: 6px; background: var(--bg); text-align: center; color: var(--ink); font-size: 13px; }.score-parts small { display: block; margin-bottom: 2px; color: var(--text-secondary); font-size: 10px; }
.raw-score { display: block; }.score-cap { display: block; margin-top: 4px; }.final-score { color: var(--primary); font-size: 18px; }
.status-badge, .review-badge { display: inline-flex; align-items: center; justify-content: center; min-height: 28px; padding: 3px 10px; border-radius: 6px; white-space: nowrap; font-size: 12px; }
.status-completed { color: var(--success); background: var(--success-light); }.status-pending, .status-queued { color: var(--warning); background: var(--warning-light); }.status-running { color: var(--primary); background: var(--primary-light); }.status-review_required, .status-system_error { color: var(--danger); background: var(--danger-light); }
.review-badge { color: var(--text-secondary); background: var(--bg); }.review-badge.required { color: var(--warning); background: var(--warning-light); }
.row-action { width: 100%; min-width: 0; max-width: 100%; height: 36px; box-sizing: border-box; padding: 0 4px; border: 1px solid var(--border); border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink); text-decoration: none; white-space: nowrap; font-size: 12px; transition: .18s ease; }.row-action:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
.pagination-bar { min-height: 70px; padding: 12px 22px; border-top: 1px solid var(--border); display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px; color: var(--text-secondary); font-size: 13px; }.pagination-bar > span:last-child { justify-self: end; padding: 9px 12px; border: 1px solid var(--border); border-radius: 7px; color: var(--ink); }
.pagination { display: flex; align-items: center; gap: 6px; }.pagination button { min-width: 34px; height: 34px; padding: 0 8px; border: 0; border-radius: 7px; background: transparent; color: var(--ink); cursor: pointer; }.pagination button:hover:not(:disabled) { background: var(--primary-light); color: var(--primary); }.pagination button.active { background: var(--primary); color: #fff; }.pagination button:disabled { color: var(--text-secondary); cursor: default; opacity: .5; }
.state-panel { min-height: 330px; padding: 48px 24px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }.state-panel strong { margin-top: 16px; font-size: 18px; }.state-panel p { max-width: 440px; margin: 8px 0 20px; color: var(--text-secondary); }.state-panel button { min-width: 112px; padding: 0 18px; }.empty-icon, .state-icon { width: 62px; height: 62px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: var(--primary-light); color: var(--primary); }.error-state .state-icon { background: var(--danger-light); color: var(--danger); font-size: 26px; font-weight: 700; }
.table-skeleton { padding: 10px 20px 20px; }.skeleton-row { height: 76px; border-bottom: 1px solid var(--border); display: grid; grid-template-columns: 1.3fr 1.3fr 1.4fr .7fr .7fr .9fr .8fr; align-items: center; gap: 24px; }.skeleton-row span { height: 16px; border-radius: 6px; background: linear-gradient(90deg, var(--bg) 25%, color-mix(in srgb, var(--border) 65%, var(--surface)) 50%, var(--bg) 75%); background-size: 200% 100%; animation: shimmer 1.3s infinite; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes shimmer { to { background-position: -200% 0; } }

@media (max-width: 1199px) {
  .ai-grading-review { padding: 26px 24px 34px; }.summary-card { padding: 21px; }.filter-bar { grid-template-columns: minmax(220px, 1.25fr) repeat(2, minmax(145px, .75fr)) 82px; padding: 22px; gap: 12px; }.grade-table th, .grade-table td { padding-left: 8px; padding-right: 8px; }.score-parts { gap: 3px; }
}
@media (max-width: 900px) {
  .summary-grid { gap: 12px; }.summary-card { min-height: 110px; gap: 14px; }.summary-icon { width: 52px; height: 52px; }.summary-card strong { font-size: 29px; }.filter-bar { grid-template-columns: 1fr 1fr; }.search-field { grid-column: 1 / -1; }.query-button { align-self: end; }.status-filter { grid-column: auto; }
  .grade-table th:nth-child(4), .grade-table td:nth-child(4) { display: none; }.grade-table th:nth-child(1) { width: 22%; }.grade-table th:nth-child(2) { width: 21%; }.grade-table th:nth-child(3) { width: 21%; }.grade-table th:nth-child(5) { width: 10%; }.grade-table th:nth-child(6) { width: 11%; }.grade-table th:nth-child(7) { width: 11%; }.grade-table th:nth-child(8) { width: 12%; }
}
@media (max-width: 767px) {
  .ai-grading-review { padding: 20px 15px 30px; }.page-heading { margin-bottom: 18px; }.page-heading h1 { font-size: 25px; }.page-heading p { font-size: 14px; }.summary-grid { grid-template-columns: 1fr; }.summary-card { min-height: 94px; padding: 17px 20px; }.summary-icon { width: 50px; height: 50px; }.filter-bar { grid-template-columns: 1fr; padding: 16px; }.search-field, .status-filter { grid-column: auto; }.query-button { width: 100%; }
  .table-wrap { overflow: visible; padding: 12px; }.grade-table, .grade-table tbody { display: block; }.grade-table thead { display: none; }.grade-table tr { display: grid; grid-template-columns: 1fr auto; gap: 14px 18px; margin-bottom: 12px; padding: 17px; border: 1px solid var(--border); border-radius: 10px; }.grade-table td, .grade-table td:nth-child(4) { width: auto; height: auto; padding: 0; border: 0; display: block; }.grade-table td::before { content: attr(data-label); display: block; margin-bottom: 6px; color: var(--text-secondary); font-size: 11px; }.grade-table td:nth-child(1), .grade-table td:nth-child(2), .grade-table td:nth-child(3) { grid-column: 1 / -1; }.grade-table td:nth-child(3) { padding: 11px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }.grade-table td:nth-child(8) { display: flex; align-items: flex-end; justify-content: flex-end; }.grade-table td:nth-child(8)::before { display: none; }.score-parts { max-width: 320px; }.row-action { min-width: 90px; }.pagination-bar { grid-template-columns: 1fr auto; }.pagination { grid-column: 1 / -1; grid-row: 1; justify-content: center; }.pagination-bar > span:last-child { justify-self: end; }
}
</style>
