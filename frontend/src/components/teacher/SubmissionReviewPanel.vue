<script setup>
/** 评分工作台组件：分数与反馈输入。校验、API 与提示由父组件处理，提交时上抛规范化载荷。 */
import { computed, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import { formatDateTime } from '../../utils/format.js'

const props = defineProps({
  submission: { type: Object, required: true },
  saving: Boolean,
})
const emit = defineEmits(['submit'])

const reviewScore = ref('')
const reviewFeedback = ref('')

const isGraded = computed(() => props.submission?.score != null)

// 父组件保存后重新加载提交 → 回填最新分数与反馈
watch(() => props.submission, (submission) => {
  reviewScore.value = submission?.score != null ? String(submission.score) : ''
  reviewFeedback.value = submission?.feedback || ''
}, { immediate: true })

function submit() {
  const rawScore = String(reviewScore.value).trim()
  emit('submit', {
    score: rawScore === '' ? null : Number(rawScore),
    feedback: reviewFeedback.value.trim(),
  })
}
</script>

<template>
  <aside class="review-panel" aria-label="评分工作台">
    <header class="panel-head">
      <div>
        <h2>评分工作台</h2>
        <p>评分保存后将同步给学生</p>
      </div>
    </header>

    <div class="current-status">
      <span>当前状态</span>
      <span class="status-pill" :class="isGraded ? 'graded' : 'pending'">{{ isGraded ? '已评分' : '待评分' }}</span>
    </div>

    <div class="score-row">
      <label for="review-score">得分</label>
      <div class="score-input">
        <input
          id="review-score"
          v-model="reviewScore"
          type="number"
          min="0"
          max="100"
          step="0.5"
          inputmode="decimal"
          placeholder="—"
        />
        <span>/ 100</span>
      </div>
    </div>

    <label class="feedback-field" for="review-feedback">
      <span>教师反馈</span>
      <textarea
        id="review-feedback"
        v-model="reviewFeedback"
        rows="8"
        maxlength="500"
        placeholder="请输入对学生提交内容的评价与建议…"
      ></textarea>
      <small>{{ reviewFeedback.length }} / 500</small>
    </label>

    <div v-if="submission?.reviewed_at" class="reviewed-time">
      <AppIcon name="clock" :size="15" />
      上次保存于 {{ formatDateTime(submission.reviewed_at) }}
    </div>

    <button type="button" class="save-button" :disabled="saving" @click="submit">
      <AppIcon name="check" :size="17" />
      {{ saving ? '保存中…' : '保存评分' }}
    </button>
  </aside>
</template>

<style scoped>
.review-panel { position: sticky; top: 16px; overflow: hidden; }
.panel-head { min-height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 18px; border-bottom: 1px solid var(--border); }
.panel-head h2 { margin: 0 0 3px; color: var(--fg); font-size: 15px; }
.panel-head p { margin: 0; color: var(--muted); font-size: 11px; }
.current-status { display: flex; align-items: center; justify-content: space-between; padding: 13px 18px; border-bottom: 1px solid var(--border); color: var(--muted); font-size: 12px; }
.status-pill { display: inline-flex; width: fit-content; padding: 4px 8px; border: 1px solid var(--accent-soft); border-radius: var(--radius-sm); background: var(--accent-soft); color: var(--accent); font-size: 11px; font-weight: 500; }
.status-pill.pending { border-color: var(--warning-bg); background: var(--warning-bg); color: var(--warning); }
.status-pill.graded { border-color: var(--success-bg); background: var(--success-bg); color: var(--success); }
.score-row { padding: 18px; border-bottom: 1px solid var(--border); }
.score-row > label, .feedback-field > span { display: block; margin-bottom: 8px; color: var(--fg); font-size: 12px; font-weight: 600; }
.score-input { display: flex; align-items: center; gap: 10px; }
.score-input input { width: 126px; height: 46px; color: var(--accent); font-size: 21px; font-weight: 700; text-align: center; }
.score-input span { color: var(--muted); font-size: 12px; }
.feedback-field { position: relative; display: block; padding: 18px; border-bottom: 1px solid var(--border); }
.feedback-field textarea { min-height: 166px; resize: vertical; line-height: 1.65; }
.feedback-field small { position: absolute; right: 28px; bottom: 26px; color: var(--faint); font-size: 10px; }
.reviewed-time { display: flex; align-items: center; gap: 6px; padding: 13px 18px 0; color: var(--faint); font-size: 11px; }
.save-button { width: calc(100% - 36px); height: 42px; margin: 16px 18px 18px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; border: 1px solid var(--accent); border-radius: var(--radius-md); background: var(--accent); color: var(--surface); font-size: 13px; font-weight: 600; cursor: pointer; }
.save-button:hover:not(:disabled) { border-color: var(--accent-hover); background: var(--accent-hover); box-shadow: var(--shadow-sm); }
.save-button:disabled { opacity: .55; cursor: not-allowed; }
@media (max-width: 1199px) {
  .review-panel { position: static; }
}
</style>
