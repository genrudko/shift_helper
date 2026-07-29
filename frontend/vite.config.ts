import { defineConfig } from 'vite';

export default defineConfig({
  base: '/static/univer-v2/',
  build: {
    outDir: '../src/shift_helper/static/univer-v2',
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        entryFileNames: 'journal-v2.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith('.css')
            ? 'journal-v2.css'
            : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
