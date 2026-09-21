<script setup>
import { computed, ref } from 'vue'
import FormularioViabilidad from './components/FormularioViabilidad.vue'
import TarjetaVeredicto from './components/TarjetaVeredicto.vue'
import BurbujaChat from './components/BurbujaChat.vue'
import MapaDistrito from './components/MapaDistrito.vue'
import VisorNormativa from './components/VisorNormativa.vue'
import { generarInformeStream } from './services/api.js'
import { createLogger } from './services/logger.js'

const log = createLogger('app.informe')

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

async function onGenerar({ codiDistricte, zonaPgm, ubicacion }) {
  const inicio = performance.now()
  cargando.value = true
  error.value = null
  codiDistrictePedido.value = codiDistricte
  ubicacionPedida.value = ubicacion

  datosDistrito.value = null
  respuestaLegal.value = ''
  articulosCitados.value = []
  textoSintesis.value = ''
  semaforoConfirmado.value = null
  resumenConfirmado.value = null

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

      log.event('informe.completado', {
        codi_districte: codiDistricte,
        zona_pgm: zonaPgm,
        semaforo: evento.semaforo,
        duration_ms: performance.now() - inicio,
        articulos_citados: articulosCitados.value.length,
      })
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
        <FormularioViabilidad :cargando="cargando" @generar="onGenerar" />
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