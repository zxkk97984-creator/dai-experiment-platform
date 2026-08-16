<script setup>
// CourseIdentity：课程身份块——92–96px 浅色图标 tile（或课程封面图）+ 标题 + 元信息插槽。
// Python 类课程用 Python 品牌图标（Logos 集）；其余按稳定标题关键词选库图标。
// 有封面 URL 且未加载失败时优先显示封面，否则回退语义图标与纯色背景。

import { computed, ref, watch } from 'vue'
import AppIcon from '../ui/AppIcon.vue'

const props = defineProps({
  title: { type: String, default: '' },
  meta: { type: String, default: '' },
  coverUrl: { type: String, default: '' },
})

const coverFailed = ref(false)
// 封面地址变化时重置失败状态（替换封面后新 URL 重新尝试）
watch(() => props.coverUrl, () => { coverFailed.value = false })

// 稳定关键词 → 语义图标（顺序优先，命中即选）
const KEYWORD_ICONS = [
  { re: /机器|数据|分析|挖掘|人工智能|深度|统计|算法/, icon: 'chart' },
  { re: /编程|代码|开发|软件|网络|系统|前端|后端/, icon: 'code' },
  { re: /实验|实践|工程|项目/, icon: 'experiment' },
  { re: /数学|概率|线性代数|微积分/, icon: 'clipboard' },
  { re: /英语|语言|写作|人文|历史/, icon: 'book' },
]

// 图标类别 → 浅色 tile 色调（保持浅色、非渐变，贴近参考图的多彩图标块）
const TILE_TONES = {
  python: 'tone-blue',
  chart: 'tone-purple',
  code: 'tone-blue',
  experiment: 'tone-green',
  clipboard: 'tone-orange',
  book: 'tone-blue',
  course: 'tone-blue',
}

const iconName = computed(() => {
  const title = props.title || ''
  if (/python/i.test(title)) return 'python'
  const hit = KEYWORD_ICONS.find((k) => k.re.test(title))
  return hit ? hit.icon : 'course'
})

const tileTone = computed(() => TILE_TONES[iconName.value] || 'tone-blue')
</script>

<template>
  <div class="course-identity">
    <img
      v-if="coverUrl && !coverFailed"
      class="course-identity__cover"
      :src="coverUrl"
      :alt="`${title}课程封面`"
      @error="coverFailed = true"
    />
    <span v-else class="course-identity__icon" :class="tileTone" aria-hidden="true">
      <AppIcon :name="iconName" :size="28" />
    </span>
    <div class="course-identity__text">
      <h3 class="course-identity__title">{{ title }}</h3>
      <div class="course-identity__meta">
        <slot>{{ meta }}</slot>
      </div>
    </div>
  </div>
</template>

<style scoped>
.course-identity {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

/* 封面与图标占位同尺寸，加载失败回退不产生布局跳动 */
.course-identity__icon,
.course-identity__cover {
  flex-shrink: 0;
  width: 94px;
  height: 94px;
  border-radius: var(--radius-control, 7px);
}

.course-identity__icon {
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.course-identity__cover {
  display: block;
  object-fit: contain;
  background: var(--surface-raised, var(--surface-subtle));
}

/* 浅色 tile 色调（非渐变） */
.course-identity__icon.tone-blue   { background: var(--accent-soft); color: var(--accent); }
.course-identity__icon.tone-purple { background: var(--info-bg);  color: var(--info); }
.course-identity__icon.tone-green  { background: var(--success-bg);  color: var(--success); }
.course-identity__icon.tone-orange { background: var(--warning-bg);  color: var(--warning); }

.course-identity__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.course-identity__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--fg);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.course-identity__meta {
  font-size: var(--text-sm);
  color: var(--muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
