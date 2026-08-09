<script setup>
// 课程封面上传组件：点击/拖拽选图、本地预览、上传进度、取消、移除与错误展示。
// 封面上传成功后立即保存并公开显示，上传与普通课程设置分别提交，
// 避免保存设置时覆盖已上传的封面。
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '../ui/AppIcon.vue'
import { coursesAPI } from '../../api/courses.js'
import { getCourseCoverUrl } from '../../utils/courseCover.js'

const props = defineProps({
  courseId: { type: [Number, String], required: true },
  course: { type: Object, required: true },
})

const emit = defineEmits(['updated', 'busy-change'])

// 前端快速校验（后端仍执行权威校验：扩展名、MIME 与魔数三者同时校验）
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const ALLOWED_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
const ALLOWED_MIMES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

const fileInput = ref(null)
const dragOver = ref(false)
const selectedFile = ref(null) // 正在上传的本地文件
const localPreviewUrl = ref('') // 本地预览对象 URL
const uploading = ref(false)
const uploadProgress = ref(null) // 0~100，无进度事件时为 null（不确定进度）
const uploadError = ref('')
const uploadCancelled = ref(false)
const controller = ref(null)
const coverFailed = ref(false) // 当前封面加载失败 → 纯色占位，不循环重试

const coverUrl = computed(() => getCourseCoverUrl(props.course))
const hasCover = computed(() => !!props.course?.cover)
// 有本地预览时优先显示本地预览（选择后立即可见，不等上传完成）
const previewSrc = computed(() => localPreviewUrl.value || coverUrl.value)

// 课程变化（上传成功/移除后）重置封面加载失败状态
watch(
  () => props.course?.cover,
  () => { coverFailed.value = false },
)

// 卸载时取消进行中的上传并释放本地预览
onBeforeUnmount(() => {
  if (controller.value) controller.value.abort()
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
})

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function validateFile(file) {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ALLOWED_EXTS.includes(ext)) return '仅支持 JPG / PNG / WebP / GIF 图片'
  if (!ALLOWED_MIMES.includes(file.type)) return '该文件类型不受支持'
  if (file.size > MAX_UPLOAD_BYTES) return '封面图片超过 5 MB 大小限制'
  return ''
}

function errorMessage(err) {
  if (err.code === 'ERR_CANCELED') return '上传已取消'
  if (err.code === 'ECONNABORTED') return '上传超时，请检查网络后重试'
  const status = err.response?.status
  if (status === 413) return '封面图片超过 5 MB 大小限制'
  if (status === 415) {
    const code = err.response?.data?.detail?.code
    if (code === 'COVER_CONTENT_INVALID') return '图片内容格式校验失败（魔数校验未通过），请更换文件'
    return '仅支持 JPG / PNG / WebP / GIF 图片'
  }
  if (status === 400) return err.response?.data?.detail?.message || '图片文件无效'
  if (status === 403) return '无权修改该课程的封面'
  if (status === 404) return '课程已不存在'
  return err.response?.data?.detail?.message || '封面上传失败，请重试'
}

async function uploadFile(file) {
  const invalid = validateFile(file)
  if (invalid) {
    uploadError.value = invalid
    return
  }
  selectedFile.value = file
  uploadError.value = ''
  uploadCancelled.value = false
  uploadProgress.value = null
  // 选择后立即生成本地预览
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  localPreviewUrl.value = URL.createObjectURL(file)
  uploading.value = true
  emit('busy-change', true)
  controller.value = new AbortController()
  try {
    const res = await coursesAPI.uploadCourseCover(props.courseId, file, {
      onUploadProgress: (e) => {
        if (e.total) uploadProgress.value = Math.round((e.loaded / e.total) * 100)
        else uploadProgress.value = null
      },
      signal: controller.value.signal,
    })
    // 上传成功：清理本地预览，把新封面交给父组件
    if (localPreviewUrl.value) {
      URL.revokeObjectURL(localPreviewUrl.value)
      localPreviewUrl.value = ''
    }
    selectedFile.value = null
    uploadProgress.value = null
    emit('updated', res.data)
  } catch (err) {
    if (err.code === 'ERR_CANCELED') {
      uploadCancelled.value = true
      uploadError.value = ''
    } else {
      uploadError.value = errorMessage(err)
    }
    // 失败保留本地预览（便于重传），不清空服务器上现有封面
  } finally {
    uploading.value = false
    controller.value = null
    emit('busy-change', false)
  }
}

function onFileChange(e) {
  const file = e.target.files?.[0]
  if (file) uploadFile(file)
  e.target.value = ''
}

function onDrop(e) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadFile(file)
}

function cancelUpload() {
  if (controller.value) controller.value.abort()
}

async function removeCover() {
  uploadError.value = ''
  emit('busy-change', true)
  try {
    await coursesAPI.deleteCourseCover(props.courseId)
    emit('updated', { ...props.course, cover: null })
  } catch (err) {
    uploadError.value = errorMessage(err)
  } finally {
    emit('busy-change', false)
  }
}
</script>

<template>
  <section class="cover-uploader" aria-label="课程封面上传">
    <div class="cover-heading">
      <h3>课程封面</h3>
      <span v-if="uploading" class="cover-busy">正在上传…</span>
    </div>
    <p class="cover-tip">
      <AppIcon name="info" :size="14" />
      支持 JPG、PNG、WebP、GIF，最大 5 MB。封面上传成功后立即保存并公开显示，请勿包含敏感信息。
    </p>

    <!-- 预览：本地预览优先，其次是当前封面；加载失败显示纯色占位 -->
    <div class="cover-preview">
      <img
        v-if="previewSrc && !coverFailed"
        class="cover-preview__img"
        :src="previewSrc"
        :alt="`${props.course?.title || '课程'}封面`"
        @error="coverFailed = true"
      />
      <div v-else class="cover-preview__placeholder">
        <AppIcon name="image" :size="22" />
        <span v-if="!previewSrc" class="cover-preview__empty-text">暂无封面</span>
      </div>
    </div>

    <!-- 上传区：点击选择或拖拽 -->
    <div
      class="cover-dropzone"
      :class="{ dragging: dragOver, disabled: uploading }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.gif,image/jpeg,image/png,image/webp,image/gif"
        class="cover-file-input"
        :disabled="uploading"
        @change="onFileChange"
      />
      <div class="cover-dropzone__inner">
        <AppIcon name="upload" :size="18" />
        <p v-if="uploading" class="cover-dropzone__title">正在上传…</p>
        <p v-else class="cover-dropzone__title">点击选择或拖拽图片到此处</p>
        <p class="cover-dropzone__hint">{{ hasCover ? '上传新图将替换当前封面' : '为课程选择一张封面图片' }}</p>
      </div>
    </div>

    <!-- 上传进度 -->
    <div v-if="uploading || uploadProgress !== null || uploadCancelled" class="cover-progress" aria-live="polite">
      <p v-if="selectedFile" class="cover-file-name">
        {{ selectedFile.name }}（{{ formatBytes(selectedFile.size) }}）
      </p>
      <div v-if="uploading" class="cover-progress-row">
        <div
          class="cover-progress-track"
          role="progressbar"
          aria-label="上传进度"
          :aria-valuenow="uploadProgress ?? 0"
        >
          <div
            class="cover-progress-fill"
            :class="{ indeterminate: uploadProgress === null }"
            :style="{ width: uploadProgress !== null ? uploadProgress + '%' : '100%' }"
          ></div>
        </div>
        <span class="cover-progress-text">{{ uploadProgress !== null ? uploadProgress + '%' : '上传中…' }}</span>
        <button type="button" class="btn-ghost cover-cancel-btn" @click="cancelUpload">取消</button>
      </div>
      <p v-else-if="uploadCancelled" class="cover-cancelled">上传已取消</p>
    </div>

    <p v-if="uploadError" class="cover-error" role="alert">{{ uploadError }}</p>

    <!-- 移除当前封面（历史外链同样可以移除） -->
    <button
      v-if="hasCover && !uploading"
      type="button"
      class="cover-remove-btn"
      @click="removeCover"
    >
      移除封面
    </button>
  </section>
</template>

<style scoped>
.cover-uploader {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border);
  border-radius: var(--radius-card, 12px);
}

.cover-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cover-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}
.cover-busy {
  font-size: var(--text-xs, 12px);
  color: var(--primary);
  font-weight: 500;
}

.cover-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  font-size: var(--text-xs, 12px);
  line-height: 1.6;
  color: var(--text-secondary);
}

/* ── 预览区 ─────────────────────────────────────────────────────── */
.cover-preview {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-control, 8px);
  overflow: hidden;
  background: var(--surface-raised, #f1f5f9);
  border: 1px solid var(--border);
}
.cover-preview__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-preview__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  color: var(--text-tertiary, #94a3b8);
  background: var(--surface-raised, #f1f5f9);
}
.cover-preview__empty-text {
  font-size: var(--text-xs, 12px);
}

/* ── 上传区 ─────────────────────────────────────────────────────── */
.cover-dropzone {
  position: relative;
  border: 1.5px dashed var(--border-strong, #cbd5e1);
  border-radius: var(--radius-control, 8px);
  background: var(--surface);
  transition: border-color 0.15s, background 0.15s;
}
.cover-dropzone.dragging {
  border-color: var(--primary);
  background: var(--primary-soft, #eff6ff);
}
.cover-dropzone.disabled { opacity: 0.6; }
.cover-file-input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.cover-dropzone__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 16px;
  text-align: center;
  cursor: pointer;
  color: var(--text-tertiary, #94a3b8);
}
.cover-dropzone__title {
  margin: 0;
  font-size: var(--text-sm, 13px);
  font-weight: 600;
  color: var(--text);
}
.cover-dropzone__hint {
  margin: 0;
  font-size: var(--text-xs, 12px);
}

/* ── 进度与错误 ─────────────────────────────────────────────────── */
.cover-progress { display: flex; flex-direction: column; gap: 6px; }
.cover-file-name {
  margin: 0;
  font-size: var(--text-xs, 12px);
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}
.cover-progress-row { display: flex; align-items: center; gap: 10px; }
.cover-progress-track {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: var(--border);
  overflow: hidden;
}
.cover-progress-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--primary);
  transition: width 0.2s;
}
.cover-progress-fill.indeterminate {
  animation: cover-indeterminate 1.2s linear infinite;
  background: var(--primary);
}
@keyframes cover-indeterminate {
  0% { width: 20%; margin-left: -20%; }
  100% { width: 20%; margin-left: 100%; }
}
.cover-progress-text {
  font-size: var(--text-xs, 12px);
  color: var(--text-secondary);
  white-space: nowrap;
}
.cover-cancel-btn { flex: none; }
.cover-cancelled {
  margin: 0;
  font-size: var(--text-sm, 13px);
  color: var(--text-secondary);
}
.cover-error {
  margin: 0;
  padding: 8px 12px;
  border: 1px solid var(--danger-soft, #fecaca);
  border-radius: var(--radius-control, 8px);
  background: var(--danger-bg, #fef2f2);
  color: var(--danger, #dc2626);
  font-size: var(--text-sm, 13px);
}

.cover-remove-btn {
  align-self: flex-start;
  padding: 5px 12px;
  background: var(--surface);
  border: 1px solid var(--danger-soft, #fecaca);
  border-radius: var(--radius-control, 8px);
  font-size: var(--text-xs, 12px);
  color: var(--danger, #dc2626);
  cursor: pointer;
}
.cover-remove-btn:hover { background: var(--danger-light, #fef2f2); }
</style>
