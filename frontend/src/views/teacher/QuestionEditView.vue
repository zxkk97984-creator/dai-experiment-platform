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
    <div class="question-editor">
      <div class="flex-between mb-4">
        <h1 class="page-title" style="margin-bottom:0">{{ assignment?.title || '作业' }} - 题目管理</h1>
        <button class="btn-primary" @click="showForm = !showForm">
          {{ showForm ? '取消' : '添加题目' }}
        </button>
      </div>

      <div v-if="showForm" class="card mb-4">
        <div class="grid-2">
          <div class="form-group">
            <label>题目标题</label>
            <input v-model="form.title" placeholder="如: 两数之和" />
          </div>
          <div class="form-group">
            <label>函数名</label>
            <input v-model="form.function_name" placeholder="如: add" />
          </div>
        </div>

        <div class="form-group">
          <label>题目描述 (Markdown)</label>
          <textarea v-model="form.description" rows="4" placeholder="支持 Markdown 格式编写题目描述"></textarea>
        </div>

        <div class="form-group">
          <label>函数签名</label>
          <input v-model="form.signature" placeholder="def add(a: int, b: int) -> int" />
        </div>

        <div class="form-group">
          <label>初始代码</label>
          <textarea v-model="form.starter_code" rows="5" class="code-editor" placeholder="def add(a, b):&#10;    # TODO&#10;    pass"></textarea>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label>公开样例 (JSON)</label>
            <textarea v-model="form.public_cases" rows="4" class="code-editor" placeholder='[{"input": [1, 2], "expected": 3}]'></textarea>
          </div>
          <div class="form-group">
            <label>隐藏测试 (pytest 代码)</label>
            <textarea v-model="form.hidden_tests" rows="4" class="code-editor" placeholder="def test_add(): assert add(1,2)==3"></textarea>
          </div>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label>超时 (ms)</label>
            <input v-model.number="form.time_limit_ms" type="number" />
          </div>
          <div class="form-group">
            <label>内存限制 (MB)</label>
            <input v-model.number="form.memory_limit_mb" type="number" />
          </div>
        </div>

        <button class="btn-primary btn-submit" :disabled="saving" @click="createQuestion">
          {{ saving ? '创建中...' : '确认创建' }}
        </button>
      </div>

      <div v-if="loading" class="text-secondary">加载中...</div>

      <div v-else-if="questions.length === 0" class="card empty-card">
        <p class="empty-text">暂无题目</p>
        <p class="text-secondary" style="font-size: var(--text-sm); margin-top: var(--space-2)">
          点击上方「添加题目」按钮创建第一道题目
        </p>
      </div>

      <div v-else v-for="(q, i) in questions" :key="q.id" class="card question-card mb-3">
        <div class="flex-between">
          <div>
            <h3 class="question-title">题目 {{ i + 1 }}: {{ q.title }}</h3>
            <p class="text-sm text-secondary question-meta">
              函数: {{ q.function_name }} | 超时: {{ q.time_limit_ms }}ms | 内存: {{ q.memory_limit_mb }}MB
            </p>
          </div>
          <span class="badge badge-neutral">#{{ i + 1 }}</span>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Question Editor — Pythonista Dark Admin
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Scope container ────────────────────────────────────────────────── */
.question-editor {
  color: #D6DEEB;
}

/* ── Page title ─────────────────────────────────────────────────────── */
.question-editor .page-title {
  color: #D6DEEB;
}

/* ── Cards ──────────────────────────────────────────────────────────── */
.card {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  color: #D6DEEB;
  transition: box-shadow var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}
.card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  border-color: #3A4050;
}

/* ── Empty state ────────────────────────────────────────────────────── */
.empty-card {
  text-align: center;
  padding: var(--space-12) !important;
}
.empty-text {
  color: #6A7086;
  font-size: var(--text-base);
  margin-bottom: 0;
}

/* ── Form labels ────────────────────────────────────────────────────── */
.form-group label {
  display: block;
  font-size: var(--text-xs);
  font-weight: 600;
  color: #6A7086;
  margin-bottom: 5px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Inputs / Textareas ─────────────────────────────────────────────── */
input,
textarea,
select {
  font-family: var(--font-body);
  font-size: var(--text-sm);
  border: 1px solid #2A3040;
  border-radius: var(--radius-md);
  padding: 8px 12px;
  color: #D6DEEB;
  background: #151821;
  width: 100%;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
  line-height: 1.5;
}
input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.18);
}
input::placeholder,
textarea::placeholder {
  color: #5A6070;
}

/* Number inputs — prevent browser spinners from clashing */
input[type="number"] {
  -moz-appearance: textfield;
}
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* ── Code editor ────────────────────────────────────────────────────── */
.code-editor {
  width: 100%;
  background: #11141D;
  color: #D6DEEB;
  border: 1px solid #2A3040;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.65;
  tab-size: 4;
  resize: vertical;
}
.code-editor:focus {
  outline: none;
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.18);
}

/* ── Buttons (dark surface overrides) ───────────────────────────────── */
button {
  background: #1A1E2B;
  border: 1px solid #2A3040;
  color: #D6DEEB;
}
button:hover {
  background: #252A38;
  border-color: #3A4050;
}

button.btn-primary {
  background: #E0553D;
  color: #fff;
  border-color: #E0553D;
  font-weight: 500;
}
button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}
button.btn-primary:focus-visible {
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.25);
}
button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.btn-submit {
  margin-top: var(--space-2);
  padding: 9px 24px;
  font-size: var(--text-sm);
}

/* ── Text utilities ─────────────────────────────────────────────────── */
.text-secondary {
  color: #6A7086;
}

/* ── Question list cards ────────────────────────────────────────────── */
.question-card:hover {
  border-color: #3A4050;
}
.question-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: #D6DEEB;
  margin-bottom: 4px;
}
.question-meta {
  margin-top: 2px;
}

/* ── Badge override ─────────────────────────────────────────────────── */
.badge-neutral {
  background: #252A38;
  color: #6A7086;
}
</style>
