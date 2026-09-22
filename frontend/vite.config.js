import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // Forzamos la caché dentro del proyecto para evitar errores de permisos en WSL
  cacheDir: './node_modules/.vite',
})