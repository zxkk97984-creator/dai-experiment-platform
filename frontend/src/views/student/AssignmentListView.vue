<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const assignments = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await assignmentsAPI.list()
    assignments.value = res.data.items || res.data
  } catch { app.showToast('加载作业列表失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">我的作业</h1>
          <p class="page-sub">查看已布置的作业，按时完成并提交代码</p>
        </div>
        <div class="page-meta">
          <div class="meta-pill">
            <span class="pill-dot"></span>
            <span>共 {{ assignments.length }} 份作业</span>
          </div>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="grid-2">
        <div v-for="i in 4" :key="i" class="skel-card">
          <div class="skel-body">
            <div class="skeleton skel-line w-50"></div>
            <div class="skeleton skel-line w-80"></div>
            <div class="skeleton skel-line w-35"></div>
          </div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="assignments.length === 0" class="empty-state">
        <p>✍️ 暂无作业，去课程页面看看吧</p>
        <button class="btn-primary btn-sm" @click="router.push('/student/courses')">浏览课程</button>
      </div>

      <!-- ── Grid ───────────────────────────────────────────────────────── -->
      <div v-else class="grid-2">
        <article
          v-for="a in assignments" :key="a.id"
          class="card assignment-card"
          @click="router.push(`/student/assignments/${a.id}`)"
        >
          <div class="card-inner">
            <div class="flex-between mb-3">
              <h3 class="assignment-title">{{ a.title }}</h3>
              <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">
                {{ statusBadge(PUBLISH_STATUS_MAP, a.status).label }}
              </span>
            </div>
            <p class="assignment-desc" v-if="a.description">{{ a.description }}</p>
            <div class="assignment-meta">
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.1"/>
                <path d="M7 4v3.5L9.5 9" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
              </svg>
              <span>截止: {{ formatDateTime(a.due_at) }}</span>
            </div>
          </div>
        </article>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Assignment List — Code Studio
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
.w-50 { width: 50%; }
.w-80 { width: 80%; }

/* ── Assignment Card — 继承 .card ──────────────────────────────────── */
.assignment-card {
  padding: 24px;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.assignment-card:hover {
  transform: translateY(-2px);
}
.card-inner {
  display: flex; flex-direction: column;
}

.assignment-title {
  margin: 0;
  font-size: 16px; font-weight: 600;
  color: var(--ink);
  line-height: 1.3;
  transition: color var(--duration-fast) var(--ease-out);
}
.assignment-card:hover .assignment-title { color: var(--primary); }

.assignment-desc {
  font-size: var(--text-sm); color: var(--text-secondary);
  line-height: 1.5; margin: 0 0 12px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

.assignment-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: var(--text-xs); color: var(--text-tertiary);
  font-family: var(--font-mono);
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
