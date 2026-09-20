<script setup>
import { computed, ref } from 'vue'
import FormularioViabilidad from './components/FormularioViabilidad.vue'
import TarjetaVeredicto from './components/TarjetaVeredicto.vue'
import BurbujaChat from './components/BurbujaChat.vue'
import MapaDistrito from './components/MapaDistrito.vue'
import VisorNormativa from './components/VisorNormativa.vue'
import { chatInformeStream, generarInformeStream } from './services/api.js'

const SEMAFOROS_VALIDOS = ['verde', 'ambar', 'rojo']

const cargando = ref(false)
const error = ref(null)
const articuloSeleccionado = ref(null)

const codiDistrictePedido = ref(null)
const ubicacionPedida = ref(null)
const datosDistrito = ref(null)
const respuestaLegal = ref('')
const articulosCitados = ref([])
const textoSintesis = ref('')

// El backend ya parsea el semáforo con tolerancia a puntuación (ver
// _parsear_semaforo_y_resumen), pero mientras el texto va llegando en
// vivo, aquí se hace una detección propia y más simple para revelar el
// veredicto cuanto antes. Si esa detección en vivo llegara a fallar por
// cualquier motivo no previsto, semaforoConfirmado (relleno por
// onDone con el resultado ya parseado del backend) corrige la pantalla
// en cuanto el streaming termina -- así nunca se queda colgada en
// "Generando el veredicto" para siempre, pase lo que pase con el texto.
const semaforoConfirmado = ref(null)
const resumenConfirmado = ref(null)

const semaforo = computed(() => {
  if (semaforoConfirmado.value) return semaforoConfirmado.value
  const primeraLinea = textoSintesis.value
    .split('\n')[0]
    ?.trim()
    .toLowerCase()
    .replace(/[.!:;,]+$/, '') // el LLM a veces añade puntuación al final (p. ej. "ambar.")
  return SEMAFOROS_VALIDOS.includes(primeraLinea) ? primeraLinea : null
})

const resumen = computed(() => {
  if (resumenConfirmado.value !== null) return resumenConfirmado.value
  if (!semaforo.value) return ''
  return textoSintesis.value.split('\n').slice(1).join('\n').trim()
})

const tieneResultados = computed(() => datosDistrito.value || respuestaLegal.value)

function reiniciarResultados() {
  error.value = null
  datosDistrito.value = null
  respuestaLegal.value = ''
  articulosCitados.value = []
  textoSintesis.value = ''
  semaforoConfirmado.value = null
  resumenConfirmado.value = null
}

async function onGenerar({ codiDistricte, zonaPgm, ubicacion }) {
  cargando.value = true
  codiDistrictePedido.value = codiDistricte
  ubicacionPedida.value = ubicacion
  reiniciarResultados()

  await generarInformeStream(codiDistricte, zonaPgm, {
    onDatos: (evento) => {
      datosDistrito.value = evento.datos_distrito
      respuestaLegal.value = evento.respuesta_legal
      articulosCitados.value = evento.articulos_citados
      cargando.value = false
    },
    onToken: (texto) => {
      textoSintesis.value += texto
    },
    onError: (detail) => {
      error.value = detail
      cargando.value = false
    },
    onDone: (evento) => {
      semaforoConfirmado.value = evento.semaforo
      resumenConfirmado.value = evento.resumen
      cargando.value = false
    },
  })
}

// --- Chat conversacional ---
// No es un agente: extrae dirección + pregunta específica de la frase
// libre, y en cuanto resuelve distrito+zona, reutiliza exactamente el
// mismo pipeline de streaming que el formulario manual. Si no puede
// resolver todo, entrega lo que sí pudo al formulario (como precarga),
// que sirve de red de seguridad -- igual que ya hace la búsqueda por
// dirección de ese mismo formulario.
const mensajeChat = ref('')
const procesandoChat = ref(false)
const distritoDesdeChat = ref(null)
const zonaDesdeChat = ref(null)
const ubicacionDesdeChat = ref(null)
const mensajeAclaracionChat = ref(null)

async function onEnviarChat() {
  const mensaje = mensajeChat.value.trim()
  if (!mensaje) return

  procesandoChat.value = true
  cargando.value = true
  distritoDesdeChat.value = null
  zonaDesdeChat.value = null
  ubicacionDesdeChat.value = null
  mensajeAclaracionChat.value = null
  codiDistrictePedido.value = null
  ubicacionPedida.value = null
  reiniciarResultados()

  await chatInformeStream(mensaje, {
    onAclaracion: (evento) => {
      mensajeAclaracionChat.value = { tipo: 'aviso', texto: evento.mensaje }
      if (evento.codi_districte) distritoDesdeChat.value = evento.codi_districte
      if (evento.zona_pgm) zonaDesdeChat.value = evento.zona_pgm
      if (evento.lat != null && evento.lon != null) {
        ubicacionDesdeChat.value = { lat: evento.lat, lon: evento.lon }
      }
      procesandoChat.value = false
      cargando.value = false
    },
    onUbicacion: (evento) => {
      codiDistrictePedido.value = evento.codi_districte
      ubicacionPedida.value = { lat: evento.lat, lon: evento.lon }
    },
    onDatos: (evento) => {
      datosDistrito.value = evento.datos_distrito
      respuestaLegal.value = evento.respuesta_legal
      articulosCitados.value = evento.articulos_citados
      cargando.value = false
      procesandoChat.value = false
    },
    onToken: (texto) => {
      textoSintesis.value += texto
    },
    onError: (detail) => {
      error.value = detail
      cargando.value = false
      procesandoChat.value = false
    },
    onDone: (evento) => {
      semaforoConfirmado.value = evento.semaforo
      resumenConfirmado.value = evento.resumen
      cargando.value = false
      procesandoChat.value = false
    },
  })
}
</script>

<template>
  <main class="fondo-plano min-h-screen">
    <div class="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16">
      <header class="mb-10 text-center sm:text-left">
        <p class="mb-2 font-mono text-xs font-bold tracking-[0.2em] text-brass uppercase">Geo-Yield-AI</p>
        <h1 class="font-display text-3xl font-semibold text-paper sm:text-5xl">
          Dossier de viabilidad de hostelería
        </h1>
        <p class="mt-4 text-sm leading-relaxed text-paper/70 sm:max-w-2xl sm:text-base">
          Selecciona un distrito y una zona urbanística de Barcelona para generar un informe
          que cruza la normativa legal vigente con datos socioeconómicos reales.
        </p>
      </header>

      <section class="mb-8 rounded-xl border border-paper/15 bg-ink-light/50 p-6 shadow-lg backdrop-blur-sm">
        <label for="chat" class="mb-1.5 block text-xs font-medium tracking-wide text-paper/60 uppercase">
          Cuéntanos qué quieres hacer
        </label>
        <div class="flex gap-2">
          <textarea
            id="chat"
            v-model="mensajeChat"
            rows="2"
            placeholder="p. ej. Quiero abrir un bar en Carrer de Sant Pau 1, ¿me lo recomiendas?"
            class="flex-1 resize-none rounded border border-paper/20 bg-ink-light px-3 py-2.5 text-paper placeholder:text-paper/30 focus:border-brass focus:ring-1 focus:ring-brass focus:outline-none"
          />
          <button
            type="button"
            @click="onEnviarChat"
            :disabled="procesandoChat || !mensajeChat.trim()"
            class="shrink-0 rounded bg-brass px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-brass/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {{ procesandoChat ? 'Analizando…' : 'Enviar' }}
          </button>
        </div>
        <p class="mt-2 text-xs text-paper/40">
          O usa el formulario manual de abajo si prefieres elegir distrito y zona tú mismo.
        </p>
      </section>

      <section class="mb-8 rounded-xl border border-paper/15 bg-ink-light/50 p-6 shadow-lg backdrop-blur-sm">
        <FormularioViabilidad
          :cargando="cargando"
          :distrito-inicial="distritoDesdeChat"
          :zona-inicial="zonaDesdeChat"
          :ubicacion-inicial="ubicacionDesdeChat"
          :mensaje-inicial="mensajeAclaracionChat"
          @generar="onGenerar"
        />
      </section>

      <div v-if="error" class="mb-8 flex items-center gap-3 rounded-lg border border-rojo/40 bg-rojo/10 px-5 py-4 text-sm text-paper shadow-sm">
        {{ error }}
      </div>

      <div v-if="cargando && !tieneResultados" class="flex items-center justify-center gap-3 py-12 text-sm text-paper/60">
        <span class="h-2.5 w-2.5 animate-ping rounded-full bg-brass" />
        Consultando la normativa y analizando datos del distrito...
      </div>

      <section v-if="tieneResultados" class="space-y-6 animate-fade-in">
        <TarjetaVeredicto
          v-if="semaforo"
          :informe="{ semaforo, resumen, datos_distrito: datosDistrito || {} }"
        />
        <div v-else class="flex items-center gap-3 rounded-xl border border-paper/15 bg-paper px-6 py-5 text-sm text-ink/60 shadow-sm">
          <span class="h-2 w-2 animate-ping rounded-full bg-brass" />
          Generando el veredicto…
        </div>

        <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
          <MapaDistrito
            v-if="datosDistrito"
            class="h-full min-h-[300px] overflow-hidden rounded-xl border border-paper/15 shadow-sm"
            :codi-districte="codiDistrictePedido"
            :nom-districte="datosDistrito.nom_districte"
            :ubicacion="ubicacionPedida"
          />

          <BurbujaChat
            v-if="respuestaLegal"
            :informe="{ respuesta_legal: respuestaLegal, articulos_citados: articulosCitados }"
            @ver-articulo="articuloSeleccionado = $event"
          />
        </div>
      </section>
    </div>

    <VisorNormativa :articulo="articuloSeleccionado" @cerrar="articuloSeleccionado = null" />
  </main>
</template>

<style>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
  animation: fadeIn 0.4s ease-out forwards;
}
</style>