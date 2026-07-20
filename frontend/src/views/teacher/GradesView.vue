<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const grades = ref([])
const loading = ref(true)

onMounted(async () => {
  try { const res = await examsAPI.getGrades(route.params.id); grades.value = res.data.items || res.data || [] }
  catch { app.showToast('加载成绩失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <h1 class="page-title">考试成绩 📊</h1>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="grades.length" class="data-table">
      <thead><tr><th>学生 ID</th><th>成绩</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="g in grades" :key="g.id">
          <td>{{ g.student_id }}</td>
          <td><strong class="score-value">{{ g.score }}</strong></td>
          <td class="text-sm text-secondary">{{ g.created_at }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无成绩</p></div>
  </AppLayout>
</template>

<style scoped>
/* ── Data table ── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.data-table th {
  background: var(--surface-sunken);
  color: var(--text-secondary);
}

.data-table td {
  border-bottom: 1px solid var(--border);
}

.data-table tbody tr:hover td {
  background: var(--surface-raised);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

/* ── Score value ── */
.score-value {
  font-size: 1.125rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
}
</style>
