/**
 * HTML 安全清洗 — 基于 DOMPurify
 * 用于 v-html 前的 XSS 防护
 */
import DOMPurify from 'dompurify'

export function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') return ''
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li',
      'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'table', 'thead', 'tbody', 'tr', 'td', 'th',
      'span', 'div', 'img', 'blockquote', 'hr', 'sup', 'sub', 'del'],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'target'],
  })
}
