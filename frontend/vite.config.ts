/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Relative base keeps `dist/index.html` openable directly from disk, which
  // matters for reviewing the built artifact without a server.
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  test: {
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    environmentMatchGlobs: [['src/**/*.test.tsx', 'jsdom']],
    environment: 'node',
  },
});
