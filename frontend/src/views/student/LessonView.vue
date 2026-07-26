<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { sanitizeHtml } from '../../utils/sanitize.js'
import { marked } from 'marked'
import CodeBlock from '../../components/common/CodeBlock.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const chapters = ref([])
const course = ref(null)
const lesson = ref(null)
const loading = ref(true)
const dropdownOpen = ref(false)

const courseId = computed(() => route.params.id)
const lessonId = computed(() => route.params.lid)

// 扁平的课时导航数组 [{ lesson, chapterTitle, chapterIndex }]
const flatLessons = computed(() => {
  const result = []
  for (let i = 0; i < chapters.value.length; i++) {
    const ch = chapters.value[i]
    if (ch.lessons) {
      for (const l of ch.lessons) {
        result.push({ lesson: l, chapterTitle: ch.title, chapterIndex: i })
      }
    }
  }
  return result
})

const currentIndex = computed(() => {
  return flatLessons.value.findIndex(f => String(f.lesson.id) === String(lessonId.value))
})

const prevLesson = computed(() => {
  if (currentIndex.value <= 0) return null
  return flatLessons.value[currentIndex.value - 1]
})

const nextLesson = computed(() => {
  if (currentIndex.value >= flatLessons.value.length - 1) return null
  return flatLessons.value[currentIndex.value + 1]
})

const currentChapterTitle = computed(() => {
  if (currentIndex.value < 0) return ''
  return flatLessons.value[currentIndex.value]?.chapterTitle || ''
})

function findLesson() {
  for (let i = 0; i < chapters.value.length; i++) {
    const ch = chapters.value[i]
    if (ch.lessons) {
      const found = ch.lessons.find(l => String(l.id) === String(lessonId.value))
      if (found) {
        lesson.value = found
        // notebook 类型自动跳转到 NotebookView
        if (found.content_type === 'notebook') {
          router.replace(`/student/courses/${courseId.value}/notebook/${found.id}`)
        }
        return
      }
    }
  }
  lesson.value = null
}

function markComplete() {
  if (!lesson.value) return
  try {
    const key = `course_${courseId.value}_completed`
    const raw = localStorage.getItem(key)
    const ids = raw ? JSON.parse(raw) : []
    if (!ids.includes(lesson.value.id)) {
      ids.push(lesson.value.id)
      localStorage.setItem(key, JSON.stringify(ids))
    }
  } catch { /* ignore */ }
}

async function fetchData() {
  loading.value = true
  try {
    const [chRes, cRes] = await Promise.all([
      coursesAPI.getChapters(courseId.value),
      coursesAPI.get(courseId.value),
    ])
    const raw = chRes.data
    chapters.value = Array.isArray(raw) ? raw : (raw.items || [])
    course.value = cRes.data
    findLesson()
    if (lesson.value) markComplete()
  } catch {
    app.showToast('加载课时失败', 'error')
  } finally { loading.value = false }
}

function goLesson(lessonId) {
  dropdownOpen.value = false
  router.push(`/student/courses/${courseId.value}/lessons/${lessonId}`)
}

function goPrev() {
  if (prevLesson.value) goLesson(prevLesson.value.lesson.id)
}

function goNext() {
  if (nextLesson.value) goLesson(nextLesson.value.lesson.id)
}

function goCourse() {
  router.push(`/student/courses/${courseId.value}`)
}

// ── 内容分段：将 markdown 拆分为文字块和代码块 ──────────────────────

const contentBlocks = computed(() => {
  const src = lesson.value?.content || ''
  if (!src.trim()) return [{ type: 'markdown', content: src }]

  const blocks = []
  // 按 ``` 代码围栏拆分
  const parts = src.split(/(```[\s\S]*?```)/g)
  let headingIndex = 0

  for (const part of parts) {
    if (part.startsWith('```')) {
      const lines = part.split('\n')
      const langLine = lines[0].replace(/```/g, '').trim()
      const language = langLine || 'python'
      // 去掉首尾行（``` 标记行）
      const code = lines.slice(1, -1).join('\n')
      blocks.push({ type: 'code', code, language })
    } else if (part.trim()) {
      const html = marked.parse(part, { async: false })
      const safe = sanitizeHtml(typeof html === 'string' ? html : '')
      // 给 h2/h3 生成 id 以便 TOC 定位
      const withIds = addHeadingIds(safe, headingIndex)
      headingIndex += (safe.match(/<h[23]/g) || []).length
      blocks.push({ type: 'markdown', html: withIds })
    }
  }
  return blocks
})

function addHeadingIds(html, startIndex) {
  let idx = startIndex
  return html.replace(/<(h[23])>/g, (_, tag) => {
    return `<${tag} id="section-${idx++}">`
  })
}

// ── TOC 目录 + 滚动监听 ───────────────────────────────────────────

const tocItems = ref([])
const activeTocId = ref('')
let tocObserver = null

function extractTOC() {
  const items = []
  const containers = document.querySelectorAll('.lesson-content')
  containers.forEach(container => {
    const headings = container.querySelectorAll('h2, h3')
    headings.forEach(h => {
      const id = h.getAttribute('id') || h.textContent?.replace(/\s+/g, '-').toLowerCase()
      if (!h.id) h.id = id
      items.push({
        id,
        text: h.textContent?.trim() || '',
        level: h.tagName === 'H2' ? 2 : 3,
      })
    })
  })
  tocItems.value = items
  // 重建 IntersectionObserver
  setupTocObserver()
}

function setupTocObserver() {
  if (tocObserver) tocObserver.disconnect()
  const headingEls = document.querySelectorAll('.lesson-content h2[id], .lesson-content h3[id]')
  if (headingEls.length === 0) return
  tocObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeTocId.value = entry.target.id
        }
      }
    },
    { rootMargin: '-80px 0px -60% 0px' }
  )
  headingEls.forEach(el => tocObserver.observe(el))
}

function scrollToHeading(id) {
  activeTocId.value = id
  const el = document.getElementById(id)
  if (el) {
    const topbar = document.querySelector('.lesson-topbar')
    const offset = (topbar?.offsetHeight || 48) + 12
    const top = el.getBoundingClientRect().top + window.pageYOffset - offset
    window.scrollTo({ top, behavior: 'smooth' })
  }
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

// 点击外部关闭下拉
function onDocClick(e) {
  const el = document.getElementById('chapter-dropdown')
  if (el && !el.contains(e.target)) dropdownOpen.value = false
}

onMounted(async () => {
  await fetchData()
  document.addEventListener('click', onDocClick)
})

// TOC 在 DOM 更新后提取
onMounted(() => {
  nextTick(() => {
    setTimeout(extractTOC, 200)
  })
})

// 监听内容变化重新提取 TOC
watch(() => lesson.value?.content, () => {
  nextTick(() => {
    setTimeout(extractTOC, 300)
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})

// 路由参数变化时重新查找
watch([lessonId, courseId], async ([newLid, newCid], [oldLid, oldCid]) => {
  if (newCid !== oldCid || chapters.value.length === 0) {
    await fetchData()
  } else {
    findLesson()
    if (lesson.value) markComplete()
  }
})
</script>

<template>
  <AppLayout>
    <!-- Loading -->
    <div v-if="loading" class="lesson-loading">
      <div class="skeleton" style="height:22px;width:360px;margin-bottom:16px"></div>
      <div class="skeleton" style="height:14px;width:100%;margin-bottom:8px" v-for="i in 8" :key="i"></div>
    </div>

    <!-- Not found -->
    <div v-else-if="!lesson" class="empty-state">
      <p>课时不存在</p>
      <button class="btn-primary" @click="goCourse" style="margin-top:12px">返回课程</button>
    </div>

    <!-- Lesson content -->
    <div v-else class="lesson-layout">
      <!-- ── Sticky Top Nav Bar ────────────────────────────────────────── -->
      <div class="lesson-topbar">
        <div class="topbar-inner">
          <button class="topbar-back" @click="goCourse">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3L5 8l5 5"/></svg>
            返回课程
          </button>
          <div class="topbar-breadcrumb">
            <template v-if="currentChapterTitle">
              <span class="topbar-crumb">{{ currentChapterTitle }}</span>
              <span class="topbar-sep">›</span>
            </template>
            <span class="topbar-crumb current">{{ lesson.title }}</span>
          </div>

          <!-- Chapter dropdown -->
          <div class="dropdown-wrap" id="chapter-dropdown">
            <button class="btn-ghost btn-sm dropdown-trigger" @click.stop="toggleDropdown">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="2" y="2" width="10" height="10" rx="1"/><path d="M5 6h4M5 9h2"/></svg>
              快速跳转
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 3.5l3 3 3-3"/></svg>
            </button>
            <transition name="dropdown-fade">
              <div v-if="dropdownOpen" class="dropdown-menu">
                <div v-for="ch in chapters" :key="ch.id" class="dropdown-group">
                  <div class="dropdown-chapter">第{{ ch.order_index + 1 }}章  {{ ch.title }}</div>
                  <div
                    v-for="l in ch.lessons" :key="l.id"
                    class="dropdown-item"
                    :class="{ active: l.id === lesson.id }"
                    @click.stop="goLesson(l.id)"
                  >
                    <span class="dropdown-item-icon">
                      <template v-if="l.content_type === 'markdown'">📖</template>
                      <template v-else-if="l.content_type === 'video'">🎥</template>
                      <template v-else>📓</template>
                    </span>
                    {{ l.title }}
                  </div>
                </div>
              </div>
            </transition>
          </div>
        </div>
      </div>

      <!-- ── Body row: 正文 + TOC 双栏 ────────────────────────────────── -->
      <div class="lesson-row">
        <!-- 正文列 -->
        <div class="lesson-body">
          <!-- Meta info -->
          <div class="lesson-meta-row">
            <span class="meta-tag">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="7"/><path d="M8 4v4l3 2"/></svg>
              预计 12 分钟
            </span>
            <span class="meta-dot">·</span>
            <span class="meta-tag">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
              4 个知识点
            </span>
            <span class="meta-dot">·</span>
            <span class="meta-tag">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="2" width="12" height="12" rx="2"/><path d="M5.5 6.5l2 2 3-4"/></svg>
              2 个练习
            </span>
          </div>

          <!-- Content blocks -->
          <template v-if="lesson.content_type === 'markdown'">
            <template v-for="(block, bi) in contentBlocks" :key="bi">
              <div v-if="block.type === 'markdown'" class="lesson-content" v-html="block.html"></div>
              <CodeBlock v-else :code="block.code" :language="block.language" :filename="'example.' + (block.language === 'python' ? 'py' : block.language)" />
            </template>
          </template>

          <div v-else-if="lesson.content_type === 'video'" class="lesson-video">
            <div v-if="lesson.video_url" class="video-wrapper">
              <div class="video-placeholder">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3"><circle cx="24" cy="24" r="20"/><path d="M20 16v16l12-8z"/></svg>
                <p class="text-sm text-secondary" style="margin-top:12px">视频课时：{{ lesson.title }}</p>
                <a :href="lesson.video_url" target="_blank" class="btn-primary" style="margin-top:12px;display:inline-flex;align-items:center;gap:6px">打开视频</a>
              </div>
            </div>
            <div v-else class="empty-state"><p>视频暂不可用</p></div>
          </div>

          <div v-else class="lesson-notebook">
            <p>Notebook 课时：{{ lesson.title }}</p>
          </div>

          <!-- Bottom nav -->
          <hr class="lesson-divider" />
          <div class="lesson-nav">
            <button v-if="prevLesson" class="nav-btn nav-prev" @click="goPrev" :title="prevLesson.lesson.title">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 3L4 7l5 5"/></svg>
              <span class="nav-label">上一课</span>
              <span class="nav-title">{{ prevLesson.lesson.title }}</span>
            </button>
            <div v-else class="nav-btn nav-prev disabled">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 3L4 7l5 5"/></svg>
              <span class="nav-label">上一课</span>
            </div>

            <button v-if="nextLesson" class="nav-btn nav-next" @click="goNext" :title="nextLesson.lesson.title">
              <span class="nav-title">{{ nextLesson.lesson.title }}</span>
              <span class="nav-label">下一课</span>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M5 3l5 4-5 5"/></svg>
            </button>
            <div v-else class="nav-btn nav-next disabled">
              <span class="nav-label">下一课</span>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M5 3l5 4-5 5"/></svg>
            </div>
          </div>
        </div>

        <!-- TOC 目录列 -->
        <aside class="lesson-toc">
          <h4 class="toc-title">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="3" cy="3" r="1.5"/><circle cx="3" cy="8" r="1.5"/><circle cx="3" cy="13" r="1.5"/><path d="M7 3h7M7 8h7M7 13h7"/></svg>
            目录
          </h4>
          <nav class="toc-nav">
            <a
              v-for="item in tocItems" :key="item.id"
              :href="'#' + item.id"
              class="toc-link"
              :class="{ 'toc-sub': item.level === 3, 'toc-active': item.id === activeTocId }"
              @click.prevent="scrollToHeading(item.id)"
            >{{ item.text }}</a>
          </nav>
          <p v-if="tocItems.length === 0" class="toc-empty">暂无目录</p>
        </aside>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Lesson View — 分段渲染 + TOC + 阅读排版
   CodeBlock 组件替代 :deep(pre) 代码块样式
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Layout ─────────────────────────────────────────────────────────── */
.lesson-layout { }
.lesson-loading { padding: var(--space-4) 0; }

/* ── Sticky Top Bar（全宽，跨 flex 行上方） ──────────────────────────── */
.lesson-topbar {
  position: sticky; top: 0; z-index: 30;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  margin: -32px -40px 0;
  padding: 0 40px;
}
.topbar-inner {
  display: flex; align-items: center; gap: 16px;
  height: 48px; max-width: 1080px; margin: 0 auto;
}

/* ── Body row：正文 + TOC 双栏 ────────────────────────────────────── */
.lesson-row {
  display: flex; justify-content: center; gap: 48px;
  max-width: 1080px; margin: 0 auto;
  padding-top: 4px;
}

/* 正文列 */
.lesson-body {
  flex: 1; min-width: 0; max-width: 780px;
}

/* TOC 目录列 */
.lesson-toc {
  width: 200px; flex-shrink: 0;
  position: sticky; top: 68px; align-self: flex-start;
  max-height: calc(100vh - 100px); overflow-y: auto;
  padding: 8px 0 32px;
}
@media (max-width: 1100px) {
  .lesson-row { gap: 24px; }
  .lesson-toc { width: 160px; }
}
@media (max-width: 900px) {
  .lesson-toc { display: none; }
  .lesson-body { max-width: 100%; }
  .topbar-inner { max-width: 100%; }
}
.topbar-back {
  display: inline-flex; align-items: center; gap: 4px;
  background: none; border: none; padding: 4px 8px;
  color: var(--text-secondary); font-size: var(--text-sm); font-weight: 500;
  cursor: pointer; border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out);
  white-space: nowrap; flex-shrink: 0;
}
.topbar-back:hover { color: var(--primary); }
.topbar-breadcrumb {
  display: flex; align-items: center; gap: 6px;
  min-width: 0; flex: 1;
}
.topbar-crumb {
  font-size: var(--text-sm); color: var(--text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.topbar-crumb.current { color: var(--ink); font-weight: 500; }
.topbar-sep { color: var(--text-tertiary); font-size: var(--text-sm); }

/* ── Dropdown ──────────────────────────────────────────────────────── */
.dropdown-wrap { position: relative; flex-shrink: 0; }
.dropdown-trigger {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--text-xs); white-space: nowrap;
}
.dropdown-menu {
  position: absolute; right: 0; top: 100%; z-index: 50;
  margin-top: 4px; min-width: 280px; max-height: 420px; overflow-y: auto;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
  padding: var(--space-2);
}
.dropdown-group { margin-bottom: var(--space-1); }
.dropdown-chapter {
  font-size: var(--text-xs); font-weight: 600; color: var(--text-secondary);
  padding: 6px 10px 4px; text-transform: uppercase; letter-spacing: 0.04em;
}
.dropdown-item {
  display: flex; align-items: center; gap: var(--space-2);
  padding: 7px 10px; border-radius: var(--radius-md);
  font-size: var(--text-sm); color: var(--text); cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.dropdown-item:hover { background: var(--surface-raised); }
.dropdown-item.active { background: var(--primary-light); color: var(--primary); font-weight: 500; }
.dropdown-item-icon { font-size: 12px; flex-shrink: 0; }

.dropdown-fade-enter-active,
.dropdown-fade-leave-active { transition: all var(--duration-fast) var(--ease-out); }
.dropdown-fade-enter-from,
.dropdown-fade-leave-to { opacity: 0; transform: translateY(-4px); }

/* ── Meta Info Row ──────────────────────────────────────────────────── */
.lesson-meta-row {
  display: flex; align-items: center; gap: 8px;
  padding: 20px 0 12px;
}
.meta-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--text-xs); font-weight: 500;
  color: var(--primary); background: var(--primary-light);
  padding: 4px 10px; border-radius: var(--radius-full);
}
.meta-dot { color: var(--text-tertiary); font-size: var(--text-xs); }

/* ── Markdown Content Block ─────────────────────────────────────────── */
.lesson-content {
  max-width: 780px; margin: 0 auto;
  font-size: 16px; line-height: 1.85; color: #1E293B;
}

.lesson-content :deep(h1) {
  font-family: var(--font-display);
  font-size: 32px; font-weight: 700;
  color: var(--ink); margin: 0 0 20px;
  letter-spacing: -0.025em; line-height: 1.2;
}

.lesson-content :deep(h2) {
  font-family: var(--font-display);
  font-size: 24px; font-weight: 600;
  color: var(--ink); margin: 36px 0 12px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  letter-spacing: -0.02em; line-height: 1.3;
}
.lesson-content :deep(h2:first-of-type) {
  border-top: none; padding-top: 0; margin-top: 8px;
}

.lesson-content :deep(h3) {
  font-size: 19px; font-weight: 600;
  color: var(--ink); margin: 24px 0 8px;
  line-height: 1.4;
}

.lesson-content :deep(p) {
  margin: 12px 0; color: #1E293B; font-size: 16px; line-height: 1.85;
}

.lesson-content :deep(a) {
  color: var(--primary); text-decoration: none;
}
.lesson-content :deep(a:hover) { color: var(--primary-dark); text-decoration: underline; }

.lesson-content :deep(code:not(pre code)) {
  font-family: var(--font-mono); font-size: 0.88em;
  background: var(--surface-raised); color: var(--primary);
  padding: 2px 6px; border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.lesson-content :deep(table) {
  width: 100%; border-collapse: collapse; margin: 16px 0;
  font-size: var(--text-sm);
}
.lesson-content :deep(th) {
  text-align: left; padding: 10px 14px; border-bottom: 2px solid var(--border);
  font-size: var(--text-xs); font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-secondary); background: var(--surface-raised);
}
.lesson-content :deep(td) {
  padding: 10px 14px; border-bottom: 1px solid var(--border); color: #1E293B;
}

.lesson-content :deep(blockquote) {
  background: var(--warning-light); border-left: 3px solid var(--warning);
  padding: var(--space-3) var(--space-4); margin: 16px 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 15px; color: #7C5E0A; line-height: 1.75;
}
.lesson-content :deep(blockquote p) { margin: 4px 0; color: inherit; }

.lesson-content :deep(img) {
  max-width: 100%; border-radius: var(--radius-md); margin: var(--space-3) 0;
}

.lesson-content :deep(ul), .lesson-content :deep(ol) {
  margin: 10px 0; padding-left: var(--space-6);
  font-size: 16px; color: #1E293B; line-height: 1.85;
}
.lesson-content :deep(li) { margin: 4px 0; }

.lesson-content :deep(strong) { color: var(--ink); font-weight: 600; }

/* ── Video / Notebook ──────────────────────────────────────────────── */
.lesson-video { margin: var(--space-6) 0; }
.video-wrapper {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); overflow: hidden;
}
.video-placeholder {
  text-align: center; padding: var(--space-12) var(--space-6);
  display: flex; flex-direction: column; align-items: center;
}
.lesson-notebook { max-width: 780px; margin: var(--space-6) auto; }

/* ── Divider ────────────────────────────────────────────────────────── */
.lesson-divider {
  border: none; border-top: 1px solid var(--border);
  margin: 40px 0 28px;
}

/* ── Bottom Navigation ──────────────────────────────────────────────── */
.lesson-nav {
  display: flex; justify-content: space-between; align-items: stretch;
  gap: var(--space-4); margin-bottom: 40px;
}
.nav-btn {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-4); border: 1px solid var(--border);
  border-radius: var(--radius-md); background: var(--surface);
  cursor: pointer; transition: all var(--duration-fast) var(--ease-out);
  flex: 1; max-width: 48%; color: var(--text); text-align: left;
}
.nav-btn:hover {
  border-color: var(--border-strong); background: var(--surface-raised);
  box-shadow: var(--shadow-md);
}
.nav-btn.disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; }
.nav-prev { justify-content: flex-start; }
.nav-next { justify-content: flex-end; }
.nav-label {
  font-size: var(--text-xs); color: var(--text-secondary);
  font-weight: 500; white-space: nowrap;
}
.nav-title {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--text); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}

/* ═══════════════════════════════════════════════════════════════════════
   TOC — flex 列内 sticky 目录，带层级缩进 + 当前位置激活态
   ═══════════════════════════════════════════════════════════════════════ */
.toc-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600;
  color: var(--text-tertiary); text-transform: uppercase;
  letter-spacing: 0.06em; margin: 0 0 12px;
}
.toc-nav {
  display: flex; flex-direction: column; gap: 1px;
  border-left: 1px solid var(--border);
}
.toc-empty {
  font-size: var(--text-xs); color: var(--text-tertiary); margin: 0;
}
.toc-link {
  display: block; padding: 5px 12px;
  font-size: 12px; color: var(--text-secondary);
  text-decoration: none; border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  transition: all var(--duration-fast) var(--ease-out);
  line-height: 1.45; position: relative;
  border-left: 2px solid transparent; margin-left: -1px;
}
.toc-link:hover {
  color: var(--primary); background: var(--primary-light);
}
.toc-link.toc-sub {
  padding-left: 22px; font-size: 11px;
}
.toc-link.toc-active {
  color: var(--primary); font-weight: 500;
  border-left-color: var(--primary);
  background: var(--primary-light);
}

/* ── Empty state ────────────────────────────────────────────────────── */
.empty-state {
  text-align: center; padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state p { font-size: var(--text-sm); margin-bottom: var(--space-3); }

/* ── Responsive ─────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .lesson-topbar {
    margin: -20px -16px 0; padding: 0 16px;
  }
  .lesson-content { font-size: 15px; }
  .lesson-content :deep(h1) { font-size: 26px; }
  .lesson-content :deep(h2) { font-size: 20px; }
  .lesson-content :deep(h3) { font-size: 17px; }
  .lesson-nav { flex-direction: column; }
  .nav-btn { max-width: 100%; }
  .nav-title { display: none; }
  .dropdown-menu { left: 0; right: auto; min-width: auto; width: 100%; }
}
</style>
