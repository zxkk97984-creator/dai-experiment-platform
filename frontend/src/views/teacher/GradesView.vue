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
    <h1 class="page-title">考试成绩</h1>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else-if="grades.length" class="card" style="padding:0">
      <thead><tr><th>学生 ID</th><th>成绩</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="g in grades" :key="g.id">
          <td>{{ g.student_id }}</td>
          <td><strong>{{ g.score }}</strong></td>
          <td class="text-sm text-secondary">{{ g.created_at }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无成绩</p></div>
  </AppLayout>
</template>
