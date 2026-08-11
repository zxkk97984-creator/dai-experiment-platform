<script setup>
import { onMounted, ref } from 'vue'
import { coursesAPI } from '../../api/courses.js'
import { usersAPI } from '../../api/users.js'
import { useAppStore } from '../../stores/app.js'

const props = defineProps({ courseId: { type: [Number, String], required: true } })
const emit = defineEmits(['changed'])
const app = useAppStore()
const students = ref([])
const candidates = ref([])
const query = ref('')
const loading = ref(false)

async function load() {
  if (typeof coursesAPI.listStudents !== 'function') return
  loading.value = true
  try {
    const res = await coursesAPI.listStudents(props.courseId, { page_size: 100 })
    students.value = res.data.items || []
  } finally { loading.value = false }
}

async function search() {
  if (typeof usersAPI.listStudents !== 'function') return
  const res = await usersAPI.listStudents({ q: query.value || undefined, page_size: 20 })
  const enrolled = new Set(students.value.map((item) => item.id))
  candidates.value = (res.data.items || []).filter((item) => !enrolled.has(item.id))
}

async function add(student) {
  await coursesAPI.addStudent(props.courseId, student.id)
  app.showToast('学生已加入课程', 'success')
  await load(); await search(); emit('changed')
}

async function remove(student) {
  await coursesAPI.removeStudent(props.courseId, student.id)
  app.showToast('学生已移出课程', 'success')
  await load(); emit('changed')
}

const originLabel = (origin) => ({ class: '班级同步', manual: '手工加入', self: '自主选课' })[origin] || origin
onMounted(load)
</script>

<template>
  <section class="roster-panel">
    <div class="roster-head"><div><strong>课程学生名单</strong><p>班级成员自动同步，也可手工添加例外学生。</p></div><span>{{ students.length }} 人</span></div>
    <div class="roster-search"><input v-model="query" placeholder="按姓名、学号或账号搜索" @keyup.enter="search" /><button type="button" class="button button-secondary" @click="search">搜索学生</button></div>
    <div v-if="candidates.length" class="candidate-list">
      <button v-for="student in candidates" :key="student.id" type="button" @click="add(student)">
        <span>{{ student.real_name }}</span><small>{{ student.student_no || student.username }}</small><b>加入</b>
      </button>
    </div>
    <div v-if="loading" class="roster-empty">正在加载名单…</div>
    <div v-else-if="!students.length" class="roster-empty">尚无学生，绑定教学班或手工添加学生。</div>
    <table v-else><thead><tr><th>姓名</th><th>学号</th><th>所属班级</th><th>来源</th><th></th></tr></thead><tbody>
      <tr v-for="student in students" :key="student.id"><td>{{ student.real_name }}</td><td>{{ student.student_no || student.username }}</td><td>{{ student.teaching_classes?.map((item) => item.name).join('、') || '—' }}</td><td>{{ originLabel(student.enrollment_origin) }}</td><td><button type="button" class="remove" @click="remove(student)">移出</button></td></tr>
    </tbody></table>
  </section>
</template>

<style scoped>
.roster-panel{display:grid;gap:12px;padding-top:18px;border-top:1px solid var(--border)}.roster-head,.roster-search{display:flex;align-items:center;justify-content:space-between;gap:12px}.roster-head p{margin:4px 0 0;color:var(--text-secondary);font-size:12px}.roster-head>span{padding:4px 10px;border-radius:999px;background:var(--primary-light);color:var(--primary);font-size:12px}.roster-search input{flex:1}.candidate-list{display:grid;gap:6px;padding:8px;border-radius:8px;background:#f8fafc}.candidate-list button{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;padding:8px;border:0;background:transparent;text-align:left}.candidate-list small{color:var(--text-secondary)}.candidate-list b{color:var(--primary)}table{width:100%;font-size:12px}th,td{padding:8px;border-bottom:1px solid var(--border);text-align:left}.remove{border:0;background:transparent;color:var(--danger)}.roster-empty{padding:16px;border-radius:8px;background:#f8fafc;color:var(--text-secondary);text-align:center}
</style>
