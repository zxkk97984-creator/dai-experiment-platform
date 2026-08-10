<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import AIQuestionConfig from '../../components/ai/AIQuestionConfig.vue'
import ChoiceOptionsEditor from '../../components/teacher/exam/ChoiceOptionsEditor.vue'
import QeTestCases from '../../components/teacher/question-editor/QeTestCases.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const route = useRoute(); const router = useRouter(); const app = useAppStore()
const examId = route.params.id; const exam = ref(null); const questions = ref([])
const loading = ref(true); const showForm = ref(false); const editingQ = ref(null)
const aiConfigQid = ref(null)  // 当前展开 AI 配置的题目 ID
const choiceEditor = ref(null)
const testCasesKey = ref(0)
const modalAiExpanded = ref(true)

function blankChoice() {
  return { options: [{ key: 'A', text: '', correct: false }, { key: 'B', text: '', correct: false }], scoring_mode: 'all_or_nothing' }
}
function blankForm(type = 'single_choice') {
  return {
    question_type: type, prompt: '', points: 1, choice: blankChoice(),
    starter_code: '', public_cases: [], hidden_tests: '', time_limit_ms: 10000,
    memory_limit_mb: 256, grading_mode: type === 'code' ? 'active' : 'legacy',
  }
}
const form = ref(blankForm())

async function load() { loading.value = true; try { const [eR,qR] = await Promise.all([examsAPI.get(examId), examsAPI.getQuestions(examId)]); exam.value = eR.data; questions.value = qR.data.items || [] } catch { app.showToast('加载失败', 'error') } finally { loading.value = false } }
function openAdd() {
  editingQ.value = null
  form.value = blankForm()
  modalAiExpanded.value = true
  testCasesKey.value++
  showForm.value = true
}
function openEdit(q) {
  editingQ.value = q.id
  const correct = new Set(q.correct_answer?.correct || [])
  form.value = {
    ...blankForm(q.question_type), question_type: q.question_type, prompt: q.prompt || '', points: q.points || 1,
    choice: {
      options: Object.entries(q.options || {}).map(([key, text]) => ({ key, text, correct: correct.has(key) })),
      scoring_mode: q.correct_answer?.scoring_mode || 'all_or_nothing',
    },
    starter_code: q.starter_code || '', public_cases: q.public_cases || [], hidden_tests: q.hidden_tests || '',
    time_limit_ms: q.time_limit_ms || 10000, memory_limit_mb: q.memory_limit_mb || 256,
    grading_mode: q.grading_mode || (q.question_type === 'code' ? 'active' : 'legacy'),
  }
  if (q.question_type !== 'code' && form.value.choice.options.length < 2) form.value.choice = blankChoice()
  modalAiExpanded.value = true
  testCasesKey.value++
  showForm.value = true
}

const functionName = computed(() => {
  const match = /^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/m.exec(form.value.starter_code || '')
  return match?.[1] || 'solution'
})

function configStatus(q) {
  if (q.question_type !== 'code') return { ok: true, text: '' }
  if (q.grading_mode === 'legacy') return { ok: Boolean(q.hidden_tests?.trim()), text: '传统判题' }
  const testsOk = Array.isArray(q.test_groups) && q.test_groups.length > 0
  const hiddenOk = q.grading_mode !== 'shadow' || Boolean(q.hidden_tests?.trim())
  const ok = testsOk && hiddenOk && q.has_locked_rubric
  return { ok, text: q.grading_mode === 'active' ? 'AI 正式评分' : 'AI 影子评分' }
}

async function save() {
  try {
    if (!form.value.prompt.trim()) throw new Error('请输入题目内容')
    if (!(Number(form.value.points) > 0)) throw new Error('分值必须大于 0')
    const p = { question_type: form.value.question_type, prompt: form.value.prompt.trim(), points: form.value.points, order_index: editingQ.value ? undefined : questions.value.length }
    if (form.value.question_type !== 'code') {
      const validationError = choiceEditor.value?.validate()
      if (validationError) throw new Error(validationError)
      p.options = Object.fromEntries(form.value.choice.options.map((row) => [row.key.trim(), row.text.trim()]))
      p.correct_answer = {
        correct: form.value.choice.options.filter((row) => row.correct).map((row) => row.key.trim()),
        scoring_mode: form.value.question_type === 'multi_choice' ? form.value.choice.scoring_mode : 'all_or_nothing',
      }
      p.grading_mode = 'legacy'
    } else {
      Object.assign(p, {
        starter_code: form.value.starter_code || '', public_cases: form.value.public_cases,
        hidden_tests: form.value.hidden_tests || '', time_limit_ms: form.value.time_limit_ms,
        memory_limit_mb: form.value.memory_limit_mb, correct_answer: {}, grading_mode: form.value.grading_mode || 'active',
      })
    }
    if (editingQ.value) {
      await examsAPI.updateQuestion(examId, editingQ.value, p)
    } else {
      const response = await examsAPI.createQuestion(examId, p)
      editingQ.value = response.data.id
    }
    await load()
    app.showToast(form.value.question_type === 'code' ? '基础信息已保存，可继续配置测试与 AI 评分' : '保存成功', 'success')
    if (form.value.question_type !== 'code') showForm.value = false
  } catch(e) { app.showToast(e.response?.data?.detail?.message || e.message || '保存失败', 'error') }
}
function finishEditing() { showForm.value = false; load() }
async function remove(qId) { if(confirm('确认删除此题？')) { try { await examsAPI.deleteQuestion(examId, qId); load() } catch { app.showToast('删除失败', 'error') } } }
onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <button class="btn-ghost btn-sm back-btn" @click="router.push('/teacher/exams')">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            返回考试列表
          </button>
          <h1 class="page-title">{{ exam?.title || '考试题目管理' }}</h1>
          <p class="page-sub">编辑考试题目，支持单选题、多选题和编程题</p>
        </div>
        <div class="page-meta">
          <button class="btn-accent" @click="openAdd" :disabled="exam?.status !== 'draft'" :title="exam?.status !== 'draft' ? '已发布考试不可修改题目' : ''">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            添加题目
          </button>
        </div>
      </header>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card" style="padding:48px;text-align:center">
        <div class="skeleton" style="height:18px;width:240px;margin:0 auto 12px"></div>
        <div class="skeleton" style="height:14px;width:360px;margin:0 auto"></div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="questions.length === 0" class="empty-state">
        <p>📝 暂无题目，点击「添加题目」创建</p>
      </div>

      <!-- ── Question List ──────────────────────────────────────────────── -->
      <div v-for="(q,i) in questions" :key="q.id" class="card question-card">
        <div class="qh">
          <strong>#{{ i + 1 }}</strong>
          <span class="badge" :class="q.question_type === 'single_choice' ? 'badge-primary' : q.question_type === 'multi_choice' ? 'badge-info' : 'badge-neutral'">
            {{ { single_choice:'单选题', multi_choice:'多选题', code:'编程题' }[q.question_type] }}
          </span>
          <span class="qp">{{ q.points }} 分</span>
          <span v-if="q.question_type === 'code'" class="badge-mode" :class="{ incomplete: !configStatus(q).ok }">
            {{ configStatus(q).text }}{{ configStatus(q).ok ? '' : ' · 配置未完成' }}
          </span>
          <span class="qa">
            <button v-if="q.question_type === 'code'" class="btn-ghost btn-sm btn-ai" @click="aiConfigQid = aiConfigQid === q.id ? null : q.id">
              {{ aiConfigQid === q.id ? '收起 AI 配置' : '🤖 AI 配置' }}
            </button>
            <button class="btn-ghost btn-sm" @click="openEdit(q)">编辑</button>
            <button class="btn-ghost btn-sm btn-del" @click="remove(q.id)">删除</button>
          </span>
        </div>
        <p class="qd">{{ q.prompt }}</p>
        <AIQuestionConfig v-if="aiConfigQid === q.id && q.question_type === 'code'" :kind="'exam'" :question-id="q.id" :expanded="true" @close="aiConfigQid = null" />
      </div>

      <!-- ── Modal Form ─────────────────────────────────────────────────── -->
      <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="exam-question-title">
          <div class="modal-header">
            <div>
              <h3 id="exam-question-title" class="modal-title">{{ editingQ ? '编辑题目' : '新建题目' }}</h3>
              <p>按题型填写内容，所有高级配置都可在保存前检查。</p>
            </div>
            <button class="modal-close" aria-label="关闭" @click="showForm = false">×</button>
          </div>

          <div class="modal-body">
          <section class="editor-section">
            <div class="section-heading"><span>1</span><div><h4>基础信息</h4><p>设置题型、题目内容和本题分值</p></div></div>

          <div class="form-group">
            <label>题目类型</label>
            <select v-model="form.question_type" @change="form.grading_mode = form.question_type === 'code' ? 'active' : 'legacy'">
              <option value="single_choice">单选题</option>
              <option value="multi_choice">多选题</option>
              <option value="code">编程题</option>
            </select>
          </div>
          <div class="form-group">
            <label>题目内容</label>
            <textarea v-model="form.prompt" rows="3" placeholder="输入题目内容"></textarea>
          </div>
          <div class="form-group">
            <label>分值</label>
            <input v-model.number="form.points" type="number" min="0.1" step="0.1" />
          </div>
          </section>

          <!-- 选择题字段 -->
          <template v-if="form.question_type !== 'code'">
            <ChoiceOptionsEditor ref="choiceEditor" v-model="form.choice" :question-type="form.question_type" />
          </template>

          <!-- 编程题字段 -->
          <template v-else>
            <section class="editor-section">
              <div class="section-heading"><span>2</span><div><h4>代码模板</h4><p>为学生提供起始代码并设置运行限制</p></div></div>
            <div class="form-group">
              <label>初始代码</label>
              <textarea v-model="form.starter_code" rows="7" class="code-input" placeholder="def solution():&#10;    pass"></textarea>
            </div>
            <div class="limit-grid">
              <div class="form-group"><label>时间限制（毫秒）</label><input v-model.number="form.time_limit_ms" type="number" min="1" /></div>
              <div class="form-group"><label>内存限制（MB）</label><input v-model.number="form.memory_limit_mb" type="number" min="1" /></div>
            </div>
            </section>

            <section class="editor-section">
              <div class="section-heading"><span>3</span><div><h4>样例与测试</h4><p>公开样例展示给学生，私有测试用于传统或影子判题</p></div></div>
              <QeTestCases
                :key="testCasesKey"
                :public-cases="form.public_cases"
                :hidden-tests="form.hidden_tests"
                :function-name="functionName"
                :question-id="editingQ"
                :show-run="false"
                @update:public-cases="form.public_cases = $event"
                @update:hidden-tests="form.hidden_tests = $event"
                @parse-failed="app.showToast('复杂 pytest 无法转为可视化用例，已保留高级模式内容', 'error')"
              />
            </section>

            <section class="editor-section ai-section">
              <div class="section-heading"><span>4</span><div><h4>AI 评分</h4><p>默认按百分制 AI 得分折算到本题分值，例如 10 分题获得 80 分即计 8.0 分</p></div></div>
              <div v-if="!editingQ" class="save-first-note">先保存基础信息，即可生成测试组、配置评分规则并锁定 Rubric。</div>
              <template v-else>
                <button v-if="!modalAiExpanded" class="btn-ghost" @click="modalAiExpanded = true">展开 AI 配置</button>
                <AIQuestionConfig v-if="modalAiExpanded" kind="exam" :question-id="editingQ" :expanded="true" @close="modalAiExpanded = false" />
              </template>
            </section>
          </template>
          </div>

          <div class="modal-actions">
            <button class="btn-ghost" @click="showForm = false">取消</button>
            <button v-if="form.question_type === 'code' && editingQ" class="btn-ghost" @click="finishEditing">完成</button>
            <button class="btn-accent" @click="save">
              {{ form.question_type === 'code' ? (editingQ ? '保存基础信息' : '保存并继续配置') : '保存题目' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Exam Question Edit — Code Studio
   page-head + question cards + modal form
   ═══════════════════════════════════════════════════════════════════════ */
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  /* Keep this editor aligned with the platform's blue primary action color. */
  --exam-action: var(--primary);
  --exam-action-hover: var(--primary-dark);
}

/* The shared .btn-accent token is orange for legacy pages.  The exam editor
   uses blue primary actions so its controls match the rest of the teacher UI. */
.page :deep(.btn-accent) {
  background: var(--exam-action);
  border-color: var(--exam-action);
  color: #fff;
}
.page :deep(.btn-accent:hover:not(:disabled)) {
  background: var(--exam-action-hover);
  border-color: var(--exam-action-hover);
  box-shadow: 0 4px 12px rgba(20, 99, 243, 0.28);
}
.page :deep(.btn-accent:focus-visible) {
  outline: none;
  box-shadow: 0 0 0 3px rgba(20, 99, 243, 0.2);
}

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.back-btn { margin-bottom: 8px; color: var(--text-secondary); }
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 0;
}

/* ── Question Cards ────────────────────────────────────────────────── */
.question-card { padding: 20px; }
.qh { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.qh strong { font-size: var(--text-sm); color: var(--ink); }
.qp { font-size: var(--text-xs); color: var(--text-secondary); }
.qa { margin-left: auto; display: flex; gap: 4px; }
.btn-del { color: var(--danger); }
.btn-del:hover { background: var(--danger-light); }
.qd { color: var(--text-secondary); font-size: var(--text-sm); margin: 0; line-height: 1.5; }
.badge-mode {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 500;
  background: #dbeafe; color: #1e40af;
}
.badge-mode.incomplete { background:#fff7ed; color:#c2410c; }
.btn-ai { color: #3b82f6; }
.btn-ai:hover { background: #eff6ff; }

/* ── Modal ─────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(2px);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 4vh 16px;
}
.modal-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  width: min(1040px, 96vw); max-height: 92vh; overflow: hidden;
  box-sizing: border-box;
  box-shadow: var(--shadow-xl);
  display:flex; flex-direction:column;
}
.modal-header {
  display:flex; align-items:flex-start; justify-content:space-between; gap:16px;
  padding:24px 28px 18px; border-bottom:1px solid var(--border); background:var(--surface);
}
.modal-header p { margin:5px 0 0; color:var(--text-secondary); font-size:13px; }
.modal-close { border:0; background:none; color:var(--text-secondary); font-size:26px; line-height:1; cursor:pointer; }
.modal-body { padding:24px 28px; overflow-y:auto; }
.editor-section { padding:0 0 22px; margin-bottom:22px; border-bottom:1px solid var(--border); }
.editor-section:last-child { border-bottom:0; margin-bottom:0; }
.section-heading { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
.section-heading > span { display:grid; place-items:center; width:28px; height:28px; border-radius:50%; background:#eff6ff; color:#2563eb; font-weight:700; font-size:13px; }
.section-heading h4 { margin:0; font-size:16px; color:var(--ink); }
.section-heading p { margin:3px 0 0; color:var(--text-secondary); font-size:12px; }
.limit-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.save-first-note { padding:14px 16px; border:1px solid #fed7aa; border-radius:10px; background:#fff7ed; color:#9a3412; font-size:13px; }
.ai-section :deep(.ai-config) { margin-top:0; }
.ai-section :deep(.ai-config-header h4) { display:none; }
.ai-section :deep(.ai-config-header) { justify-content:flex-end; }
.modal-title {
  font-size: 20px; font-weight: 650; color: var(--ink);
  margin: 0; letter-spacing: -0.01em;
}
.modal-actions {
  display: flex; gap: 8px; justify-content: flex-end;
  padding:16px 28px; border-top:1px solid var(--border); background:var(--surface);
  box-shadow:0 -8px 22px rgba(15,23,42,.04);
}

/* ── Code input (monospace textarea) ────────────────────────────────── */
.code-input {
  font-family: var(--font-mono); font-size: var(--text-xs);
  background: var(--surface-sunken); line-height: 1.6;
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
  .modal-overlay { padding:0; align-items:stretch; }
  .modal-card { width:100vw; max-height:100vh; border-radius:0; }
  .modal-header, .modal-body, .modal-actions { padding-left:16px; padding-right:16px; }
  .limit-grid { grid-template-columns:1fr; gap:0; }
}
</style>
