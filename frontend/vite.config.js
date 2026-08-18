import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Optional HTTPS for local development.
 *
 * `navigator.geolocation` is only available in a secure context. That means
 * HTTPS, or localhost. A phone on the same Wi-Fi reaches this server on a LAN
 * IP, which is NOT a secure context, so over plain HTTP the browser refuses to
 * hand over a position however the device's Location Services are configured.
 *
 * Run `npm run cert` once, then `npm run dev:https`.
 */
function devHttps() {
  const dir = path.resolve(__dirname, 'certs');
  const key = path.join(dir, 'dev-key.pem');
  const cert = path.join(dir, 'dev-cert.pem');
  if (process.env.HTTPS !== 'true') return false;
  if (!fs.existsSync(key) || !fs.existsSync(cert)) {
    throw new Error(
      'HTTPS requested but frontend/certs is empty. Run `npm run cert` first.',
    );
  }
  return { key: fs.readFileSync(key), cert: fs.readFileSync(cert) };
}

// The dev server proxies /api to FastAPI so the browser sees a single origin,
// which is what the production deployment looks like too. Same-origin keeps the
// refresh-token cookie SameSite=Lax instead of the weaker SameSite=None.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // required to open the app from a phone on the same network
    port: 5173,
    https: devHttps(),
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
