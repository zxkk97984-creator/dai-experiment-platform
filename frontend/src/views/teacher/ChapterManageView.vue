<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import AppLayout from '../../components/layout/AppLayout.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { coursesAPI } from '../../api/courses.js'
import { studioAPI } from '../../api/studio.js'
import { useAppStore } from '../../stores/app.js'
import { sanitizeHtml } from '../../utils/sanitize.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

// ── 后端 API 能力边界 ─────────────────────────────────────────────────
// 只为已接通的 API 渲染真实操作。排序接口尚未实现 → 不显示拖拽手柄。
const API_CAPS = {
  chapterCopy: true, // 复制章节 = 新建章节 + 逐课时复制（POST /chapters + /chapters/:id/lessons）
  chapterEdit: true, // PATCH /chapters/:id
  chapterDelete: true, // DELETE /chapters/:id
  chapterMove: true, // 上移 / 下移 = 批量重排 order_index（PATCH /chapters/:id）
  lessonCopy: true, // 复制课时（POST /chapters/:id/lessons）
  lessonMove: true, // 移动到其他章节（PATCH /lessons/:id 传 chapter_id）
  lessonPublish: true, // 发布 / 设为草稿（PATCH /lessons/:id 传 status）
  lessonDelete: true, // DELETE /lessons/:id
  dragSort: false, // 无排序接口 → 不显示拖拽手柄
}

const CONTENT_TYPES = [
  { type: 'markdown', label: '讲义', desc: '创建文字与代码讲解内容' },
  { type: 'notebook', label: 'Notebook 实验', desc: '创建可运行的交互式实验' },
  { type: 'experiment', label: '普通实验', desc: '创建实验任务和提交要求' },
  { type: 'video', label: '视频', desc: '添加视频课程' },
]

const course = ref(null)
const chapters = ref([])
const loading = ref(true)

const expanded = ref({})
const openMenu = ref(null) // 'chapter:{id}' | 'lesson:{id}'
const showChapterForm = ref(false)
const chapterTitle = ref('')

const contentPicker = ref(null) // chapterId：选择添加课时内容类型
const lessonForm = ref(null) // { chapterId, type, title, content, video_url }

const editingLesson = ref(null)
const editForm = ref({ title: '', content: '', video_url: '' })
const savingEdit = ref(false)

// 编辑章节标题（抽屉）
const editingChapter = ref(null)
const chapterEditTitle = ref('')
const savingChapterEdit = ref(false)

// 课时移动到其他章节（弹窗）
const movingLesson = ref(null) // { id, title, targetId, targetTitle }
const moveTargetChapterId = ref(null)
const savingMove = ref(false)

// 删除确认：{ kind: 'chapter' | 'lesson', title, lessonCount? }
const deleteTarget = ref(null)
const deleting = ref(false)

const previewLesson = ref(null)
const previewHtml = ref('')

const settingsOpen = ref(false)
const savingSettings = ref(false)
const settings = ref({})

const courseId = computed(() => route.params.courseId || route.params.id)
const lessons = computed(() => chapters.value.flatMap((chapter) => chapter.lessons || []))

const courseStatusLabel = computed(
  () => ({ published: '已发布', draft: '草稿', archived: '已归档' })[course.value?.status] || '待发布',
)
const stats = computed(() => [
  { value: chapters.value.length, label: '章节' },
  { value: lessons.value.length, label: '课时' },
  { value: lessons.value.filter((lesson) => lesson.content_type === 'notebook').length, label: '实验 Notebook' },
  { value: courseStatusLabel.value, label: '课程状态' },
])

async function loadPage() {
  loading.value = true
  try {
    const [courseResponse, chapterResponse] = await Promise.all([
      coursesAPI.get(courseId.value),
      coursesAPI.getChapters(courseId.value),
    ])
    course.value = courseResponse.data
    const raw = chapterResponse.data
    chapters.value = Array.isArray(raw) ? raw : (raw.items || [])
    settings.value = {
      title: course.value.title || '',
      description: course.value.description || '',
      status: course.value.status || 'draft',
    }
    restoreExpandedState()
  } catch {
    app.showToast('课程内容加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function restoreExpandedState() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(`teacher-course-${courseId.value}-chapters`) || '{}')
    expanded.value = Object.fromEntries(chapters.value.map((chapter) => [chapter.id, saved[chapter.id] !== false]))
  } catch {
    expanded.value = Object.fromEntries(chapters.value.map((chapter) => [chapter.id, true]))
  }
}

function toggleChapter(chapterId) {
  expanded.value[chapterId] = !expanded.value[chapterId]
  sessionStorage.setItem(`teacher-course-${courseId.value}-chapters`, JSON.stringify(expanded.value))
}

function toggleMenu(key) {
  openMenu.value = openMenu.value === key ? null : key
}

function closeMenus() {
  openMenu.value = null
}

function onDocumentClick(event) {
  if (openMenu.value && !event.target.closest('[data-menu]')) openMenu.value = null
}

function onKeydown(event) {
  if (event.key !== 'Escape') return
  openMenu.value = null
  contentPicker.value = null
  lessonForm.value = null
  previewLesson.value = null
  editingLesson.value = null
  editingChapter.value = null
  movingLesson.value = null
  deleteTarget.value = null
  settingsOpen.value = false
}

// ── 展示辅助 ──────────────────────────────────────────────────────────
function isPublished(lesson) {
  return lesson.status === 'published' || lesson.published === true
}

function chapterLessons(chapter) {
  return chapter.lessons || []
}

function statusLabel(lesson) {
  if (isPublished(lesson)) return '已发布'
  if (lesson.status === 'pending') return '待发布'
  return '草稿'
}

function statusClass(lesson) {
  if (isPublished(lesson)) return 'published'
  if (lesson.status === 'pending') return 'pending'
  return 'draft'
}

function typeLabel(type) {
  return { markdown: '讲义', notebook: 'Notebook', experiment: '实验', video: '视频' }[type] || '讲义'
}

function durationLabel(lesson) {
  if (!lesson.duration && !lesson.duration_minutes) return '未设置'
  return `约 ${lesson.duration_minutes || lesson.duration} 分钟`
}

function chapterSummary(chapter) {
  const list = chapter.lessons || []
  const parts = [`${list.length} 个课时`]
  const lectures = list.filter((l) => l.content_type === 'markdown').length
  const labs = list.filter((l) => l.content_type === 'notebook' || l.content_type === 'experiment').length
  const videos = list.filter((l) => l.content_type === 'video').length
  if (lectures) parts.push(`${lectures} 个讲义`)
  if (labs) parts.push(`${labs} 个实验`)
  if (videos) parts.push(`${videos} 个视频`)
  return parts.join(' · ')
}

function renderMarkdown(src) {
  const raw = marked.parse(src || '', { async: false })
  return sanitizeHtml(typeof raw === 'string' ? raw : '')
}

// ── 章节 ──────────────────────────────────────────────────────────────
async function createChapter() {
  if (!chapterTitle.value.trim()) return
  try {
    await coursesAPI.createChapter(courseId.value, { title: chapterTitle.value.trim(), order_index: chapters.value.length })
    chapterTitle.value = ''
    showChapterForm.value = false
    await loadPage()
    app.showToast('章节已创建', 'success')
  } catch {
    app.showToast('创建章节失败', 'error')
  }
}

async function copyChapter(chapter) {
  closeMenus()
  try {
    const response = await coursesAPI.createChapter(courseId.value, {
      title: `${chapter.title}（副本）`,
      order_index: chapters.value.length,
    })
    for (const lesson of chapter.lessons || []) {
      await coursesAPI.createLesson(response.data.id, {
        title: lesson.title,
        content_type: lesson.content_type,
        content: lesson.content || undefined,
        notebook_path: lesson.notebook_path || undefined,
        video_url: lesson.video_url || undefined,
        order_index: lesson.order_index || 0,
      })
    }
    await loadPage()
    app.showToast('章节已复制', 'success')
  } catch {
    app.showToast('复制章节失败', 'error')
  }
}

// ── 添加课时（先选类型，再进入对应创建表单） ─────────────────────────
function openAddLesson(chapterId) {
  contentPicker.value = chapterId
  lessonForm.value = null
  closeMenus()
}

function chooseContent(chapterId, type) {
  contentPicker.value = null
  lessonForm.value = { chapterId, type, title: '', content: '', video_url: '' }
}

async function createLesson() {
  if (!lessonForm.value?.title.trim()) return
  const form = lessonForm.value
  try {
    const payload = {
      title: form.title.trim(),
      content_type: form.type === 'experiment' ? 'experiment' : form.type,
      content: form.content || undefined,
      order_index: 0,
    }
    if (form.type === 'video') payload.video_url = form.video_url || undefined
    const response = await coursesAPI.createLesson(form.chapterId, payload)
    if (form.type === 'notebook') {
      const template = await studioAPI.createTemplate({ name: form.title.trim(), lesson_id: response.data.id })
      router.push(`/teacher/courses/${courseId.value}/studio/${template.data.id}`)
      return
    }
    lessonForm.value = null
    expanded.value[form.chapterId] = true
    await loadPage()
    app.showToast('课时已创建', 'success')
  } catch {
    app.showToast('创建课时失败', 'error')
  }
}

// ── 课时操作 ──────────────────────────────────────────────────────────
function openEditLesson(lesson) {
  closeMenus()
  if (lesson.content_type === 'notebook' && lesson.template_id) {
    router.push(`/teacher/courses/${courseId.value}/studio/${lesson.template_id}`)
    return
  }
  editingLesson.value = lesson
  editForm.value = {
    title: lesson.title || '',
    content: lesson.content || '',
    video_url: lesson.video_url || '',
  }
}

async function saveEditLesson() {
  if (!editingLesson.value || !editForm.value.title.trim()) return
  savingEdit.value = true
  try {
    const payload = { title: editForm.value.title.trim() }
    if (editingLesson.value.content_type === 'video') {
      payload.video_url = editForm.value.video_url || null
    } else {
      payload.content = editForm.value.content
    }
    await coursesAPI.updateLesson(editingLesson.value.id, payload)
    editingLesson.value = null
    await loadPage()
    app.showToast('课时已保存', 'success')
  } catch {
    app.showToast('保存课时失败', 'error')
  } finally {
    savingEdit.value = false
  }
}

function openPreview(lesson) {
  closeMenus()
  previewLesson.value = lesson
  previewHtml.value = lesson.content_type === 'video' ? '' : renderMarkdown(lesson.content)
}

function openStudioForPreview(lesson) {
  if (lesson.template_id) {
    router.push(`/teacher/courses/${courseId.value}/studio/${lesson.template_id}`)
  }
}

async function copyLesson(lesson) {
  closeMenus()
  try {
    await coursesAPI.createLesson(lesson.chapter_id, {
      title: `${lesson.title}（副本）`,
      content_type: lesson.content_type,
      content: lesson.content || undefined,
      notebook_path: lesson.notebook_path || undefined,
      video_url: lesson.video_url || undefined,
      order_index: (lesson.order_index || 0) + 1,
    })
    await loadPage()
    app.showToast('课时已复制', 'success')
  } catch {
    app.showToast('复制课时失败', 'error')
  }
}

// ── 删除（章节 / 课时） ──────────────────────────────────────────────
function askDeleteChapter(chapter) {
  closeMenus()
  deleteTarget.value = {
    kind: 'chapter',
    id: chapter.id,
    title: chapter.title,
    lessonCount: chapterLessons(chapter).length,
  }
}

function askDeleteLesson(lesson) {
  closeMenus()
  deleteTarget.value = { kind: 'lesson', id: lesson.id, title: lesson.title }
}

async function confirmDelete() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  const kind = deleteTarget.value.kind
  try {
    if (kind === 'chapter') {
      await coursesAPI.deleteChapter(deleteTarget.value.id)
    } else {
      await coursesAPI.deleteLesson(deleteTarget.value.id)
    }
    deleteTarget.value = null
    await loadPage()
    app.showToast(kind === 'chapter' ? '章节已删除' : '课时已删除', 'success')
  } catch {
    app.showToast('删除失败', 'error')
  } finally {
    deleting.value = false
  }
}

// ── 编辑章节 ─────────────────────────────────────────────────────────
function openEditChapter(chapter) {
  closeMenus()
  editingChapter.value = chapter
  chapterEditTitle.value = chapter.title || ''
}

async function saveEditChapter() {
  if (!editingChapter.value || !chapterEditTitle.value.trim()) return
  savingChapterEdit.value = true
  try {
    await coursesAPI.updateChapter(editingChapter.value.id, { title: chapterEditTitle.value.trim() })
    editingChapter.value = null
    await loadPage()
    app.showToast('章节已保存', 'success')
  } catch {
    app.showToast('保存章节失败', 'error')
  } finally {
    savingChapterEdit.value = false
  }
}

// ── 移动章节（上移 / 下移）：重排全部章节的 order_index ──────────────
async function moveChapter(chapter, direction) {
  closeMenus()
  const list = [...chapters.value]
  const index = list.findIndex((item) => item.id === chapter.id)
  const targetIndex = index + direction
  if (index < 0 || targetIndex < 0 || targetIndex >= list.length) return
  const [moved] = list.splice(index, 1)
  list.splice(targetIndex, 0, moved)
  try {
    await Promise.all(
      list.map((item, position) => coursesAPI.updateChapter(item.id, { order_index: position })),
    )
    await loadPage()
  } catch {
    app.showToast('移动章节失败', 'error')
  }
}

// ── 取消发布章节：章节内全部课时设为草稿 ─────────────────────────────
async function unpublishChapter(chapter) {
  closeMenus()
  const pending = chapterLessons(chapter)
  if (!pending.length) return
  try {
    await Promise.all(pending.map((lesson) => coursesAPI.updateLesson(lesson.id, { status: 'draft' })))
    await loadPage()
    app.showToast('章节已取消发布', 'success')
  } catch {
    app.showToast('取消发布失败', 'error')
  }
}

// ── 课时发布状态切换 ─────────────────────────────────────────────────
async function toggleLessonPublish(lesson) {
  closeMenus()
  const next = isPublished(lesson) ? 'draft' : 'published'
  try {
    await coursesAPI.updateLesson(lesson.id, { status: next })
    await loadPage()
    app.showToast(next === 'published' ? '课时已发布' : '课时已设为草稿', 'success')
  } catch {
    app.showToast('操作失败', 'error')
  }
}

// ── 课时移动到其他章节 ───────────────────────────────────────────────
function openMoveLesson(lesson) {
  closeMenus()
  movingLesson.value = lesson
  moveTargetChapterId.value = lesson.chapter_id
}

async function confirmMoveLesson() {
  if (!movingLesson.value || !moveTargetChapterId.value) return
  savingMove.value = true
  try {
    await coursesAPI.updateLesson(movingLesson.value.id, {
      chapter_id: moveTargetChapterId.value,
      order_index: 0,
    })
    movingLesson.value = null
    await loadPage()
    app.showToast('课时已移动', 'success')
  } catch {
    app.showToast('移动课时失败', 'error')
  } finally {
    savingMove.value = false
  }
}

// ── 课程设置 ──────────────────────────────────────────────────────────
async function saveSettings() {
  savingSettings.value = true
  try {
    await coursesAPI.update(courseId.value, settings.value)
    course.value = { ...course.value, ...settings.value }
    settingsOpen.value = false
    app.showToast('课程设置已保存', 'success')
  } catch {
    app.showToast('课程设置保存失败', 'error')
  } finally {
    savingSettings.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  loadPage()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <AppLayout>
    <div class="catalog-page">
      <!-- 顶部课程概览 -->
      <section class="course-overview">
        <div class="overview-heading">
          <h1>{{ course?.title || '课程管理' }}</h1>
          <p class="subtitle">管理章节、课时、讲义与实验内容</p>
        </div>
        <div class="overview-actions">
          <button class="button button-secondary" type="button" @click="settingsOpen = true">
            <AppIcon name="settings" :size="16" /> 课程设置
          </button>
          <button class="button button-primary" type="button" @click="showChapterForm = !showChapterForm">
            <AppIcon name="plus" :size="16" /> {{ showChapterForm ? '取消' : '添加章节' }}
          </button>
        </div>
      </section>

      <!-- 课程统计 -->
      <section class="stats-grid" aria-label="课程统计">
        <article v-for="stat in stats" :key="stat.label" class="stat-card">
          <strong>{{ stat.value }}</strong>
          <span>{{ stat.label }}</span>
        </article>
      </section>

      <!-- 添加章节 -->
      <form v-if="showChapterForm" class="inline-form" @submit.prevent="createChapter">
        <label for="chapter-title">新章节名称</label>
        <input id="chapter-title" v-model="chapterTitle" placeholder="例如：Python 基础" autofocus />
        <button class="button button-primary" type="submit">创建章节</button>
      </form>

      <div v-if="loading" class="loading-card">正在加载课程目录…</div>

      <!-- 课程空状态 -->
      <section v-else-if="chapters.length === 0" class="empty-card">
        <h2>尚未创建课程章节</h2>
        <p>创建章节后，可以在章节中添加讲义、Notebook 和实验内容。</p>
        <button class="button button-primary" type="button" @click="showChapterForm = true">创建第一个章节</button>
      </section>

      <!-- 章节卡片 -->
      <section v-else class="chapter-stack" aria-label="课程章节">
        <article v-for="(chapter, index) in chapters" :key="chapter.id" class="chapter-card">
          <header class="chapter-header">
            <div class="chapter-heading">
              <span class="chapter-number">第 {{ index + 1 }} 章</span>
              <h2 class="chapter-name">{{ chapter.title }}</h2>
            </div>
            <div class="chapter-actions">
              <button class="text-button" type="button" @click="openAddLesson(chapter.id)">
                <AppIcon name="plus" :size="14" /> 添加课时
              </button>
              <button v-if="API_CAPS.chapterEdit" class="text-button" type="button" @click="openEditChapter(chapter)">
                <AppIcon name="edit" :size="14" /> 编辑章节
              </button>
              <div class="menu-wrap" data-menu>
                <button
                  class="icon-button"
                  type="button"
                  aria-label="章节更多操作"
                  @click.stop="toggleMenu(`chapter:${chapter.id}`)"
                >
                  <AppIcon name="more" :size="18" />
                </button>
                <div v-if="openMenu === `chapter:${chapter.id}`" class="action-menu">
                  <button v-if="API_CAPS.chapterCopy" type="button" @click="copyChapter(chapter)">
                    <AppIcon name="copy" :size="15" /> 复制章节
                  </button>
                  <template v-if="API_CAPS.chapterMove">
                    <button type="button" :disabled="index === 0" @click="moveChapter(chapter, -1)">
                      <AppIcon name="chevron-up" :size="15" /> 上移
                    </button>
                    <button type="button" :disabled="index === chapters.length - 1" @click="moveChapter(chapter, 1)">
                      <AppIcon name="chevron-down" :size="15" /> 下移
                    </button>
                  </template>
                  <template v-if="API_CAPS.lessonPublish && chapterLessons(chapter).length">
                    <div class="menu-divider"></div>
                    <button type="button" @click="unpublishChapter(chapter)">
                      <AppIcon name="eye-off" :size="15" /> 取消发布章节
                    </button>
                  </template>
                  <template v-if="API_CAPS.chapterDelete">
                    <div class="menu-divider"></div>
                    <button class="menu-danger" type="button" @click="askDeleteChapter(chapter)">
                      <AppIcon name="trash" :size="15" /> 删除章节
                    </button>
                  </template>
                </div>
              </div>
              <button
                class="icon-button"
                type="button"
                :aria-label="expanded[chapter.id] ? '收起章节' : '展开章节'"
                @click="toggleChapter(chapter.id)"
              >
                <AppIcon :name="expanded[chapter.id] ? 'chevron-down' : 'chevron-right'" :size="18" />
              </button>
            </div>
          </header>

          <div v-if="expanded[chapter.id]" class="chapter-body">
            <!-- 选择内容类型 -->
            <div v-if="contentPicker === chapter.id" class="content-picker">
              <div class="picker-heading">
                <strong>添加课时</strong>
                <button class="close-button" type="button" aria-label="关闭" @click="contentPicker = null">
                  <AppIcon name="close" :size="16" />
                </button>
              </div>
              <button
                v-for="item in CONTENT_TYPES"
                :key="item.type"
                type="button"
                @click="chooseContent(chapter.id, item.type)"
              >
                <strong>{{ item.label }}</strong>
                <span>{{ item.desc }}</span>
              </button>
            </div>

            <!-- 创建课时表单 -->
            <form v-if="lessonForm?.chapterId === chapter.id" class="lesson-form" @submit.prevent="createLesson">
              <div class="picker-heading">
                <strong>新建{{ CONTENT_TYPES.find((i) => i.type === lessonForm.type)?.label || lessonForm.type }}</strong>
                <button class="close-button" type="button" aria-label="关闭" @click="lessonForm = null">
                  <AppIcon name="close" :size="16" />
                </button>
              </div>
              <input v-model="lessonForm.title" placeholder="课时标题" autofocus />
              <textarea
                v-if="lessonForm.type !== 'video'"
                v-model="lessonForm.content"
                rows="4"
                placeholder="内容（可选）"
              ></textarea>
              <input v-if="lessonForm.type === 'video'" v-model="lessonForm.video_url" placeholder="视频链接 URL" />
              <div class="form-actions">
                <button class="button button-secondary" type="button" @click="lessonForm = null">取消</button>
                <button class="button button-primary" type="submit">创建课时</button>
              </div>
            </form>

            <!-- 课时列表 -->
            <div v-if="chapter.lessons?.length" class="lesson-table">
              <div class="lesson-row lesson-head">
                <span>编号</span>
                <span>课时标题</span>
                <span>类型</span>
                <span class="duration-col">时长</span>
                <span>状态</span>
                <span>操作</span>
              </div>
              <div
                v-for="(lesson, lessonIndex) in chapter.lessons"
                :key="lesson.id"
                class="lesson-row"
                @click="openEditLesson(lesson)"
              >
                <span class="lesson-index">{{ index + 1 }}.{{ lessonIndex + 1 }}</span>
                <span class="lesson-title">{{ lesson.title }}</span>
                <span class="type-cell">
                  <em class="lesson-type">{{ typeLabel(lesson.content_type) }}</em>
                  <span class="duration-inline">· {{ durationLabel(lesson) }}</span>
                </span>
                <span class="duration-col duration">{{ durationLabel(lesson) }}</span>
                <span class="status-cell">
                  <em class="publish-status" :class="statusClass(lesson)">
                    <i class="status-dot"></i>{{ statusLabel(lesson) }}
                  </em>
                </span>
                <span class="lesson-actions" @click.stop>
                  <button class="row-action" type="button" @click="openEditLesson(lesson)">
                    <AppIcon name="edit" :size="14" /> 编辑
                  </button>
                  <button class="row-action" type="button" @click="openPreview(lesson)">
                    <AppIcon name="eye" :size="14" /> 预览
                  </button>
                  <div class="menu-wrap" data-menu>
                    <button
                      class="row-action more"
                      type="button"
                      aria-label="更多操作"
                      @click="toggleMenu(`lesson:${lesson.id}`)"
                    >
                      <AppIcon name="more" :size="16" />
                    </button>
                    <div v-if="openMenu === `lesson:${lesson.id}`" class="action-menu">
                      <button v-if="API_CAPS.lessonCopy" type="button" @click="copyLesson(lesson)">
                        <AppIcon name="copy" :size="15" /> 复制课时
                      </button>
                      <button v-if="API_CAPS.lessonMove" type="button" @click="openMoveLesson(lesson)">
                        <AppIcon name="move" :size="15" /> 移动到其他章节
                      </button>
                      <template v-if="API_CAPS.lessonPublish">
                        <div class="menu-divider"></div>
                        <button type="button" @click="toggleLessonPublish(lesson)">
                          <AppIcon name="eye-off" :size="15" />
                          {{ isPublished(lesson) ? '设为草稿' : '发布课时' }}
                        </button>
                      </template>
                      <template v-if="API_CAPS.lessonDelete">
                        <div class="menu-divider"></div>
                        <button class="menu-danger" type="button" @click="askDeleteLesson(lesson)">
                          <AppIcon name="trash" :size="15" /> 删除课时
                        </button>
                      </template>
                    </div>
                  </div>
                </span>
              </div>
            </div>

            <!-- 章节空状态 -->
            <div v-else class="chapter-empty">
              <h3>本章节暂无课时</h3>
              <p>添加讲义、Notebook 或实验，开始构建课程内容。</p>
              <button class="button button-secondary" type="button" @click="openAddLesson(chapter.id)">添加课时</button>
            </div>
          </div>

          <!-- 折叠摘要 -->
          <div v-else class="chapter-summary">{{ chapterSummary(chapter) }}</div>
        </article>
      </section>
    </div>

    <!-- 课程设置抽屉 -->
    <div v-if="settingsOpen" class="modal-backdrop" @click.self="settingsOpen = false">
      <form class="side-panel" @submit.prevent="saveSettings">
        <div class="panel-header">
          <div>
            <p class="panel-eyebrow">课程设置</p>
            <h2>课程信息</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="settingsOpen = false">
            <AppIcon name="close" :size="18" />
          </button>
        </div>
        <label>
          课程名称
          <input v-model="settings.title" />
        </label>
        <label>
          课程简介
          <textarea v-model="settings.description" rows="4"></textarea>
        </label>
        <label>
          课程状态
          <select v-model="settings.status">
            <option value="draft">草稿</option>
            <option value="published">已发布</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <div class="settings-grid">
          <label>
            课程封面
            <input disabled placeholder="暂未开放" />
          </label>
          <label>
            开课时间
            <input disabled type="datetime-local" />
          </label>
          <label>
            课程可见范围
            <select disabled>
              <option>仅自己可见</option>
            </select>
          </label>
          <label>
            默认评分设置
            <input disabled type="number" placeholder="100" />
          </label>
        </div>
        <p class="settings-note">
          课程封面、开课时间、可见范围与默认评分设置暂未接入后端，保存不会生效，已禁用。
        </p>
        <div class="form-actions">
          <button class="button button-secondary" type="button" @click="settingsOpen = false">取消</button>
          <button class="button button-primary" type="submit" :disabled="savingSettings">
            {{ savingSettings ? '保存中…' : '保存设置' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 编辑课时抽屉 -->
    <div v-if="editingLesson" class="modal-backdrop" @click.self="editingLesson = null">
      <form class="side-panel" @submit.prevent="saveEditLesson">
        <div class="panel-header">
          <div>
            <p class="panel-eyebrow">编辑课时</p>
            <h2>{{ editingLesson.title }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="editingLesson = null">
            <AppIcon name="close" :size="18" />
          </button>
        </div>
        <label>
          课时标题
          <input v-model="editForm.title" />
        </label>
        <label v-if="editingLesson.content_type === 'video'">
          视频链接
          <input v-model="editForm.video_url" placeholder="视频链接 URL" />
        </label>
        <label v-else>
          内容
          <textarea v-model="editForm.content" rows="12" placeholder="Markdown 内容"></textarea>
        </label>
        <div class="form-actions">
          <button class="button button-secondary" type="button" @click="editingLesson = null">取消</button>
          <button class="button button-primary" type="submit" :disabled="savingEdit">
            {{ savingEdit ? '保存中…' : '保存课时' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 学生视角预览 -->
    <div v-if="previewLesson" class="modal-backdrop preview-backdrop" @click.self="previewLesson = null">
      <div class="preview-panel" role="dialog" aria-modal="true" aria-label="课时预览">
        <header class="preview-header">
          <div>
            <p class="panel-eyebrow">学生视角预览</p>
            <h2>{{ previewLesson.title }}</h2>
            <p class="preview-meta">
              <em class="lesson-type">{{ typeLabel(previewLesson.content_type) }}</em>
              <span>· {{ durationLabel(previewLesson) }}</span>
              <em class="publish-status" :class="statusClass(previewLesson)">
                <i class="status-dot"></i>{{ statusLabel(previewLesson) }}
              </em>
            </p>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="previewLesson = null">
            <AppIcon name="close" :size="18" />
          </button>
        </header>
        <div v-if="previewLesson.content_type === 'video'" class="preview-body">
          <p v-if="previewLesson.video_url">
            视频地址：
            <a :href="previewLesson.video_url" target="_blank" rel="noopener noreferrer">{{ previewLesson.video_url }}</a>
          </p>
          <p v-else>该课时尚未设置视频地址。</p>
        </div>
        <div v-else class="preview-body lesson-content" v-html="previewHtml"></div>
        <footer v-if="previewLesson.content_type === 'notebook' && previewLesson.template_id" class="preview-footer">
          <button class="button button-secondary" type="button" @click="openStudioForPreview(previewLesson)">
            在 Studio 中打开
          </button>
        </footer>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-backdrop confirm-backdrop" @click.self="deleteTarget = null">
      <div class="confirm-panel" role="dialog" aria-modal="true" aria-labelledby="delete-confirm-title">
        <h2 id="delete-confirm-title">确认删除{{ deleteTarget.kind === 'chapter' ? '章节' : '课时' }}？</h2>
        <p>
          {{ deleteTarget.kind === 'chapter' ? '章节' : '课时' }}“{{ deleteTarget.title }}”删除后将无法恢复。
          <template v-if="deleteTarget.kind === 'chapter' && deleteTarget.lessonCount > 0">
            章节内 {{ deleteTarget.lessonCount }} 个课时将一并删除。
          </template>
          如果已有学生学习记录，不建议直接删除。
        </p>
        <div class="confirm-actions">
          <button class="button button-secondary" type="button" @click="deleteTarget = null">取消</button>
          <button class="button button-danger" type="button" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑章节抽屉 -->
    <div v-if="editingChapter" class="modal-backdrop" @click.self="editingChapter = null">
      <form class="side-panel" @submit.prevent="saveEditChapter">
        <div class="panel-header">
          <div>
            <p class="panel-eyebrow">编辑章节</p>
            <h2>{{ editingChapter.title }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="editingChapter = null">
            <AppIcon name="close" :size="18" />
          </button>
        </div>
        <label>
          章节名称
          <input v-model="chapterEditTitle" />
        </label>
        <div class="form-actions">
          <button class="button button-secondary" type="button" @click="editingChapter = null">取消</button>
          <button class="button button-primary" type="submit" :disabled="savingChapterEdit">
            {{ savingChapterEdit ? '保存中…' : '保存章节' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 移动到其他章节弹窗 -->
    <div v-if="movingLesson" class="modal-backdrop confirm-backdrop" @click.self="movingLesson = null">
      <form class="confirm-panel" role="dialog" aria-modal="true" aria-label="移动到其他章节" @submit.prevent="confirmMoveLesson">
        <h2>移动课时</h2>
        <p>课时“{{ movingLesson.title }}”将移动到：</p>
        <label class="move-select">
          <select v-model="moveTargetChapterId">
            <option v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">
              {{ chapter.title }}
            </option>
          </select>
        </label>
        <div class="confirm-actions">
          <button class="button button-secondary" type="button" @click="movingLesson = null">取消</button>
          <button class="button button-primary" type="submit" :disabled="savingMove || !moveTargetChapterId">
            {{ savingMove ? '移动中…' : '确认移动' }}
          </button>
        </div>
      </form>
    </div>
  </AppLayout>
</template>

<style scoped>
/* 变量定义需同时作用于页面主体与抽屉/弹窗容器（.modal-backdrop）：
   抽屉在 DOM 中是 .catalog-page 的兄弟节点，若变量只定义在 .catalog-page 上，
   抽屉内按钮的 var(--primary-hover) 将解析为空 → hover 时背景回退为透明导致按钮消失 */
.catalog-page,
.modal-backdrop {
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --border: #e2e8f0;
  --border-light: #edf1f5;
  --page-bg: #f7f9fc;
  --card-bg: #ffffff;
  --hover-bg: #f8fafc;
}
.catalog-page {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 32px 48px;
  color: var(--text-primary);
  background: var(--page-bg);
}

/* ── 顶部课程概览 ─────────────────────────────────────────────────── */
.course-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.overview-heading { min-width: 0; }
.course-overview h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  font-weight: 700;
  letter-spacing: -0.02em;
  overflow-wrap: anywhere;
}
.subtitle { margin: 6px 0 0; color: var(--text-muted); font-size: 14px; }
.overview-actions { display: flex; align-items: center; gap: 8px; flex: none; }

.button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 42px;
  padding: 0 16px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}
.button-primary { color: #fff; background: var(--primary); border-color: var(--primary); }
.button-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); }
.button-secondary { color: var(--text-secondary); background: #fff; border-color: var(--border); }
.button-secondary:hover { color: var(--text-primary); background: #fff; border-color: #cbd5e1; }
.button-danger { color: #fff; background: #dc2626; border-color: #dc2626; }
.button-danger:hover { background: #b91c1c; border-color: #b91c1c; }

/* ── 课程统计 ─────────────────────────────────────────────────────── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.stat-card {
  min-height: 82px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  border: 1px solid #e5eaf2;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.stat-card strong { font-size: 22px; line-height: 1.15; font-weight: 700; color: var(--text-primary); }
.stat-card span { color: var(--text-muted); font-size: 13px; }

/* ── 章节卡片 ─────────────────────────────────────────────────────── */
.chapter-card {
  margin-top: 16px;
  /* 不能用 overflow:hidden：会把课时行向下弹出的更多菜单裁掉 */
  overflow: visible;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.chapter-header {
  min-height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e8edf3;
}
.chapter-heading { display: flex; align-items: center; min-width: 0; }
.chapter-number {
  flex: none;
  padding: 5px 10px;
  border-radius: 7px;
  background: #eff6ff;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.chapter-name {
  min-width: 0;
  margin-left: 14px;
  font-size: 17px;
  font-weight: 650;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}
.chapter-actions { display: flex; align-items: center; gap: 6px; flex: none; }

.text-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}
.text-button:hover { color: var(--primary); background: transparent; border-color: transparent; }

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  border-radius: 7px;
}
.icon-button:hover { color: var(--text-primary); background: var(--hover-bg); border-color: transparent; }

.menu-wrap { position: relative; }
.action-menu {
  position: absolute;
  /* 高于相邻卡片内容，避免被后面章节卡片覆盖；低于弹窗层(40) */
  z-index: 30;
  top: calc(100% + 6px);
  right: 0;
  min-width: 150px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 6px 16px rgba(15, 23, 42, 0.08);
}
.action-menu button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-start;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  border-radius: 7px;
}
.action-menu button:hover { background: var(--hover-bg); color: var(--text-primary); border-color: transparent; }
.action-menu button:disabled { color: #cbd5e1; cursor: not-allowed; }
.action-menu button:disabled:hover { background: transparent; color: #cbd5e1; }
/* 课时行的菜单向上弹出：避免最后一行课时向下弹出超出视口底部被裁 */
.lesson-row .action-menu,
.lesson-actions .action-menu {
  top: auto;
  bottom: calc(100% + 6px);
}
.menu-divider { height: 1px; margin: 5px 8px; background: var(--border-light); }
.menu-danger { color: #dc2626 !important; }
.menu-danger:hover { background: #fef2f2 !important; color: #b91c1c !important; }

/* 移动课时弹窗 */
.move-select { display: block; margin: 0 0 20px; }
.move-select select { width: 100%; border-radius: 8px; }

/* ── 课时列表 ─────────────────────────────────────────────────────── */
.chapter-body { padding: 0 18px; }
.lesson-table { width: 100%; }
.lesson-row {
  min-height: 56px;
  padding: 0;
  display: grid;
  align-items: center;
  grid-template-columns: 52px minmax(240px, 1fr) 110px 110px 100px auto;
  border-bottom: 1px solid var(--border-light);
  background: #fff;
  font-size: 13px;
  transition: background var(--duration-fast, 120ms) ease;
}
.lesson-row:last-child { border-bottom: 0; }
.lesson-row:not(.lesson-head):hover { background: var(--hover-bg); }
.lesson-head { min-height: 40px; color: var(--text-muted); font-size: 12px; }
.lesson-head span { white-space: nowrap; }

.lesson-index {
  color: var(--text-muted);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}
.lesson-title {
  min-width: 0;
  font-size: 15px;
  font-weight: 550;
  color: #172033;
  overflow-wrap: anywhere;
}
.type-cell { min-width: 0; display: flex; align-items: center; gap: 4px; }
.duration-inline { display: none; }
.duration { color: var(--text-muted); font-size: 13px; white-space: nowrap; }

.lesson-type {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
  font-style: normal;
  white-space: nowrap;
}

.publish-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border-radius: 6px;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}
.publish-status .status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.publish-status.published { color: #15803d; background: #ecfdf3; }
.publish-status.draft { color: #64748b; background: #f1f5f9; }
.publish-status.pending { color: #c2410c; background: #fff7ed; }

.lesson-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  white-space: nowrap;
}
.row-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 7px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  border-radius: 6px;
}
.row-action:hover { color: var(--primary); background: var(--hover-bg); border-color: transparent; }
.row-action.more { color: var(--text-muted); padding: 6px 8px; }
.row-action.more:hover { color: var(--text-primary); }

/* ── 添加课时选择 / 创建表单 ───────────────────────────────────────── */
.content-picker,
.lesson-form {
  margin: 16px 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--hover-bg);
}
.content-picker {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.picker-heading {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-primary);
  font-size: 14px;
}
.close-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  border-radius: 7px;
}
.close-button:hover { background: #fff; color: var(--text-primary); border-color: transparent; }
.content-picker button {
  min-height: 74px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  text-align: left;
  font-weight: 500;
}
.content-picker button:hover { border-color: #93c5fd; background: #eff6ff; }
.content-picker button span { color: var(--text-muted); font-size: 12px; line-height: 1.4; }

.lesson-form { display: grid; gap: 12px; }
.lesson-form .form-actions { justify-content: flex-end; }
.form-actions { display: flex; align-items: center; gap: 8px; }

/* ── 章节空状态 / 折叠摘要 / 加载 / 课程空状态 ─────────────────────── */
.chapter-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 20px 44px;
  text-align: center;
}
.chapter-empty h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary); }
.chapter-empty p { margin: 0; color: var(--text-muted); font-size: 13px; }

.chapter-summary {
  padding: 14px 20px 18px;
  color: var(--text-muted);
  font-size: 13px;
}

.inline-form,
.loading-card,
.empty-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.inline-form {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.inline-form label { white-space: nowrap; font-size: 14px; font-weight: 600; }
.inline-form input { flex: 1; border-radius: 8px; }
.loading-card,
.empty-card { padding: 48px 24px; text-align: center; }
.empty-card h2 { margin: 0 0 8px; font-size: 18px; color: var(--text-primary); }
.empty-card p { margin: 0 0 20px; color: var(--text-muted); font-size: 14px; }

/* ── 抽屉 / 弹窗 ──────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: flex;
  justify-content: flex-end;
  background: rgba(15, 23, 42, 0.25);
}
.side-panel {
  width: min(460px, 100%);
  height: 100%;
  overflow-y: auto;
  padding: 28px;
  background: #fff;
  box-shadow: -4px 0 16px rgba(15, 23, 42, 0.08);
}
.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}
.panel-header h2 { margin: 0; font-size: 22px; line-height: 1.3; color: var(--text-primary); overflow-wrap: anywhere; }
.panel-eyebrow { margin: 0 0 4px; color: var(--text-muted); font-size: 12px; font-weight: 600; }
.side-panel label {
  display: grid;
  gap: 6px;
  margin-bottom: 16px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}
.side-panel input,
.side-panel textarea,
.side-panel select {
  width: 100%;
  border-radius: 8px;
}
.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.settings-note {
  margin: 4px 0 0;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--hover-bg);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}
.side-panel .form-actions { justify-content: flex-end; margin-top: 24px; }

.preview-backdrop {
  justify-content: center;
  align-items: flex-start;
  padding: 40px 16px;
  overflow-y: auto;
}
.preview-panel {
  width: min(760px, 100%);
  border-radius: 14px;
  border: 1px solid var(--border);
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 12px 32px rgba(15, 23, 42, 0.1);
  overflow: hidden;
}
.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-light);
}
.preview-header h2 { margin: 0; font-size: 20px; color: var(--text-primary); overflow-wrap: anywhere; }
.preview-meta { display: flex; align-items: center; gap: 8px; margin: 8px 0 0; color: var(--text-muted); font-size: 13px; }
.preview-body { padding: 24px; color: #334155; font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.preview-footer { padding: 12px 24px 20px; }
.lesson-content :deep(p) { margin: 0 0 12px; }
.lesson-content :deep(h1),
.lesson-content :deep(h2),
.lesson-content :deep(h3) { margin: 20px 0 10px; color: var(--text-primary); }
.lesson-content :deep(pre) { padding: 12px 14px; overflow-x: auto; background: #f1f5f9; border-radius: 8px; }
.lesson-content :deep(code) { background: #f1f5f9; border: 0; color: #0f172a; }
.lesson-content :deep(a) { color: var(--primary); }
.lesson-content :deep(ul),
.lesson-content :deep(ol) { margin: 0 0 12px; padding-left: 22px; }
.lesson-content :deep(blockquote) { margin: 0 0 12px; padding-left: 12px; border-left: 3px solid var(--border); color: var(--text-muted); }

.confirm-backdrop {
  justify-content: center;
  align-items: center;
}
.confirm-panel {
  width: min(420px, calc(100% - 32px));
  padding: 24px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}
.confirm-panel h2 { margin: 0 0 10px; font-size: 17px; color: var(--text-primary); }
.confirm-panel p { margin: 0 0 20px; color: var(--text-muted); font-size: 13px; line-height: 1.6; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 8px; }

/* ── 响应式 ───────────────────────────────────────────────────────── */
/* 1024–1199px：隐藏时长列，保留标题/类型/状态/操作 */
@media (max-width: 1199px) {
  .catalog-page { padding-inline: 24px; }
  .lesson-row { grid-template-columns: 52px minmax(180px, 1fr) 110px 100px auto; }
  .duration-col { display: none; }
}

/* <900px：课时改为上下两层，时长合并进类型行 */
@media (max-width: 899px) {
  .catalog-page { padding: 24px 16px 40px; }
  .course-overview { align-items: flex-start; flex-direction: column; }
  .overview-actions { width: 100%; }
  .overview-actions .button { flex: 1; }
  .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }

  .chapter-header {
    flex-wrap: wrap;
    align-items: flex-start;
    padding: 12px 16px;
    gap: 10px;
  }
  .chapter-heading { flex: 1 1 auto; min-width: 0; }
  .chapter-actions { margin-left: auto; }
  .chapter-body { padding-inline: 12px; }

  .lesson-row {
    min-height: 0;
    grid-template-columns: 48px minmax(0, 1fr) auto;
    row-gap: 4px;
    padding: 10px 12px;
  }
  .lesson-head { display: none; }
  .lesson-row > :nth-child(1) { grid-column: 1; grid-row: 1; }
  .lesson-row > :nth-child(2) { grid-column: 2; grid-row: 1; }
  .lesson-row > :nth-child(3) { grid-column: 2; grid-row: 2; }
  .lesson-row > :nth-child(4) { display: none; }
  .lesson-row > :nth-child(5) { grid-column: 3; grid-row: 1; justify-self: end; }
  .lesson-row > :nth-child(6) { grid-column: 3; grid-row: 2; justify-self: end; }
  .duration-inline { display: inline; }

  .content-picker { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .inline-form { align-items: stretch; flex-wrap: wrap; }
  .inline-form label { width: 100%; }
  .inline-form input { min-width: 180px; }
}

@media (max-width: 520px) {
  .course-overview h1 { font-size: 26px; }
  .stats-grid { gap: 8px; }
  .stat-card { padding: 14px; }
  .content-picker { grid-template-columns: 1fr; }
  .side-panel { padding: 20px; }
  .settings-grid { grid-template-columns: 1fr; }
  .preview-body { padding: 16px; }
}
</style>
