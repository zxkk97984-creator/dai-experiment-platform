import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  // 流程会写入考试/提交状态；复用同一数据库自动重试会产生假失败。
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: process.env.CI ? [] : [],  // 外部提供 API/前端
})
