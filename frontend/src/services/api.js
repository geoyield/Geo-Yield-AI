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

/**
 * Centralized Error Handler.
 * Intercepts failed HTTP responses, attempts to parse FastAPI's specific 
 * `detail` field, and throws a normalized JavaScript Error for the UI to catch.
 */
async function handleResponse(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const mensaje = body?.detail || `Error HTTP ${response.status}: Error al conectar con el servidor.`
    throw new Error(mensaje)
  }
  return response.json()
}

/** Fetches available districts. */
export async function obtenerDistritos() {
  const response = await fetch(`${API_BASE_URL}/api/districts`)
  return handleResponse(response)
}

/** Fetches urban zoning classifications (Claus PGM). */
export async function obtenerZonasPgm() {
  const response = await fetch(`${API_BASE_URL}/api/pgm-zones`)
  return handleResponse(response)
}

/** Generates a synchronous AI report (blocks until the full JSON is ready). */
export async function generarInforme(codiDistricte, zonaPgm) {
  const response = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codi_districte: codiDistricte, zona_pgm: zonaPgm }),
  })
  return handleResponse(response)
}

/** Retrieves the full text of a specific legal article for verification. */
export async function obtenerArticulo(fuenteLegal, numeroArticulo) {
  const params = new URLSearchParams({ fuente_legal: fuenteLegal, numero_articulo: numeroArticulo })
  const response = await fetch(`${API_BASE_URL}/api/articles?${params}`)
  return handleResponse(response)
}

/**
 * Geocodes a free-text address. Throws a normalized error (via handleResponse) 
 * if the address falls outside the limits of Barcelona.
 */
export async function geocodificarDireccion(direccion) {
  const params = new URLSearchParams({ direccion })
  const response = await fetch(`${API_BASE_URL}/api/geocode?${params}`)
  return handleResponse(response)
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
  const response = await fetch(`${API_BASE_URL}/api/competitors?${params}`)
  return handleResponse(response)
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

  try {
    const response = await fetch(`${API_BASE_URL}/api/reports/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codi_districte: codiDistricte, zona_pgm: zonaPgm }),
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
          else if (evento.type === 'error') onError?.(evento.detail)
        } catch (e) {
          console.warn('Error parseando bloque SSE:', bloque)
        }
      }
    }
  } catch (error) {
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