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
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">考试成绩</h1>
          <p class="page-sub">{{ grades.length ? '共 ' + grades.length + ' 名学生' : '暂无成绩记录' }}</p>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 4" :key="i">
          <div class="skeleton skel-cell w-30"></div>
          <div class="skeleton skel-cell w-20"></div>
          <div class="skeleton skel-cell w-40"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="grades.length === 0" class="empty-state">
        <p>📊 暂无成绩记录</p>
      </div>

      <!-- ── Table ──────────────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table>
          <thead>
            <tr><th>学生 ID</th><th>成绩</th><th>时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="g in grades" :key="g.id">
              <td>{{ g.student_id }}</td>
              <td><strong class="score-value">{{ g.score }}</strong></td>
              <td class="text-sm text-secondary">{{ g.created_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Exam Grades — Code Studio
   page-head + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 0;
}

/* ── Table ──────────────────────────────────────────────────────────── */
.table-card { padding: 0; overflow: hidden; }
.table-card table { margin: 0; }

/* ── Skeleton ──────────────────────────────────────────────────────── */
.skeleton-row {
  display: flex; gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: none; }
.skel-cell { height: 16px; border-radius: var(--radius-sm); }
.w-20 { width: 20%; }
.w-30 { width: 30%; }
.w-40 { width: 40%; }

/* ── Score ──────────────────────────────────────────────────────────── */
.score-value {
  font-size: var(--text-md); font-weight: 700;
  font-family: var(--font-mono); color: var(--accent);
}
</style>