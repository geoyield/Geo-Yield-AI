import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import { log } from './services/logger'

const app = createApp(App)

// Without these, an uncaught error blanks the page leaving no trace at all.

// 1. Errors inside Vue components (render, lifecycle, watchers).
app.config.errorHandler = (error, instance, info) => {
  log.error('Unhandled error in a Vue component', {
    error,
    component: instance?.$options?.__name || instance?.$?.type?.__name || 'unknown',
    hook: info,
  })
  // Re-emitted so the browser's interactive stack trace is not lost.
  console.error(error)
}

// 2. JavaScript errors outside Vue.
window.addEventListener('error', (event) => {
  log.error('Unhandled JavaScript error', {
    error: event.error || event.message,
    source: event.filename,
    line: event.lineno,
  })
})

// 3. Rejected promises with no catch, the common async/await case.
window.addEventListener('unhandledrejection', (event) => {
  log.error('Unhandled promise rejection', { error: event.reason })
})

app.mount('#app')
