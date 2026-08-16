<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  prompt: { type: String, default: '' },
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:prompt', 'update:modelValue'])
const promptInput = ref(null)

const segments = computed(() => {
  const output = []
  const text = props.prompt || ''
  let last = 0
  for (const match of text.matchAll(/\[\[blank:([A-Za-z0-9_-]+)\]\]/g)) {
    if (match.index > last) output.push({ type: 'text', text: text.slice(last, match.index) })
    output.push({ type: 'blank', id: match[1] })
    last = match.index + match[0].length
  }
  if (last < text.length) output.push({ type: 'text', text: text.slice(last) })
  return output
})

function updateRows(rows) { emit('update:modelValue', rows.map(row => ({ ...row, accepted_answers: [...row.accepted_answers] }))) }

async function insertBlank() {
  const used = new Set(props.modelValue.map(item => item.id))
  let index = 1
  while (used.has(`blank${index}`)) index += 1
  const id = `blank${index}`
  const marker = `[[blank:${id}]]`
  const input = promptInput.value
  const start = input?.selectionStart ?? props.prompt.length
  const end = input?.selectionEnd ?? start
  const nextPrompt = `${props.prompt.slice(0, start)}${marker}${props.prompt.slice(end)}`
  emit('update:prompt', nextPrompt)
  updateRows([...props.modelValue, { id, accepted_answers: [''], case_sensitive: false }])
  await nextTick()
  input?.focus()
  input?.setSelectionRange(start + marker.length, start + marker.length)
}

function removeBlank(index) {
  const row = props.modelValue[index]
  emit('update:prompt', props.prompt.replace(`[[blank:${row.id}]]`, ''))
  updateRows(props.modelValue.filter((_, rowIndex) => rowIndex !== index))
}

function updateRow(index, patch) {
  updateRows(props.modelValue.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
}

function addAnswer(index) {
  const row = props.modelValue[index]
  updateRow(index, { accepted_answers: [...row.accepted_answers, ''] })
}

function updateAnswer(rowIndex, answerIndex, value) {
  const answers = [...props.modelValue[rowIndex].accepted_answers]
  answers[answerIndex] = value
  updateRow(rowIndex, { accepted_answers: answers })
}

function removeAnswer(rowIndex, answerIndex) {
  const row = props.modelValue[rowIndex]
  if (row.accepted_answers.length <= 1) return
  updateRow(rowIndex, { accepted_answers: row.accepted_answers.filter((_, index) => index !== answerIndex) })
}
</script>

<template>
  <section class="fill-editor">
    <div class="fill-toolbar">
      <div><h4>题干与空格</h4><p>把光标放在题干中需要留空的位置，再插入一个稳定空格。</p></div>
      <button type="button" class="btn-primary" @click="insertBlank">＋ 插入空格</button>
    </div>
    <textarea ref="promptInput" :value="prompt" rows="5" placeholder="例如：Python 的创建者是……" @input="emit('update:prompt', $event.target.value)"></textarea>
    <div class="preview" aria-label="填空题预览">
      <span class="preview-label">学生端预览</span>
      <p><template v-for="(segment, index) in segments" :key="index"><span v-if="segment.type === 'text'">{{ segment.text }}</span><input v-else disabled :aria-label="segment.id" /></template></p>
    </div>

    <div v-if="modelValue.length" class="blank-list">
      <article v-for="(blank, rowIndex) in modelValue" :key="blank.id" class="blank-row">
        <header><div><strong>空格 {{ rowIndex + 1 }}</strong><code>{{ blank.id }}</code></div><button type="button" class="remove" @click="removeBlank(rowIndex)">删除空格</button></header>
        <label class="case-toggle"><input type="checkbox" :checked="blank.case_sensitive" @change="updateRow(rowIndex, { case_sensitive: $event.target.checked })"> 区分大小写</label>
        <div class="answers">
          <label v-for="(answer, answerIndex) in blank.accepted_answers" :key="answerIndex"><span>可接受答案 {{ answerIndex + 1 }}</span><div><input :value="answer" placeholder="输入标准答案" @input="updateAnswer(rowIndex, answerIndex, $event.target.value)"><button type="button" :disabled="blank.accepted_answers.length <= 1" @click="removeAnswer(rowIndex, answerIndex)">×</button></div></label>
        </div>
        <button type="button" class="add-answer" @click="addAnswer(rowIndex)">＋ 添加另一个可接受答案</button>
      </article>
    </div>
    <p v-else class="empty-note">尚未插入空格。发布前，每个空格都必须至少设置一个标准答案。</p>
  </section>
</template>

<style scoped>
.fill-editor{display:grid;gap:16px}.fill-toolbar{display:flex;align-items:center;justify-content:space-between;gap:18px}.fill-toolbar h4{margin:0;color:var(--fg);font-size:14px}.fill-toolbar p{margin:5px 0 0;color:var(--muted);font-size:12px}.fill-toolbar button{flex:none;padding:8px 12px}.fill-editor>textarea{box-sizing:border-box;width:100%;padding:11px 12px;border:1px solid var(--border);border-radius: var(--radius-md);resize:vertical}.preview{padding:14px;border:1px dashed var(--info-bg);border-radius: var(--radius-md);background:var(--surface-sunken)}.preview-label{color:var(--accent);font-size:10px;font-weight:750;letter-spacing:.08em}.preview p{margin:10px 0 0;color:var(--fg);white-space:pre-wrap;line-height:2.2}.preview input{display:inline-block;width:105px;height:24px;margin:0 6px;border:0;border-bottom:2px solid var(--info-bg);background:var(--accent-soft)}.blank-list{display:grid;gap:12px}.blank-row{padding:16px;border:1px solid var(--border);border-radius: var(--radius-md);background:var(--surface)}.blank-row header{display:flex;align-items:center;justify-content:space-between}.blank-row header div{display:flex;align-items:center;gap:8px}.blank-row strong{font-size:13px}.blank-row code{padding:3px 6px;border-radius: var(--radius-md);background:var(--surface-subtle);color:var(--muted);font-size:10px}.remove{border:0;background:transparent;color:var(--danger);font-size:11px}.case-toggle{display:block;margin:13px 0;color:var(--muted);font-size:12px}.answers{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.answers label>span{display:block;margin-bottom:5px;color:var(--muted);font-size:10px}.answers label>div{display:flex}.answers input{min-width:0;flex:1;padding:8px;border:1px solid var(--border);border-radius: var(--radius-md) 0 0 7px}.answers button{width:32px;border:1px solid var(--border);border-left:0;border-radius:0 7px 7px 0;background:var(--surface-subtle);color:var(--muted)}.add-answer{margin-top:10px;padding:0;border:0;background:transparent;color:var(--accent);font-size:11px}.empty-note{margin:0;padding:13px;border-radius: var(--radius-md);background:var(--warning-bg);color:var(--danger);font-size:12px}@media(max-width:640px){.fill-toolbar{align-items:flex-start;flex-direction:column}.answers{grid-template-columns:1fr}}
</style>
