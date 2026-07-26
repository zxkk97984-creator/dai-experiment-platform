<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, EXAM_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const exams = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await examsAPI.list()
    exams.value = res.data.items || res.data
  } catch { app.showToast('加载考试列表失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">考试中心</h1>
          <p class="page-sub">查看即将进行和已结束的考试，进入答题</p>
        </div>
        <div class="page-meta">
          <div class="meta-pill">
            <span class="pill-dot"></span>
            <span>共 {{ exams.length }} 场考试</span>
          </div>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="grid-2">
        <div v-for="i in 4" :key="i" class="skel-card">
          <div class="skel-body">
            <div class="skeleton skel-line w-50"></div>
            <div class="skeleton skel-line w-35"></div>
            <div class="skeleton skel-line w-40"></div>
          </div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="exams.length === 0" class="empty-state">
        <p>📋 暂无考试安排</p>
      </div>

      <!-- ── Grid ───────────────────────────────────────────────────────── -->
      <div v-else class="grid-2">
        <article
          v-for="e in exams" :key="e.id"
          class="card exam-card"
          @click="router.push(`/student/exams/${e.id}`)"
        >
          <div class="card-inner">
            <div class="flex-between mb-3">
              <h3 class="exam-title">{{ e.title }}</h3>
              <span class="badge" :class="'badge-' + statusBadge(EXAM_STATUS_MAP, e.status).color">
                {{ statusBadge(EXAM_STATUS_MAP, e.status).label }}
              </span>
            </div>
            <div class="exam-meta-list">
              <div class="exam-meta">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.1"/>
                  <path d="M7 4v3.5L9.5 9" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
                </svg>
                <span>时长: {{ e.duration_minutes }} 分钟</span>
              </div>
              <div class="exam-meta">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <rect x="1.5" y="2.5" width="11" height="10" rx="1.5" stroke="currentColor" stroke-width="1.1"/>
                  <path d="M1.5 5.5h11 M4 1v3 M10 1v3" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
                </svg>
                <span>开始: {{ formatDateTime(e.start_at) }}</span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Exam List — Code Studio
   page-head + card grid + badge + hover + empty
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
.meta-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 13px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: var(--text-xs); color: var(--text-secondary); font-weight: 500;
}
.pill-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}

/* ── Skeleton ──────────────────────────────────────────────────────── */
.skel-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}
.skel-line { height: 12px; margin-bottom: 8px; border-radius: var(--radius-sm); }
.w-35 { width: 35%; }
.w-40 { width: 40%; }
.w-50 { width: 50%; }

/* ── Exam Card — 继承 .card ──────────────────────────────────────── */
.exam-card {
  padding: 24px;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.exam-card:hover { transform: translateY(-2px); }
.card-inner { display: flex; flex-direction: column; }

.exam-title {
  margin: 0;
  font-size: 16px; font-weight: 600;
  color: var(--ink);
  line-height: 1.3;
  transition: color var(--duration-fast) var(--ease-out);
}
.exam-card:hover .exam-title { color: var(--primary); }

.exam-meta-list {
  display: flex; flex-direction: column; gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.exam-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: var(--text-xs); color: var(--text-secondary);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
