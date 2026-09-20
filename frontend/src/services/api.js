import { createLogger, generateTraceId } from './logger'

/**
 * URL base de la API. Se obtiene de las variables de entorno de Vite.
 * @constant {string}
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const log = createLogger('api')

/**
 * Procesa la respuesta de Fetch, parseando el JSON o lanzando un error detallado.
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

/**
 * Obtiene la lista de distritos disponibles.
 */
export async function obtenerDistritos() {
  return request('obtenerDistritos', `${API_BASE_URL}/api/distritos`)
}

/**
 * Obtiene las zonas urbanísticas PGM.
 */
export async function obtenerZonasPgm() {
  return request('obtenerZonasPgm', `${API_BASE_URL}/api/zonas-pgm`)
}

/**
 * Genera un informe de forma síncrona (completo de una vez).
 */
export async function generarInforme(codiDistricte, zonaPgm) {
  return request('generarInforme', `${API_BASE_URL}/api/informes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codi_districte: codiDistricte, zona_pgm: zonaPgm }),
  })
}

/**
 * Obtiene el texto completo de un artículo legal.
 */
export async function obtenerArticulo(fuenteLegal, numeroArticulo) {
  const params = new URLSearchParams({ fuente_legal: fuenteLegal, numero_articulo: numeroArticulo })
  return request('obtenerArticulo', `${API_BASE_URL}/api/articulos?${params}`)
}

/**
 * Geocodifica una dirección de texto libre -- devuelve distrito y zona
 * PGM sugeridos, cuando se pueden determinar. Lanza un error (que
 * handleResponse convierte en Error con el detail del backend) si la
 * dirección no se encuentra dentro de Barcelona.
 *
 * PRIVACY: the address typed by the user is personal data and is never
 * logged -- only the outcome (whether it matched, and which district/zone).
 */
export async function geocodificarDireccion(direccion) {
  const params = new URLSearchParams({ direccion })
  return request('geocodificarDireccion', `${API_BASE_URL}/api/geocodificar?${params}`)
}

/**
 * Obtiene la lista de competidores en un distrito. Si se pasa ubicacion
 * ({lat, lon}), busca por radio alrededor de ese punto exacto en vez de
 * todo el distrito.
 */
export async function obtenerCompetidores(codiDistricte, ubicacion = null) {
  const params = new URLSearchParams({ codi_districte: codiDistricte })
  if (ubicacion) {
    params.set('lat', ubicacion.lat)
    params.set('lon', ubicacion.lon)
  }
  return request('obtenerCompetidores', `${API_BASE_URL}/api/competidores?${params}`)
}

/**
 * Consume el endpoint de informes mediante Server-Sent Events (streaming).
 *
 * Atrapa sus propios errores (red, HTTP, o un bloque SSE mal formado) y los
 * reporta vía el callback onError, en vez de dejarlos propagar hacia quien
 * llama -- así un solo fragmento corrupto del streaming no aborta todo lo
 * demás, solo se registra un aviso y continúa con el resto.
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
    const response = await fetch(`${API_BASE_URL}/api/informes/stream`, {
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

      // Conservamos el último fragmento si está incompleto
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
