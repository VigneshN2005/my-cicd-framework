// vitest.config.js
// Test settings for the React frontend.
// The coverage gate comes from pipeline-config.yml: the pipeline passes
// testing.frontend_coverage_min in as FRONTEND_COVERAGE_MIN, and the run
// fails if line coverage drops below it.

import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const minCoverage = Number(process.env.FRONTEND_COVERAGE_MIN ?? 70)

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/setupTests.js', 'src/**/*.test.{js,jsx}'],
      reporter: ['text', 'json-summary'],
      thresholds: { lines: minCoverage },
    },
  },
})
