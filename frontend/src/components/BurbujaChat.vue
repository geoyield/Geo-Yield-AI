<script setup>
import { computed } from 'vue'

const props = defineProps({
  informe: { type: Object, required: true },
})

const emit = defineEmits(['ver-articulo'])

const tieneArticulos = computed(() => {
  return Array.isArray(props.informe.articulos_citados) && props.informe.articulos_citados.length > 0
})
</script>

<template>
  <div class="flex gap-4">
    <div
      class="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-brass/40 bg-ink text-brass shadow-sm font-display text-sm"
      aria-hidden="true"
    >
      GY
    </div>

    <div class="flex-1 space-y-4 rounded-2xl rounded-tl-sm border border-paper/10 bg-ink-light px-5 py-4 shadow-sm">
      <header>
        <p class="mb-1.5 font-mono text-[10px] font-semibold tracking-widest text-brass uppercase">
          Fundamento legal
        </p>
        <p class="text-sm leading-relaxed whitespace-pre-line text-paper/90">
          {{ informe.respuesta_legal }}
        </p>
      </header>

      <footer v-if="tieneArticulos" class="flex flex-wrap gap-2 border-t border-paper/10 pt-4">
        <button
          v-for="articulo in informe.articulos_citados"
          :key="`${articulo.fuente_legal}-${articulo.numero_articulo}`"
          type="button"
          @click="emit('ver-articulo', articulo)"
          class="flex items-center gap-1.5 rounded-full border border-brass/30 bg-brass/10 px-3 py-1 font-mono text-xs text-brass transition-all hover:bg-brass hover:text-ink hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brass"
          title="Abrir visor de normativa"
        >
          Art. {{ articulo.numero_articulo }}
        </button>
      </footer>
    </div>
  </div>
</template>