<script setup>
// AIGradingReviewDetailView：教师 AI 评分详情（评分工作台）。
// 顶部上下文 + 突出最终得分 + 两栏卡片布局（≥1200px）+ 高级信息默认折叠置底。
// 主操作按真实状态推导（等待教师复核→确认复核并生效；已完成→调整评分）。

import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import UiStatusPill from '../../components/ui/UiStatusPill.vue'
import TeacherScoreOverview from '../../components/ai/TeacherScoreOverview.vue'
import CodeViewer from '../../components/ai/CodeViewer.vue'
import TeacherReviewPanel from '../../components/ai/TeacherReviewPanel.vue'
import { aiGradingAPI } from '../../api/aiGrading.js'
import { useAuthStore } from '../../stores/auth.js'
import {
  fmtDateTime, feedbackBlocks, modeText, reviewState, safeNumber, statusText, testSummary,
} from '../../utils/gradingUi.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const gradeId = route.params.id
const detail = ref(null)
const loading = ref(true)
const error = ref('')
const retrying = ref(false)
const submitting = ref(false)
const activeLine = ref(null)
const codeViewerRef = ref(null)
const reviewPanelRef = ref(null)

const basePath = computed(() => (auth.isAdmin ? '/admin/ai-grading' : '/teacher/ai-grading'))
const state = computed(() => reviewState(detail.value))
const blocks = computed(() => feedbackBlocks(detail.value?.ai_result?.student_feedback))
const summary = computed(() => testSummary(detail.value?.deterministic_details?.groups))

const pageTitle = computed(() => {
  const t = detail.value?.question_title
  return t ? `${t} · 评分详情` : `提交 #${gradeId} · 评分详情`
})

// AI 评分依据维度（algorithm → 算法关键步骤，code_quality → 代码质量）
const aiDimensions = computed(() => {
  const r = detail.value?.ai_result
  if (!r) return []
  return [
    { key: 'algorithm', title: '算法关键步骤', items: r.algorithm?.items || [] },
    { key: 'quality', title: '代码质量', items: r.code_quality?.items || [] },
  ]
})

// 全部证据涉及的行（CodeViewer 高亮）
const evidenceLines = computed(() => {
  const seen = new Set()
  for (const dim of aiDimensions.value) {
    for (const item of dim.items) {
      for (const n of item.code_lines || []) {
        if (Number.isInteger(n) && n > 0) seen.add(n)
      }
    }
  }
  return [...seen].sort((a, b) => a - b)
})

function levelText(level) {
  const map = { complete: '完成', partial: '部分完成', missing: '未得分' }
  return map[level] || level || ''
}

// 复制原始 JSON（clipboard + 降级）
function copyRaw() {
  const text = detail.value?.raw_response || ''
  if (!text) return
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text))
  } else {
    fallbackCopy(text)
  }
}

function fallbackCopy(text) {
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  } catch {
    /* 静默失败 */
  }
}

const submittedLabel = computed(() => {
  const v = detail.value?.submitted_at
  return v ? `提交时间 ${fmtDateTime(v)}` : ''
})

// 测试摘要行：通过 X/Y · 失败 N · 错误 M · 运行时间
const summaryLine = computed(() => {
  const d = detail.value
  if (!d || !d.deterministic_details?.groups?.length) return ''
  const parts = [`测试通过 ${summary.value.passed} / ${summary.value.total}`]
  if (summary.value.failed > 0) parts.push(`失败 ${summary.value.failed}`)
  if (summary.value.errors > 0) parts.push(`错误 ${summary.value.errors}`)
  if (d.execution_time_ms != null) parts.push(`运行时间 ${safeNumber(d.execution_time_ms)} ms`)
  return parts.join(' · ')
})

// 证据行号 → 代码定位（组件暴露的 focusLine 可能缺失，双可选链防御）
function focusLine(line) {
  activeLine.value = line
  codeViewerRef.value?.focusLine?.(line)
}

// 覆盖提交：页面负责 API 调用、消息、刷新与草稿清理
async function handleOverride(payload) {
  submitting.value = true
  error.value = ''
  try {
    await aiGradingAPI.overrideGrade(gradeId, payload)
    await fetchDetail()
    reviewPanelRef.value?.clearDraft()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '覆盖失败'
  } finally {
    submitting.value = false
  }
}

async function doRetry() {
  retrying.value = true
  error.value = ''
  try {
    await aiGradingAPI.retryGrade(gradeId)
    await fetchDetail()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '重试失败'
  } finally {
    retrying.value = false
  }
}

// 返回列表：回传列表页带出的筛选上下文
function goBack() {
  const query = {}
  for (const key of ['kind', 'status', 'page']) {
    if (route.query[key] != null) query[key] = route.query[key]
  }
  router.push({ path: basePath.value, query })
}

async function fetchDetail() {
  loading.value = true
  error.value = ''
  try {
    const res = await aiGradingAPI.getGrade(gradeId)
    detail.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchDetail)
</script>

<template>
  <AppLayout>
    <div class="grading-workspace">
      <div v-if="loading" class="grading-loading">加载中...</div>
      <div v-else-if="error" class="grading-error">{{ error }}</div>

      <template v-else-if="detail">
        <!-- 页头：上下文 -->
        <header class="grading-head">
          <button type="button" class="grading-back" @click="goBack">
            ← 返回 AI 评分复核
          </button>
          <h1 class="grading-title">{{ pageTitle }}</h1>
          <p class="grading-context">
            <template v-if="detail.student_name"><span>{{ detail.student_name }}</span></template>
            <template v-if="detail.student_username"><span>{{ detail.student_username }}</span></template>
            <template v-if="detail.course_title"><span>{{ detail.course_title }}</span></template>
            <template v-if="submittedLabel"><span>{{ submittedLabel }}</span></template>
            <span>提交编号 #{{ gradeId }}</span>
          </p>
          <div class="grading-status">
            <UiStatusPill :tone="state.tone" :label="state.label" />
          </div>
        </header>

        <!-- 顶部概览 -->
        <TeacherScoreOverview :detail="detail" />
        <p v-if="summaryLine" class="grading-summary-line">{{ summaryLine }}</p>

        <!-- 两栏布局：≥1200 双栏，≤1199 单列 -->
        <div class="grading-layout">
          <div class="grading-main">
            <!-- 学生代码 -->
            <section class="grade-card">
              <h3 class="grade-card__title">学生代码</h3>
              <CodeViewer
                ref="codeViewerRef"
                :code="detail.student_code || ''"
                filename="submission"
                :highlight-lines="evidenceLines"
                :active-line="activeLine"
              />
            </section>

            <!-- 测试结果 -->
            <section v-if="detail.deterministic_details" class="grade-card">
              <h3 class="grade-card__title">测试结果</h3>
              <p v-if="summaryLine" class="grade-card__sub">{{ summaryLine }}</p>
              <table v-if="detail.deterministic_details.groups?.length" class="test-table">
                <thead>
                  <tr>
                    <th>测试组</th>
                    <th>维度</th>
                    <th>得分/满分</th>
                    <th>通过</th>
                    <th>失败</th>
                    <th>错误</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="g in detail.deterministic_details.groups" :key="g.id">
                    <td>{{ g.name || g.id }}</td>
                    <td>{{ g.dimension === 'F' ? '功能正确性' : '鲁棒性与性能' }}</td>
                    <td class="num">{{ safeNumber(g.score) }}/{{ safeNumber(g.max_score) }}</td>
                    <td class="num pass">{{ safeNumber(g.counts?.passed) }}</td>
                    <td class="num" :class="safeNumber(g.counts?.failed) > 0 ? 'fail' : ''">{{ safeNumber(g.counts?.failed) }}</td>
                    <td class="num" :class="safeNumber(g.counts?.errors) > 0 ? 'fail' : ''">{{ safeNumber(g.counts?.errors) }}</td>
                    <td>
                      <span class="group-pill" :class="safeNumber(g.counts?.failed) + safeNumber(g.counts?.errors) > 0 ? 'pill-fail' : 'pill-pass'">
                        {{ safeNumber(g.counts?.failed) + safeNumber(g.counts?.errors) > 0 ? '部分失败' : '通过' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <ul v-if="detail.deterministic_details.system_errors?.length" class="sys-errors">
                <li v-for="(e, ei) in detail.deterministic_details.system_errors" :key="ei">{{ e }}</li>
              </ul>
            </section>

            <!-- AI 评分依据 -->
            <section v-if="detail.ai_result" class="grade-card">
              <h3 class="grade-card__title">AI 评分依据</h3>
              <div v-for="dim in aiDimensions" :key="dim.key" class="evidence-dim">
                <h4 class="evidence-dim__title">{{ dim.title }}</h4>
                <ul v-if="dim.items.length" class="evidence-list">
                  <li v-for="item in dim.items" :key="item.criterion_id" class="evidence-item">
                    <div class="evidence-item__head">
                      <span class="evidence-item__name">{{ item.criterion }}</span>
                      <span class="evidence-item__score">{{ safeNumber(item.score) }}/{{ safeNumber(item.max_score) }}</span>
                    </div>
                    <div class="evidence-item__meta">
                      <span class="level-tag" :class="'level-' + item.level">{{ levelText(item.level) }}</span>
                      <span v-if="item.code_lines?.length" class="evidence-lines">
                        <button
                          v-for="n in item.code_lines"
                          :key="n"
                          type="button"
                          class="line-chip"
                          @click="focusLine(n)"
                        >第 {{ n }} 行</button>
                      </span>
                    </div>
                    <p class="evidence-item__text">{{ item.evidence }}</p>
                  </li>
                </ul>
                <p v-else class="evidence-empty">该维度无评分项</p>
              </div>
            </section>

            <!-- 学生反馈 -->
            <section v-if="detail.ai_result?.student_feedback" class="grade-card">
              <h3 class="grade-card__title">给学生的反馈</h3>
              <div class="feedback-blocks">
                <div v-for="block in blocks" :key="block.key" class="feedback-block">
                  <h4 class="feedback-block__title">{{ block.title }}</h4>
                  <ul v-if="block.items.length" class="feedback-block__list">
                    <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
                  </ul>
                  <p v-else class="feedback-block__empty">{{ block.emptyText }}</p>
                </div>
              </div>
            </section>
          </div>

          <!-- 右侧：教师复核，与左侧内容同步滚动 -->
          <aside class="grading-side">
            <TeacherReviewPanel
              ref="reviewPanelRef"
              :detail="detail"
              :teacher-id="auth.user?.id"
              :submitting="submitting"
              @submit="handleOverride"
            />
          </aside>
        </div>

        <!-- 高级信息：默认折叠，置底 -->
        <details class="advanced-info">
          <summary>高级信息（开发与审计）</summary>
          <div class="advanced-info__body">
            <div class="advanced-info__grid">
              <dl class="kv-list">
                <div class="kv-row">
                  <dt>评分模式</dt>
                  <dd>{{ modeText(detail.mode) }}（{{ detail.mode }}）</dd>
                </div>
                <div class="kv-row">
                  <dt>评分状态</dt>
                  <dd>{{ statusText(detail.status) }}（{{ detail.status }}）</dd>
                </div>
                <div class="kv-row">
                  <dt>评分尝试</dt>
                  <dd>{{ detail.attempt_count }} 次</dd>
                </div>
                <div v-if="detail.ai_result?.rubric_version != null" class="kv-row">
                  <dt>评分规则版本</dt>
                  <dd>评分规则版本 {{ detail.ai_result.rubric_version }}</dd>
                </div>
                <div v-if="detail.rubric_id" class="kv-row">
                  <dt>Rubric ID</dt>
                  <dd>{{ detail.rubric_id }}</dd>
                </div>
                <div v-if="detail.last_error" class="kv-row">
                  <dt>最近错误</dt>
                  <dd class="danger-text">{{ detail.last_error }}</dd>
                </div>
              </dl>

              <div v-if="detail.static_analysis?.metrics" class="static-summary">
                <h4>静态分析</h4>
                <p v-if="detail.static_analysis.parse_error" class="danger-text">
                  语法错误：{{ detail.static_analysis.parse_error }}
                </p>
                <p v-else>
                  {{ detail.static_analysis.metrics.lines }} 行 ·
                  函数 {{ detail.static_analysis.metrics.functions }} 个 ·
                  圈复杂度 {{ detail.static_analysis.metrics.complexity }}
                </p>
                <ul v-if="detail.static_analysis.diagnostics?.length" class="diag-list">
                  <li v-for="(d, i) in detail.static_analysis.diagnostics.slice(0, 20)" :key="i">{{ d }}</li>
                </ul>
              </div>
            </div>

            <div v-if="detail.raw_response" class="raw-json">
              <div class="raw-json__head">
                <span>AI 原始响应</span>
                <button type="button" class="raw-json__copy" @click="copyRaw">复制 JSON</button>
              </div>
              <pre class="raw-json__body"><code>{{ detail.raw_response }}</code></pre>
            </div>
          </div>
        </details>
      </template>
    </div>
  </AppLayout>
</template>

<style scoped>
.grading-workspace {
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.grading-loading { color: var(--text-secondary); padding: 24px 0; }
.grading-error { color: var(--danger); padding: 24px 0; }

/* ── 页头 ─────────────────────────────────────────────────────── */
.grading-head {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.grading-back {
  align-self: flex-start;
  background: none;
  border: none;
  padding: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
}
.grading-back:hover { color: var(--primary); }
.grading-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.25;
}
.grading-context {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.grading-status { align-self: flex-start; }

.grading-summary-line {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* ── 两栏布局 ─────────────────────────────────────────────────── */
.grading-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
}
.grading-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.grading-side {
  min-width: 0;
  align-self: start;
}

@media (max-width: 1199px) {
  .grading-layout { grid-template-columns: 1fr; }
}

/* ── 卡片 ─────────────────────────────────────────────────────── */
.grade-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  min-width: 0;
}
.grade-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}
.grade-card__sub {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* ── 测试表格 ─────────────────────────────────────────────────── */
.test-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.test-table th, .test-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.test-table th {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-tertiary);
}
.test-table .num { font-variant-numeric: tabular-nums; }
.test-table .pass { color: var(--success); }
.test-table .fail { color: var(--danger); }
.group-pill {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
.pill-pass { color: var(--success); background: var(--success-light); }
.pill-fail { color: var(--danger); background: var(--danger-light); }

.sys-errors {
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--danger);
  font-size: var(--text-xs);
  line-height: 1.6;
}

/* ── AI 评分依据 ─────────────────────────────────────────────── */
.evidence-dim { display: flex; flex-direction: column; gap: 8px; }
.evidence-dim + .evidence-dim { margin-top: 12px; }
.evidence-dim__title { margin: 0; font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary); }
.evidence-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
.evidence-item {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--paper);
}
.evidence-item__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.evidence-item__name { font-size: var(--text-sm); font-weight: 600; color: var(--ink); }
.evidence-item__score { font-size: var(--text-sm); font-weight: 700; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.evidence-item__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
.level-tag {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
}
.level-complete { color: var(--success); background: var(--success-light); }
.level-partial { color: var(--warning); background: var(--warning-light); }
.level-missing { color: var(--danger); background: var(--danger-light); }
.evidence-lines { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.line-chip {
  padding: 2px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: var(--surface);
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
}
.line-chip:hover { background: var(--primary-light); }
.evidence-item__text { margin: 6px 0 0; font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }
.evidence-empty { margin: 0; font-size: var(--text-xs); color: var(--text-tertiary); }

/* ── 学生反馈 ─────────────────────────────────────────────────── */
.feedback-blocks { display: flex; flex-direction: column; gap: 12px; }
.feedback-block {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--paper);
}
.feedback-block__title { margin: 0 0 6px; font-size: var(--text-sm); font-weight: 600; color: var(--ink); }
.feedback-block__list { margin: 0; padding: 0; list-style: none; font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.7; }
.feedback-block__list li { padding-left: 14px; position: relative; }
.feedback-block__list li::before { content: '·'; position: absolute; left: 2px; color: var(--text-tertiary); }
.feedback-block__empty { margin: 0; font-size: var(--text-sm); color: var(--text-tertiary); font-style: normal; }

/* ── 高级信息 ─────────────────────────────────────────────────── */
.advanced-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
}
.advanced-info summary {
  cursor: pointer;
  padding: 14px 18px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  list-style: none;
}
.advanced-info summary::after { content: '展开'; float: right; color: var(--text-tertiary); font-weight: 500; }
.advanced-info[open] summary::after { content: '收起'; }
.advanced-info__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0 18px 18px;
  min-width: 0;
}
.advanced-info__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 767.98px) {
  .advanced-info__grid { grid-template-columns: 1fr; }
}
.kv-list { margin: 0; display: flex; flex-direction: column; gap: 6px; }
.kv-row { display: flex; gap: 12px; font-size: var(--text-sm); }
.kv-row dt { color: var(--text-tertiary); min-width: 90px; }
.kv-row dd { margin: 0; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.danger-text { color: var(--danger); }
.static-summary h4 { margin: 0 0 6px; font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary); }
.static-summary p { margin: 0; font-size: var(--text-sm); color: var(--text-secondary); }
.diag-list { margin: 8px 0 0; padding: 0 0 0 18px; font-size: var(--text-xs); color: var(--text-tertiary); line-height: 1.6; }
.raw-json {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
}
.raw-json__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: var(--paper);
  border-bottom: 1px solid var(--border);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}
.raw-json__copy {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
}
.raw-json__copy:hover { color: var(--primary); background: var(--primary-light); }
.raw-json__body {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  padding: 12px 14px;
  background: #0f172a;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
}
</style>
