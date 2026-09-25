/**
 * ==============================================================================
 * VUE APPLICATION ENTRY POINT (BOOTSTRAP)
 * ==============================================================================
 * File: frontend/src/main.js
 * 
 * This is the primary JavaScript file executed by the browser (via Vite).
 * It acts as the bridge between the static HTML file and the reactive Vue framework.
 */

import { createApp } from 'vue'

// Injects global CSS (including Tailwind base styles) into the Vite build graph
import './style.css'

// Imports the root orchestrator component
import App from './App.vue'

// 1. createApp(App): Initializes a new Vue 3 application instance using the Factory Pattern.
// 2. .mount('#app'): Injects the reactive component tree into the empty <div id="app"> 
//    found in index.html, officially bringing the UI to life.
createApp(App).mount('#app')
