/**
 * ==============================================================================
 * BUILD TOOL CONFIGURATION (VITE)
 * ==============================================================================
 * File: frontend/vite.config.js
 * 
 * Vite is the module bundler and development server. It compiles Vue Single 
 * File Components (.vue) and Tailwind CSS into highly optimized static assets 
 * (HTML, vanilla JS, CSS) for production, while providing ultra-fast Hot Module 
 * Replacement (HMR) during development.
 */
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // DevOps / Environment Fix:
  // Forces Vite's pre-bundling cache to reside inside the local project folder 
  // instead of the default global OS directory. This prevents fatal file permission 
  // errors (EACCES) when developing inside WSL (Windows Subsystem for Linux).
  cacheDir: './node_modules/.vite',
})