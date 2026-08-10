<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import UiStatusPill from '../../components/ui/UiStatusPill.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { formatDateTime } from '../../utils/format.js'
import { EXPERIMENT_STATUS_MAP, statusBadge } from '../../utils/status.js'
import { createLatestRequestGuard } from '../../utils/latestRequest.js'

const router = useRouter()

const items = ref([])
const summary = ref({ total: 0, not_started: 0, started: 0, submitted: 0, graded: 0 })
const loading = ref(true)
const failed = ref(false)
const searchInput = ref('')
const query = ref('')
const activeStatus = ref('')
const sortBy = ref('default')
const page = ref(1)
const pageSize = 10
const total = ref(0)
let searchTimer = null
const requestGuard = createLatestRequestGuard()

const statusTabs = computed(() => [
  { value: '', label: '全部', count: summary.value.total },
  { value: 'started', label: '进行中', count: summary.value.started },
  { value: 'not_started', label: '未开始', count: summary.value.not_started },
  { value: 'submitted', label: '已提交', count: summary.value.submitted },
  { value: 'graded', label: '已评分', count: summary.value.graded },
])

const summaryItems = computed(() => [
  { key: 'started', label: '进行中', value: summary.value.started },
  { key: 'not_started', label: '未开始', value: summary.value.not_started },
  { key: 'submitted', label: '已提交', value: summary.value.submitted },
  { key: 'graded', label: '已评分', value: summary.value.graded },
  { key: 'total', label: '模块总数', value: summary.value.total },
])

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const visiblePages = computed(() => {
  const start = Math.max(1, Math.min(page.value - 2, pageCount.value - 4))
  const end = Math.min(pageCount.value, start + 4)
  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
})
const isFiltered = computed(() => Boolean(query.value || activeStatus.value))

function statusMeta(value) {
  return statusBadge(EXPERIMENT_STATUS_MAP, value)
}

function actionLabel(value) {
  if (value === 'not_started') return '开始实验'
  if (value === 'graded') return '查看实验'
  return '继续实验'
}

async function loadCatalog() {
  const sequence = requestGuard.begin()
  loading.value = true
  failed.value = false
  try {
    const response = await experimentsAPI.listStudentCatalog({
      q: query.value || undefined,
      status: activeStatus.value || undefined,
      sort: sortBy.value,
      page: page.value,
      page_size: pageSize,
    })
    if (!requestGuard.isLatest(sequence)) return
    const data = response.data
    items.value = data.items || []
    summary.value = data.summary || summary.value
    total.value = data.total || 0
    if (page.value > Math.max(1, Math.ceil(total.value / pageSize))) {
      page.value = Math.max(1, Math.ceil(total.value / pageSize))
    }
  } catch {
    if (!requestGuard.isLatest(sequence)) return
    items.value = []
    failed.value = true
  } finally {
    if (requestGuard.isLatest(sequence)) loading.value = false
  }
}

function selectStatus(value) {
  if (activeStatus.value === value) return
  activeStatus.value = value
  page.value = 1
}

function goToPage(value) {
  const nextPage = Math.min(Math.max(value, 1), pageCount.value)
  if (nextPage !== page.value) page.value = nextPage
}

function enterExperiment(module) {
  router.push(`/student/experiments/${module.id}`)
}

watch(searchInput, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const nextQuery = value.trim()
    if (query.value === nextQuery) return
    query.value = nextQuery
    page.value = 1
    loadCatalog()
  }, 350)
})

watch([activeStatus, sortBy, page], loadCatalog)

onMounted(loadCatalog)
onBeforeUnmount(() => { clearTimeout(searchTimer); requestGuard.invalidate() })
</script>

<template>
  <AppLayout>
    <div class="experiment-page">
      <header class="page-head">
        <div>
          <h1>实验模块</h1>
          <p>进入在线实验环境，动手实践编程与数据分析</p>
        </div>
      </header>

      <section class="summary-panel" aria-label="实验状态汇总">
        <div
          v-for="stat in summaryItems"
          :key="stat.key"
          class="summary-item"
          :class="`summary-item--${stat.key}`"
        >
          <span class="summary-marker" aria-hidden="true"></span>
          <span class="summary-copy">
            <span class="summary-label">{{ stat.label }}</span>
            <strong>{{ stat.value }} <small>个模块</small></strong>
          </span>
        </div>
      </section>

      <section class="catalog-section">
        <div class="catalog-toolbar">
          <div class="status-tabs" role="tablist" aria-label="按实验状态筛选">
            <button
              v-for="tab in statusTabs"
              :key="tab.value || 'all'"
              type="button"
              role="tab"
              :aria-selected="activeStatus === tab.value"
              :class="{ active: activeStatus === tab.value }"
              @click="selectStatus(tab.value)"
            >
              {{ tab.label }}
              <span>{{ tab.count }}</span>
            </button>
          </div>

          <div class="catalog-tools">
            <label class="search-box">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="7"></circle>
                <path d="m20 20-3.7-3.7"></path>
              </svg>
              <span class="sr-only">搜索实验模块</span>
              <input v-model="searchInput" type="search" placeholder="搜索实验模块名称" />
            </label>
            <label class="sort-select">
              <span class="sr-only">实验排序</span>
              <select v-model="sortBy">
                <option value="default">默认排序</option>
                <option value="recent_desc">最近学习</option>
                <option value="name_asc">名称排序</option>
              </select>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 10 4 4 4-4"></path></svg>
            </label>
          </div>
        </div>

        <div class="catalog-heading">
          <h2>{{ activeStatus ? statusMeta(activeStatus).label : '全部实验模块' }}</h2>
          <span>共 {{ total }} 个</span>
        </div>

        <div v-if="loading" class="table-shell loading-shell" aria-label="正在加载实验模块">
          <div v-for="index in 6" :key="index" class="skeleton-row">
            <span class="skeleton skeleton-name"></span>
            <span class="skeleton skeleton-status"></span>
            <span class="skeleton skeleton-date"></span>
            <span class="skeleton skeleton-action"></span>
          </div>
        </div>

        <div v-else-if="failed" class="table-shell state-panel" role="alert">
          <strong>实验模块加载失败</strong>
          <p>请检查网络连接后重试。</p>
          <button type="button" class="retry-button" @click="loadCatalog">重新加载</button>
        </div>

        <div v-else-if="items.length === 0" class="table-shell state-panel">
          <strong>{{ isFiltered ? '没有找到匹配的实验模块' : '暂无可学习的实验模块' }}</strong>
          <p>{{ isFiltered ? '请尝试更换关键词或状态筛选。' : '教师发布实验后会显示在这里。' }}</p>
        </div>

        <div v-else class="table-shell">
          <table class="catalog-table">
            <thead>
              <tr>
                <th>实验名称</th>
                <th>状态</th>
                <th>最近学习</th>
                <th class="action-column">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="module in items" :key="module.id">
                <td data-label="实验名称">
                  <strong class="module-name" :title="module.name">{{ module.name }}</strong>
                </td>
                <td data-label="状态">
                  <UiStatusPill
                    :tone="statusMeta(module.learning_status).tone"
                    :label="statusMeta(module.learning_status).label"
                  />
                </td>
                <td data-label="最近学习" class="last-learning">
                  {{ module.last_learning_at ? formatDateTime(module.last_learning_at) : '—' }}
                </td>
                <td data-label="操作" class="action-column">
                  <button type="button" class="enter-button" @click="enterExperiment(module)">
                    {{ actionLabel(module.learning_status) }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <nav v-if="!loading && !failed && total > 0" class="pagination" aria-label="实验模块分页">
          <span class="pagination-total">共 {{ total }} 条</span>
          <div class="pagination-controls">
            <button
              type="button"
              class="page-arrow"
              :disabled="page === 1"
              aria-label="上一页"
              @click="goToPage(page - 1)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
            </button>
            <button
              v-for="pageNumber in visiblePages"
              :key="pageNumber"
              type="button"
              class="page-number"
              :class="{ active: pageNumber === page }"
              :aria-current="pageNumber === page ? 'page' : undefined"
              @click="goToPage(pageNumber)"
            >
              {{ pageNumber }}
            </button>
            <button
              type="button"
              class="page-arrow"
              :disabled="page === pageCount"
              aria-label="下一页"
              @click="goToPage(page + 1)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>
            </button>
          </div>
          <span class="page-size">10 条/页</span>
        </nav>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
.experiment-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--ink);
}

.page-head h1 {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.025em;
}

.page-head p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.summary-panel {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  min-height: 116px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.summary-item {
  --marker: var(--primary);
  --marker-bg: var(--primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-width: 0;
  padding: 24px 18px;
  position: relative;
}

.summary-item + .summary-item::before {
  content: '';
  position: absolute;
  inset: 28px auto 28px 0;
  width: 1px;
  background: var(--border);
}

.summary-item--not_started { --marker: #f59e0b; --marker-bg: #fff7e7; }
.summary-item--submitted { --marker: #8b5cf6; --marker-bg: #f4efff; }
.summary-item--graded { --marker: var(--success); --marker-bg: var(--success-light); }
.summary-item--total { --marker: var(--primary); --marker-bg: var(--primary-light); }

.summary-marker {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border-radius: 50%;
  background: var(--marker-bg);
  border: 8px solid color-mix(in srgb, var(--marker) 24%, transparent);
  box-shadow: inset 0 0 0 4px #fff;
}

.summary-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.summary-label {
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.summary-copy strong {
  font-size: 22px;
  line-height: 1;
  font-weight: 700;
}

.summary-copy small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 400;
}

.catalog-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.catalog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 58px;
  padding: 0 14px 0 20px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.status-tabs {
  display: flex;
  align-self: stretch;
  gap: 28px;
}

.status-tabs button {
  position: relative;
  flex: 0 0 auto;
  min-width: auto;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  box-shadow: none;
}

.status-tabs button:hover,
.status-tabs button.active {
  color: var(--primary);
  background: transparent;
  transform: none;
}

.status-tabs button.active::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--primary);
}

.status-tabs button span {
  margin-left: 3px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.catalog-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-box,
.sort-select {
  display: flex;
  align-items: center;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: #fff;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}

.search-box:focus-within,
.sort-select:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-light);
}

.search-box {
  width: 250px;
  padding: 0 11px;
  gap: 8px;
}

.search-box svg,
.sort-select svg {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  fill: none;
  stroke: var(--text-tertiary);
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.search-box input,
.sort-select select {
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 13px;
  box-shadow: none;
}

.search-box input:focus,
.sort-select select:focus { box-shadow: none; }

.sort-select {
  position: relative;
  width: 120px;
  padding: 0 10px 0 12px;
}

.sort-select select {
  appearance: none;
  cursor: pointer;
  padding-right: 18px;
}

.sort-select svg {
  position: absolute;
  right: 9px;
  pointer-events: none;
}

.catalog-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.catalog-heading h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
}

.catalog-heading span {
  color: var(--text-secondary);
  font-size: 13px;
}

.table-shell {
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.catalog-table {
  margin: 0;
  table-layout: fixed;
}

.catalog-table th {
  height: 46px;
  padding: 0 20px;
  background: #f8fafc;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.catalog-table th:first-child { width: 48%; }
.catalog-table th:nth-child(2) { width: 16%; }
.catalog-table th:nth-child(3) { width: 22%; }
.catalog-table th:last-child { width: 14%; }

.catalog-table td {
  height: 60px;
  padding: 0 20px;
  border-top: 1px solid var(--border);
  vertical-align: middle;
}

.catalog-table tbody tr {
  transition: background var(--duration-fast);
}

.catalog-table tbody tr:hover { background: #f8fbff; }

.module-name {
  display: block;
  overflow: hidden;
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.last-learning {
  color: var(--text-secondary);
  font-size: 13px;
}

.action-column { text-align: right; }

.enter-button,
.retry-button {
  min-height: 32px;
  padding: 6px 14px;
  border: 1px solid var(--primary-soft);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.enter-button:hover,
.retry-button:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

.state-panel {
  display: flex;
  min-height: 240px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 40px 20px;
  text-align: center;
}

.state-panel strong { font-size: 16px; }
.state-panel p {
  margin: 8px 0 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

.loading-shell { padding: 0 20px; }
.skeleton-row {
  display: grid;
  grid-template-columns: 48% 16% 22% 14%;
  align-items: center;
  height: 60px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: 0; }
.skeleton { height: 12px; border-radius: var(--radius-sm); }
.skeleton-name { width: 58%; }
.skeleton-status { width: 64px; }
.skeleton-date { width: 120px; }
.skeleton-action { width: 72px; justify-self: end; }

.pagination {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 40px;
  color: var(--text-secondary);
  font-size: 12px;
}

.pagination-controls {
  display: flex;
  gap: 8px;
}

.pagination button {
  width: 34px;
  height: 34px;
  min-width: 34px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--text-secondary);
  font-size: 12px;
}

.pagination button:hover:not(:disabled) {
  border-color: var(--primary-soft);
  color: var(--primary);
}

.pagination button.active {
  border-color: var(--primary);
  background: var(--primary);
  color: #fff;
}

.pagination button:disabled { cursor: not-allowed; opacity: .45; }
.pagination svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.page-size { justify-self: end; }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1100px) {
  .summary-panel { grid-template-columns: repeat(5, minmax(120px, 1fr)); overflow-x: auto; }
  .summary-item { padding-inline: 14px; }
  .summary-marker { width: 34px; height: 34px; flex-basis: 34px; border-width: 6px; }
  .catalog-toolbar { align-items: stretch; flex-direction: column; padding: 0 16px 14px; }
  .status-tabs { min-height: 54px; overflow-x: auto; }
  .catalog-tools { justify-content: flex-end; }
}

@media (max-width: 767.98px) {
  .experiment-page { gap: 16px; }
  .page-head h1 { font-size: 24px; }
  .summary-panel {
    grid-template-columns: repeat(2, 1fr);
    overflow: visible;
  }
  .summary-item { justify-content: flex-start; min-height: 82px; padding: 16px; }
  .summary-item + .summary-item::before { display: none; }
  .summary-item:nth-child(odd) { border-right: 1px solid var(--border); }
  .summary-item:nth-child(n + 3) { border-top: 1px solid var(--border); }
  .summary-item:last-child { grid-column: 1 / -1; justify-content: center; border-right: 0; }
  .summary-copy strong { font-size: 19px; }
  .catalog-toolbar { padding-inline: 12px; }
  .status-tabs { gap: 22px; }
  .catalog-tools { align-items: stretch; flex-direction: column; }
  .search-box, .sort-select { width: 100%; }
  .table-shell { overflow: visible; border: 0; background: transparent; box-shadow: none; }
  .catalog-table, .catalog-table tbody { display: block; }
  .catalog-table thead { display: none; }
  .catalog-table tr {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 14px 18px;
    margin-bottom: 10px;
    padding: 18px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xs);
  }
  .catalog-table td {
    display: block;
    width: auto;
    height: auto;
    padding: 0;
    border: 0;
    text-align: left;
  }
  .catalog-table td:first-child { grid-column: 1 / -1; }
  .catalog-table td:nth-child(3) { align-self: center; }
  .catalog-table td:nth-child(3)::before {
    content: '最近学习  ';
    color: var(--text-tertiary);
  }
  .catalog-table .action-column { grid-column: 1 / -1; justify-self: end; }
  .module-name { white-space: normal; }
  .loading-shell { padding: 0; }
  .skeleton-row {
    grid-template-columns: 1fr 80px;
    height: 126px;
    margin-bottom: 10px;
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: #fff;
  }
  .skeleton-date { display: none; }
  .pagination { grid-template-columns: 1fr auto; }
  .pagination-total { display: none; }
  .pagination-controls { justify-self: start; }
}

@media (prefers-reduced-motion: reduce) {
  .catalog-table tbody tr,
  .search-box,
  .sort-select { transition: none; }
}
</style>
