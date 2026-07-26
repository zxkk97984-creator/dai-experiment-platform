<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const route = useRoute(); const router = useRouter(); const app = useAppStore()
const examId = route.params.id; const exam = ref(null); const questions = ref([])
const loading = ref(true); const showForm = ref(false); const editingQ = ref(null)
const form = ref({ question_type: 'single_choice', prompt: '', options_text: '{}', correct_answer_text: '{}', points: 1, starter_code: '', hidden_tests: '' })
async function load() { loading.value = true; try { const [eR,qR] = await Promise.all([examsAPI.get(examId), examsAPI.getQuestions(examId)]); exam.value = eR.data; questions.value = qR.data.items || [] } catch { app.showToast('加载失败', 'error') } finally { loading.value = false } }
function openAdd() { editingQ.value = null; form.value = { question_type: 'single_choice', prompt: '', options_text: '{}', correct_answer_text: '{}', points: 1, starter_code: '', hidden_tests: '' }; showForm.value = true }
function openEdit(q) { editingQ.value = q.id; form.value = { question_type: q.question_type, prompt: q.prompt || '', options_text: JSON.stringify(q.options||{}), correct_answer_text: JSON.stringify(q.correct_answer||{}), points: q.points||1, starter_code: q.starter_code||'', hidden_tests: q.hidden_tests||'' }; showForm.value = true }
async function save() {
  try {
    const p = { question_type: form.value.question_type, prompt: form.value.prompt, points: form.value.points, order_index: editingQ.value ? undefined : questions.value.length }
    if (form.value.question_type !== 'code') { try { p.options = JSON.parse(form.value.options_text) } catch { p.options = {} }; try { p.correct_answer = JSON.parse(form.value.correct_answer_text) } catch { p.correct_answer = {} } }
    else { p.starter_code = form.value.starter_code || ''; p.hidden_tests = form.value.hidden_tests || ''; p.correct_answer = {} }
    if (editingQ.value) await examsAPI.updateQuestion(examId, editingQ.value, p); else await examsAPI.createQuestion(examId, p)
    showForm.value = false; load(); app.showToast('保存成功', 'success')
  } catch(e) { app.showToast(e.response?.data?.detail?.message || '保存失败', 'error') }
}
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
          <span class="qa">
            <button class="btn-ghost btn-sm" @click="openEdit(q)">编辑</button>
            <button class="btn-ghost btn-sm btn-del" @click="remove(q.id)">删除</button>
          </span>
        </div>
        <p class="qd">{{ q.prompt }}</p>
      </div>

      <!-- ── Modal Form ─────────────────────────────────────────────────── -->
      <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
        <div class="modal-card">
          <h3 class="modal-title">{{ editingQ ? '编辑题目' : '新建题目' }}</h3>

          <div class="form-group">
            <label>题目类型</label>
            <select v-model="form.question_type">
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
            <input v-model.number="form.points" type="number" />
          </div>

          <!-- 选择题字段 -->
          <template v-if="form.question_type !== 'code'">
            <div class="form-group">
              <label>选项 (JSON)</label>
              <textarea v-model="form.options_text" rows="3" class="code-input" placeholder='{"A":"选项A","B":"选项B"}'></textarea>
            </div>
            <div class="form-group">
              <label>正确答案 (JSON)</label>
              <input v-model="form.correct_answer_text" placeholder='{"correct":["A"]}' />
            </div>
          </template>

          <!-- 编程题字段 -->
          <template v-else>
            <div class="form-group">
              <label>初始代码</label>
              <textarea v-model="form.starter_code" rows="4" class="code-input" placeholder="def solution(): pass"></textarea>
            </div>
            <div class="form-group">
              <label>隐藏测试 (pytest)</label>
              <textarea v-model="form.hidden_tests" rows="4" class="code-input" placeholder="def test_solution(): assert solution() == expected"></textarea>
            </div>
          </template>

          <div class="modal-actions">
            <button class="btn-ghost" @click="showForm = false">取消</button>
            <button class="btn-accent" @click="save">保存</button>
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
.page { display: flex; flex-direction: column; gap: 24px; }

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

/* ── Modal ─────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(2px);
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 10vh;
}
.modal-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-xl); padding: 28px;
  width: 90vw; max-width: 560px; max-height: 80vh; overflow-y: auto;
  box-shadow: var(--shadow-xl);
}
.modal-title {
  font-size: 18px; font-weight: 600; color: var(--ink);
  margin: 0 0 20px; letter-spacing: -0.01em;
}
.modal-actions {
  display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px;
}

/* ── Code input (monospace textarea) ────────────────────────────────── */
.code-input {
  font-family: var(--font-mono); font-size: var(--text-xs);
  background: var(--surface-sunken); line-height: 1.6;
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
  .modal-card { padding: 20px; }
}
</style>