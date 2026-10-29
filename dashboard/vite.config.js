import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'https://04ozfc8hhk.execute-api.us-east-1.amazonaws.com',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
