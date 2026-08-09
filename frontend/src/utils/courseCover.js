// 课程封面地址工具：受管存储 key → 公开媒体 URL；历史 URL 原样兼容
//
// - `covers/` 开头：新受管 key，转公开媒体端点并带版本参数 v（替换封面后
//   v 变化，旧缓存自动失效）；
// - 其他值：历史 http(s)/协议相对/根路径 URL 或未识别相对路径，原样返回，
//   由图片加载失败回退占位图兜底。

export function getCourseCoverUrl(course) {
  const cover = course?.cover
  if (!cover) return ''
  if (!cover.startsWith('covers/')) return cover
  return `/api/v1/media/course-covers/${encodeURIComponent(course.id)}?v=${encodeURIComponent(cover)}`
}
