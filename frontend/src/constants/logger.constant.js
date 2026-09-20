/**
 * Configuration for frontend/src/services/logger.js.
 *
 * Vite only exposes MODE/DEV/PROD plus VITE_-prefixed vars --
 * `import.meta.env.ENV` does not exist and would leave IS_PRODUCTION false.
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const LOGS_ENDPOINT = `${API_BASE_URL}/api/logs`

export const SERVICE = 'geoyield-frontend'
export const ENVIRONMENT = import.meta.env.MODE || 'development'
export const VERSION = import.meta.env.VITE_APP_VERSION || '0.0.0'

/** In production events ship to the API; elsewhere console only. */
export const IS_PRODUCTION = import.meta.env.PROD

/** Numeric values match Python's logging module. */
export const LEVELS = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50 }

export const MIN_LEVEL =
  LEVELS[(import.meta.env.VITE_LOG_LEVEL || '').toUpperCase()] ??
  (IS_PRODUCTION ? LEVELS.INFO : LEVELS.DEBUG)

export const REMOTE_ENABLED =
  import.meta.env.VITE_LOG_REMOTE === 'true' ||
  (IS_PRODUCTION && import.meta.env.VITE_LOG_REMOTE !== 'false')

export const FLUSH_INTERVAL_MS = 5000
export const EVENTS_PER_BATCH = 20
/** Cap so an error loop against a dead backend cannot exhaust tab memory. */
export const MAX_BUFFERED_EVENTS = 200
export const MAX_RETRIES = 2
export const FAILURES_BEFORE_DISABLE = 5
/** Matches MAX_EVENTS_PER_BATCH in backend/api/schemas/logs.py. */
export const MAX_EVENTS_PER_REQUEST = 100
