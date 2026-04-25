import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside Docker the frontend container reaches the backend via the
// Docker Compose service name "backend" on port 8000.
// The browser (on the host machine) reaches it via localhost:8000 —
// but the Vite proxy runs server-side inside the container, so it
// must resolve using the internal Docker network name, not localhost.
const BACKEND_INTERNAL = 'http://backend:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: BACKEND_INTERNAL,
        changeOrigin: true,
      },
      '/health': {
        target: BACKEND_INTERNAL,
        changeOrigin: true,
      },
    },
  },
})
