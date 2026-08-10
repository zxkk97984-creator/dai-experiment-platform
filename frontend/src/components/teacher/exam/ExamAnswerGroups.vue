<script setup>
/** 成绩详情答案分组折叠组件：按题型聚合得分、展开查看学生作答。展示状态在组件内部。 */
import { computed, ref } from 'vue'
import AppIcon from '../../ui/AppIcon.vue'

const props = defineProps({
  answers: { type: Array, required: true },
})
const emit = defineEmits(['toggle'])

const typeMeta = {
  single_choice: { label: '单选题', order: 1 },
  multi_choice: { label: '多选题', order: 2 },
  code: { label: '编程题', order: 3 },
}
const expanded = ref(new Set())

const groups = computed(() => Object.entries(props.answers.reduce((acc, answer) => {
  ;(acc[answer.question_type] ||= []).push(answer)
  return acc
}, {})).map(([type, answers]) => ({
  type,
  label: typeMeta[type]?.label || '其他题型',
  answers,
  score: answers.reduce((sum, answer) => sum + Number(answer.score || 0), 0),
  total: answers.reduce((sum, answer) => sum + Number(answer.points || 0), 0),
  order: typeMeta[type]?.order || 9,
})).sort((a, b) => a.order - b.order))

function answerState(answer) {
  if (answer.score == null) return { label: '待评分', tone: 'pending' }
  if (Number(answer.score) >= Number(answer.points)) return { label: '正确', tone: 'correct' }
  if (Number(answer.score) <= 0) return { label: '错误', tone: 'wrong' }
  return { label: '部分正确', tone: 'partial' }
}

function toggle(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
  emit('toggle', id)
}
</script>

<template>
  <div v-if="!groups.length" class="empty-state">暂无答题明细</div>
  <section v-for="(group, groupIndex) in groups" :key="group.type" class="question-group">
    <header><strong>{{ ['一', '二', '三', '四'][groupIndex] || groupIndex + 1 }}、{{ group.label }}（共{{ group.answers.length }}题，{{ group.total }}分）</strong><span>得分：{{ group.score }} / {{ group.total }}</span></header>
    <div v-for="answer in group.answers" :key="answer.id" class="question-row" :class="{ expanded: expanded.has(answer.id) }">
      <button @click="toggle(answer.id)">
        <span class="question-number">{{ answer.order_index + 1 }}</span>
        <span class="question-prompt">{{ answer.prompt }}</span>
        <strong>{{ answer.score ?? '—' }} / {{ answer.points }}</strong>
        <span class="answer-state" :class="answerState(answer).tone">{{ answerState(answer).label }}</span>
        <AppIcon :name="expanded.has(answer.id) ? 'chevron-up' : 'chevron-down'" :size="17" />
      </button>
      <div v-if="expanded.has(answer.id)" class="answer-detail">
        <div v-if="answer.question_type === 'code'"><small>学生代码</small><pre>{{ answer.code_answer || '未作答' }}</pre></div>
        <p v-else><small>学生答案</small>{{ answer.selected_options?.join('、') || '未作答' }}</p>
        <p v-if="answer.system_error" class="error-note">评分异常：{{ answer.system_error }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.question-group {
  margin: 0 14px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.question-group > header {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f4f7fb;
  color: var(--ink);
  font-size: 13px;
}
.question-group > header span { font-weight: 600; }
.question-row { border-top: 1px solid var(--border); }
.question-row:first-of-type { border-top: 0; }
.question-row > button {
  display: grid;
  grid-template-columns: 25px 1fr 65px 78px 18px;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 0;
  background: #fff;
  text-align: left;
}
.question-row > button:hover { background: #f8fafc; }
.question-number {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  color: var(--primary);
  background: var(--primary-light);
  font-size: 11px;
}
.question-prompt {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.question-row > button strong { color: var(--ink); font-size: 12px; text-align: right; }
.answer-state { font-size: 11px; text-align: center; }
.answer-state.correct { color: #07985e; }
.answer-state.partial { color: #e68309; }
.answer-state.wrong { color: #dc3e49; }
.answer-state.pending { color: #64748b; }
.answer-detail {
  padding: 12px 16px;
  border-top: 1px dashed var(--border);
  background: #f8fafc;
}
.answer-detail small { display: block; margin-bottom: 5px; color: var(--text-secondary); }
.answer-detail p { margin: 0; color: var(--ink); font-size: 13px; }
.answer-detail pre {
  max-height: 230px;
  margin: 0;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  color: #dce7f7;
  background: #142034;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
}
.error-note { margin-top: 8px !important; color: var(--danger) !important; }
@media (max-width: 760px) {
  .question-row > button { grid-template-columns: 25px 1fr 55px 18px; }
  .answer-state { display: none; }
}
</style>
