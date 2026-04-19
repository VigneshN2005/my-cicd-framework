// vite.config.js
// This file configures Vite - our build tool
// Vite converts React code → browser-ready HTML/CSS/JS

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],  // enables React support in Vite

  server: {
    port: 3001,        // frontend runs on port 3001 locally

    // This connects frontend to backend
    // Any request to /api gets forwarded to FastAPI on port 8000
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },

  build: {
    outDir: 'dist',    // CI/CD pipeline looks for this folder
                       // Docker copies this folder to serve
  },

  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}']
  }
})