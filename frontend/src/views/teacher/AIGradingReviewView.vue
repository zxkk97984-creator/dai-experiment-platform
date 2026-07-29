<template>
  <AppLayout>
  <div class="ai-grading-review">
    <h2>AI 评分复核</h2>

    <div class="filters">
      <select v-model="filterKind" @change="load">
        <option value="">全部类型</option>
        <option value="assignment">作业</option>
        <option value="exam">考试</option>
      </select>
      <select v-model="filterStatus" @change="load">
        <option value="">全部状态</option>
        <option value="pending">等待中</option>
        <option value="queued">排队中</option>
        <option value="running">评分中</option>
        <option value="completed">已完成</option>
        <option value="review_required">需复核</option>
        <option value="system_error">系统错误</option>
      </select>
      <input v-model="filterStudent" placeholder="学生 ID" type="number" @change="load" />
      <button @click="load">查询</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <table v-else-if="items.length" class="grade-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>类型</th>
          <th>模式</th>
          <th>状态</th>
          <th>F</th>
          <th>A</th>
          <th>R</th>
          <th>Q</th>
          <th>原始分</th>
          <th>上限</th>
          <th>最终分</th>
          <th>需复核</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.submission_id ? '作业' : '考试' }}</td>
          <td>{{ item.mode }}</td>
          <td>
            <span :class="'badge badge-' + item.status">{{ statusMap[item.status] || item.status }}</span>
          </td>
          <td>{{ item.functional_score }}</td>
          <td>{{ item.algorithm_score ?? '-' }}</td>
          <td>{{ item.robustness_score }}</td>
          <td>{{ item.quality_score ?? '-' }}</td>
          <td>{{ item.raw_total ?? '-' }}</td>
          <td>{{ item.score_cap ?? '-' }}</td>
          <td>{{ item.final_score_100 ?? '-' }}</td>
          <td>{{ item.needs_teacher_review ? '是' : '否' }}</td>
          <td>
            <router-link :to="basePath + '/' + item.id">详情</router-link>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else>暂无数据</div>

    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="page--; load()">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; load()">下一页</button>
    </div>
  </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAuthStore } from '../../stores/auth.js'
import { aiGradingAPI } from '../../api/aiGrading.js'

const auth = useAuthStore()
const basePath = computed(() => auth.isAdmin ? '/admin/ai-grading' : '/teacher/ai-grading')

const items = ref([])
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filterKind = ref('')
const filterStatus = ref('')
const filterStudent = ref('')

const statusMap = {
  pending: '等待中', queued: '排队中', running: '评分中', completed: '已完成',
  review_required: '需复核', system_error: '系统错误',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterKind.value) params.kind = filterKind.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterStudent.value) params.student_id = Number(filterStudent.value)
    const res = await aiGradingAPI.listGrades(params)
    items.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ai-grading-review { padding: 20px; }
.filters { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
.filters select, .filters input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.grade-table { width: 100%; border-collapse: collapse; }
.grade-table th, .grade-table td { border: 1px solid #eee; padding: 8px 12px; text-align: left; font-size: 14px; }
.badge { padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.badge-completed { background: #d4edda; color: #155724; }
.badge-review_required, .badge-system_error { background: #f8d7da; color: #721c24; }
.badge-pending, .badge-queued { background: #fff3cd; color: #856404; }
.badge-running { background: #cce5ff; color: #004085; }
.error { color: #dc3545; }
.loading { color: #666; }
.pagination { margin-top: 20px; display: flex; gap: 15px; align-items: center; }
</style>
