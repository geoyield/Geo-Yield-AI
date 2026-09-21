<script setup>
import { computed } from 'vue'

const props = defineProps({
  informe: { type: Object, required: true },
})

const COLORES = {
  rojo: { bg: 'bg-rojo', ring: 'ring-rojo/40', texto: 'Riesgo alto', textoClase: 'text-rojo' },
  ambar: { bg: 'bg-ambar', ring: 'ring-ambar/40', texto: 'Viable con reservas', textoClase: 'text-brass' },
  verde: { bg: 'bg-verde', ring: 'ring-verde/40', texto: 'Condiciones favorables', textoClase: 'text-verde' },
}

const veredicto = computed(() => COLORES[props.informe.semaforo] ?? COLORES.ambar)

const formatoNumero = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 })
const formatoMoneda = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })

const datos = computed(() => props.informe.datos_distrito ?? {})
</script>

<template>
  <div class="rounded-lg border border-paper/15 bg-paper text-ink shadow-xl">
    <!-- Cabecera de expediente -->
    <div class="flex items-start justify-between gap-4 border-b border-ink/10 px-6 py-4">
      <div>
        <p class="font-mono text-[11px] tracking-widest text-ink/50 uppercase">Expediente de viabilidad</p>
        <h2 class="font-display text-2xl font-semibold text-ink">
          {{ datos.nom_districte ?? 'Distrito sin datos' }}
        </h2>
      </div>

      <!-- Semáforo vertical: solo la luz del veredicto encendida -->
      <div class="flex flex-col items-center gap-1.5 rounded-md bg-ink px-2.5 py-2.5" aria-hidden="true">
        <span
          v-for="color in ['rojo', 'ambar', 'verde']"
          :key="color"
          class="h-3.5 w-3.5 rounded-full transition"
          :class="
            color === informe.semaforo
              ? [COLORES[color].bg, 'shadow-[0_0_10px_2px]', COLORES[color].ring]
              : 'bg-paper/10'
          "
        />
      </div>
    </div>

    <!-- Veredicto en prosa -->
    <div class="border-b border-ink/10 px-6 py-4">
      <p class="mb-1 text-xs font-medium tracking-wide uppercase" :class="veredicto.textoClase">
        {{ veredicto.texto }}
      </p>
      <p class="text-sm leading-relaxed text-ink/80">{{ informe.resumen }}</p>
    </div>

    <!-- Ficha de datos -->
    <dl class="grid grid-cols-2 gap-x-4 gap-y-3 px-6 py-4 text-sm sm:grid-cols-4">
      <div>
        <dt class="text-[11px] tracking-wide text-ink/45 uppercase">Renta media</dt>
        <dd class="font-mono font-medium">{{ datos.renta_media != null ? formatoMoneda.format(datos.renta_media) : '—' }}</dd>
      </div>
      <div>
        <dt class="text-[11px] tracking-wide text-ink/45 uppercase">Afluencia diaria</dt>
        <dd class="font-mono font-medium">{{ datos.daily_foot_traffic != null ? formatoNumero.format(datos.daily_foot_traffic) : '—' }}</dd>
      </div>
      <div>
        <dt class="text-[11px] tracking-wide text-ink/45 uppercase">Competidores</dt>
        <dd class="font-mono font-medium">{{ datos.total_competitors != null ? formatoNumero.format(datos.total_competitors) : '—' }}</dd>
      </div>
      <div>
        <dt class="text-[11px] tracking-wide text-ink/45 uppercase">Índice de oportunidad</dt>
        <dd class="font-mono font-medium">{{ datos.opportunity_score != null ? `${datos.opportunity_score} / 100` : '—' }}</dd>
      </div>
    </dl>
  </div>
</template>
