import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { coursesAPI } from '../api/courses.js'
import { useAppStore } from '../stores/app.js'

/**
 * 课时编辑页共享逻辑：加载课时、保存、dirty 离开守卫（自定义确认弹窗）、
 * beforeunload 浏览器刷新守卫。
 *
 * 用法（编辑页组件内）：
 *   const { lesson, loading, loadError, saving, saveState, showLeaveDialog,
 *           load, save, goBack, onConfirmLeave, onCancelLeave } =
 *     useLessonEditor({ courseId, lessonId, backPath, isDirty, buildPayload })
 *
 * 组件负责：表单双向绑定 lesson 字段、isDirty 快照对比、
 * 保存成功后重置快照（await save() 返回后）、渲染 ConfirmDialog。
 *
 * @param {object} opts
 * @param {string|number} opts.courseId 课程 id
 * @param {string|number} opts.lessonId 课时 id
 * @param {string|object} opts.backPath 返回路径（router.push 目标）
 * @param {() => boolean} opts.isDirty 表单相对已保存快照是否有修改（未加载完成时应返回 false）
 * @param {(lesson: object) => object} opts.buildPayload 构造 updateLesson payload
 */
export function useLessonEditor({ courseId, lessonId, backPath, isDirty, buildPayload }) {
  const app = useAppStore()
  const router = useRouter()

  const lesson = ref(null)
  const loading = ref(true)
  const loadError = ref('')
  const saving = ref(false)
  const showLeaveDialog = ref(false)

  // 保存状态文字：保存中… / 未保存 / 已保存（加载完成前固定"已保存"占位，不闪动）
  const saveState = computed(() => {
    if (saving.value) return '保存中…'
    if (lesson.value && isDirty()) return '未保存'
    return '已保存'
  })

  // 离开守卫：confirmedLeave 一次生效后永久放行（避免二次导航被再次拦截）；
  // leaveResolver 单一出口，resolve 后立即置 null（双击确认按钮安全）
  let confirmedLeave = false
  let leaveResolver = null

  onBeforeRouteLeave((_to, _from) => {
    if (confirmedLeave || !isDirty()) return true
    return new Promise((resolve) => {
      leaveResolver = resolve
      showLeaveDialog.value = true
    })
  })

  function onConfirmLeave() {
    if (!leaveResolver) return
    confirmedLeave = true
    showLeaveDialog.value = false
    const resolve = leaveResolver
    leaveResolver = null
    resolve(true)
  }

  function onCancelLeave() {
    if (!leaveResolver) return
    showLeaveDialog.value = false
    const resolve = leaveResolver
    leaveResolver = null
    resolve(false)
  }

  async function load() {
    loading.value = true
    loadError.value = ''
    try {
      const response = await coursesAPI.getChapters(courseId)
      const raw = response.data
      const list = Array.isArray(raw) ? raw : (raw.items || [])
      const found = list
        .flatMap((chapter) => chapter.lessons || [])
        .find((item) => String(item.id) === String(lessonId))
      if (!found) {
        loadError.value = '课时不存在或已被删除'
        lesson.value = null
      } else {
        lesson.value = found
      }
    } catch (err) {
      loadError.value = '课时加载失败，请稍后重试'
      console.error('[useLessonEditor] 加载课时失败', err)
    } finally {
      loading.value = false
    }
  }

  /** @returns {Promise<boolean>} 保存是否成功（组件据此决定是否重置 dirty 快照） */
  async function save() {
    if (!lesson.value || saving.value) return false
    saving.value = true
    try {
      await coursesAPI.updateLesson(lessonId, buildPayload(lesson.value))
      app.showToast('课时已保存', 'success')
      return true
    } catch (err) {
      app.showToast('保存失败，请重试', 'error')
      console.error('[useLessonEditor] 保存课时失败', err)
      return false
    } finally {
      saving.value = false
    }
  }

  function goBack() {
    router.push(backPath)
  }

  // 浏览器刷新/关闭兜底：有未保存修改时触发系统级离开确认
  function onBeforeUnload(e) {
    if (isDirty()) e.preventDefault()
  }
  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

  return {
    lesson,
    loading,
    loadError,
    saving,
    saveState,
    showLeaveDialog,
    load,
    save,
    goBack,
    onConfirmLeave,
    onCancelLeave,
  }
}
