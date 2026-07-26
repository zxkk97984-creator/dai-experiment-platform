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
      <header class="page-head">
        <div>
          <h1 class="page-title">{{ assignment?.title || '作业' }} - 题目管理</h1>
          <p class="page-sub">添加与编辑判题题目，配置测试用例</p>
        </div>
        <button class="btn-primary" @click="showForm = !showForm">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          {{ showForm ? '取消' : '添加题目' }}
        </button>
      </header>

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
            <textarea v-model="form.public_cases" rows="4" class="code-editor" placeholder='[{"args": [1, 2], "expected": 3}]'></textarea>
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

      <div v-if="loading" class="card" style="padding:48px;text-align:center">
        <div class="skeleton" style="height:22px;width:200px;margin:0 auto 12px"></div>
        <div class="skeleton" style="height:14px;width:300px;margin:0 auto"></div>
      </div>

      <div v-else-if="questions.length === 0" class="empty-state">
        <p>🧩 暂无题目，点击「添加题目」创建第一道题目</p>
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
   Question Edit — Code Studio
   page-head + create form + question cards
   ═══════════════════════════════════════════════════════════════════════ */
.question-editor { display: flex; flex-direction: column; gap: 24px; }

/* ── Page head ─────────────────────────────────────────────────────── */
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

/* ── Code editor (keep dark surface) ── */
.code-editor {
  width: 100%;
  background: #0F172A;
  color: #E2E8F0;
  border: 1px solid #1E293B;
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
  border-color: var(--primary);
  box-shadow: var(--shadow-glow-primary);
}

/* ── Number inputs ── */
input[type="number"] {
  -moz-appearance: textfield;
}
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* ── Submit button ── */
.btn-submit {
  margin-top: var(--space-2);
  padding: 9px 24px;
  font-size: var(--text-sm);
}

/* ── Question list cards ── */
.question-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}
.question-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}
.question-meta {
  margin-top: 2px;
}
</style>
