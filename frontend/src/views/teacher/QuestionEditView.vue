<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const assignment = ref(null)
const questions = ref([])
const loading = ref(true)
const showForm = ref(false)
const form = ref({
  title: '', description: '', function_name: '', signature: '',
  starter_code: '', public_cases: '[]', hidden_tests: '',
  time_limit_ms: 10000, memory_limit_mb: 256,
})
const saving = ref(false)

async function fetch() {
  loading.value = true
  try {
    const [aRes, qRes] = await Promise.all([
      assignmentsAPI.get(route.params.id),
      assignmentsAPI.getQuestions(route.params.id),
    ])
    assignment.value = aRes.data
    questions.value = qRes.data.items || qRes.data
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function createQuestion() {
  if (!form.value.title || !form.value.function_name) {
    app.showToast('请填写标题和函数名', 'error'); return
  }
  saving.value = true
  try {
    let publicCases = []
    try { publicCases = JSON.parse(form.value.public_cases) }
    catch { app.showToast('公开样例 JSON 格式错误', 'error'); saving.value = false; return }
    await assignmentsAPI.createQuestion(route.params.id, { ...form.value, public_cases: publicCases })
    app.showToast('题目已创建', 'success')
    showForm.value = false
    form.value = {
      title: '', description: '', function_name: '', signature: '',
      starter_code: '', public_cases: '[]', hidden_tests: '',
      time_limit_ms: 10000, memory_limit_mb: 256,
    }
    fetch()
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') }
  finally { saving.value = false }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">{{ assignment?.title || '作业' }} - 题目管理</h1>
      <button class="btn-primary" @click="showForm = !showForm">{{ showForm ? '取消' : '添加题目' }}</button>
    </div>

    <div v-if="showForm" class="card mb-4">
      <div class="grid-2">
        <div class="form-group"><label>题目标题</label><input v-model="form.title" placeholder="如: 两数之和" /></div>
        <div class="form-group"><label>函数名</label><input v-model="form.function_name" placeholder="如: add" /></div>
      </div>
      <div class="form-group"><label>题目描述 (Markdown)</label><textarea v-model="form.description" rows="4"></textarea></div>
      <div class="form-group"><label>函数签名</label><input v-model="form.signature" placeholder="def add(a: int, b: int) -> int" /></div>
      <div class="form-group"><label>初始代码</label><textarea v-model="form.starter_code" rows="4" class="code-editor" placeholder="def add(a, b):&#10;    # TODO&#10;    pass"></textarea></div>
      <div class="grid-2">
        <div class="form-group"><label>公开样例 (JSON)</label><textarea v-model="form.public_cases" rows="3" placeholder='[{"input": [1, 2], "expected": 3}]'></textarea></div>
        <div class="form-group"><label>隐藏测试 (pytest 代码)</label><textarea v-model="form.hidden_tests" rows="3" placeholder="def test_add(): assert add(1,2)==3" class="code-editor"></textarea></div>
      </div>
      <div class="grid-2">
        <div class="form-group"><label>超时 (ms)</label><input v-model.number="form.time_limit_ms" type="number" /></div>
        <div class="form-group"><label>内存限制 (MB)</label><input v-model.number="form.memory_limit_mb" type="number" /></div>
      </div>
      <button class="btn-primary" :disabled="saving" @click="createQuestion">{{ saving ? '创建中...' : '确认创建' }}</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <div v-else-if="questions.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无题目</p>
    </div>
    <div v-else v-for="(q, i) in questions" :key="q.id" class="card mb-3">
      <h3 style="font-size:14px">题目 {{ i + 1 }}: {{ q.title }}</h3>
      <p class="text-sm text-secondary">函数: {{ q.function_name }} | 超时: {{ q.time_limit_ms }}ms | 内存: {{ q.memory_limit_mb }}MB</p>
    </div>
  </AppLayout>
</template>

<style scoped>
.code-editor { width:100%; background:#1e2532; color:#e5e7eb; border:none; border-radius:4px; padding:10px; font-family:var(--font-mono); font-size:13px; }
.code-editor:focus { outline:2px solid var(--accent); }
</style>
