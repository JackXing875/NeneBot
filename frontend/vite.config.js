import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        admin: resolve(__dirname, 'admin.html'),
      },
    },
  },
  server: {
    // In dev, proxy API calls to the FastAPI backend.
    // This lets the frontend use relative URLs (/v1/...) in all environments.
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/admin/api': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
    },
  },
})
