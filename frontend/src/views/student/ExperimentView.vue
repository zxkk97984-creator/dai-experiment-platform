<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import ExperimentCatalog from '../../components/student/ExperimentCatalog.vue'
import { experimentsAPI } from '../../api/experiments.js'
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

const summaryItems = computed(() => [
  { key: 'started', label: '进行中', value: summary.value.started },
  { key: 'not_started', label: '未开始', value: summary.value.not_started },
  { key: 'submitted', label: '已提交', value: summary.value.submitted },
  { key: 'graded', label: '已评分', value: summary.value.graded },
  { key: 'total', label: '模块总数', value: summary.value.total },
])

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

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

      <ExperimentCatalog
        :items="items"
        :loading="loading"
        :failed="failed"
        :total="total"
        :page="page"
        :page-count="pageCount"
        :active-status="activeStatus"
        :query="searchInput"
        :sort-by="sortBy"
        :summary="summary"
        @retry="loadCatalog"
        @page="goToPage"
        @open="enterExperiment"
        @update:query="searchInput = $event"
        @update:sort-by="sortBy = $event"
        @select-status="selectStatus"
      />
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

@media (max-width: 1100px) {
  .summary-panel { grid-template-columns: repeat(5, minmax(120px, 1fr)); overflow-x: auto; }
  .summary-item { padding-inline: 14px; }
  .summary-marker { width: 34px; height: 34px; flex-basis: 34px; border-width: 6px; }
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
}
</style>
