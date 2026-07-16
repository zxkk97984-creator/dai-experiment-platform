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
          <td><strong class="score-value">{{ g.score }}</strong></td>
          <td class="text-sm text-secondary">{{ g.created_at }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="card" style="text-align:center;padding:48px"><p class="text-secondary">暂无成绩</p></div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   GradesView — Dark Admin Theme
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page title ─────────────────────────────────────────────────────── */
.page-title {
  color: #D6DEEB;
}

/* ── Cards ──────────────────────────────────────────────────────────── */
.card {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #D6DEEB;
}
.card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  border-color: #3A4050;
}

/* ── Table ──────────────────────────────────────────────────────────── */
table {
  color: #D6DEEB;
}
th {
  background: #151821;
  color: #8891A4;
  border-bottom-color: #2A3040;
}
td {
  border-bottom-color: #2A3040;
}
tbody tr:hover td {
  background: #1F2433;
}

/* ── Score value ────────────────────────────────────────────────────── */
.score-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: #E0553D;
}

/* ── Type utilities ─────────────────────────────────────────────────── */
.text-secondary {
  color: #8891A4;
}
.text-sm {
  color: #8891A4;
}
</style>
