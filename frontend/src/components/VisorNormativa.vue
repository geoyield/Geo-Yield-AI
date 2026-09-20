<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { obtenerArticulo } from '../services/api.js'
import { createLogger } from '../services/logger.js'

const log = createLogger('component.visor-normativa')

const props = defineProps({
  articulo: { type: Object, default: null },
})
const emit = defineEmits(['cerrar'])

const cargando = ref(false)
const error = ref(null)
const detalle = ref(null)

const manejarTeclado = (e) => {
  if (e.key === 'Escape' && props.articulo) emit('cerrar')
}

onMounted(() => document.addEventListener('keydown', manejarTeclado))
onUnmounted(() => document.removeEventListener('keydown', manejarTeclado))

watch(
  () => props.articulo,
  async (nuevo) => {
    if (!nuevo) {
      detalle.value = null
      return
    }
    cargando.value = true
    error.value = null
    detalle.value = null

    try {
      detalle.value = await obtenerArticulo(nuevo.fuente_legal, nuevo.numero_articulo)
      log.event('articulo.abierto', {
        fuente_legal: nuevo.fuente_legal,
        numero_articulo: nuevo.numero_articulo,
      })
    } catch (err) {
      // A cited article that cannot be opened points to a hallucinated
      // citation or a stale legal corpus, so it is worth recording.
      log.error('Could not load the legal article', {
        error: err,
        fuente_legal: nuevo.fuente_legal,
        numero_articulo: nuevo.numero_articulo,
        status: err?.status,
      })
      error.value = err.message
    } finally {
      cargando.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="articulo" class="fixed inset-0 z-[1999] bg-ink/70 backdrop-blur-sm" @click="emit('cerrar')" />
    </Transition>

    <Transition
      enter-active-class="transition-transform duration-300 ease-out"
      enter-from-class="translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition-transform duration-200 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="translate-x-full"
    >
      <aside
        v-if="articulo"
        class="fixed inset-y-0 right-0 z-[2000] flex w-full max-w-md flex-col overflow-y-auto border-l border-paper/15 bg-paper text-ink shadow-2xl"
      >
        <header class="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ink/10 bg-paper/95 px-6 py-4 backdrop-blur">
          <div>
            <p class="font-mono text-[11px] tracking-widest text-ink/50 uppercase">Visor de normativa</p>
            <h2 class="font-display text-xl font-semibold text-ink">Artículo {{ articulo.numero_articulo }}</h2>
          </div>
          <button
            @click="emit('cerrar')"
            class="rounded-full px-3 py-1.5 text-lg text-ink/40 transition-colors hover:bg-ink/5 hover:text-ink focus:outline-none focus:ring-2 focus:ring-brass/50"
            aria-label="Cerrar visor"
          >
            ✕
          </button>
        </header>

        <main class="flex-1 px-6 py-5">
          <div v-if="cargando" class="animate-pulse space-y-4">
            <div class="h-3 w-1/3 rounded bg-ink/10"></div>
            <div class="h-6 w-2/3 rounded bg-ink/10"></div>
            <div class="space-y-2 pt-4">
              <div class="h-4 w-full rounded bg-ink/10"></div>
              <div class="h-4 w-5/6 rounded bg-ink/10"></div>
              <div class="h-4 w-4/6 rounded bg-ink/10"></div>
            </div>
          </div>

          <div v-else-if="error" class="rounded-lg border border-rojo/30 bg-rojo/10 px-4 py-3 text-sm text-rojo">
            <span class="font-bold">Error:</span> {{ error }}
          </div>

          <article v-else-if="detalle" class="space-y-4">
            <p class="inline-block rounded bg-brass/10 px-2 py-1 font-mono text-xs text-brass">
              {{ detalle.fuente_legal }}
            </p>
            <h3 class="font-display text-lg font-medium text-ink">{{ detalle.titulo }}</h3>
            <p class="text-sm leading-relaxed whitespace-pre-line text-ink/80">{{ detalle.contenido }}</p>
          </article>
        </main>
      </aside>
    </Transition>
  </Teleport>
</template>