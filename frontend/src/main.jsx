import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// The service worker caches the app shell only; it never touches /api, so an
// offline device can open the app but cannot record attendance.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // A failed registration only costs offline shell caching; the app works.
    });
  });

  // A tab left open across a deploy keeps running the old JavaScript, which
  // shows up as fixed behaviour "not working". The new worker calls
  // skipWaiting, so when it takes control the page is stale by definition:
  // reload once to pick up the new build.
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });
}
