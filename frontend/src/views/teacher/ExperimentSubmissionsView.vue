<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import AppLayout from '../../components/layout/AppLayout.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()
const submissions = ref([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 20

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const hasPrev = computed(() => page.value > 1)
const hasNext = computed(() => page.value < totalPages.value)

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
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
  const prefix = auth.isAdmin ? '/admin' : '/teacher'
  router.push(`${prefix}/submissions/${subId}`)
}

function goPage(p) {
  page.value = p
  load()
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
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
          <span v-else class="no-score">未评分</span>
        </div>
        <div class="card-meta">
          <span v-if="sub.student_name" class="student-name">{{ sub.student_name }}</span>
          <span v-if="sub.entry_name" class="entry-name">{{ sub.entry_name }}</span>
          <span>提交时间: {{ formatTime(sub.submitted_at) }}</span>
        </div>
        <div v-if="sub.feedback" class="feedback">
          <span class="feedback-label">反馈:</span>
          {{ sub.feedback.substring(0, 80) }}{{ sub.feedback.length > 80 ? '...' : '' }}
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button :disabled="!hasPrev" @click="goPage(page - 1)" class="page-btn">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
        <button :disabled="!hasNext" @click="goPage(page + 1)" class="page-btn">下一页</button>
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
.no-score { color: var(--text-tertiary); font-size: var(--text-xs); }
.card-meta {
  display: flex; gap: var(--space-4); font-size: var(--text-xs);
  color: var(--text-secondary); margin-top: var(--space-2); flex-wrap: wrap;
}
.student-name { font-weight: 500; color: var(--ink); }
.entry-name { color: var(--text-secondary); }
.feedback {
  margin-top: var(--space-2); font-size: var(--text-xs); color: var(--text-secondary);
  background: var(--surface-raised); padding: 4px 8px; border-radius: var(--radius-sm);
}
.feedback-label { font-weight: 500; }

.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: var(--space-3); margin-top: var(--space-6); padding-top: var(--space-4);
  border-top: 1px solid var(--border);
}
.page-btn {
  padding: 6px 16px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); cursor: pointer; font-size: var(--text-sm);
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn:hover:not(:disabled) { background: var(--primary-light); border-color: var(--primary); }
.page-info { font-size: var(--text-sm); color: var(--text-secondary); }
</style>
