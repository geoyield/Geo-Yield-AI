/**
 * Structured frontend logger.
 *
 * Emits the same JSON schema as the Python logger
 * (backend/observability/logging_config.py), batched to POST /api/logs since
 * the browser cannot reach CloudWatch without exposing AWS credentials.
 *
 * Logging must never break the app: everything is wrapped in try/catch, the
 * buffer is capped, retries are bounded and shipping disables itself after
 * sustained failures.
 *
 * @module services/logger
 */

import {
  ENVIRONMENT,
  EVENTS_PER_BATCH,
  FAILURES_BEFORE_DISABLE,
  FLUSH_INTERVAL_MS,
  IS_PRODUCTION,
  LEVELS,
  LOGS_ENDPOINT,
  MAX_BUFFERED_EVENTS,
  MAX_EVENTS_PER_REQUEST,
  MAX_RETRIES,
  MIN_LEVEL,
  REMOTE_ENABLED,
  SERVICE,
  VERSION
} from "../constants/logger.constant"

let buffer = []
let flushTimer = null
let consecutiveFailures = 0
let shippingDisabled = false

/** Falls back to Math.random in insecure contexts, where crypto is absent. */
function randomId(length = 16) {
  try {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID().replace(/-/g, '').slice(0, length)
    }
  } catch {
    // Falls through.
  }
  let out = ''
  while (out.length < length) {
    out += Math.random().toString(16).slice(2)
  }
  return out.slice(0, length)
}

/** Correlation id sent as the `X-Request-ID` header by services/api.js. */
export function generateTraceId() {
  return randomId(16)
}

/** Stable per tab. sessionStorage throws in private mode, hence the catch. */
const SESSION_ID = (() => {
  const KEY = 'geoyield_session_id'
  try {
    const stored = sessionStorage.getItem(KEY)
    if (stored) return stored
    const fresh = randomId(16)
    sessionStorage.setItem(KEY, fresh)
    return fresh
  } catch {
    return randomId(16)
  }
})()

function serialiseError(error) {
  if (!error) return undefined
  if (error instanceof Error) {
    return {
      type: error.name || 'Error',
      message: error.message || String(error),
      stack: error.stack ? String(error.stack).slice(0, 8000) : undefined,
    }
  }
  return { type: typeof error, message: String(error) }
}

function toConsole(event) {
  const method =
    event.level === 'ERROR' || event.level === 'CRITICAL'
      ? 'error'
      : event.level === 'WARNING'
        ? 'warn'
        : 'log'

  if (!IS_PRODUCTION) {
    const extras = { ...(event.context || {}) }
    if (event.error) extras.error = event.error
    if (event.duration_ms !== undefined) extras.duration_ms = event.duration_ms
    console[method](
      `[${event.level}] ${event.logger}: ${event.message}`,
      Object.keys(extras).length ? extras : '',
    )
  } else {
    console[method](JSON.stringify(event))
  }
}

function enqueue(event) {
  if (!REMOTE_ENABLED || shippingDisabled) return

  buffer.push(event)

  // Drops the oldest: on overflow the recent events are the relevant ones.
  if (buffer.length > MAX_BUFFERED_EVENTS) {
    buffer = buffer.slice(-MAX_BUFFERED_EVENTS)
  }

  // Errors go immediately: they may be the last thing before the tab closes.
  if (buffer.length >= EVENTS_PER_BATCH || LEVELS[event.level] >= LEVELS.ERROR) {
    flush()
    return
  }

  if (flushTimer === null) {
    flushTimer = setTimeout(flush, FLUSH_INTERVAL_MS)
  }
}

async function sendBatch(batch, attempt = 0) {
  try {
    const response = await fetch(LOGS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(batch),
      keepalive: true,
    })

    // 429 and 413 are final answers; retrying would only make it worse.
    if (response.status === 429 || response.status === 413) {
      consecutiveFailures = 0
      return
    }

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    consecutiveFailures = 0
  } catch {
    if (attempt < MAX_RETRIES) {
      await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt))
      return sendBatch(batch, attempt + 1)
    }

    consecutiveFailures += 1
    if (consecutiveFailures >= FAILURES_BEFORE_DISABLE) {
      shippingDisabled = true
      buffer = []
      // console directly, not the logger: reporting a logger failure through
      // the logger would feed the loop we are trying to break.
      console.warn(
        '[logger] Log shipping disabled after repeated failures. The app continues normally.',
      )
    }
  }
}

/** @param {boolean} [useBeacon] sendBeacon is the only transport that survives tab close. */
export function flush(useBeacon = false) {
  if (flushTimer !== null) {
    clearTimeout(flushTimer)
    flushTimer = null
  }

  if (!REMOTE_ENABLED || shippingDisabled || buffer.length === 0) return

  const batch = buffer.slice(0, MAX_EVENTS_PER_REQUEST)
  buffer = buffer.slice(MAX_EVENTS_PER_REQUEST)

  if (useBeacon) {
    try {
      const blob = new Blob([JSON.stringify(batch)], { type: 'application/json' })
      if (navigator.sendBeacon(LOGS_ENDPOINT, blob)) return
    } catch {
      // Falls back to fetch below.
    }
  }

  sendBatch(batch)
}

// More reliable than beforeunload on mobile, which may never fire.
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush(true)
  })
  window.addEventListener('pagehide', () => flush(true))
}

/**
 * @param {string} name Becomes the `logger` field, e.g. `api.informes`.
 * @param {object} [baseContext] Context merged into every event.
 */
export function createLogger(name, baseContext = {}) {
  /** @param {object} [options] { error, event, duration_ms, trace_id, ...context } */
  function emit(level, message, options = {}) {
    try {
      if (LEVELS[level] < MIN_LEVEL) return

      const { error, event, duration_ms, trace_id, ...context } = options
      const mergedContext = { ...baseContext, ...context }

      const payload = {
        timestamp: new Date().toISOString(),
        level,
        service: SERVICE,
        env: ENVIRONMENT,
        version: VERSION,
        logger: name,
        message: String(message ?? ''),
        session_id: SESSION_ID,
      }

      if (trace_id) payload.trace_id = trace_id
      if (event) payload.event = event
      if (duration_ms !== undefined) payload.duration_ms = Math.round(duration_ms * 100) / 100
      if (error) payload.error = serialiseError(error)
      if (Object.keys(mergedContext).length) payload.context = mergedContext

      toConsole(payload)
      enqueue(payload)
    } catch {
      // Logging never takes the app down.
    }
  }

  return {
    debug: (message, options) => emit('DEBUG', message, options),
    info: (message, options) => emit('INFO', message, options),
    warn: (message, options) => emit('WARNING', message, options),
    error: (message, options) => emit('ERROR', message, options),

    /** Named user action, e.g. `logger.event('informe.generado', {...})`. */
    event: (eventName, options = {}) => {
      // Extracted, not forwarded, or they would become `context` keys.
      const { level = 'INFO', message, ...rest } = options
      emit(level, message || eventName, { ...rest, event: eventName })
    },

    /** Child logger with extra context, like pino's `child()`. */
    child: (extraContext) => createLogger(name, { ...baseContext, ...extraContext }),

    name,
    sessionId: SESSION_ID,
  }
}

/** Default application logger. */
export const log = createLogger('app')

export default log
