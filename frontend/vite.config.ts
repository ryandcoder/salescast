import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API runs on :8000 (docker compose publishes it); in the container image
// nginx serves the build and proxies /api to the backend service (see nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: true } },
  },
})
