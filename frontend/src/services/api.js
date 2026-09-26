import { createLogger, generateTraceId } from './logger'

/**
 * ==============================================================================
 * API GATEWAY & NETWORK SERVICE LAYER
 * ==============================================================================
 * File: frontend/src/services/api.js
 *
 * Abstracts all HTTP communication with the FastAPI Backend.
 * Implements centralized error handling and manual Server-Sent Events (SSE)
 * parsing for AI LLM Streaming.
 */

/**
* Base API URL derived from Vite's environment variables.
 * @constant {string}
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const log = createLogger('api')

/**
 * Centralized Error Handler.
 * Intercepts failed HTTP responses, attempts to parse FastAPI's specific
 * `detail` field, and throws a normalized JavaScript Error for the UI to catch.
 */
async function handleResponse(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const mensaje = body?.detail || `Error HTTP ${response.status}: Error al conectar con el servidor.`
    const error = new Error(mensaje)
    error.status = response.status
    throw error
  }
  return response.json()
}

/**
 * fetch wrapper that adds correlation, timing and error logging.
 *
 * The trace id travels in `X-Request-ID` and the backend propagates it to
 * every log line of that request, so a failed call can be followed through
 * to the RAG, agent and database lines it produced.
 *
 * @param {string} operation
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function request(operation, url, options = {}) {
  const traceId = generateTraceId()
  const start = performance.now()

  try {
    const response = await fetch(url, {
      ...options,
      headers: { ...(options.headers || {}), 'X-Request-ID': traceId },
    })
    const data = await handleResponse(response)

    log.debug(`${operation} ok`, {
      trace_id: traceId,
      duration_ms: performance.now() - start,
      operation,
      status: response.status,
    })
    return data
  } catch (error) {
    log.error(`${operation} failed`, {
      error,
      trace_id: traceId,
      duration_ms: performance.now() - start,
      operation,
      status: error.status,
    })
    throw error
  }
}

/** Fetches available districts. */
export async function obtenerDistritos() {
  return request('obtenerDistritos', `${API_BASE_URL}/api/districts`)
}

/** Fetches urban zoning classifications (Claus PGM). */
export async function obtenerZonasPgm() {
  return request('obtenerZonasPgm', `${API_BASE_URL}/api/pgm-zones`)
}

/** Generates a synchronous AI report (blocks until the full JSON is ready). */
export async function generarInforme(codiDistricte, zonaPgm) {
  return request('generarInforme', `${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codi_districte: codiDistricte, zona_pgm: zonaPgm }),
  })
}

/** Retrieves the full text of a specific legal article for verification. */
export async function obtenerArticulo(fuenteLegal, numeroArticulo) {
  const params = new URLSearchParams({ fuente_legal: fuenteLegal, numero_articulo: numeroArticulo })
  return request('obtenerArticulo', `${API_BASE_URL}/api/articles?${params}`)
}

/**
 * Geocodes a free-text address -- returns the suggested district and PGM
 * zone, when they can be determined. Throws an error (which handleResponse
 * turns into an Error carrying the backend's detail) if the address is not
 * found within Barcelona.
 *
 * PRIVACY: the address typed by the user is personal data and is never
 * logged -- only the outcome (whether it matched, and which district/zone).
 */
export async function geocodificarDireccion(direccion) {
  const params = new URLSearchParams({ direccion })
  return request('geocodificarDireccion', `${API_BASE_URL}/api/geocode?${params}`)
}

/**
 * Fetches commercial competitors. If coordinates {lat, lon} are provided,
 * performs a geospatial radius search instead of a district-wide search.
 */
export async function obtenerCompetidores(codiDistricte, ubicacion = null) {
  const params = new URLSearchParams({ codi_districte: codiDistricte })
  if (ubicacion) {
    params.set('lat', ubicacion.lat)
    params.set('lon', ubicacion.lon)
  }
  return request('obtenerCompetidores', `${API_BASE_URL}/api/competitors?${params}`)
}

/**
 * LLM Streaming Engine (Server-Sent Events via POST).
 *
 * Note: Browsers' native EventSource API only supports GET requests. Because
 * we must send a complex JSON payload (POST), we manually consume the network
 * byte stream using the Fetch API's Response Reader.
 */
export async function generarInformeStream(codiDistricte, zonaPgm, callbacks = {}) {
  const { onDatos, onToken, onDone, onError } = callbacks

  const traceId = generateTraceId()
  const start = performance.now()
  const streamLog = log.child({
    trace_id: traceId,
    codi_districte: codiDistricte,
    zona_pgm: zonaPgm,
  })

  try {
    const response = await fetch(`${API_BASE_URL}/api/reports/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': traceId },
      body: JSON.stringify({ codi_districte: codiDistricte, zona_pgm: zonaPgm }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail || `Error ${response.status} al llamar a la API`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let corruptBlocks = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const bloques = buffer.split('\n\n')

      // Network Chunking Safety: Keep the last fragment if it's incomplete
      // to avoid breaking JSON.parse on the next iteration.
      buffer = bloques.pop() ?? ''

      for (const bloque of bloques) {
        if (!bloque.startsWith('data: ')) continue

        try {
          const evento = JSON.parse(bloque.slice(6))
          if (evento.type === 'datos') onDatos?.(evento)
          else if (evento.type === 'token') onToken?.(evento.text)
          else if (evento.type === 'done') onDone?.(evento)
          else if (evento.type === 'error') {
            streamLog.error('Backend reported an error during streaming', {
              detail: evento.detail,
            })
            onError?.(evento.detail)
          }
        } catch (error) {
          corruptBlocks += 1
          streamLog.warn('Malformed SSE block, ignored', {
            error,
            fragment: String(bloque).slice(0, 200),
          })
        }
      }
    }

    streamLog.event('informe.generado', {
      duration_ms: performance.now() - start,
      corrupt_blocks: corruptBlocks,
    })
  } catch (error) {
    streamLog.error('Report streaming failed', {
      error,
      duration_ms: performance.now() - start,
    })
    onError?.(error.message)
  }
}

/**
 * Conversational AI Streaming Engine.
 *
 * Handles conversational specific events like 'aclaracion' (geocoding failed,
 * asking user for input) and 'ubicacion' (geocoding succeeded, centering the map).
 */
export async function chatInformeStream(mensaje, callbacks = {}) {
  const { onAclaracion, onUbicacion, onDatos, onToken, onDone, onError } = callbacks

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/informe/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail || `Error ${response.status} al llamar a la API`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const bloques = buffer.split('\n\n')
      buffer = bloques.pop() ?? ''

      for (const bloque of bloques) {
        if (!bloque.startsWith('data: ')) continue

        try {
          const evento = JSON.parse(bloque.slice(6))
          if (evento.type === 'aclaracion') onAclaracion?.(evento)
          else if (evento.type === 'ubicacion') onUbicacion?.(evento)
          else if (evento.type === 'datos') onDatos?.(evento)
          else if (evento.type === 'token') onToken?.(evento.text)
          else if (evento.type === 'done') onDone?.(evento)
          else if (evento.type === 'error') onError?.(evento.detail)
        } catch (e) {
          console.warn('Error parseando bloque SSE del chat:', bloque)
        }
      }
    }
  } catch (error) {
    onError?.(error.message)
  }
}