<script setup>
import { computed } from 'vue'

const props = defineProps({
  breakdown: {
    type: Object,
    required: true,
  },
  heading: {
    type: String,
    default: 'AI 评分详情',
  },
})

const dimensions = computed(() => {
  const b = props.breakdown
  return [
    { key: 'functional', label: '功能正确性 F', score: b.functional_score, max: 60 },
    { key: 'algorithm', label: '算法关键步骤 A', score: b.algorithm_score, max: 20 },
    { key: 'robustness', label: '鲁棒性与性能 R', score: b.robustness_score, max: 10 },
    { key: 'quality', label: '代码质量 Q', score: b.quality_score, max: 10 },
  ]
})

const finalScore = computed(() => props.breakdown.final_score_100 ?? 0)
const scaledScore = computed(() => props.breakdown.scaled_score ?? null)
const strengths = computed(() => props.breakdown.strengths || [])
const issues = computed(() => props.breakdown.issues || [])
const suggestions = computed(() => props.breakdown.suggestions || [])
const codeSuggestions = computed(() => props.breakdown.code_suggestions || [])
const testGroups = computed(() => props.breakdown.test_groups || [])

const deductions = computed(() => {
  const items = [
    ...(props.breakdown.algorithm_items || []),
    ...(props.breakdown.quality_items || []),
  ]
  return items.filter((item) => {
    const max = Number(item.max_score || 0)
    const score = Number(item.score || 0)
    return score < max || item.level === 'missing' || item.level === 'partial'
  })
})

function percent(score, max) {
  const value = Number(score)
  const limit = Number(max)
  if (!Number.isFinite(value) || !Number.isFinite(limit) || limit <= 0) return 0
  return Math.min(100, Math.max(0, (value / limit) * 100))
}

function diffLines(diff) {
  return String(diff || '').split('\n')
}

function diffClass(line) {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) return 'diff-header'
  if (line.startsWith('+')) return 'diff-add'
  if (line.startsWith('-')) return 'diff-del'
  return 'diff-context'
}
</script>

<template>
  <section class="ai-result evidence-block ai">
    <div class="ai-result-head">
      <h3 class="ai-result-title">{{ heading }}</h3>
      <div v-if="breakdown.raw_total != null" class="ai-result-meta">
        原始 {{ breakdown.raw_total }}
        <template v-if="breakdown.score_cap != null"> · 上限 {{ breakdown.score_cap }}</template>
      </div>
    </div>

    <div class="ai-result-overview">
      <div class="ai-score">
        <div class="ai-score-value">{{ finalScore }}</div>
        <div class="ai-score-label">最终得分</div>
        <div v-if="scaledScore != null" class="ai-score-scaled">本题折算 {{ scaledScore }}</div>
      </div>

      <div class="ai-dimensions">
        <div v-for="dim in dimensions" :key="dim.key" class="ai-dimension">
          <div class="ai-dimension-top">
            <span class="ai-dimension-label">{{ dim.label }}</span>
            <strong class="ai-dimension-score">{{ dim.score ?? '-' }} / {{ dim.max }}</strong>
          </div>
          <div class="ai-dimension-track">
            <span
              class="ai-dimension-fill"
              :style="{ width: percent(dim.score, dim.max) + '%' }"
            ></span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="strengths.length" class="ai-card ai-card-neutral">
      <h4 class="ai-card-title">优点</h4>
      <ul class="ai-card-list">
        <li v-for="(item, index) in strengths" :key="index">{{ item }}</li>
      </ul>
    </div>

    <div v-if="issues.length" class="ai-card ai-card-issue">
      <h4 class="ai-card-title">问题</h4>
      <ul class="ai-card-list">
        <li v-for="(item, index) in issues" :key="index">{{ item }}</li>
      </ul>
    </div>

    <div v-if="suggestions.length || codeSuggestions.length" class="ai-card ai-card-suggestion">
      <h4 class="ai-card-title">改进建议</h4>
      <ul v-if="suggestions.length" class="ai-card-list">
        <li v-for="(item, index) in suggestions" :key="index">{{ item }}</li>
      </ul>

      <div v-for="(suggestion, index) in codeSuggestions" :key="index" class="ai-diff">
        <div class="ai-diff-title">{{ suggestion.title || '代码修改建议' }}</div>
        <pre class="ai-diff-body"><code><span v-for="(line, lineIndex) in diffLines(suggestion.diff)" :key="lineIndex" :class="diffClass(line)">{{ line }}</span></code></pre>
      </div>
    </div>

    <details v-if="deductions.length" class="ai-collapse">
      <summary>扣分依据</summary>
      <div class="ai-collapse-body">
        <div v-for="(item, index) in deductions" :key="index" class="ai-deduction">
          <div class="ai-deduction-head">
            <span class="ai-deduction-name">{{ item.criterion }}</span>
            <span class="ai-deduction-score">{{ item.score }} / {{ item.max_score }}</span>
          </div>
          <div class="ai-deduction-meta">
            <span>{{ item.level }}</span>
            <span v-if="item.code_lines?.length">行 {{ item.code_lines.join(', ') }}</span>
          </div>
          <p class="ai-deduction-evidence">{{ item.evidence }}</p>
          <p v-if="item.deduction_reason" class="ai-deduction-reason">{{ item.deduction_reason }}</p>
        </div>
      </div>
    </details>

    <details v-if="testGroups.length" class="ai-collapse">
      <summary>测试用例结果</summary>
      <div class="ai-collapse-body">
        <div v-for="group in testGroups" :key="group.id" class="ai-test-group">
          <div class="ai-test-group-head">
            <span class="ai-test-group-name">{{ group.name || group.id }}</span>
            <span class="ai-test-group-score">{{ group.score }} / {{ group.max_score }}</span>
          </div>
          <div class="ai-test-counts">
            <span class="test-pass">通过 {{ group.counts?.passed ?? 0 }}</span>
            <span v-if="(group.counts?.failed ?? 0) > 0" class="test-fail">失败 {{ group.counts.failed }}</span>
            <span v-if="(group.counts?.errors ?? 0) > 0" class="test-fail">错误 {{ group.counts.errors }}</span>
            <span v-if="(group.counts?.skipped ?? 0) > 0" class="test-muted">跳过 {{ group.counts.skipped }}</span>
          </div>
        </div>
      </div>
    </details>
  </section>
</template>

<style scoped>
/* V2 学生端 AI 评分结果：AI 证据块（虚线 + info）语义，不紫、不发光。 */
.ai-result { display: flex; flex-direction: column; gap: 16px; }

.ai-result-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.ai-result-title { margin: 0; color: var(--fg); font-size: var(--text-lg); font-weight: 600; }
.ai-result-meta { color: var(--muted); font-size: var(--text-sm); font-variant-numeric: tabular-nums; }

.ai-result-overview {
  display: grid;
  grid-template-columns: 170px 1fr;
  gap: 24px;
  align-items: stretch;
  padding: 16px 0;
  border-top: 1px dashed var(--border-strong);
  border-bottom: 1px dashed var(--border-strong);
}
.ai-score { display: flex; flex-direction: column; justify-content: center; align-items: flex-start; padding-right: 24px; border-right: 1px solid var(--border); }
.ai-score-value { color: var(--fg); font-family: var(--font-mono); font-size: 44px; font-weight: 600; line-height: 1; font-variant-numeric: tabular-nums; letter-spacing: -0.03em; }
.ai-score-label { margin-top: 6px; color: var(--muted); font-size: var(--text-sm); font-weight: 500; }
.ai-score-scaled { margin-top: 6px; color: var(--info); font-size: var(--text-xs); }
.ai-dimensions { display: flex; flex-direction: column; justify-content: center; gap: 12px; min-width: 0; }
.ai-dimension { display: flex; flex-direction: column; gap: 6px; }
.ai-dimension-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.ai-dimension-label { color: var(--muted); font-size: var(--text-sm); }
.ai-dimension-score { color: var(--fg); font-size: var(--text-sm); font-weight: 600; font-variant-numeric: tabular-nums; }
.ai-dimension-track { height: 6px; overflow: hidden; border-radius: var(--radius-sm); background: var(--surface-sunken); }
.ai-dimension-fill { display: block; height: 100%; border-radius: var(--radius-sm); background: var(--accent); }

.ai-card { padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.ai-card-issue { border-color: var(--danger); }
.ai-card-title { margin: 0 0 8px; color: var(--fg); font-size: var(--text-base); font-weight: 600; }
.ai-card-list { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; color: var(--muted); font-size: var(--text-base); line-height: 1.6; }
.ai-card-issue .ai-card-list { color: var(--danger); }

.ai-diff { margin-top: 12px; overflow: hidden; border: 1px solid var(--border-strong); border-radius: var(--radius-lg); background: oklch(0.225 0.018 155); }
.ai-diff-title { padding: 8px 12px; border-bottom: 1px solid oklch(0.32 0.02 155); background: oklch(0.20 0.016 155); color: oklch(0.78 0.015 155); font-size: var(--text-sm); font-weight: 600; }
.ai-diff-body { margin: 0; padding: 12px 14px; overflow-x: auto; font-family: var(--font-mono); font-size: var(--text-base); line-height: 1.65; color: oklch(0.84 0.01 155); }
.ai-diff-body code { display: block; min-width: max-content; }
.ai-diff-body span { display: block; white-space: pre; }
.diff-header { color: oklch(0.62 0.015 155); }
.diff-add { color: var(--success); background: color-mix(in oklch, var(--success) 10%, transparent); }
.diff-del { color: var(--danger); background: color-mix(in oklch, var(--danger) 10%, transparent); }
.diff-context { color: oklch(0.62 0.015 155); }

.ai-collapse { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.ai-collapse summary { cursor: pointer; padding: 11px 14px; color: var(--fg); font-size: var(--text-base); font-weight: 600; list-style: none; }
.ai-collapse summary::after { content: '+'; float: right; color: var(--muted); font-weight: 500; }
.ai-collapse[open] summary::after { content: '−'; }
.ai-collapse-body { display: flex; flex-direction: column; gap: 10px; padding: 0 14px 14px; }
.ai-deduction, .ai-test-group { padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); }
.ai-deduction-head, .ai-test-group-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.ai-deduction-name, .ai-test-group-name { color: var(--fg); font-size: var(--text-base); font-weight: 600; }
.ai-deduction-score, .ai-test-group-score { color: var(--muted); font-size: var(--text-sm); font-variant-numeric: tabular-nums; }
.ai-deduction-meta { display: flex; gap: 10px; margin-top: 4px; color: var(--faint); font-size: var(--text-xs); }
.ai-deduction-evidence, .ai-deduction-reason { margin: 6px 0 0; color: var(--muted); font-size: var(--text-sm); line-height: 1.6; }
.ai-deduction-reason { color: var(--danger); }
.ai-test-counts { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; font-size: var(--text-sm); font-variant-numeric: tabular-nums; }
.test-pass { color: var(--success); }
.test-fail { color: var(--danger); }
.test-muted { color: var(--faint); }

@media (max-width: 820px) {
  .ai-result-overview { grid-template-columns: 1fr; gap: 16px; }
  .ai-score { padding-right: 0; padding-bottom: 16px; border-right: 0; border-bottom: 1px dashed var(--border-strong); }
  .ai-score-value { font-size: 36px; }
}
</style>
