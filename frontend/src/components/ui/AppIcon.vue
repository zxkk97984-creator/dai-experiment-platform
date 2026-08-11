<script setup>
// AppIcon：语义图标原语。全部图标为本地打包的 Iconify 数据（Remix/Logos），
// 运行时不依赖 Iconify API。禁止用 emoji、自制 SVG 或 CSS 图案代替真实图标。

import { computed } from 'vue'
import { Icon } from '@iconify/vue'

// ── 本地图标数据（仅导入语义键实际用到的图标）─────────────────────────
import home from '@iconify-icons/ri/home-5-line'
import course from '@iconify-icons/ri/graduation-cap-line'
import assignment from '@iconify-icons/ri/file-list-3-line'
import code from '@iconify-icons/ri/code-s-slash-line'
import exam from '@iconify-icons/ri/file-edit-line'
import experiment from '@iconify-icons/ri/flask-line'
import notification from '@iconify-icons/ri/notification-3-line'
import search from '@iconify-icons/ri/search-line'
import calendar from '@iconify-icons/ri/calendar-line'
import clock from '@iconify-icons/ri/time-line'
import check from '@iconify-icons/ri/check-line'
import close from '@iconify-icons/ri/close-line'
import warning from '@iconify-icons/ri/alert-line'
import info from '@iconify-icons/ri/information-line'
import image from '@iconify-icons/ri/image-line'
import upload from '@iconify-icons/ri/upload-2-line'
import arrowRight from '@iconify-icons/ri/arrow-right-line'
import chevronRight from '@iconify-icons/ri/arrow-right-s-line'
import chevronDown from '@iconify-icons/ri/arrow-down-s-line'
import book from '@iconify-icons/ri/book-2-line'
import clipboard from '@iconify-icons/ri/clipboard-line'
import chart from '@iconify-icons/ri/bar-chart-2-line'
import user from '@iconify-icons/ri/user-3-line'
import logout from '@iconify-icons/ri/logout-box-r-line'
import more from '@iconify-icons/ri/more-2-fill'
import cube from '@iconify-icons/ri/box-3-line'
import python from '@iconify-icons/logos/python'
import plus from '@iconify-icons/ri/add-line'
import settings from '@iconify-icons/ri/settings-3-line'
import edit from '@iconify-icons/ri/edit-line'
import eye from '@iconify-icons/ri/eye-line'
import eyeOff from '@iconify-icons/ri/eye-off-line'
import copy from '@iconify-icons/ri/file-copy-line'
import chevronUp from '@iconify-icons/ri/arrow-up-s-line'
import move from '@iconify-icons/ri/drag-move-2-line'
import dragHandle from '@iconify-icons/ri/menu-line'
import trash from '@iconify-icons/ri/delete-bin-line'
import back from '@iconify-icons/ri/arrow-left-line'
import video from '@iconify-icons/ri/video-line'
import send from '@iconify-icons/ri/send-plane-line'
import save from '@iconify-icons/ri/save-3-line'
import draft from '@iconify-icons/ri/draft-line'
import trophy from '@iconify-icons/ri/trophy-line'
import pie from '@iconify-icons/ri/pie-chart-line'
import download from '@iconify-icons/ri/download-2-line'
import refresh from '@iconify-icons/ri/refresh-line'
import brain from '@iconify-icons/ri/brain-line'

// 语义键 → { data: 图标数据, set: 来源图标集 }；set 透传为 data-set 属性便于测试与排查
const ICONS = {
  home: { data: home, set: 'ri' },
  cube: { data: cube, set: 'ri' },
  course: { data: course, set: 'ri' },
  assignment: { data: assignment, set: 'ri' },
  code: { data: code, set: 'ri' },
  exam: { data: exam, set: 'ri' },
  experiment: { data: experiment, set: 'ri' },
  notification: { data: notification, set: 'ri' },
  search: { data: search, set: 'ri' },
  calendar: { data: calendar, set: 'ri' },
  clock: { data: clock, set: 'ri' },
  check: { data: check, set: 'ri' },
  close: { data: close, set: 'ri' },
  warning: { data: warning, set: 'ri' },
  info: { data: info, set: 'ri' },
  image: { data: image, set: 'ri' },
  upload: { data: upload, set: 'ri' },
  'arrow-right': { data: arrowRight, set: 'ri' },
  'chevron-right': { data: chevronRight, set: 'ri' },
  'chevron-down': { data: chevronDown, set: 'ri' },
  book: { data: book, set: 'ri' },
  clipboard: { data: clipboard, set: 'ri' },
  chart: { data: chart, set: 'ri' },
  user: { data: user, set: 'ri' },
  logout: { data: logout, set: 'ri' },
  more: { data: more, set: 'ri' },
  python: { data: python, set: 'logos' },
  plus: { data: plus, set: 'ri' },
  settings: { data: settings, set: 'ri' },
  edit: { data: edit, set: 'ri' },
  eye: { data: eye, set: 'ri' },
  'eye-off': { data: eyeOff, set: 'ri' },
  copy: { data: copy, set: 'ri' },
  'chevron-up': { data: chevronUp, set: 'ri' },
  move: { data: move, set: 'ri' },
  drag: { data: dragHandle, set: 'ri' },
  trash: { data: trash, set: 'ri' },
  back: { data: back, set: 'ri' },
  video: { data: video, set: 'ri' },
  send: { data: send, set: 'ri' },
  save: { data: save, set: 'ri' },
  draft: { data: draft, set: 'ri' },
  trophy: { data: trophy, set: 'ri' },
  pie: { data: pie, set: 'ri' },
  download: { data: download, set: 'ri' },
  refresh: { data: refresh, set: 'ri' },
  brain: { data: brain, set: 'ri' },
}

const props = defineProps({
  /** 语义键，如 home / course / python */
  name: { type: String, required: true },
  /** 数字（px）或字符串（如 '1.25em'） */
  size: { type: [Number, String], default: 20 },
  /** 提供时图标作为图像暴露给辅助技术 */
  label: { type: String, default: null },
})

const icon = computed(() => ICONS[props.name] || null)

if (import.meta.env.DEV && !icon.value) {
  console.warn(`[AppIcon] 未知图标语义键: ${props.name}`)
}
</script>

<template>
  <Icon
    v-if="icon"
    :icon="icon.data"
    :data-set="icon.set"
    :data-icon="name"
    :width="size"
    :height="size"
    class="app-icon"
    :aria-hidden="label ? 'false' : 'true'"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
  />
</template>
