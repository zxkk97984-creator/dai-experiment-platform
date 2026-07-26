<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'
import { formatDate } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const loading = ref(true)
const total = ref(0)
const page = ref(1)
const pageSize = 12

async function fetchCourses() {
  loading.value = true
  try {
    const res = await coursesAPI.list({ page: page.value, page_size: pageSize })
    courses.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    app.showToast('加载课程列表失败', 'error')
  } finally { loading.value = false }
}

async function handleEnroll(course) {
  try {
    await coursesAPI.enroll(course.id)
    app.showToast('选课成功 🎉', 'success')
    fetchCourses()
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '选课失败'
    app.showToast(msg, 'error')
  }
}

function goDetail(id) { router.push(`/student/courses/${id}`) }

const cardColors = ['blue', 'green', 'orange', 'purple', 'cyan', 'pink']
function colorFor(id) { return cardColors[id % cardColors.length] }

onMounted(fetchCourses)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Header ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">课程目录</h1>
          <p class="page-sub">浏览本期可修读课程，点击卡片查看详情或选课</p>
        </div>
        <div class="page-meta">
          <div class="meta-pill">
            <span class="pill-dot"></span>
            <span>共 {{ total }} 门课程</span>
          </div>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────── -->
      <div v-if="loading" class="grid-3">
        <div v-for="i in 6" :key="i" class="skel-card">
          <div class="skeleton skel-top"></div>
          <div class="skel-body">
            <div class="skeleton skel-line w-60"></div>
            <div class="skeleton skel-line w-90"></div>
            <div class="skeleton skel-line w-40"></div>
            <div class="skeleton skel-btn"></div>
          </div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────── -->
      <div v-else-if="courses.length === 0" class="empty-state">
        <div class="empty-emoji">📭</div>
        <p>本期尚无可修读课程</p>
      </div>

      <!-- ── Grid ───────────────────────────────────────────────────── -->
      <div v-else class="grid-3">
        <article
          v-for="(c, i) in courses" :key="c.id"
          class="course-card"
          :class="'card-' + colorFor(i)"
          @click="goDetail(c.id)"
        >
          <div class="card-top">
            <div class="card-icon">{{ ['📘', '📗', '📙', '📓', '📔', '📕'][i % 6] }}</div>
            <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, c.status).color">
              {{ statusBadge(PUBLISH_STATUS_MAP, c.status).label }}
            </span>
          </div>

          <div class="card-body">
            <div class="card-code">CRS-{{ String(c.id).padStart(4, '0') }}</div>
            <h3 class="card-title">{{ c.title }}</h3>
            <p class="card-desc">{{ c.description || '暂无简介。点击查看课程详情。' }}</p>

            <div class="card-foot">
              <div class="card-date">
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                  <rect x="1.5" y="2.5" width="11" height="10" rx="1.5" stroke="currentColor" stroke-width="1.1"/>
                  <path d="M1.5 5.5h11 M4 1v3 M10 1v3" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
                </svg>
                <span>{{ formatDate(c.created_at) }}</span>
              </div>
              <button
                class="btn-primary btn-sm enroll-btn"
                @click.stop="handleEnroll(c)"
              >
                选课
                <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6h8 M6 2l4 4-4 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        </article>
      </div>

      <!-- ── Pagination ─────────────────────────────────────────────── -->
      <nav v-if="total > pageSize" class="pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="page--; fetchCourses()">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M10 3l-5 5 5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          上一页
        </button>
        <div class="pg-meta">
          <span class="pg-current">{{ page }}</span>
          <span class="pg-sep">/</span>
          <span class="pg-total">{{ Math.ceil(total / pageSize) }}</span>
        </div>
        <button class="pg-btn" :disabled="page >= Math.ceil(total / pageSize)" @click="page++; fetchCourses()">
          下一页
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </nav>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Course List — modern card grid
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* Header */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.meta-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 13px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}
.pill-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}

/* Skeleton */
.skel-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.skel-top { height: 80px; border-radius: 0; }
.skel-body { padding: 20px; }
.skel-line { height: 12px; margin-bottom: 8px; border-radius: var(--radius-sm); }
.skel-btn { height: 32px; width: 80px; margin-top: 14px; border-radius: var(--radius-md); }
.w-40 { width: 40%; }
.w-60 { width: 60%; }
.w-90 { width: 90%; }

/* Empty */
.empty-emoji {
  font-size: 48px;
  margin-bottom: 8px;
}
.empty-state p {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Course card */
.course-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  display: flex; flex-direction: column;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.course-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-3px);
}

.card-top {
  height: 80px;
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}
.card-top::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.85;
  z-index: 0;
}
.card-blue   .card-top::before { background: linear-gradient(135deg, var(--primary-soft) 0%, var(--primary-light) 100%); }
.card-green  .card-top::before { background: linear-gradient(135deg, var(--success-soft) 0%, var(--success-light) 100%); }
.card-orange .card-top::before { background: linear-gradient(135deg, var(--accent-soft) 0%, var(--accent-light) 100%); }
.card-purple .card-top::before { background: linear-gradient(135deg, var(--purple-soft) 0%, var(--purple-light) 100%); }
.card-cyan   .card-top::before { background: linear-gradient(135deg, var(--info-soft) 0%, var(--info-light) 100%); }
.card-pink   .card-top::before { background: linear-gradient(135deg, #FBCFE8 0%, #F9A8D4 100%); }

.card-icon {
  position: relative; z-index: 1;
  width: 40px; height: 40px;
  background: var(--surface);
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  box-shadow: var(--shadow-sm);
}
.card-top .badge {
  position: relative; z-index: 1;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(4px);
}

.card-body {
  padding: 18px 20px 16px;
  flex: 1;
  display: flex; flex-direction: column;
}
.card-code {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-weight: 500;
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
  line-height: 1.3;
  margin: 0 0 8px;
}
.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0 0 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-foot {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  margin-top: auto;
}
.card-date {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}
.enroll-btn {
  font-weight: 600;
}
.enroll-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}

/* Pagination */
.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: 16px;
  padding: 16px 0 0;
}
.pg-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.pg-btn:hover:not(:disabled) {
  background: var(--surface-raised);
  border-color: var(--border-strong);
}
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.pg-meta {
  display: flex; align-items: baseline; gap: 4px;
  font-size: 13px;
  font-family: var(--font-mono);
  padding: 0 8px;
}
.pg-current {
  color: var(--primary);
  font-weight: 700;
  font-size: 15px;
}
.pg-sep { color: var(--text-tertiary); }
.pg-total { color: var(--text-secondary); }

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
