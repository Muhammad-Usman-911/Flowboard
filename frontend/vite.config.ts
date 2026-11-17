/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// In development the React app runs on Vite (port 5183) and forwards API and WebSocket
// calls to FastAPI, so the browser only ever talks to one origin (no CORS needed).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_PROXY_TARGET ?? 'http://localhost:8103'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: Number(env.VITE_PORT ?? 5183),
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/ws': { target: apiTarget.replace(/^http/, 'ws'), ws: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
