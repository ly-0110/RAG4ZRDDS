import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// 后端地址：默认 make serve 的 127.0.0.1:8000；
// 后端改端口时设 RAG_BACKEND_URL=http://127.0.0.1:9000 npm run dev 即可。
const BACKEND_URL = process.env.RAG_BACKEND_URL || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // 开发联调代理（2026-08-29 接线修复）：前端请求 /query 等 API 路径
  // 由 Vite 转发到后端，避免跨域与"打到 dev server 自己 404"的问题。
  server: {
    proxy: {
      '/query': { target: BACKEND_URL, changeOrigin: true },
      '/sources': { target: BACKEND_URL, changeOrigin: true },
      '/healthz': { target: BACKEND_URL, changeOrigin: true },
    },
  },
})
