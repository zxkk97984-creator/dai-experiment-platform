<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { experimentsAPI } from '../../api/experiments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()

const modules = ref([])
const records = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const mRes = await experimentsAPI.listModules()
    modules.value = mRes.data.items || mRes.data
  } catch {
    modules.value = []
  }
  try {
    const rRes = await experimentsAPI.listRecords()
    records.value = rRes.data.items || rRes.data
  } catch {
    records.value = []
  }
  loading.value = false
})

function enterExperiment(m) {
  router.push(`/student/experiments/${m.id}`)
}
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">实验模块</h1>
          <p class="page-sub">进入在线实验环境，动手实践编程与数据分析</p>
        </div>
        <div class="page-meta">
          <div class="meta-pill">
            <span class="pill-dot"></span>
            <span>共 {{ modules.length }} 个模块</span>
          </div>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="grid-2">
        <div v-for="i in 4" :key="i" class="skel-card">
          <div class="skel-body">
            <div class="skeleton skel-line w-50"></div>
            <div class="skeleton skel-line w-90"></div>
            <div class="skeleton skel-btn"></div>
          </div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="modules.length === 0" class="empty-state">
        <p>🧪 暂无实验模块，请联系教师配置</p>
      </div>

      <!-- ── Module Grid ────────────────────────────────────────────────── -->
      <div v-else class="grid-2">
        <article
          v-for="m in modules" :key="m.id"
          class="card module-card"
          @click="enterExperiment(m)"
        >
          <div class="card-inner">
            <div class="flex-between mb-3">
              <h3 class="module-title">{{ m.name }}</h3>
              <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, m.status).color">
                {{ statusBadge(PUBLISH_STATUS_MAP, m.status).label }}
              </span>
            </div>
            <p class="module-desc">{{ m.description || '暂无描述' }}</p>
            <div class="module-action">
              <span class="btn-accent btn-enter">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="8" height="8" rx="1.5"/><path d="M5.5 3v8M3 5.5h8"/>
                </svg>
                进入实验
              </span>
            </div>
          </div>
        </article>
      </div>

      <!-- ── Records Section ────────────────────────────────────────────── -->
      <section v-if="!loading" class="records-section">
        <div class="panel-head">
          <h2 class="panel-title">我的实验记录</h2>
          <p class="panel-sub">{{ records.length ? records.length + ' 条记录' : '暂无记录' }}</p>
        </div>

        <div v-if="records.length === 0" class="empty-state" style="padding:32px 24px">
          <p>📊 还没有实验记录，进入模块开始实验吧</p>
        </div>

        <div v-else class="card table-card">
          <table>
            <thead>
              <tr>
                <th>模块 ID</th>
                <th>状态</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in records" :key="r.id">
                <td>
                  <span class="text-mono">{{ r.module_id }}</span>
                </td>
                <td>
                  <span class="badge" :class="r.status === 'started' ? 'badge-info' : r.status === 'submitted' ? 'badge-warning' : 'badge-success'">
                    {{ r.status }}
                  </span>
                </td>
                <td class="text-sm text-secondary">{{ r.created_at }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Experiment View — Code Studio
   page-head + module cards + records table
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
.skel-body { display: flex; flex-direction: column; }
.skel-line { height: 12px; margin-bottom: 8px; border-radius: var(--radius-sm); }
.skel-btn { height: 32px; width: 100px; margin-top: 14px; border-radius: var(--radius-md); }
.w-50 { width: 50%; }
.w-90 { width: 90%; }

/* ── Module Card — 继承 .card ─────────────────────────────────────── */
.module-card {
  padding: 24px;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.module-card:hover { transform: translateY(-2px); }
.card-inner { display: flex; flex-direction: column; }

.module-title {
  margin: 0;
  font-size: 16px; font-weight: 600;
  color: var(--ink);
  line-height: 1.3;
  transition: color var(--duration-fast) var(--ease-out);
}
.module-card:hover .module-title { color: var(--primary); }

.module-desc {
  font-size: var(--text-sm); color: var(--text-secondary);
  line-height: 1.55; margin: 0 0 16px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

.module-action {
  display: flex; padding-top: 12px;
  border-top: 1px solid var(--border);
}
.btn-enter {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: var(--text-sm); font-weight: 500;
}

/* ── Records Section ───────────────────────────────────────────────── */
.records-section { margin-top: 8px; }
.panel-head {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 12px;
}
.panel-title {
  font-size: 17px; font-weight: 600;
  color: var(--ink); letter-spacing: -0.01em; margin: 0;
}
.panel-sub {
  font-size: var(--text-xs); color: var(--text-secondary); margin: 0;
}

/* Table wrapper — 复用 .card 外壳 */
.table-card {
  padding: 0;
  overflow: hidden;
}
.table-card table { margin: 0; }

.text-mono {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--text-secondary);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
}
</style>
