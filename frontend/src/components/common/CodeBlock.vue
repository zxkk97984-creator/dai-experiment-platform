<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  code: { type: String, required: true },
  language: { type: String, default: 'python' },
  filename: { type: String, default: 'main.py' },
})

const copied = ref(false)

const lines = computed(() => {
  return (props.code || '').split('\n')
})

const langLabel = computed(() => {
  const map = {
    python: 'Python 3.11',
    javascript: 'JavaScript',
    bash: 'Bash',
    shell: 'Shell',
    html: 'HTML',
    css: 'CSS',
    json: 'JSON',
    yaml: 'YAML',
    sql: 'SQL',
    text: 'Text',
  }
  return map[props.language] || props.language.toUpperCase()
})

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = props.code
    ta.style.position = 'fixed'; ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}
</script>

<template>
  <div class="code-block" data-code-theme="light">
    <div class="cb-toolbar">
      <div class="cb-toolbar-left">
        <span class="cb-filename">{{ filename }}</span>
        <span class="cb-lang">{{ langLabel }}</span>
      </div>
      <button class="cb-copy" @click="handleCopy" :class="{ copied: copied }">
        <svg v-if="!copied" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="5.5" y="5.5" width="8" height="9" rx="1" />
          <path d="M2.5 10.5V2.5h8" />
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 8l3.5 3.5L13 5" />
        </svg>
        <span>{{ copied ? '已复制' : '复制' }}</span>
      </button>
    </div>

    <div class="cb-body">
      <div class="cb-gutter" aria-hidden="true">
        <span v-for="(_, i) in lines" :key="i" class="cb-ln">{{ i + 1 }}</span>
      </div>
      <pre class="cb-code"><code>{{ code }}</code></pre>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid var(--border);
  border-left: 3px solid var(--primary);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface);
  margin: 20px 0;
  max-width: 100%;
  box-shadow: var(--shadow-xs);
}

.cb-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  background: var(--surface-sunken);
  border-bottom: 1px solid var(--border);
}

.cb-toolbar-left {
  display: flex; align-items: center; gap: 10px;
}

.cb-filename {
  font-size: 11px; font-weight: 500;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.cb-lang {
  font-size: 11px; font-weight: 600;
  color: var(--primary);
  text-transform: uppercase; letter-spacing: 0.05em;
  font-family: var(--font-mono);
}

.cb-copy {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 11px; font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}
.cb-copy:hover {
  background: var(--primary-light);
  border-color: var(--primary-soft);
  color: var(--primary);
}
.cb-copy.copied {
  color: var(--success);
  border-color: rgba(18, 168, 100, 0.3);
  background: var(--success-light);
}

.cb-body {
  display: flex;
  overflow-x: auto;
}

.cb-gutter {
  display: flex; flex-direction: column;
  width: 44px; flex-shrink: 0;
  padding: 16px 12px;
  text-align: right;
  color: var(--text-tertiary);
  user-select: none;
  border-right: 1px solid var(--border);
  background: var(--surface-sunken);
  font-family: 'JetBrains Mono', var(--font-mono);
  font-size: 13px; line-height: 1.7;
}
.cb-ln { display: block; }

.cb-code {
  flex: 1; margin: 0;
  padding: 16px 20px;
  font-family: 'JetBrains Mono', var(--font-mono);
  font-size: 13px; line-height: 1.7;
  color: var(--ink);
  white-space: pre;
  overflow-x: auto;
  tab-size: 4;
  background: transparent;
  border: none; border-radius: 0;
}
.cb-code code {
  font-family: inherit; font-size: inherit;
  color: inherit; background: none; padding: 0;
  border: none;
}
</style>
