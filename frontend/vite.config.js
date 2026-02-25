
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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          const modulePath = id.split('node_modules/')[1];
          const parts = modulePath.split('/');
          const pkg = parts[0].startsWith('@') ? `${parts[0]}/${parts[1]}` : parts[0];

          if (pkg === 'react' || pkg === 'react-dom' || pkg === 'scheduler') return 'vendor-react';
          if (pkg === 'react-router' || pkg === 'react-router-dom') return 'vendor-router';
          if (pkg === 'lucide-react') return 'vendor-icons';
          return 'vendor-misc';
        },
      },
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
