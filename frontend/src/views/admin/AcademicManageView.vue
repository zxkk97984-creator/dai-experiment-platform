<script setup>
import { computed, onMounted, ref } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import TeacherPagination from '../../components/teacher/TeacherPagination.vue'
import { academicsAPI } from '../../api/academics.js'
import { usersAPI } from '../../api/users.js'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()
const terms = ref([])
const classes = ref([])
const selectedClassId = ref(null)
const classStudents = ref([])
const termPage = ref(1)
const classPage = ref(1)
const rosterPage = ref(1)
const termTotal = ref(0)
const classTotal = ref(0)
const rosterTotal = ref(0)
const candidates = ref([])
const studentQuery = ref('')
const termForm = ref({ code: '', name: '', start_date: '', end_date: '', status: 'planned' })
const classForm = ref({ academic_term_id: null, code: '', name: '' })
const selectedClass = computed(() => classes.value.find((item) => item.id === Number(selectedClassId.value)))
const termName = (id) => terms.value.find((item) => item.id === Number(id))?.name || '—'
const pageSize = 20
const termPageCount = computed(() => Math.max(1, Math.ceil(termTotal.value / pageSize)))
const classPageCount = computed(() => Math.max(1, Math.ceil(classTotal.value / pageSize)))
const rosterPageCount = computed(() => Math.max(1, Math.ceil(rosterTotal.value / pageSize)))

async function loadTerms() {
  const res = await academicsAPI.listTerms({ page: termPage.value, page_size: pageSize })
  terms.value = res.data.items || []
  termTotal.value = Number(res.data.total ?? terms.value.length)
}
async function loadClasses() {
  const res = await academicsAPI.listClasses({ page: classPage.value, page_size: pageSize })
  classes.value = res.data.items || []
  classTotal.value = Number(res.data.total ?? classes.value.length)
}
async function load() {
  await Promise.all([loadTerms(), loadClasses()])
  if (selectedClassId.value) await loadRoster()
}
async function changeTermPage(nextPage) {
  termPage.value = nextPage
  await loadTerms()
}
async function changeClassPage(nextPage) {
  classPage.value = nextPage
  await loadClasses()
}
async function createTerm() {
  try { await academicsAPI.createTerm(termForm.value); termForm.value = { code: '', name: '', start_date: '', end_date: '', status: 'planned' }; await load(); app.showToast('学期已创建', 'success') }
  catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}
async function closeTerm(term) { await academicsAPI.closeTerm(term.id); await load() }
async function createClass() {
  try { await academicsAPI.createClass(classForm.value); classForm.value = { academic_term_id: null, code: '', name: '' }; await load(); app.showToast('教学班已创建', 'success') }
  catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
}
async function archiveClass(item) { await academicsAPI.archiveClass(item.id); await load() }
async function selectClass(item) { selectedClassId.value = item.id; rosterPage.value = 1; candidates.value = []; await loadRoster() }
async function loadRoster() {
  const res = await academicsAPI.listClassStudents(selectedClassId.value, { page: rosterPage.value, page_size: pageSize })
  classStudents.value = res.data.items || []
  rosterTotal.value = Number(res.data.total ?? classStudents.value.length)
}
async function changeRosterPage(nextPage) {
  rosterPage.value = nextPage
  await loadRoster()
}
async function searchStudents() {
  const res = await usersAPI.listStudents({ q: studentQuery.value || undefined, page_size: 30 })
  const existing = new Set(classStudents.value.map((item) => item.id))
  candidates.value = (res.data.items || []).filter((item) => !existing.has(item.id))
}
async function addStudent(student) { await academicsAPI.addClassStudents(selectedClassId.value, [student.id]); await load(); await searchStudents() }
async function removeStudent(student) { await academicsAPI.removeClassStudent(selectedClassId.value, student.id); await load() }
onMounted(load)
</script>

<template>
  <AppLayout><main class="academic-page">
    <header><div><p>ACADEMIC OPERATIONS</p><h1>教务管理</h1><span>维护学期、教学班和学生名单，课程人数会自动同步。</span></div><AppIcon name="course" :size="32" /></header>
    <section class="grid">
      <article class="panel"><h2>学期</h2><form class="form-grid" @submit.prevent="createTerm"><input v-model="termForm.code" required placeholder="编码，如 2026-FALL"/><input v-model="termForm.name" required placeholder="名称，如 2026 秋季学期"/><input v-model="termForm.start_date" required type="date"/><input v-model="termForm.end_date" required type="date"/><select v-model="termForm.status"><option value="planned">计划中</option><option value="active">进行中</option></select><button class="btn-primary">创建学期</button></form>
        <div class="rows"><div v-for="term in terms" :key="term.id"><span><strong>{{ term.name }}</strong><small>{{ term.code }} · {{ term.start_date }} — {{ term.end_date }}</small></span><em :class="term.status">{{ term.status }}</em><button v-if="term.status !== 'closed'" @click="closeTerm(term)">关闭</button></div></div>
        <TeacherPagination v-if="termTotal > 0" :current-page="termPage" :page-count="termPageCount" :total="termTotal" :page-size="pageSize" aria-label="学期列表分页" @change="changeTermPage" />
      </article>
      <article class="panel"><h2>教学班</h2><form class="form-grid" @submit.prevent="createClass"><select v-model="classForm.academic_term_id" required><option :value="null">选择学期</option><option v-for="term in terms.filter(t => t.status !== 'closed')" :key="term.id" :value="term.id">{{ term.name }}</option></select><input v-model="classForm.code" required placeholder="班级编码"/><input v-model="classForm.name" required placeholder="班级名称"/><button class="btn-primary">创建教学班</button></form>
        <div class="rows"><div v-for="item in classes" :key="item.id" :class="{ selected: item.id === selectedClassId }" @click="selectClass(item)"><span><strong>{{ item.name }}</strong><small>{{ termName(item.academic_term_id) }} · {{ item.student_count }} 人</small></span><em :class="item.status">{{ item.status }}</em><button v-if="item.status !== 'archived'" @click.stop="archiveClass(item)">归档</button></div></div>
        <TeacherPagination v-if="classTotal > 0" :current-page="classPage" :page-count="classPageCount" :total="classTotal" :page-size="pageSize" aria-label="教学班列表分页" @change="changeClassPage" />
      </article>
    </section>
    <section v-if="selectedClass" class="panel roster"><div class="roster-title"><div><h2>{{ selectedClass.name }} · 班级名单</h2><p>{{ termName(selectedClass.academic_term_id) }}</p></div><span>{{ rosterTotal }} 人</span></div>
      <div class="search"><input v-model="studentQuery" placeholder="按姓名、学号或账号搜索学生" @keyup.enter="searchStudents"/><button class="btn-primary" @click="searchStudents">搜索并添加</button></div>
      <div v-if="candidates.length" class="candidates"><button v-for="student in candidates" :key="student.id" @click="addStudent(student)">{{ student.real_name }} · {{ student.student_no || student.username }} <b>加入</b></button></div>
      <table class="ds-table"><thead><tr><th>姓名</th><th>学号</th><th>账号</th><th></th></tr></thead><tbody><tr v-for="student in classStudents" :key="student.id"><td>{{ student.real_name }}</td><td>{{ student.student_no }}</td><td>{{ student.username }}</td><td><button @click="removeStudent(student)">移出</button></td></tr></tbody></table>
      <TeacherPagination v-if="rosterTotal > 0" :current-page="rosterPage" :page-count="rosterPageCount" :total="rosterTotal" :page-size="pageSize" aria-label="班级名单分页" @change="changeRosterPage" />
    </section>
  </main></AppLayout>
</template>

<style scoped>
.academic-page{display:grid;gap:20px}header,.panel{border:1px solid var(--border);border-radius: var(--radius-lg);background:var(--surface);box-shadow:none}header{display:flex;justify-content:space-between;align-items:center;padding:24px 28px;background:linear-gradient(135deg,var(--accent-soft),var(--surface))}header p{margin:0;color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.12em}header h1{margin:4px 0;font-size:30px}header span,small{color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{padding:20px}.panel h2{margin:0 0 14px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.form-grid button{min-height:42px}.rows{display:grid;gap:8px;margin-top:16px}.rows>div{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:10px;padding:12px;border:1px solid var(--border);border-radius: var(--radius-md);cursor:pointer}.rows>div.selected{border-color:var(--accent);background:var(--accent-soft)}.rows span{display:grid;gap:3px}.rows em{padding:3px 8px;border-radius: var(--radius-full);background:var(--surface-subtle);font-size:11px;font-style:normal}.rows em.active{color:var(--success);background:var(--success-bg)}.rows button,table button{border:0;background:transparent;color:var(--danger)}.roster-title,.search{display:flex;align-items:center;justify-content:space-between;gap:12px}.roster-title h2,.roster-title p{margin:0}.roster-title>span{padding:5px 12px;border-radius: var(--radius-full);background:var(--accent-soft);color:var(--accent)}.search{margin:18px 0}.search input{flex:1}.candidates{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}.candidates button{padding:8px 10px;border:1px solid var(--border);border-radius: var(--radius-md);background:var(--surface-subtle)}.candidates b{margin-left:8px;color:var(--accent)}table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid var(--border);text-align:left}@media(max-width:900px){.grid{grid-template-columns:1fr}.form-grid{grid-template-columns:1fr}}
</style>
