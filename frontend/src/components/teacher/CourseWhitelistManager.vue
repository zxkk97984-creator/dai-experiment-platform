<script setup>
// 课程白名单管理：查看/添加/移除可见学生。
// 增删即时生效；可见范围本身需在课程设置中保存。
// 仅当课程 visibility === 'whitelist' 时由设置抽屉渲染。

import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

import ConfirmDialog from '../ui/ConfirmDialog.vue'
import AppIcon from '../ui/AppIcon.vue'
import { coursesAPI } from '../../api/courses.js'
import { usersAPI } from '../../api/users.js'
import { useAppStore } from '../../stores/app.js'

const props = defineProps({
  courseId: { type: [String, Number], default: null },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const app = useAppStore()

const entries = ref([]) // 已加入名单（后端 CourseWhitelistEntryRead）
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const loadingMore = ref(false)

const searchQuery = ref('')
const candidates = ref([])
const searching = ref(false)
const mutationIds = ref(new Set()) // 正在添加/移除的学生 id，防重复提交

const removeTarget = ref(null) // { student_id, name }
const removing = ref(false)

let debounceTimer = null

const hasMore = computed(() => !isDraftMode.value && entries.value.length < total.value)
const isDraftMode = computed(() => !props.courseId)
const visibleEntries = computed(() => (
  isDraftMode.value
    ? props.modelValue.map((student) => ({ student }))
    : entries.value
))
const visibleTotal = computed(() => (isDraftMode.value ? props.modelValue.length : total.value))

async function loadWhitelist(reset = true) {
  if (reset) {
    page.value = 1
    loading.value = true
  } else {
    loadingMore.value = true
  }
  try {
    const res = await coursesAPI.listWhitelist(props.courseId, {
      page: page.value,
      page_size: pageSize,
    })
    const items = res.data.items || []
    if (reset) entries.value = items
    else entries.value = [...entries.value, ...items]
    total.value = res.data.total ?? entries.value.length
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '白名单加载失败', 'error')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  page.value += 1
  loadWhitelist(false)
}

async function searchStudents() {
  try {
    const res = await usersAPI.listStudents({
      q: searchQuery.value.trim(),
      page: 1,
      page_size: 20,
    })
    candidates.value = res.data.items || []
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '学生查询失败', 'error')
    candidates.value = []
  } finally {
    searching.value = false
  }
}

function onSearchInput() {
  searching.value = true
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(searchStudents, 300)
}

function isAdded(studentId) {
  return visibleEntries.value.some((entry) => entry.student.id === studentId)
}

async function addStudent(student) {
  if (mutationIds.value.has(student.id)) return
  if (isDraftMode.value) {
    if (!isAdded(student.id)) emit('update:modelValue', [...props.modelValue, student])
    return
  }
  mutationIds.value.add(student.id)
  try {
    await coursesAPI.addWhitelistStudent(props.courseId, student.id)
    app.showToast('已加入白名单', 'success')
    await loadWhitelist(true)
  } catch (e) {
    // 失败保留原列表，仅提示
    app.showToast(e.response?.data?.detail?.message || '添加失败', 'error')
  } finally {
    mutationIds.value.delete(student.id)
  }
}

function askRemove(entry) {
  removeTarget.value = entry
}

async function confirmRemove() {
  if (!removeTarget.value) return
  const studentId = removeTarget.value.student.id
  if (isDraftMode.value) {
    emit('update:modelValue', props.modelValue.filter((student) => student.id !== studentId))
    removeTarget.value = null
    return
  }
  removing.value = true
  try {
    await coursesAPI.removeWhitelistStudent(props.courseId, studentId)
    app.showToast('已移出白名单', 'success')
    removeTarget.value = null
    await loadWhitelist(true)
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '移除失败', 'error')
  } finally {
    removing.value = false
  }
}

onMounted(() => {
  if (!isDraftMode.value) loadWhitelist()
  else loading.value = false
  searchStudents()
})

onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<template>
  <section class="whitelist-manager" aria-label="可见学生白名单">
    <div class="wl-heading">
      <h3>可见学生白名单</h3>
      <span class="wl-count">{{ visibleTotal }} 名学生</span>
    </div>
    <p class="wl-tip">
      <AppIcon name="info" :size="14" />
      {{ isDraftMode ? '所选学生将在课程创建成功后加入白名单。' : '名单修改即时生效；可见范围本身需点击下方“保存设置”后生效。' }}
    </p>

    <!-- 已加入列表 -->
    <div v-if="loading" class="wl-loading">正在加载名单…</div>
    <template v-else>
      <div v-if="visibleEntries.length === 0" class="wl-empty">
        当前未添加学生，保存为白名单后将没有学生可以看到该课程。
      </div>
      <ul v-else class="wl-list wl-selected-list">
        <li v-for="entry in visibleEntries" :key="entry.student.id" class="wl-item">
          <div class="wl-item-info">
            <span class="wl-name">{{ entry.student.real_name || entry.student.username }}</span>
            <span class="wl-username">{{ entry.student.username }}</span>
            <span class="wl-status">{{ entry.student.status === 'active' ? '正常' : '禁用' }}</span>
          </div>
          <button
            type="button"
            class="wl-remove"
            :disabled="mutationIds.has(entry.student.id)"
            @click="askRemove(entry)"
          >
            移除
          </button>
        </li>
      </ul>
      <button
        v-if="hasMore"
        type="button"
        class="wl-more"
        :disabled="loadingMore"
        @click="loadMore"
      >
        {{ loadingMore ? '加载中…' : '加载更多' }}
      </button>
    </template>

    <!-- 搜索添加 -->
    <div class="wl-search">
      <input
        v-model="searchQuery"
        type="search"
        placeholder="输入姓名或用户名搜索学生"
        aria-label="搜索学生"
        @input="onSearchInput"
      />
    </div>
    <p v-if="searching" class="wl-loading">搜索中…</p>
    <ul v-else-if="candidates.length > 0" class="wl-list">
      <li v-for="student in candidates" :key="student.id" class="wl-item">
        <div class="wl-item-info">
          <span class="wl-name">{{ student.real_name || student.username }}</span>
          <span class="wl-username">{{ student.username }}</span>
        </div>
        <button
          v-if="isAdded(student.id)"
          type="button"
          class="wl-added"
          disabled
        >
          已添加
        </button>
        <button
          v-else
          type="button"
          class="wl-add"
          :disabled="mutationIds.has(student.id)"
          @click="addStudent(student)"
        >
          添加
        </button>
      </li>
    </ul>
    <p v-else-if="searchQuery.trim()" class="wl-empty">没有匹配的学生</p>

    <!-- 移除确认 -->
    <ConfirmDialog
      v-if="removeTarget"
      title="移出白名单"
      :message="`确定将 ${removeTarget.student.real_name || removeTarget.student.username} 移出白名单吗？该学生将立即失去课程可见性（不影响已选课关系）。`"
      confirm-text="移出"
      danger
      @confirm="confirmRemove"
      @cancel="removeTarget = null"
    />
  </section>
</template>

<style scoped>
.whitelist-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--surface-muted, var(--surface-subtle));
  border: 1px solid var(--border);
  border-radius: var(--radius-card, 12px);
}

.wl-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.wl-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--fg);
}
.wl-count {
  font-size: var(--text-xs, 12px);
  color: var(--muted);
  font-weight: 500;
}

.wl-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: var(--text-xs, 12px);
  color: var(--muted);
}

.wl-loading {
  margin: 0;
  font-size: var(--text-sm, 13px);
  color: var(--muted);
}

.wl-empty {
  margin: 0;
  padding: 12px;
  font-size: var(--text-sm, 13px);
  color: var(--muted);
  background: var(--surface);
  border: 1px dashed var(--border-strong, var(--border-strong));
  border-radius: var(--radius-control, 8px);
}

.wl-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 260px;
  overflow-y: auto;
}

.wl-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-control, 8px);
}

.wl-item-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}
.wl-name {
  font-size: var(--text-sm, 13px);
  font-weight: 600;
  color: var(--fg);
}
.wl-username {
  font-size: var(--text-xs, 12px);
  color: var(--muted);
}
.wl-status {
  font-size: var(--text-xs, 12px);
  color: var(--faint);
}

.wl-remove {
  padding: 5px 12px;
  background: var(--surface);
  border: 1px solid var(--border-strong, var(--border-strong));
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-xs, 12px);
  color: var(--danger, var(--danger));
  cursor: pointer;
  flex-shrink: 0;
}
.wl-remove:hover { background: var(--danger-light, var(--danger-bg)); }
.wl-remove:disabled { opacity: 0.5; cursor: not-allowed; }

.wl-add {
  padding: 5px 12px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-xs, 12px);
  color: var(--surface);
  cursor: pointer;
  flex-shrink: 0;
}
.wl-add:hover { opacity: 0.9; }
.wl-add:disabled { opacity: 0.5; cursor: not-allowed; }

.wl-added {
  padding: 5px 12px;
  background: var(--surface-muted, var(--surface-subtle));
  border: 1px solid var(--border);
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-xs, 12px);
  color: var(--faint);
  flex-shrink: 0;
}

.wl-more {
  align-self: flex-start;
  padding: 6px 14px;
  background: var(--surface);
  border: 1px solid var(--border-strong, var(--border-strong));
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-xs, 12px);
  color: var(--accent);
  cursor: pointer;
}
.wl-more:disabled { opacity: 0.5; cursor: not-allowed; }

.wl-search input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-sm, 13px);
}
</style>
