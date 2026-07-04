import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: true,
    port: 5174,
    proxy: {
      // Dev proxy: forward /api to the FastAPI backend so the SPA can call it
      // same-origin during development.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  preview: { host: true, port: 4174 },
})
