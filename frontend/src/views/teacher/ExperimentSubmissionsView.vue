<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const submissions = ref([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (route.query.record_id) params.record_id = route.query.record_id
    const res = await experimentsAPI.listSubmissions(params)
    submissions.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    app.showToast('加载提交列表失败', 'error')
  } finally {
    loading.value = false
  }
}

function viewDetail(subId) {
  router.push(`/teacher/submissions/${subId}`)
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page-header">
      <h1>实验提交列表</h1>
      <p v-if="!loading" class="subtitle">共 {{ total }} 条提交记录</p>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="submissions.length === 0" class="empty">暂无提交记录</div>

    <div v-else class="submission-list">
      <div v-for="sub in submissions" :key="sub.id" class="submission-card card" @click="viewDetail(sub.id)">
        <div class="card-header">
          <span class="attempt-badge">第 {{ sub.attempt_number }} 次提交</span>
          <span v-if="sub.score != null" class="score">评分: {{ sub.score }}</span>
        </div>
        <div class="card-meta">
          <span>提交时间: {{ new Date(sub.submitted_at).toLocaleString('zh-CN') }}</span>
          <span v-if="sub.feedback" class="feedback-preview">反馈: {{ sub.feedback.substring(0, 100) }}</span>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.page-header { margin-bottom: var(--space-6); }
.page-header h1 { font-size: 24px; font-weight: 700; margin: 0 0 4px; }
.subtitle { color: var(--text-secondary); font-size: var(--text-sm); margin: 0; }
.loading, .empty { text-align: center; padding: var(--space-12); color: var(--text-secondary); }
.submission-card {
  padding: var(--space-4); margin-bottom: var(--space-3); cursor: pointer;
  transition: box-shadow var(--duration-fast);
}
.submission-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.attempt-badge { font-weight: 600; font-size: var(--text-sm); }
.score { color: var(--primary); font-weight: 600; }
.card-meta { display: flex; gap: var(--space-4); font-size: var(--text-xs); color: var(--text-secondary); margin-top: var(--space-2); }
.feedback-preview { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
