import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server proxies /api to FastAPI so the browser sees a single origin,
// which is what the production deployment looks like too. Same-origin keeps the
// refresh-token cookie SameSite=Lax instead of the weaker SameSite=None.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // required to open the app from a phone on the same network
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
