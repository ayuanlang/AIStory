
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
// Forced Reload Update
export default defineConfig({
  plugins: [
    react({
      babel: {
        compact: true,
        generatorOpts: {
          compact: true,
        },
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: '0.0.0.0', // Bind to all interfaces
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Use IP to avoid localhost DNS issues
        changeOrigin: true,
        secure: false,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
