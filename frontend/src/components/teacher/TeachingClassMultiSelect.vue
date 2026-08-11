<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AppIcon from '../ui/AppIcon.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '请选择教学班' },
  emptyText: { type: String, default: '该学期暂无教学班' },
  loadingText: { type: String, default: '正在加载教学班…' },
  testId: { type: String, default: 'teaching-class-select' },
})

const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const searchInput = ref(null)
const open = ref(false)
const query = ref('')

const normalizedSelectedIds = computed(() => new Set((props.modelValue || []).map((id) => Number(id))))
const selectedOptions = computed(() => props.options.filter((item) => normalizedSelectedIds.value.has(Number(item.id))))
const filteredOptions = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return props.options
  return props.options.filter((item) => `${item.name || ''} ${item.code || ''}`.toLowerCase().includes(keyword))
})
const allVisibleSelected = computed(() => (
  filteredOptions.value.length > 0
  && filteredOptions.value.every((item) => normalizedSelectedIds.value.has(Number(item.id)))
))
const selectedSummary = computed(() => `${selectedOptions.value.length}/${props.options.length}`)

function isSelected(item) {
  return normalizedSelectedIds.value.has(Number(item.id))
}

function updateSelection(ids) {
  emit('update:modelValue', [...new Set(ids.map((id) => Number(id)))])
}

function toggleOption(item) {
  if (props.disabled) return
  const id = Number(item.id)
  const ids = [...normalizedSelectedIds.value]
  const index = ids.indexOf(id)
  if (index >= 0) ids.splice(index, 1)
  else ids.push(id)
  updateSelection(ids)
}

function toggleAllVisible() {
  if (props.disabled) return
  const visibleIds = filteredOptions.value.map((item) => Number(item.id))
  const ids = [...normalizedSelectedIds.value]
  if (allVisibleSelected.value) {
    updateSelection(ids.filter((id) => !visibleIds.includes(id)))
    return
  }
  updateSelection([...ids, ...visibleIds])
}

function removeSelected(item) {
  if (props.disabled) return
  updateSelection([...normalizedSelectedIds.value].filter((id) => id !== Number(item.id)))
}

function closeDropdown() {
  open.value = false
  query.value = ''
}

function toggleDropdown() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) nextTick(() => searchInput.value?.focus())
}

function handleTriggerKeydown(event) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleDropdown()
  }
  if (event.key === 'Escape') closeDropdown()
}

function handleDocumentClick(event) {
  if (open.value && root.value && !root.value.contains(event.target)) closeDropdown()
}

onMounted(() => document.addEventListener('click', handleDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', handleDocumentClick))
</script>

<template>
  <div ref="root" class="teaching-class-select" :class="{ 'is-open': open, 'is-disabled': disabled }" :data-testid="testId">
    <div
      class="teaching-class-trigger"
      role="combobox"
      tabindex="0"
      :aria-expanded="open"
      :aria-disabled="disabled"
      @click="toggleDropdown"
      @keydown="handleTriggerKeydown"
    >
      <div class="teaching-class-tags">
        <span v-if="!selectedOptions.length" class="teaching-class-placeholder">
          {{ loading ? loadingText : placeholder }}
        </span>
        <span v-for="item in selectedOptions" :key="item.id" class="teaching-class-tag" :title="item.name">
          <span class="teaching-class-tag-text">{{ item.name }}</span>
          <button type="button" aria-label="移除教学班" :disabled="disabled" @click.stop="removeSelected(item)">
            <AppIcon name="close" :size="13" />
          </button>
        </span>
      </div>
      <AppIcon name="chevron-down" :size="17" class="teaching-class-chevron" />
    </div>

    <div v-if="open" class="teaching-class-menu" role="listbox" aria-multiselectable="true" @click.stop>
      <div class="teaching-class-search-wrap">
        <AppIcon name="search" :size="16" />
        <input ref="searchInput" v-model="query" type="search" aria-label="搜索教学班名称或编码" placeholder="搜索教学班名称或编码" @keydown.esc.stop="closeDropdown" />
      </div>
      <div v-if="!loading && options.length" class="teaching-class-toolbar">
        <span>已选 {{ selectedSummary }}</span>
        <button type="button" @click="toggleAllVisible">{{ allVisibleSelected ? '取消全选' : '全选' }}</button>
      </div>
      <div class="teaching-class-options">
        <div v-if="loading" class="teaching-class-empty">{{ loadingText }}</div>
        <div v-else-if="!options.length" class="teaching-class-empty">{{ emptyText }}</div>
        <div v-else-if="!filteredOptions.length" class="teaching-class-empty">没有匹配的教学班</div>
        <button
          v-for="item in filteredOptions"
          v-else
          :key="item.id"
          type="button"
          class="teaching-class-option"
          role="option"
          :aria-selected="isSelected(item)"
          @click="toggleOption(item)"
        >
          <span class="teaching-class-checkbox" :class="{ checked: isSelected(item) }">
            <AppIcon v-if="isSelected(item)" name="check" :size="13" />
          </span>
          <span class="teaching-class-option-content">
            <strong>{{ item.name }}</strong>
            <small v-if="item.code || item.student_count != null">
              <span v-if="item.code">{{ item.code }}</span><span v-if="item.code && item.student_count != null"> · </span><span v-if="item.student_count != null">{{ item.student_count }} 人</span>
            </small>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.teaching-class-select { position: relative; min-width: 0; }
.teaching-class-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--border, #dbe4f0);
  border-radius: 8px;
  background: #fff;
  color: var(--text-primary, #172033);
  cursor: pointer;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.teaching-class-trigger:hover,
.teaching-class-select.is-open .teaching-class-trigger,
.teaching-class-trigger:focus-visible { border-color: var(--primary, #2563eb); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); outline: 0; }
.teaching-class-select.is-disabled .teaching-class-trigger { cursor: not-allowed; opacity: 0.65; background: var(--surface-raised, #f8fafc); }
.teaching-class-tags { display: flex; flex: 1; flex-wrap: wrap; align-items: center; gap: 4px; min-width: 0; }
.teaching-class-placeholder { padding: 3px 0; color: var(--text-tertiary, #94a3b8); font-size: 13px; font-weight: 400; }
.teaching-class-tag { display: inline-flex; align-items: center; gap: 3px; max-width: 100%; padding: 3px 5px 3px 8px; border-radius: 5px; background: #eef4ff; color: #2458b8; font-size: 12px; font-weight: 500; }
.teaching-class-tag-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.teaching-class-tag button { display: inline-flex; align-items: center; justify-content: center; width: 17px; height: 17px; padding: 0; border: 0; border-radius: 4px; background: transparent; color: #6b8dcc; cursor: pointer; }
.teaching-class-tag button:hover { background: #dbe8ff; color: #2458b8; }
.teaching-class-tag button:disabled { cursor: not-allowed; }
.teaching-class-chevron { flex: 0 0 auto; color: var(--text-muted, #64748b); transition: transform 120ms ease; }
.teaching-class-select.is-open .teaching-class-chevron { transform: rotate(180deg); }
.teaching-class-menu { position: absolute; z-index: 60; top: calc(100% + 6px); left: 0; width: 100%; min-width: 0; max-width: 100%; overflow: hidden; border: 1px solid var(--border, #dbe4f0); border-radius: 9px; background: #fff; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.14); }
.teaching-class-search-wrap { display: flex; align-items: center; gap: 7px; margin: 8px 8px 5px; padding: 0 9px; border: 1px solid var(--border, #dbe4f0); border-radius: 7px; color: var(--text-tertiary, #94a3b8); }
.teaching-class-search-wrap:focus-within { border-color: var(--primary, #2563eb); box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1); }
.teaching-class-search-wrap input { width: 100%; min-width: 0; height: 32px; padding: 0; border: 0; outline: 0; background: transparent; color: var(--text-primary, #172033); font-size: 12px; }
.teaching-class-search-wrap input:hover,
.teaching-class-search-wrap input:focus,
.teaching-class-search-wrap input:focus-visible {
  border: 0;
  border-color: transparent;
  outline: none;
  box-shadow: none;
}
.teaching-class-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 5px 12px 7px; color: var(--text-tertiary, #94a3b8); font-size: 11px; }
.teaching-class-toolbar button { padding: 0; border: 0; background: transparent; color: var(--primary, #2563eb); font-size: 12px; cursor: pointer; }
.teaching-class-toolbar button:hover { color: #1d4ed8; }
.teaching-class-options { max-height: 240px; overflow-y: auto; padding: 2px 6px 6px; }
.teaching-class-option { display: flex; align-items: center; gap: 9px; width: 100%; padding: 8px 8px; border: 0; border-radius: 6px; background: transparent; color: var(--text-primary, #172033); text-align: left; cursor: pointer; }
.teaching-class-option:hover,
.teaching-class-option[aria-selected='true'] { background: #f1f6ff; }
.teaching-class-checkbox { display: inline-flex; align-items: center; justify-content: center; width: 17px; height: 17px; flex: 0 0 auto; border: 1px solid #cbd5e1; border-radius: 4px; color: #fff; }
.teaching-class-checkbox.checked { border-color: var(--primary, #2563eb); background: var(--primary, #2563eb); }
.teaching-class-option-content { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 2px; }
.teaching-class-option-content strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 500; }
.teaching-class-option-content small { color: var(--text-tertiary, #94a3b8); font-size: 11px; font-weight: 400; }
.teaching-class-empty { padding: 22px 12px; color: var(--text-tertiary, #94a3b8); font-size: 12px; text-align: center; }

@media (max-width: 520px) {
  .teaching-class-menu { width: 100%; }
  .teaching-class-options { max-height: 200px; }
}
</style>
