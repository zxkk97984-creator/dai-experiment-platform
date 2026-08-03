<script setup>
// TeacherScoreOverview：评分工作台顶部概览卡。
// 最终得分大数字 + F/A/R/Q 四条中文评分（字母仅辅助小标签）+ 状态徽章 + 辅助行。

import { computed } from 'vue'
import UiStatusPill from '../ui/UiStatusPill.vue'
import { dimensionRows, reviewState, safeNumber } from '../../utils/gradingUi.js'

const props = defineProps({
  detail: { type: Object, required: true },
})

const state = computed(() => reviewState(props.detail))
const rows = computed(() => dimensionRows(props.detail))
const finalScore = computed(() => {
  const v = props.detail?.final_score_100
  return v == null ? '—' : safeNumber(v)
})

const metaParts = computed(() => {
  const d = props.detail || {}
  const parts = []
  if (d.raw_total != null) parts.push(`原始 ${safeNumber(d.raw_total)}`)
  // cap 为 null 时不显示；为 0 时是合法上限，用 isFinite 判断
  if (d.score_cap != null && Number.isFinite(Number(d.score_cap))) parts.push(`上限 ${safeNumber(d.score_cap)}`)
  if (d.scaled_score != null) parts.push(`折算 ${safeNumber(d.scaled_score)}`)
  return parts
})
</script>

<template>
  <section class="score-overview">
    <div class="score-overview__main">
      <div class="score-overview__score">
        <span class="score-overview__value">{{ finalScore }}</span>
        <span class="score-overview__label">最终得分</span>
        <UiStatusPill :tone="state.tone" :label="state.label" />
      </div>

      <div class="score-overview__dims">
        <div v-for="row in rows" :key="row.key" class="score-overview__dim">
          <span class="score-overview__dim-label">
            {{ row.label }}
            <small class="score-overview__dim-letter">{{ row.letter }}</small>
          </span>
          <strong class="score-overview__dim-score">{{ row.score ?? '—' }} / {{ row.max }}</strong>
        </div>
      </div>
    </div>

    <p v-if="metaParts.length" class="score-overview__meta">
      {{ metaParts.join(' · ') }}
    </p>
  </section>
</template>

<style scoped>
.score-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.score-overview__main {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 24px;
  align-items: stretch;
}

.score-overview__score {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding-right: 24px;
  border-right: 1px solid var(--border);
}

.score-overview__value {
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 64px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.score-overview__label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
}

.score-overview__dims {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
  align-content: center;
  min-width: 0;
}

.score-overview__dim {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  min-width: 0;
}

.score-overview__dim-label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  white-space: nowrap;
}

.score-overview__dim-letter {
  margin-left: 4px;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.score-overview__dim-score {
  color: var(--ink);
  font-size: var(--text-sm);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.score-overview__meta {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 767.98px) {
  .score-overview__main {
    grid-template-columns: 1fr;
  }
  .score-overview__score {
    padding-right: 0;
    padding-bottom: 16px;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
  .score-overview__value {
    font-size: 48px;
  }
  .score-overview__dims {
    grid-template-columns: 1fr;
  }
}
</style>
