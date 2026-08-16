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
/* V2 评分总览：最终得分用 .score-orb 大数字，维度用 .score-bar。
   面板 / 徽标视觉来自全局 token，卡片不再投影。 */
.score-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.score-overview__main {
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 20px;
  align-items: stretch;
}

.score-overview__score {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding-right: 20px;
  border-right: 1px solid var(--border);
}

.score-overview__value {
  color: var(--fg);
  font-family: var(--font-mono);
  font-size: 44px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.score-overview__label { color: var(--muted); font-size: var(--text-sm); font-weight: 500; }

.score-overview__dims {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
  align-content: center;
  min-width: 0;
}

.score-overview__dim {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  min-width: 0;
}

.score-overview__dim-label { color: var(--muted); font-size: var(--text-sm); font-weight: 500; white-space: nowrap; }
.score-overview__dim-letter { margin-left: 4px; font-size: var(--text-xs); color: var(--faint); }
.score-overview__dim-score { color: var(--fg); font-size: var(--text-sm); font-weight: 600; font-variant-numeric: tabular-nums; }

.score-overview__meta {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 820px) {
  .score-overview__main { grid-template-columns: 1fr; }
  .score-overview__score { padding-right: 0; padding-bottom: 12px; border-right: none; border-bottom: 1px solid var(--border); }
  .score-overview__dims { grid-template-columns: 1fr; }
}
</style>
