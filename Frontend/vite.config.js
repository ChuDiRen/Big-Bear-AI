import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/langgraph': {
        target: process.env.VITE_LANGGRAPH_PROXY_TARGET ?? 'http://127.0.0.1:2026',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/langgraph/, ''),
      },
    },
  },
})
