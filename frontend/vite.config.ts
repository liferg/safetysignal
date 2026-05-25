import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// VITE_API_TARGET overrides the dev-server proxy target.
// Local dev: defaults to localhost:8000 (backend running on host).
// Docker dev: set to http://backend:8000 (backend service's hostname).
const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,        // listen on 0.0.0.0 so Docker port-mapping reaches us
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
