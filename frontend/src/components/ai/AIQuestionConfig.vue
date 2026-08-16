<template>
  <div class="ai-config" v-if="expanded">
    <div class="ai-config-header">
      <h4>AI 评分配置</h4>
      <button class="btn-sm" @click="$emit('close')">收起</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <!-- Rubric 门禁前置提示：shadow/active 且无可锁定 Rubric 时提前告知（后端 503 仍兜底） -->
      <div v-if="rubricGateMsg" class="gate-warn" role="alert">
        <p class="gate-warn-text">⚠ {{ rubricGateMsg }}</p>
      </div>

      <!-- 纯表单层：读写配置数据；保存/Rubric/AI 生成由本容器负责 -->
      <AiConfigForm
        :key="formKey"
        :model-value="config"
        :generating="generating"
        @update:model-value="onFormUpdate"
        @generate-test-groups="onGenerateTestGroups"
      />

      <!-- 测试组生成状态：成功提示回填；失败保留旧草稿并展示逐项问题 -->
      <div v-if="generateMsg" :class="generateOk ? 'gen-success' : 'gen-error'" role="status">
        <p class="gen-msg">{{ generateMsg }}</p>
        <ul v-if="generateIssues.length" class="gen-issues">
          <li v-for="(issue, i) in generateIssues" :key="i">{{ issue }}</li>
        </ul>
      </div>

      <!-- 覆盖确认：已有草稿时先确认，默认取消；不提供自动合并 -->
      <ConfirmDialog
        v-if="showOverwriteDialog"
        title="覆盖当前测试组草稿？"
        message="生成结果将覆盖当前测试组草稿，且不会自动保存。确认后原草稿将被替换。"
        confirm-text="确认生成"
        cancel-text="取消"
        @confirm="onConfirmOverwrite"
        @cancel="showOverwriteDialog = false"
      />

      <!-- Rubric -->
      <div class="section">
        <div class="section-header">
          <h5>评分标准 (Rubric)</h5>
          <button class="btn-sm btn-primary" :disabled="rubricLoading" @click="generateRubricAction">
            {{ rubricLoading ? '生成中...' : 'AI 生成 Rubric' }}
          </button>
        </div>
        <div v-if="rubrics.length === 0 && !rubricLoading" class="hint">尚无 Rubric，请先生成。</div>
        <div v-for="r in rubrics" :key="r.id" class="rubric-row">
          <span>v{{ r.version }} — <span :class="'badge-sm badge-' + r.status">{{ r.status }}</span></span>
          <span class="text-sm text-secondary">{{ r.model_name }}</span>
          <button v-if="r.status === 'draft'" class="btn-sm btn-outline" @click="lockRubricAction(r.id)">锁定</button>
        </div>
      </div>

      <!-- 保存 -->
      <div class="actions">
        <button class="btn-primary" :disabled="saving || !dirty" @click="save">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <span v-if="saveMsg" :class="saveOk ? 'success' : 'error'">{{ saveMsg }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
// AIQuestionConfig：AI 评分配置「持久化容器层」——已有题目（questionId 必填）的
// 远程配置编辑器：GET 加载 / PUT 保存 / Rubric 生成与锁定。
// 表单编辑能力委托给 AiConfigForm（纯表单层），本层只管数据加载与落库。
import { ref, watch, computed, nextTick } from 'vue'
import { aiGradingAPI } from '../../api/aiGrading.js'
import AiConfigForm from './AiConfigForm.vue'
import ConfirmDialog from '../ui/ConfirmDialog.vue'

const props = defineProps({
  kind: { type: String, required: true },  // 'assignment' | 'exam'
  questionId: { type: Number, required: true },
  expanded: { type: Boolean, default: false },
})

defineEmits(['close'])

const config = ref({ grading_mode: 'active', teacher_constraints: {}, reference_solution: null, test_groups: [], score_cap_rules: [] })
const loading = ref(false)
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)
const error = ref('')
const rubrics = ref([])
const rubricLoading = ref(false)
const formKey = ref(0)  // 表单层重挂 key：加载/切换题目后按最新配置重新初始化

// AI 生成测试组状态（请求/通知/回填由本容器管理，表单层只上抛事件）
const generating = ref(false)
const generateMsg = ref('')
const generateOk = ref(false)
const generateIssues = ref([])
const showOverwriteDialog = ref(false)
let requestSeq = 0  // 请求序号：切题/关闭后自增，使迟到响应失效

// 脏标记：当前值与「已加载/已保存基线」不同即为有未保存修改
const initialSnapshot = ref('')
const snapshot = () => JSON.stringify(config.value)
const dirty = computed(() => snapshot() !== initialSnapshot.value)

// Rubric 门禁：shadow/active 必须先生成并锁定 Rubric 才能发布
const rubricGateMsg = computed(() => {
  if (config.value.grading_mode === 'legacy') return ''
  if (rubrics.value.some((r) => r.status === 'locked')) return ''
  return `当前为 ${config.value.grading_mode} 模式，尚无可发布的 Rubric，请先生成并锁定`
})

async function load() {
  loading.value = true; error.value = ''
  // 切换题目：作废在途生成请求并清空生成状态，禁止迟到响应污染新题目
  requestSeq++
  generating.value = false
  generateMsg.value = ''
  generateIssues.value = []
  showOverwriteDialog.value = false
  try {
    const [cfgRes, rubRes] = await Promise.all([
      aiGradingAPI.getConfig(props.kind, props.questionId),
      aiGradingAPI.listRubrics(props.kind, props.questionId),
    ])
    config.value = {
      grading_mode: cfgRes.data.grading_mode || 'legacy',
      teacher_constraints: cfgRes.data.teacher_constraints || {},
      reference_solution: cfgRes.data.reference_solution || '',
      test_groups: cfgRes.data.test_groups || [],
      score_cap_rules: cfgRes.data.score_cap_rules || [],
    }
    rubrics.value = rubRes.data.items || []
    formKey.value++  // 按最新配置重新初始化表单层
    initialSnapshot.value = snapshot()  // 加载值视为干净基线
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '加载失败'
  } finally { loading.value = false }
}

// 表单层编辑结果上抛：直接接管配置数据（脏标记经快照比较自动置位）
function onFormUpdate(v) { config.value = v }

async function save() {
  saving.value = true; saveMsg.value = ''
  try {
    await aiGradingAPI.updateConfig(props.kind, props.questionId, {
      grading_mode: config.value.grading_mode,
      teacher_constraints: config.value.teacher_constraints || {},
      reference_solution: config.value.reference_solution || null,
      test_groups: config.value.test_groups,
      score_cap_rules: config.value.score_cap_rules,
    })
    saveOk.value = true; saveMsg.value = '保存成功'
    initialSnapshot.value = snapshot()  // 保存成功视为干净基线
  } catch (e) {
    saveOk.value = false; saveMsg.value = e.response?.data?.detail?.message || e.message || '保存失败'
  } finally { saving.value = false }
}

async function generateRubricAction() {
  rubricLoading.value = true; error.value = ''
  try {
    // 未保存的配置先自动保存，确保 Rubric 按最新配置生成
    if (dirty.value) {
      await save()
      if (!saveOk.value) {
        error.value = '请先修正配置错误再生成 Rubric'
        rubricLoading.value = false
        return
      }
    }
    const res = await aiGradingAPI.generateRubric(props.kind, props.questionId)
    rubrics.value.unshift({
      id: res.data.id, version: res.data.version, status: res.data.status,
      model_name: res.data.rubric_json?.model_name || '', created_at: new Date().toISOString(),
    })
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '生成失败'
  } finally { rubricLoading.value = false }
}

async function lockRubricAction(id) {
  try {
    await aiGradingAPI.lockRubric(id)
    const idx = rubrics.value.findIndex(r => r.id === id)
    if (idx >= 0) rubrics.value[idx].status = 'locked'
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '锁定失败'
  }
}

// ── AI 生成测试组（只生成、不保存；结果回填草稿并标记 dirty） ──

function onGenerateTestGroups() {
  if (generating.value) return  // 生成中禁用防重复
  generateMsg.value = ''
  generateIssues.value = []
  // 已有草稿先确认覆盖（默认取消，不提供自动合并）
  if (config.value.test_groups?.length) {
    showOverwriteDialog.value = true
  } else {
    startGenerate()
  }
}

function onConfirmOverwrite() {
  showOverwriteDialog.value = false
  startGenerate()
}

async function startGenerate() {
  generating.value = true
  generateMsg.value = ''
  generateIssues.value = []
  const seq = ++requestSeq
  const myKind = props.kind
  const myQuestionId = props.questionId
  try {
    const res = await aiGradingAPI.generateTestGroups(props.kind, props.questionId, {
      teacher_constraints: config.value.teacher_constraints || {},
      reference_solution: config.value.reference_solution || null,
    })
    // 迟到响应保护：期间已切题则丢弃，禁止回填到新题目
    if (seq !== requestSeq || myKind !== props.kind || myQuestionId !== props.questionId) return
    // 整体替换草稿（不做自动合并），dirty 经快照比较自然置位；不触发 PUT
    config.value = { ...config.value, test_groups: res.data.test_groups }
    formKey.value++  // 表单层按新测试组重新初始化
    generateOk.value = true
    generateMsg.value = '已回填草稿，请检查并保存'
    await nextTick()
    document.getElementById('test-groups-section')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (e) {
    if (seq !== requestSeq) return
    const detail = e.response?.data?.detail
    generateOk.value = false
    generateMsg.value = detail?.message || e.message || '生成失败'
    generateIssues.value = detail?.fields?.issues || []
  } finally {
    if (seq === requestSeq) generating.value = false
  }
}

watch(() => props.expanded, (val) => { if (val) load() }, { immediate: true })
// 右侧栏单实例复用：切换题目（questionId 变化）时重新加载该题配置；
// 切换本身使在途生成请求的序号失效（迟到响应在 startGenerate 中被丢弃）
watch(() => props.questionId, () => { if (props.expanded) load() })
</script>

<style scoped>
.ai-config {
  background: var(--surface-subtle); border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 16px; margin-top: 12px;
}
.ai-config-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.ai-config-header h4 { margin: 0; font-size: 15px; }
.section { margin: 16px 0; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-header h5 { margin: 0; font-size: 13px; font-weight: 600; color: var(--muted); }
.rubric-row { display: flex; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border); }
.badge-sm { padding: 1px 6px; border-radius: var(--radius-md); font-size: 11px; }
.badge-draft { background: var(--warning-bg); color: var(--warning); }
.badge-locked { background: var(--success-bg); color: var(--success); }
.badge-superseded { background: var(--border); color: var(--muted); }
.actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; }
.btn-sm { padding: 4px 12px; font-size: 12px; border-radius: var(--radius-sm); cursor: pointer; border: 1px solid var(--border-strong); background: var(--surface); }
.btn-primary { padding: 6px 16px; background: var(--accent); color: var(--surface); border: none; border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { border: 1px solid var(--accent); color: var(--accent); background: var(--surface); }
.loading { color: var(--muted); }
.error { color: var(--danger); font-size: 13px; }
.success { color: var(--success); font-size: 13px; }
.text-sm { font-size: 12px; }
.text-secondary { color: var(--faint); }
/* 测试组生成状态：成功绿 / 失败红（保留旧草稿，展示逐项问题） */
.gen-success { margin: 10px 0; padding: 8px 12px; border: 1px solid var(--success-bg); border-radius: var(--radius-md); background: var(--success-bg); }
.gen-error { margin: 10px 0; padding: 8px 12px; border: 1px solid var(--danger-bg); border-radius: var(--radius-md); background: var(--danger-bg); }
.gen-msg { margin: 0; font-size: 12.5px; font-weight: 600; }
.gen-success .gen-msg { color: var(--success); }
.gen-error .gen-msg { color: var(--danger); }
.gen-issues { margin: 6px 0 0; padding-left: 18px; }
.gen-issues li { font-size: 12px; color: var(--danger); line-height: 1.6; }
/* Rubric 门禁前置提示（浅橙警告卡，与 QuestionEditView 的 qe-warn-card 一致） */
.gate-warn {
  margin: 0 0 12px; padding: 10px 12px;
  border: 1px solid oklch(0.66 0.14 75 / 0.35); border-radius: var(--radius-md);
  background: var(--warning-bg);
}
.gate-warn-text { margin: 0; font-size: 12.5px; font-weight: 600; color: var(--warning); line-height: 1.5; }
</style>
