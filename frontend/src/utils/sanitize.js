/**
 * Lightweight HTML sanitizer — strips dangerous tags/attributes
 * without external dependencies. Use before v-html.
 */
const DANGEROUS_TAGS = /<(\s*\/?\s*)(script|iframe|object|embed|form|input|link|meta|base|applet|frame|frameset|ilayer|layer|bgsound|title|style)[\s>]/gi
const EVENT_ATTRS = /\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]*)/gi
const JS_URL = /(href|src|action)\s*=\s*["']\s*javascript:/gi

export function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') return ''
  return html
    .replace(DANGEROUS_TAGS, (match) => '&lt;' + match.slice(1))
    .replace(EVENT_ATTRS, '')
    .replace(JS_URL, '$1="#"')
}
