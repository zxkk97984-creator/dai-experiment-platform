<template>
  <div class="ai-config" v-if="expanded">
    <div class="ai-config-header">
      <h4>🤖 AI 评分配置</h4>
      <button class="btn-sm" @click="$emit('close')">收起</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <!-- 评分模式 -->
      <div class="form-group">
        <label>评分模式</label>
        <select v-model="config.grading_mode" @change="dirty = true">
          <option value="legacy">legacy — 传统判题（仅通过/不通过）</option>
          <option value="shadow">shadow — AI 评分仅教师可见，正式分用旧规则</option>
          <option value="active">active — AI 评分计入正式成绩</option>
        </select>
      </div>

      <!-- 测试组（F/R） -->
      <div class="section">
        <div class="section-header">
          <h5>功能/鲁棒性测试组 (F + R = 70)</h5>
          <button class="btn-sm btn-outline" @click="addGroup">+ 添加测试组</button>
        </div>
        <div v-if="!config.test_groups?.length" class="hint">暂无测试组。F 组满分总计 60，R 组满分总计 10。</div>
        <div v-for="(g, i) in config.test_groups" :key="i" class="group-card">
          <div class="group-row">
            <input v-model="g.id" placeholder="ID (如 F1)" class="input-sm" @change="dirty = true" />
            <input v-model="g.name" placeholder="名称" class="input-sm" @change="dirty = true" />
            <select v-model="g.dimension" class="input-sm" @change="dirty = true">
              <option value="F">F 功能 (满分合计 60)</option>
              <option value="R">R 鲁棒性 (满分合计 10)</option>
            </select>
            <input v-model.number="g.max_score" type="number" placeholder="满分" class="input-sm input-num" @change="dirty = true" />
            <button class="btn-sm btn-danger-text" @click="removeGroup(i)">删除</button>
          </div>
          <textarea v-model="g.tests" rows="4" class="code-editor" placeholder="pytest 测试代码..." @change="dirty = true"></textarea>
        </div>
        <div v-if="validationMsg" :class="validationMsg.ok ? 'hint-ok' : 'hint-err'">{{ validationMsg.text }}</div>
      </div>

      <!-- 教师约束 -->
      <div class="form-group">
        <label>教师硬性要求 (JSON，可选)</label>
        <textarea v-model="constraintsStr" rows="3" class="code-editor" placeholder='{"required_algorithm": "二分查找", "required_complexity": "O(log n)"}' @change="dirty = true"></textarea>
      </div>

      <!-- 参考答案 -->
      <div class="form-group">
        <label>参考答案 (可选，仅供 AI 理解题目)</label>
        <textarea v-model="config.reference_solution" rows="6" class="code-editor" placeholder="# 参考实现..." @change="dirty = true"></textarea>
      </div>

      <!-- 上限规则 -->
      <div class="section">
        <div class="section-header">
          <h5>分数上限规则</h5>
          <button class="btn-sm btn-outline" @click="addCapRule">+ 添加上限</button>
        </div>
        <div v-if="!config.score_cap_rules?.length" class="hint">无上限规则。</div>
        <div v-for="(r, i) in config.score_cap_rules" :key="i" class="cap-row">
          <input v-model="r.id" placeholder="ID" class="input-sm" @change="dirty = true" />
          <select v-model="r.condition_code" class="input-sm" @change="dirty = true">
            <option value="off_topic">偏题</option>
            <option value="hardcoded_public_examples">硬编码样例</option>
            <option value="required_algorithm_missing">缺失要求算法</option>
            <option value="required_complexity_missing">复杂度不达标</option>
            <option value="dangerous_operation">危险操作</option>
          </select>
          <input v-model="r.description" placeholder="描述（必填）" class="input-sm" @change="dirty = true" style="width:120px" />
          <input v-model.number="r.cap" type="number" placeholder="上限分" class="input-sm input-num" @change="dirty = true" />
          <button class="btn-sm btn-danger-text" @click="removeCapRule(i)">删除</button>
        </div>
      </div>

      <!-- Rubric -->
      <div class="section">
        <div class="section-header">
          <h5>评分标准 (Rubric)</h5>
          <button class="btn-sm btn-primary" :disabled="rubricLoading" @click="generateRubricAction">
            {{ rubricLoading ? '生成中...' : '🤖 AI 生成 Rubric' }}
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
import { ref, watch, computed } from 'vue'
import { aiGradingAPI } from '../../api/aiGrading.js'

const props = defineProps({
  kind: { type: String, required: true },  // 'assignment' | 'exam'
  questionId: { type: Number, required: true },
  expanded: { type: Boolean, default: false },
})

defineEmits(['close'])

const config = ref({ grading_mode: 'shadow', teacher_constraints: {}, reference_solution: null, test_groups: [], score_cap_rules: [] })
const constraintsStr = ref('')
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)
const error = ref('')
const rubrics = ref([])
const rubricLoading = ref(false)

const validationMsg = computed(() => {
  const groups = config.value.test_groups || []
  if (!groups.length) return null
  const fSum = groups.filter(g => g.dimension === 'F').reduce((s, g) => s + (Number(g.max_score) || 0), 0)
  const rSum = groups.filter(g => g.dimension === 'R').reduce((s, g) => s + (Number(g.max_score) || 0), 0)
  const fOk = Math.abs(fSum - 60) < 1e-6
  const rOk = Math.abs(rSum - 10) < 1e-6
  if (fOk && rOk) return { ok: true, text: `✓ F 总计 ${fSum}/60, R 总计 ${rSum}/10` }
  return { ok: false, text: `⚠ F 总计 ${fSum}/60 (需=60), R 总计 ${rSum}/10 (需=10)` }
})

async function load() {
  loading.value = true; error.value = ''
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
    constraintsStr.value = JSON.stringify(config.value.teacher_constraints, null, 2)
    rubrics.value = rubRes.data.items || []
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.message || '加载失败'
  } finally { loading.value = false }
}

function addGroup() {
  if (!config.value.test_groups) config.value.test_groups = []
  config.value.test_groups.push({ id: '', name: '', dimension: 'F', max_score: 0, tests: '' })
  dirty.value = true
}

function removeGroup(i) {
  config.value.test_groups.splice(i, 1)
  dirty.value = true
}

function addCapRule() {
  if (!config.value.score_cap_rules) config.value.score_cap_rules = []
  config.value.score_cap_rules.push({ id: '', description: '', condition_code: 'off_topic', cap: 0 })
  dirty.value = true
}

function removeCapRule(i) {
  config.value.score_cap_rules.splice(i, 1)
  dirty.value = true
}

async function save() {
  saving.value = true; saveMsg.value = ''
  try {
    // 解析约束 JSON：空字符串→{}，非法 JSON→阻止保存
    let constraints = {}
    const raw = (constraintsStr.value || '').trim()
    if (raw) {
      try { constraints = JSON.parse(raw) }
      catch {
        saveMsg.value = '教师约束 JSON 格式错误，请修正后重试'
        saveOk.value = false
        return
      }
    }
    await aiGradingAPI.updateConfig(props.kind, props.questionId, {
      grading_mode: config.value.grading_mode,
      teacher_constraints: constraints,
      reference_solution: config.value.reference_solution || null,
      test_groups: config.value.test_groups,
      score_cap_rules: config.value.score_cap_rules,
    })
    saveOk.value = true; saveMsg.value = '保存成功'; dirty.value = false
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

watch(() => props.expanded, (val) => { if (val) load() })
</script>

<style scoped>
.ai-config {
  background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 16px; margin-top: 12px;
}
.ai-config-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.ai-config-header h4 { margin: 0; font-size: 15px; }
.section { margin: 16px 0; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-header h5 { margin: 0; font-size: 13px; font-weight: 600; color: #475569; }
.form-group { margin: 12px 0; }
.form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; color: #475569; }
.form-group select { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.group-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; margin: 8px 0; background: #fff; }
.group-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.cap-row { display: flex; gap: 6px; align-items: center; margin: 4px 0; }
.rubric-row { display: flex; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 1px solid #eee; }
.input-sm { padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; }
.input-num { width: 70px; }
.code-editor {
  width: 100%; background: #0F172A; color: #E2E8F0; border: 1px solid #1E293B;
  border-radius: 4px; padding: 8px; font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px; line-height: 1.5; resize: vertical; margin-top: 4px;
}
.hint { color: #94a3b8; font-size: 12px; }
.hint-ok { color: #16a34a; font-size: 12px; margin-top: 4px; }
.hint-err { color: #dc2626; font-size: 12px; margin-top: 4px; }
.badge-sm { padding: 1px 6px; border-radius: 10px; font-size: 11px; }
.badge-draft { background: #fef3c7; color: #92400e; }
.badge-locked { background: #d1fae5; color: #065f46; }
.badge-superseded { background: #e2e8f0; color: #64748b; }
.actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; }
.btn-sm { padding: 4px 12px; font-size: 12px; border-radius: 4px; cursor: pointer; border: 1px solid #ddd; background: #fff; }
.btn-primary { padding: 6px 16px; background: #3b82f6; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { border: 1px solid #3b82f6; color: #3b82f6; background: #fff; }
.btn-danger-text { border: none; background: none; color: #dc2626; cursor: pointer; }
.loading { color: #666; }
.error { color: #dc3545; font-size: 13px; }
.success { color: #16a34a; font-size: 13px; }
.text-sm { font-size: 12px; }
.text-secondary { color: #94a3b8; }
</style>
