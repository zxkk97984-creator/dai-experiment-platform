<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { assignmentsAPI } from '../../api/assignments.js'
import { examsAPI } from '../../api/exams.js'

const router = useRouter()

const courseCount = ref(null)
const assignmentCount = ref(null)
const examCount = ref(null)

async function loadCounts() {
  try {
    const cRes = await coursesAPI.list({ per_page: 1 })
    const courses = cRes.data.items || cRes.data
    courseCount.value = Array.isArray(courses) ? courses.length : (courses.total ?? courses.length ?? null)
  } catch { courseCount.value = null }

  try {
    const aRes = await assignmentsAPI.list({ per_page: 1 })
    const assignments = aRes.data.items || aRes.data
    assignmentCount.value = Array.isArray(assignments) ? assignments.length : (assignments.total ?? assignments.length ?? null)
  } catch { assignmentCount.value = null }

  try {
    const eRes = await examsAPI.list({ per_page: 1 })
    const exams = eRes.data.items || eRes.data
    examCount.value = Array.isArray(exams) ? exams.length : (exams.total ?? exams.length ?? null)
  } catch { examCount.value = null }
}

onMounted(loadCounts)
</script>

<template>
  <AppLayout>
    <h1 class="page-title-dark">教师工作台</h1>

    <!-- Stats row -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon stat-icon-courses">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M2.5 4.5h5.5l1.8 2.7h7.7v8.3H2.5V4.5z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ courseCount !== null ? courseCount : '—' }}</span>
          <span class="stat-label">课程数</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon-assignments">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M6 7.5L3.5 10 6 12.5M14 7.5l2.5 2.5-2.5 2.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ assignmentCount !== null ? assignmentCount : '—' }}</span>
          <span class="stat-label">作业数</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon-exams">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="3.5" y="2.5" width="13" height="15" rx="1.3" stroke="currentColor" stroke-width="1.3"/>
            <path d="M6.5 8.5h7M6.5 12h4.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ examCount !== null ? examCount : '—' }}</span>
          <span class="stat-label">考试数</span>
        </div>
      </div>
    </div>

    <!-- Action cards -->
    <div class="action-grid">
      <div class="action-card" @click="router.push('/teacher/courses')">
        <div class="action-icon action-icon-courses">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M3 5h7l2 3h9v10H3V5z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3>课程管理</h3>
        <p>创建和管理课程、章节、课时</p>
      </div>
      <div class="action-card" @click="router.push('/teacher/assignments')">
        <div class="action-icon action-icon-assignments">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M7 9l-3.5 3.5L7 16M17 9l3.5 3.5L17 16" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3>作业管理</h3>
        <p>布置作业、创建判题题目</p>
      </div>
      <div class="action-card" @click="router.push('/teacher/exams')">
        <div class="action-icon action-icon-exams">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="3.5" y="2.5" width="17" height="19" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <path d="M7 10h10M7 14h6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>考试管理</h3>
        <p>创建考试、查看成绩</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Page background override ── */
:deep(.content) {
  background: #0F1118;
}

/* ── Page title ── */
.page-title-dark {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: #D6DEEB;
  margin-bottom: var(--space-6);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

/* ── Stats row ── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-8);
}

.stat-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.stat-card:hover {
  border-color: #E0553D;
  box-shadow: 0 0 12px rgba(224, 85, 61, 0.12);
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-courses {
  background: rgba(26, 92, 138, 0.15);
  color: #4A9FD0;
}

.stat-icon-assignments {
  background: rgba(224, 85, 61, 0.12);
  color: #E0553D;
}

.stat-icon-exams {
  background: rgba(181, 118, 14, 0.15);
  color: #E2A83C;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-family: var(--font-mono);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: #D6DEEB;
  line-height: 1.1;
}

.stat-label {
  font-size: var(--text-xs);
  color: #6A7086;
  letter-spacing: 0.04em;
}

/* ── Action grid ── */
.action-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.action-card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-6) var(--space-5);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}

.action-card:hover {
  border-color: #E0553D;
  box-shadow: 0 0 16px rgba(224, 85, 61, 0.1);
  transform: translateY(-1px);
}

.action-card:active {
  transform: scale(0.99);
}

.action-card h3 {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 400;
  color: #D6DEEB;
  margin: var(--space-4) 0 var(--space-2);
  letter-spacing: -0.01em;
}

.action-card p {
  font-size: var(--text-sm);
  color: #6A7086;
  line-height: 1.5;
}

.action-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon-courses {
  background: rgba(26, 92, 138, 0.15);
  color: #4A9FD0;
}

.action-icon-assignments {
  background: rgba(224, 85, 61, 0.12);
  color: #E0553D;
}

.action-icon-exams {
  background: rgba(181, 118, 14, 0.15);
  color: #E2A83C;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .stats-row,
  .action-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .stats-row,
  .action-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
