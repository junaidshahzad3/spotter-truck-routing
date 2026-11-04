import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: 5173,
    // In dev, the Django API runs on :8000; same-origin /api avoids CORS entirely.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  worker: { format: 'es' },
  build: {
    chunkSizeWarningLimit: 1500, // maplibre-gl alone is ~1 MB minified
  },
})
