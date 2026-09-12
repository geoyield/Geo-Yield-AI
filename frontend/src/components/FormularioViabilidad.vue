<script setup>
import { onMounted, ref, watch } from 'vue'
import { geocodificarDireccion, obtenerDistritos, obtenerZonasPgm } from '../services/api.js'

const emit = defineEmits(['generar'])
const props = defineProps({
  cargando: { type: Boolean, default: false },
  // Precarga desde el chat: cuando la extracción de intención resuelve
  // distrito/zona/ubicación (total o parcialmente), se reflejan aquí --
  // el usuario sigue pudiendo corregirlos, igual que con la búsqueda por
  // dirección de este mismo formulario.
  distritoInicial: { type: Number, default: null },
  zonaInicial: { type: String, default: null },
  ubicacionInicial: { type: Object, default: null },
  mensajeInicial: { type: Object, default: null },
})

const distritos = ref([])
const zonas = ref([])
const codiDistricte = ref(null)
const zonaPgm = ref(null)
const errorCarga = ref(null)

// Búsqueda por dirección: autocompleta distrito y zona, pero nunca los
// oculta ni los bloquea -- el usuario siempre puede corregirlos a mano,
// sobre todo porque la zona no siempre se puede determinar con certeza.
const direccionInput = ref('')
const buscandoDireccion = ref(false)
const mensajeDireccion = ref(null) // { tipo: 'exito' | 'aviso' | 'error', texto }

// Coordenadas exactas de la última dirección geocodificada con éxito,
// para centrar el mapa en el punto real en vez del distrito completo.
// Se limpia si el usuario cambia el distrito a mano después de buscar
// -- el punto ya no correspondería con seguridad a lo seleccionado.
const ubicacionGeocodificada = ref(null) // { lat, lon } | null
const distritoDeLaUbicacion = ref(null)

watch(codiDistricte, (nuevo) => {
  if (distritoDeLaUbicacion.value !== null && nuevo !== distritoDeLaUbicacion.value) {
    ubicacionGeocodificada.value = null
    distritoDeLaUbicacion.value = null
  }
})

// Precarga desde el chat -- mismo tratamiento que si el usuario hubiera
// usado el campo de búsqueda de este formulario.
watch(
  () => props.distritoInicial,
  (nuevo) => {
    if (nuevo) {
      codiDistricte.value = nuevo
      distritoDeLaUbicacion.value = nuevo
    }
  },
)
watch(
  () => props.zonaInicial,
  (nuevo) => {
    if (nuevo) zonaPgm.value = nuevo
  },
)
watch(
  () => props.ubicacionInicial,
  (nuevo) => {
    if (nuevo) ubicacionGeocodificada.value = nuevo
  },
)
watch(
  () => props.mensajeInicial,
  (nuevo) => {
    if (nuevo) mensajeDireccion.value = nuevo
  },
)

onMounted(async () => {
  try {
    const [listaDistritos, listaZonas] = await Promise.all([obtenerDistritos(), obtenerZonasPgm()])
    distritos.value = listaDistritos
    zonas.value = listaZonas
  } catch (err) {
    errorCarga.value = 'No se pudieron cargar los distritos y zonas. Comprueba que la API esté arrancada.'
  }
})

async function buscarDireccion() {
  const direccion = direccionInput.value.trim()
  if (!direccion) return

  buscandoDireccion.value = true
  mensajeDireccion.value = null

  try {
    const resultado = await geocodificarDireccion(direccion)

    ubicacionGeocodificada.value = { lat: resultado.lat, lon: resultado.lon }

    if (resultado.codi_districte) {
      codiDistricte.value = resultado.codi_districte
      distritoDeLaUbicacion.value = resultado.codi_districte
    }
    if (resultado.zona_pgm) zonaPgm.value = resultado.zona_pgm

    if (resultado.codi_districte && resultado.zona_pgm) {
      mensajeDireccion.value = {
        tipo: 'exito',
        texto: `Distrito y zona detectados a partir de: ${resultado.direccion_encontrada}`,
      }
    } else if (resultado.codi_districte) {
      mensajeDireccion.value = {
        tipo: 'aviso',
        texto: 'Distrito detectado, pero no se pudo determinar la zona con precisión -- selecciónala tú abajo.',
      }
    } else {
      mensajeDireccion.value = {
        tipo: 'aviso',
        texto: 'Dirección encontrada, pero no se pudo determinar el distrito automáticamente -- selecciónalo tú abajo.',
      }
    }
  } catch (err) {
    mensajeDireccion.value = {
      tipo: 'error',
      texto: 'No se encontró esa dirección dentro de Barcelona. Puedes seleccionar distrito y zona manualmente.',
    }
  } finally {
    buscandoDireccion.value = false
  }
}

function onSubmit() {
  if (codiDistricte.value && zonaPgm.value) {
    emit('generar', {
      codiDistricte: codiDistricte.value,
      zonaPgm: zonaPgm.value,
      ubicacion: ubicacionGeocodificada.value,
    })
  }
}
</script>

<template>
  <form @submit.prevent="onSubmit" class="space-y-5">
    <div v-if="errorCarga" class="rounded border border-rojo/40 bg-rojo/10 px-4 py-3 text-sm text-paper">
      {{ errorCarga }}
    </div>

    <div>
      <label for="direccion" class="mb-1.5 block text-xs font-medium tracking-wide text-paper/60 uppercase">
        Buscar por dirección (opcional)
      </label>
      <div class="flex gap-2">
        <input
          id="direccion"
          v-model="direccionInput"
          type="text"
          placeholder="p. ej. Carrer de Sant Pau 1, Barcelona"
          class="flex-1 rounded border border-paper/20 bg-ink-light px-3 py-2.5 text-paper placeholder:text-paper/30 focus:border-brass focus:ring-1 focus:ring-brass focus:outline-none"
          @keydown.enter.prevent="buscarDireccion"
        />
        <button
          type="button"
          @click="buscarDireccion"
          :disabled="buscandoDireccion || !direccionInput.trim()"
          class="shrink-0 rounded border border-brass/30 bg-brass/10 px-4 py-2.5 text-sm text-brass transition hover:bg-brass/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {{ buscandoDireccion ? 'Buscando…' : 'Buscar' }}
        </button>
      </div>
      <p
        v-if="mensajeDireccion"
        class="mt-2 rounded px-3 py-2 text-xs"
        :class="{
          'bg-verde/10 text-verde': mensajeDireccion.tipo === 'exito',
          'bg-brass/10 text-brass': mensajeDireccion.tipo === 'aviso',
          'bg-rojo/10 text-rojo': mensajeDireccion.tipo === 'error',
        }"
      >
        {{ mensajeDireccion.texto }}
      </p>
    </div>

    <div>
      <label for="distrito" class="mb-1.5 block text-xs font-medium tracking-wide text-paper/60 uppercase">
        Distrito
      </label>
      <select
        id="distrito"
        v-model="codiDistricte"
        required
        class="w-full rounded border border-paper/20 bg-ink-light px-3 py-2.5 text-paper focus:border-brass focus:ring-1 focus:ring-brass focus:outline-none"
      >
        <option :value="null" disabled>Selecciona un distrito</option>
        <option v-for="d in distritos" :key="d.codi_districte" :value="d.codi_districte">
          {{ d.nom_districte }}
        </option>
      </select>
    </div>

    <div>
      <label for="zona" class="mb-1.5 block text-xs font-medium tracking-wide text-paper/60 uppercase">
        Zona urbanística (PGM)
      </label>
      <select
        id="zona"
        v-model="zonaPgm"
        required
        class="w-full rounded border border-paper/20 bg-ink-light px-3 py-2.5 text-paper focus:border-brass focus:ring-1 focus:ring-brass focus:outline-none"
      >
        <option :value="null" disabled>Selecciona una zona</option>
        <option v-for="z in zonas" :key="z.id" :value="z.id">{{ z.nombre }}</option>
      </select>
      <p class="mt-1.5 text-xs text-paper/40">
        Un distrito puede abarcar varias zonas PGM -- indícala tú si la conoces.
      </p>
    </div>

    <button
      type="submit"
      :disabled="cargando || !codiDistricte || !zonaPgm"
      class="w-full rounded bg-brass px-4 py-2.5 font-medium text-ink transition hover:bg-brass/90 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {{ cargando ? 'Generando informe…' : 'Generar informe de viabilidad' }}
    </button>
  </form>
</template>