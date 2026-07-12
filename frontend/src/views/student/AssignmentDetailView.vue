<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { judgeAPI } from '../../api/judge.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const assignment = ref(null)
const questions = ref([])
const activeQ = ref(0)
const code = ref('')
const submitting = ref(false)

onMounted(async () => {
  try {
    const [aRes, qRes] = await Promise.all([
      assignmentsAPI.get(route.params.id),
      assignmentsAPI.getQuestions(route.params.id),
    ])
    assignment.value = aRes.data
    questions.value = qRes.data.items || qRes.data || []
    if (questions.value.length > 0) {
      code.value = questions.value[0].starter_code || ''
    }
  } catch { app.showToast('加载作业失败', 'error') }
})

function selectQuestion(idx) {
  activeQ.value = idx
  code.value = questions.value[idx]?.starter_code || ''
}

async function handleSubmit() {
  const q = questions.value[activeQ.value]
  if (!q) return
  submitting.value = true
  try {
    const res = await judgeAPI.submit({ question_id: q.id, code: code.value })
    app.showToast('提交成功', 'success')
    router.push(`/student/submissions/${res.data.id}`)
  } catch (e) {
    const msg = e.response?.data?.detail?.message || '提交失败'
    app.showToast(msg, 'error')
  } finally { submitting.value = false }
}
</script>

<template>
  <AppLayout>
    <div v-if="!assignment" class="text-secondary">加载中...</div>
    <template v-else>
      <h1 class="page-title">{{ assignment.title }}</h1>
      <p class="text-secondary mb-4">{{ assignment.description }}</p>

      <div v-if="questions.length === 0" class="card" style="text-align:center;padding:32px">
        <p class="text-secondary">暂无题目</p>
      </div>

      <template v-else>
        <div class="flex gap-2 mb-4">
          <button v-for="(q, i) in questions" :key="q.id" class="btn-sm"
            :class="{ 'btn-primary': i === activeQ }"
            @click="selectQuestion(i)">题目 {{ i + 1 }}</button>
        </div>

        <div class="card mb-4">
          <h3 style="margin-bottom:12px">{{ questions[activeQ]?.title }}</h3>
          <div class="text-sm mb-4" style="white-space:pre-wrap">
            {{ questions[activeQ]?.description }}
          </div>
          <div class="text-sm text-secondary mb-4">
            <strong>函数签名:</strong>
            <code class="text-mono" style="background:#f3f4f6;padding:2px 6px;border-radius:4px">
              {{ questions[activeQ]?.signature || questions[activeQ]?.function_name }}
            </code>
          </div>
          <div v-if="questions[activeQ]?.public_cases?.length" class="text-sm text-secondary mb-4">
            <strong>公开样例:</strong>
            <pre class="text-mono" style="background:#f9fafb;padding:10px;border-radius:4px;overflow-x:auto">
              {{ JSON.stringify(questions[activeQ].public_cases, null, 2) }}</pre>
          </div>
        </div>

        <div class="card mb-4">
          <h3 style="margin-bottom:12px">代码编辑器</h3>
          <textarea v-model="code" class="code-editor" rows="16" spellcheck="false"
            placeholder="# 在此编写 Python 代码"></textarea>
        </div>

        <button class="btn-primary" :disabled="submitting" @click="handleSubmit"
          style="padding:10px 32px;font-size:15px">
          {{ submitting ? '提交中...' : '提交代码' }}
        </button>
      </template>
    </template>
  </AppLayout>
</template>

<style scoped>
.code-editor {
  width: 100%; background: #1e2532; color: #e5e7eb; border: none; border-radius: 6px;
  padding: 16px; font-family: var(--font-mono); font-size: 13px; line-height: 1.6;
  resize: vertical; tab-size: 4;
}
.code-editor:focus { outline: 2px solid var(--accent); }
</style>
