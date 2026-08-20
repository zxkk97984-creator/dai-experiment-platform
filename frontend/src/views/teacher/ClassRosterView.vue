<script setup>
import { computed, onMounted, ref } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { academicsAPI } from '../../api/academics.js'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()
const classes = ref([])
const selectedClassId = ref(null)
const selectedClass = ref(null)
const students = ref([])
const loading = ref(true)
const query = ref('')

const filteredStudents = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return students.value
  return students.value.filter((student) => `${student.real_name || ''} ${student.student_no || ''} ${student.username || ''}`.toLowerCase().includes(q))
})

function classTitle(item) {
  const name = item.name || ''
  const code = item.code || ''
  return code && name !== code ? code : name
}

function classSubtitle(item) {
  const name = item.name || ''
  const code = item.code || ''
  const term = code && name.endsWith(code) ? name.slice(0, -code.length).trim() : name
  const parts = []
  if (term && term !== code) parts.push(term)
  parts.push(`${item.student_count} 人`)
  return parts.join(' · ')
}

async function load() {
  loading.value = true
  try {
    const res = await academicsAPI.listClasses({ page_size: 100, scope: 'linked' })
    classes.value = res.data.items || []
    if (classes.value.length && !selectedClassId.value) {
      selectedClassId.value = String(classes.value[0].id)
    }
    if (selectedClassId.value) await loadRoster(selectedClassId.value)
  } catch {
    app.showToast('加载教学班失败', 'error')
  } finally {
    loading.value = false
  }
}

async function selectClass(item) {
  selectedClassId.value = String(item.id)
  selectedClass.value = item
  await loadRoster(item.id)
}

async function loadRoster(classId) {
  try {
    const res = await academicsAPI.listClassStudents(classId, { page_size: 100 })
    students.value = res.data.items || []
  } catch {
    students.value = []
    app.showToast('加载学员名单失败', 'error')
  }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <main class="roster-page">
      <section class="page-head">
        <div class="ph-title">
          <p class="eyebrow">教学 / 班级</p>
          <h1>班级与学员</h1>
          <p class="lead">查看自己课程关联的教学班与在册学员名单。</p>
        </div>
      </section>

      <section class="metric-strip">
        <div class="metric"><span class="m-value">{{ classes.length }}</span><span class="m-label">关联教学班</span></div>
        <div class="metric"><span class="m-value">{{ selectedClass?.student_count ?? students.length }}</span><span class="m-label">当前班级人数</span></div>
        <div class="metric"><span class="m-value">{{ filteredStudents.length }}</span><span class="m-label">筛选结果</span></div>
      </section>

      <div class="grid-2-1 roster-grid">
        <section class="panel">
          <div class="panel-head"><div class="ph-label"><p class="eyebrow">Classes</p><h3>教学班</h3></div></div>
          <div class="panel-body">
            <div v-if="loading" class="loading-text">加载中…</div>
            <div v-else-if="classes.length === 0" class="empty">
              <div class="empty-mark"><AppIcon name="user" :size="20" /></div>
              <h3>暂无关联教学班</h3>
              <p>请先在课程设置中绑定教学班。</p>
            </div>
            <div v-else class="class-list">
              <button
                v-for="item in classes"
                :key="item.id"
                type="button"
                class="class-row"
                :class="{ active: selectedClassId === String(item.id) }"
                @click="selectClass(item)"
              >
                <span class="class-title">{{ classTitle(item) }}</span>
                <span class="class-meta">{{ classSubtitle(item) }}</span>
              </button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="ph-label"><p class="eyebrow">Students</p><h3>学员名单</h3></div>
          </div>
          <div class="panel-body">
            <label class="searchbox" style="width: 100%; margin-bottom: 12px;">
              <AppIcon name="search" :size="15" />
              <input v-model="query" type="search" class="input" placeholder="搜索姓名、学号或账号" />
              <button v-if="query" type="button" class="clear" aria-label="清空搜索" @click="query = ''">
                <AppIcon name="close" :size="13" />
              </button>
            </label>
            <div v-if="filteredStudents.length === 0" class="empty">
              <div class="empty-mark"><AppIcon name="user" :size="20" /></div>
              <h3>暂无学员</h3>
              <p>选择左侧教学班查看名单。</p>
            </div>
            <div v-else class="table-scroll">
              <table class="ds-table">
                <thead><tr><th>姓名</th><th>学号</th><th>账号</th></tr></thead>
                <tbody>
                  <tr v-for="student in filteredStudents" :key="student.id">
                    <td><span class="cell-main">{{ student.real_name }}</span></td>
                    <td>{{ student.student_no || '—' }}</td>
                    <td>{{ student.username }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </main>
  </AppLayout>
</template>

<style scoped>
.roster-page { display: flex; flex-direction: column; gap: var(--space-5); }
.roster-grid { align-items: start; }
.loading-text { color: var(--muted); padding: 12px 0; }
.class-list { display: flex; flex-direction: column; }
.class-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 11px 12px;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  text-align: left;
}
.class-row:hover, .class-row.active { background: var(--accent-faint); border-color: var(--accent-soft); }
.class-title { font-weight: 600; color: var(--fg); }
.class-meta { color: var(--muted); font-size: var(--text-sm); }
@media (max-width: 1024px) { .roster-grid { grid-template-columns: 1fr; } }
</style>
