import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Tauri expects a fixed dev port; the engine allows the shell origins in its CORS list (skin_editor/server.py SHELL_ORIGINS).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: '127.0.0.1' },
  build: { chunkSizeWarningLimit: 6000 },
})
