// TASK-023（F-26）回归：学生首页等核心页面在 1024/1280/1440/1920 无水平溢出。
// 断言 document 与主内容 scrollWidth <= clientWidth + 1（+1 容忍亚像素/滚动条取整），
// 并保存各视口截图（test-results/，gitignored）作为回归证据。
// 需要已种子的环境（student / Passw0rd!，scripts/seed_e2e.py）。
import { test, expect } from '@playwright/test'

const VIEWPORTS = [
  { width: 1024, height: 900 },
  { width: 1280, height: 900 },
  { width: 1440, height: 900 },
  { width: 1920, height: 900 },
]

/** 返回 document/main 的溢出度量与越过视口的真实元素（排除 fixed 与父级裁剪） */
async function measureOverflow(page) {
  return page.evaluate(() => {
    const doc = document.documentElement
    const vw = doc.clientWidth
    const main = document.querySelector('main')
    const realOffenders = []
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect()
      if (r.right <= vw + 1 && r.left >= -1) continue
      if (getComputedStyle(el).position === 'fixed') continue
      // 被 overflow 裁剪的装饰元素（如空态 glow）不构成真实溢出
      let p = el.parentElement
      let clipped = false
      while (p) {
        const o = getComputedStyle(p).overflow
        if (o === 'hidden' || o === 'clip' || o === 'auto' || o === 'scroll') { clipped = true; break }
        p = p.parentElement
      }
      if (clipped) continue
      realOffenders.push({
        tag: el.tagName,
        cls: typeof el.className === 'string' ? el.className.slice(0, 60) : '',
        right: Math.round(r.right),
      })
    }
    return {
      doc: { scrollW: doc.scrollWidth, clientW: doc.clientWidth },
      main: main ? { scrollW: main.scrollWidth, clientW: main.clientWidth } : null,
      offenders: realOffenders.slice(0, 5),
    }
  })
}

test.describe('学生核心页面水平溢出回归（TASK-023）', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student/)
  })

  for (const vp of VIEWPORTS) {
    test(`学生首页 ${vp.width}px 无水平溢出`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto('/student')
      await page.waitForLoadState('networkidle')
      const m = await measureOverflow(page)
      expect(m.doc.scrollW, `document 溢出: ${JSON.stringify(m)}`).toBeLessThanOrEqual(m.doc.clientW + 1)
      if (m.main) {
        expect(m.main.scrollW, `main 溢出: ${JSON.stringify(m)}`).toBeLessThanOrEqual(m.main.clientW + 1)
      }
      expect(m.offenders, `越界元素: ${JSON.stringify(m.offenders)}`).toEqual([])
      await page.screenshot({ path: `test-results/dashboard-${vp.width}.png` })
    })
  }
})
