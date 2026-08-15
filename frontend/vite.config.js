import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// API 代理目标：默认 8000，可用 VITE_API_PROXY_TARGET 覆盖
// （如 8000 被占用、后端改跑 8001 时：VITE_API_PROXY_TARGET=http://localhost:8001 npm run dev）
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
