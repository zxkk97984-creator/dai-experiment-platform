<template>
  <AppLayout>
  <div class="ai-grading-detail">
    <h2>评分详情 #{{ gradeId }}</h2>
    <div v-if="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else-if="detail">
      <div class="summary">
        <p><strong>模式：</strong>{{ detail.mode }} | <strong>状态：</strong>{{ detail.status }}</p>
        <p><strong>分数：</strong>F={{ detail.functional_score }} A={{ detail.algorithm_score ?? '-' }} R={{ detail.robustness_score }} Q={{ detail.quality_score ?? '-' }}</p>
        <p><strong>原始总分：</strong>{{ detail.raw_total ?? '-' }} | <strong>上限：</strong>{{ detail.score_cap ?? '-' }} | <strong>最终分：</strong>{{ detail.final_score_100 ?? '-' }} | <strong>折算：</strong>{{ detail.scaled_score ?? '-' }}</p>
        <p v-if="detail.review_reason"><strong>复核原因：</strong>{{ detail.review_reason }}</p>
        <p v-if="detail.last_error"><strong>最近错误：</strong>{{ detail.last_error }}</p>
      </div>

      <div v-if="detail.ai_result" class="ai-result">
        <h3>AI 评分详情</h3>
        <div v-if="detail.ai_result.algorithm?.items?.length">
          <h4>算法评分</h4>
          <table class="item-table">
            <thead><tr><th>项</th><th>等级</th><th>得分/满分</th><th>行号</th><th>证据</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.ai_result.algorithm.items" :key="item.criterion_id">
                <td>{{ item.criterion }}</td>
                <td>{{ item.level }}</td>
                <td>{{ item.score }}/{{ item.max_score }}</td>
                <td>{{ item.code_lines?.join(', ') }}</td>
                <td>{{ item.evidence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="detail.ai_result.code_quality?.items?.length">
          <h4>代码质量</h4>
          <table class="item-table">
            <thead><tr><th>项</th><th>等级</th><th>得分/满分</th><th>行号</th><th>证据</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.ai_result.code_quality.items" :key="item.criterion_id">
                <td>{{ item.criterion }}</td>
                <td>{{ item.level }}</td>
                <td>{{ item.score }}/{{ item.max_score }}</td>
                <td>{{ item.code_lines?.join(', ') }}</td>
                <td>{{ item.evidence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="detail.ai_result.student_feedback">
          <h4>学生反馈</h4>
          <p><strong>优点：</strong>{{ detail.ai_result.student_feedback.strengths?.join('；') || '无' }}</p>
          <p><strong>问题：</strong>{{ detail.ai_result.student_feedback.issues?.join('；') || '无' }}</p>
          <p><strong>建议：</strong>{{ detail.ai_result.student_feedback.suggestions?.join('；') || '无' }}</p>
        </div>
      </div>

      <div class="actions">
        <button @click="doRetry" :disabled="retrying">重试 AI 评分</button>
        <div class="override-form">
          <h4>覆盖评分</h4>
          <label>A: <input v-model.number="ovA" type="number" min="0" max="20" step="0.1" /></label>
          <label>Q: <input v-model.number="ovQ" type="number" min="0" max="10" step="0.1" /></label>
          <label>最终分: <input v-model.number="ovFinal" type="number" min="0" max="100" step="0.1" /></label>
          <label>理由: <input v-model="ovReason" required minlength="3" /></label>
          <button @click="doOverride" :disabled="!ovReason || ovReason.length < 3">提交覆盖</button>
          <div v-if="overrideMsg" :class="overrideOk ? 'success' : 'error'">{{ overrideMsg }}</div>
        </div>
      </div>

      <div v-if="detail.overrides?.length" class="override-history">
        <h3>覆盖历史</h3>
        <div v-for="o in detail.overrides" :key="o.id" class="override-entry">
          <p>原始: {{ JSON.stringify(o.original_snapshot) }}</p>
          <p>替换: {{ JSON.stringify(o.replacement_snapshot) }}</p>
          <p>理由: {{ o.reason }} | 时间: {{ o.created_at }}</p>
        </div>
      </div>

      <details v-if="detail.raw_response">
        <summary>原始 AI 响应（仅教师可见）</summary>
        <pre>{{ detail.raw_response }}</pre>
      </details>
    </template>
  </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { aiGradingAPI } from '../../api/aiGrading.js'

const route = useRoute()
const gradeId = route.params.id
const detail = ref(null)
const loading = ref(true)
const error = ref('')
const retrying = ref(false)
const ovA = ref(null)
const ovQ = ref(null)
const ovFinal = ref(null)
const ovReason = ref('')
const overrideMsg = ref('')
const overrideOk = ref(false)

async function fetchDetail() {
  loading.value = true
  try {
    const res = await aiGradingAPI.getGrade(gradeId)
    detail.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message
  } finally {
    loading.value = false
  }
}

async function doRetry() {
  retrying.value = true
  try {
    await aiGradingAPI.retryGrade(gradeId)
    await fetchDetail()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message
  } finally {
    retrying.value = false
  }
}

async function doOverride() {
  overrideMsg.value = ''
  try {
    await aiGradingAPI.overrideGrade(gradeId, {
      algorithm_score: ovA.value, quality_score: ovQ.value,
      final_score_100: ovFinal.value, reason: ovReason.value,
    })
    overrideOk.value = true
    overrideMsg.value = '覆盖成功'
    await fetchDetail()
  } catch (e) {
    overrideOk.value = false
    overrideMsg.value = e.response?.data?.detail?.message || e.message
  }
}

onMounted(fetchDetail)
</script>

<style scoped>
.ai-grading-detail { padding: 20px; max-width: 900px; }
.summary { background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
.item-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
.item-table th, .item-table td { border: 1px solid #eee; padding: 6px 10px; font-size: 13px; }
.actions { margin: 20px 0; }
.override-form { margin-top: 15px; display: flex; flex-direction: column; gap: 8px; max-width: 400px; }
.override-form label { display: flex; gap: 8px; align-items: center; }
.override-history { margin-top: 20px; }
.override-entry { background: #fff3cd; padding: 10px; border-radius: 4px; margin: 8px 0; }
pre { background: #f5f5f5; padding: 10px; font-size: 12px; overflow-x: auto; max-height: 300px; }
.error { color: #dc3545; }
.success { color: #28a745; }
button { padding: 6px 16px; cursor: pointer; }
</style>
