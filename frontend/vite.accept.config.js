import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 独立验收环境前端配置：5174 端口，代理到 8010 验收后端
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8010',
        changeOrigin: true,
      },
    },
  },
})
