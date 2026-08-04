<script setup>
// 视频编辑页：标题 + 视频链接 URL + 简介，底部预览外链（对齐管理页预览弹窗写法）
import { computed, onMounted, ref } from 'vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import ConfirmDialog from '../../components/ui/ConfirmDialog.vue'
import { useLessonEditor } from '../../composables/useLessonEditor.js'

const props = defineProps({
  courseId: { type: [String, Number], required: true },
  lessonId: { type: [String, Number], required: true },
  backPath: { type: [String, Object], required: true },
})

const title = ref('')
const videoUrl = ref('')
const content = ref('')
const snapshot = ref(null)

function isDirty() {
  if (!snapshot.value) return false
  return title.value !== snapshot.value.title
    || videoUrl.value !== snapshot.value.videoUrl
    || content.value !== snapshot.value.content
}

const {
  lesson, loading, loadError, saving, saveState, showLeaveDialog,
  load, save, goBack, onConfirmLeave, onCancelLeave,
} = useLessonEditor({
  courseId: props.courseId,
  lessonId: props.lessonId,
  backPath: props.backPath,
  isDirty,
  buildPayload: () => ({
    title: title.value.trim(),
    // 空串归一 null：后端字段可空
    video_url: videoUrl.value.trim() || null,
    content: content.value || undefined,
  }),
})

async function initForm() {
  await load()
  if (lesson.value) {
    title.value = lesson.value.title || ''
    videoUrl.value = lesson.value.video_url || ''
    content.value = lesson.value.content || ''
    snapshot.value = { title: title.value, videoUrl: videoUrl.value, content: content.value }
  }
}
onMounted(initForm)

async function handleSave() {
  const ok = await save()
  if (ok) snapshot.value = { title: title.value, videoUrl: videoUrl.value, content: content.value }
}

const charCount = computed(() => content.value.length)
const canSave = computed(() => !saving.value && title.value.trim().length > 0)
</script>

<template>
  <div class="editor-page">
    <!-- 页头：返回 + 类型徽标 + 标题 + 保存状态 + 保存 -->
    <header class="editor-header">
      <button class="back-btn" type="button" @click="goBack">
        <AppIcon name="back" :size="16" /> 返回
      </button>
      <em class="type-badge">视频</em>
      <input v-model="title" class="title-input" placeholder="课时标题" aria-label="课时标题" />
      <span class="save-state" :class="{ dirty: isDirty() }">{{ saveState }}</span>
      <button class="btn-primary save-btn" type="button" :disabled="!canSave" @click="handleSave">保存</button>
    </header>

    <div v-if="loading" class="editor-body">
      <div v-for="i in 4" :key="i" class="skeleton skeleton-line"></div>
    </div>

    <!-- 加载失败 / 课时不存在 -->
    <div v-else-if="loadError" class="error-card">
      <h2>{{ loadError }}</h2>
      <p>请返回课时列表确认该课时仍然存在。</p>
      <button class="btn-primary" type="button" @click="goBack">返回</button>
    </div>

    <div v-else class="editor-body">
      <label class="field-label" for="video-url">视频链接 URL</label>
      <input
        id="video-url"
        v-model="videoUrl"
        class="video-url-input"
        type="url"
        placeholder="https://example.com/video.mp4"
        aria-label="视频链接 URL"
      />
      <label class="field-label" for="video-desc">简介</label>
      <textarea
        id="video-desc"
        v-model="content"
        class="content-textarea"
        rows="8"
        placeholder="课程简介（可选）…"
        aria-label="视频简介"
      ></textarea>
      <p class="char-count">{{ charCount }} 字</p>

      <!-- 预览区：显示外链（对齐管理页预览弹窗写法） -->
      <section class="preview-pane">
        <p class="pane-title">预览</p>
        <p v-if="videoUrl.trim()">
          视频地址：
          <a :href="videoUrl.trim()" target="_blank" rel="noopener noreferrer">{{ videoUrl.trim() }}</a>
        </p>
        <p v-else>该课时尚未设置视频地址。</p>
      </section>
    </div>

    <!-- 未保存离开确认（四页统一文案） -->
    <ConfirmDialog
      v-if="showLeaveDialog"
      title="有未保存的修改"
      message="确定离开吗？未保存的内容将丢失。"
      confirm-text="离开"
      cancel-text="取消"
      @confirm="onConfirmLeave"
      @cancel="onCancelLeave"
    />
  </div>
</template>

<style scoped>
.editor-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 48px;
  color: var(--text);
}

/* ── 页头 ─────────────────────────────────────────────────────────── */
.editor-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}
.back-btn:hover { border-color: var(--border-strong); color: var(--text); }
.type-badge {
  flex: none;
  padding: 3px 8px;
  border-radius: 6px;
  background: #eff6ff;
  color: var(--primary);
  font-size: 12px;
  font-weight: 500;
  font-style: normal;
  white-space: nowrap;
}
.title-input {
  flex: 1;
  min-width: 220px;
  font-size: 16px;
  font-weight: 600;
}
.save-state { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.save-state.dirty { color: var(--warning); }
.save-btn { flex: none; }

/* ── 正文区 ───────────────────────────────────────────────────────── */
.editor-body { min-height: 200px; }
.skeleton-line { height: 18px; margin-bottom: 14px; }
.field-label {
  display: block;
  margin: 0 0 6px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}
.video-url-input { margin-bottom: 18px; }
.content-textarea {
  width: 100%;
  min-height: 120px;
  resize: vertical;
  font-size: 13px;
  line-height: 1.7;
}
.char-count { margin: 8px 0 0; color: var(--text-tertiary); font-size: 12px; text-align: right; }

/* ── 预览区（对齐管理页预览弹窗的链接写法） ──────────────────────── */
.preview-pane {
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-raised);
  font-size: 13px;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}
.pane-title { margin: 0 0 6px; font-size: 12px; font-weight: 600; color: var(--text-tertiary); }
.preview-pane a { color: var(--primary); }

/* ── 错误态 ───────────────────────────────────────────────────────── */
.error-card {
  padding: 48px 24px;
  text-align: center;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}
.error-card h2 { margin: 0 0 8px; font-size: 18px; color: var(--text); }
.error-card p { margin: 0 0 20px; color: var(--text-secondary); font-size: 14px; }
</style>
