import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    css: true,
    globals: true,
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
  },
})
