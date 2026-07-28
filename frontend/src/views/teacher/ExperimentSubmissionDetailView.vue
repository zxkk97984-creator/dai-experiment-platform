<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const submission = ref(null)
const loading = ref(true)
const reviewScore = ref('')
const reviewFeedback = ref('')
const saving = ref(false)

const cells = computed(() => {
  if (!submission.value?.cells_snapshot) return []
  const cellMap = submission.value.cell_metadata || {}
  const outputs = submission.value.outputs_snapshot || {}

  return Object.entries(submission.value.cells_snapshot).map(([id, source], idx) => {
    const meta = cellMap[id] || {}
    return {
      id,
      source: source || '',
      type: meta.type || 'code',
      order: meta.order ?? idx,
      outputs: outputs[id] || null,
    }
  }).sort((a, b) => a.order - b.order)
})

async function load() {
  loading.value = true
  try {
    const res = await experimentsAPI.getSubmission(route.params.id)
    submission.value = res.data
    if (res.data.score != null) reviewScore.value = String(res.data.score)
    if (res.data.feedback) reviewFeedback.value = res.data.feedback
  } catch {
    app.showToast('加载提交详情失败', 'error')
  } finally {
    loading.value = false
  }
}

async function submitReview() {
  const score = reviewScore.value ? parseFloat(reviewScore.value) : null
  if (score != null && (isNaN(score) || score < 0 || score > 100)) {
    app.showToast('评分必须在 0-100 之间', 'error')
    return
  }
  saving.value = true
  try {
    const payload = {}
    if (score != null) payload.score = score
    if (reviewFeedback.value) payload.feedback = reviewFeedback.value
    await experimentsAPI.updateReview(submission.value.id, payload)
    app.showToast('评分已保存', 'success')
    await load()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '评分失败', 'error')
  } finally {
    saving.value = false
  }
}

function goBack() {
  // 根据角色返回正确的提交列表页
  const role = route.meta?.role
  if (role === 'admin') router.push('/admin/submissions')
  else router.push('/teacher/submissions')
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <button class="btn-back" @click="goBack">← 返回提交列表</button>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else-if="submission">
      <div class="detail-header">
        <h1>提交详情 — 第 {{ submission.attempt_number }} 次</h1>
        <p class="meta">提交时间: {{ new Date(submission.submitted_at).toLocaleString('zh-CN') }}</p>
      </div>

      <!-- 快照（只读） -->
      <div class="snapshot-section">
        <h2>提交快照（只读）</h2>
        <div v-for="cell in cells" :key="cell.id" class="cell-card card">
          <div class="cell-header">
            <span class="cell-id">{{ cell.id }}</span>
            <span class="cell-type">{{ cell.type === 'markdown' ? '📝 Markdown' : '💻 Code' }}</span>
            <span class="cell-order">#{{ cell.order }}</span>
          </div>
          <pre class="cell-source">{{ cell.source || '(空)' }}</pre>
          <!-- 输出展示（如有） -->
          <div v-if="cell.outputs" class="cell-outputs">
            <div class="outputs-label">执行输出 (execution_count: {{ cell.outputs.execution_count }})</div>
            <div v-for="(out, oi) in (cell.outputs.outputs || [])" :key="oi" class="output-item">
              <pre class="output-text">{{ out.text || out.data || JSON.stringify(out) }}</pre>
            </div>
          </div>
        </div>
        <div v-if="cells.length === 0" class="empty">无代码快照</div>
      </div>

      <!-- 评分反馈 -->
      <div class="review-section card">
        <h2>评分与反馈</h2>
        <div class="review-form">
          <label>
            评分 (0-100):
            <input type="number" v-model="reviewScore" min="0" max="100" step="0.5"
                   class="input" placeholder="输入评分" />
          </label>
          <label>
            反馈:
            <textarea v-model="reviewFeedback" class="textarea" rows="4"
                      placeholder="输入反馈意见..."></textarea>
          </label>
          <button class="btn-primary" @click="submitReview" :disabled="saving">
            {{ saving ? '保存中...' : '保存评分' }}
          </button>
          <span v-if="submission.reviewed_at" class="reviewed-at">
            上次评分: {{ new Date(submission.reviewed_at).toLocaleString('zh-CN') }}
          </span>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
.btn-back { background: none; border: none; color: var(--primary); cursor: pointer; margin-bottom: var(--space-4); font-size: var(--text-sm); }
.loading, .empty { text-align: center; padding: var(--space-8); color: var(--text-secondary); }
.detail-header { margin-bottom: var(--space-6); }
.detail-header h1 { font-size: 22px; margin: 0 0 4px; }
.meta { color: var(--text-secondary); font-size: var(--text-sm); margin: 0; }
.snapshot-section { margin-bottom: var(--space-8); }
.snapshot-section h2, .review-section h2 { font-size: 16px; margin: 0 0 var(--space-3); }
.cell-card { padding: var(--space-3); margin-bottom: var(--space-2); }
.cell-header { display: flex; align-items: center; gap: var(--space-2); margin-bottom: 4px; }
.cell-id { font-size: var(--text-xs); color: var(--text-secondary); }
.cell-type { font-size: var(--text-xs); padding: 1px 6px; border-radius: 10px; background: var(--primary-light); color: var(--primary); }
.cell-order { font-size: var(--text-xs); color: var(--text-tertiary); }
.cell-source { font-family: var(--font-mono); font-size: 13px; margin: 0; white-space: pre-wrap; word-break: break-all; }
.cell-outputs { margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px dashed var(--border); }
.outputs-label { font-size: var(--text-xs); color: var(--text-secondary); margin-bottom: 4px; }
.output-text { font-family: var(--font-mono); font-size: 12px; background: var(--surface-raised); padding: 6px 8px; border-radius: var(--radius-sm); margin: 0; white-space: pre-wrap; word-break: break-all; }
.review-form { display: flex; flex-direction: column; gap: var(--space-3); }
.review-form label { display: flex; flex-direction: column; gap: 4px; font-size: var(--text-sm); }
.input, .textarea { padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: var(--text-sm); }
.input:focus, .textarea:focus { outline: none; border-color: var(--primary); }
.btn-primary { align-self: flex-start; padding: 8px 24px; background: var(--primary); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; font-size: var(--text-sm); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.reviewed-at { font-size: var(--text-xs); color: var(--text-secondary); }
</style>
