<!-- 
==============================================================================
GEOSPATIAL VISUALIZATION COMPONENT
==============================================================================
File: frontend/src/components/DistrictMap.vue

Renders the interactive map using Vue-Leaflet. Dynamically fetches and plots 
competitors using client-side clustering for performance optimization.
-->
<script setup>
import { ref, watch } from 'vue'
import L from 'leaflet'

// ---------------------------------------------------------------------------
// LEGACY MODULE BRIDGING
// ---------------------------------------------------------------------------
// The 'leaflet.markercluster' plugin predates modern ES Modules and blindly 
// expects 'L' to exist on the global Window object. In Vite, modules are 
// scoped tightly. By explicitly injecting 'L' into globalThis, we bridge the 
// gap and prevent "L is not defined" crashes.
globalThis.L = L

import 'leaflet/dist/leaflet.css'
import 'vue-leaflet-markercluster/dist/style.css'
import { LMap, LTileLayer, LMarker, LPopup } from '@vue-leaflet/vue-leaflet'
import { LMarkerClusterGroup } from 'vue-leaflet-markercluster'
import { obtenerCompetidores } from '../services/api.js'

const props = defineProps({
  codiDistricte: { type: Number, required: true },
  nomDistricte: { type: String, default: '' },
  // If provided, triggers a 'Radius Search' instead of a 'District Search'
  ubicacion: { type: Object, default: null }, // { lat, lon } | null
})

// Fallback coordinate to prevent rendering a broken "gray ocean" map 
// if a district has zero competitors in the database.
const CENTRO_BARCELONA = [41.3851, 2.1734]

const cargando = ref(false)
const error = ref(null)
const centro = ref(CENTRO_BARCELONA)
const competidores = ref([])
const totalReal = ref(0)
const modo = ref('distrito') // 'distrito' | 'radio'
const radioMetros = ref(null)
const zoom = ref(14)
const mostrarCompetidores = ref(true)

async function cargarCompetidores() {
  cargando.value = true
  error.value = null
  try {
    const datos = await obtenerCompetidores(props.codiDistricte, props.ubicacion)
    centro.value = datos.centro ? [datos.centro.lat, datos.centro.lng] : CENTRO_BARCELONA
    competidores.value = datos.competidores
    totalReal.value = datos.total
    modo.value = datos.modo
    radioMetros.value = datos.radio_metros

    // UX Polish: A 500m radius search requires a closer zoom (16) than 
    // a full district overview (14) to be visually useful.
    zoom.value = datos.modo === 'radio' ? 16 : 14
  } catch (err) {
    error.value = 'No se pudieron cargar los competidores del distrito.'
  } finally {
    cargando.value = false
  }
}

// Reactively reload data if the user changes the district OR the specific address
watch(() => [props.codiDistricte, props.ubicacion], cargarCompetidores, { immediate: true, deep: true })

// ---------------------------------------------------------------------------
// SEMANTIC MAP DESIGN (CSS-IN-JS)
// ---------------------------------------------------------------------------
// Overrides the default neon-colored clusters from Leaflet with our custom 
// Design Tokens (Brass, Ink, Paper) to maintain visual coherence.
function crearIconoCluster(cluster) {
  const cantidad = cluster.getChildCount()
  return L.divIcon({
    html: `<div style="background:#B8863D;color:#152238;border-radius:9999px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-weight:600;font-family:'IBM Plex Mono',monospace;border:2px solid #F5F1E8;">${cantidad}</div>`,
    className: '',
    iconSize: [36, 36],
  })
}

// Custom "You Are Here" marker. Uses semantic Red for high contrast against 
// the Brass clusters.
const iconoUbicacion = L.divIcon({
  html: '<div style="width:18px;height:18px;border-radius:9999px;background:#9C4A3C;border:3px solid #F5F1E8;box-shadow:0 0 0 6px rgba(156,74,60,0.25);"></div>',
  className: '',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-paper/15">
    <div class="flex items-center justify-between border-b border-paper/10 bg-ink-light px-4 py-2.5">
      <p class="text-xs tracking-wide text-paper/60 uppercase">
        {{ nomDistricte || 'Mapa del distrito' }}
        <span v-if="modo === 'radio'" class="text-paper/40">
          · {{ totalReal }} competidores en un radio de {{ radioMetros }}m
        </span>
        <span v-else-if="totalReal" class="text-paper/40"> · {{ totalReal }} competidores en la base de datos </span>
      </p>
      <button
        @click="mostrarCompetidores = !mostrarCompetidores"
        class="rounded border border-brass/30 bg-brass/10 px-2.5 py-1 text-xs text-brass transition hover:bg-brass/20"
      >
        {{ mostrarCompetidores ? 'Ocultar competidores' : 'Mostrar competidores' }}
      </button>
    </div>

    <div v-if="error" class="bg-rojo/10 px-4 py-3 text-sm text-paper">{{ error }}</div>

    <div class="relative h-80 w-full">
      <div v-if="cargando" class="absolute inset-0 z-[1000] flex items-center justify-center bg-ink/60 text-sm text-paper/70">
        Cargando competidores…
      </div>
      <l-map :key="centro.join(',')" :zoom="zoom" :center="centro" :use-global-leaflet="true" class="h-full w-full">
        <l-tile-layer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        <l-marker v-if="modo === 'radio'" :lat-lng="centro" :icon="iconoUbicacion" :z-index-offset="1000">
          <l-popup><span class="text-sm font-medium">Tu ubicación</span></l-popup>
        </l-marker>

        <l-marker-cluster-group v-if="mostrarCompetidores" :icon-create-function="crearIconoCluster">
          <l-marker v-for="c in competidores" :key="c.id_global" :lat-lng="[c.lat, c.lng]">
            <l-popup><span class="text-sm">{{ c.nom_activitat }}</span></l-popup>
          </l-marker>
        </l-marker-cluster-group>
      </l-map>
    </div>

    <p v-if="totalReal > competidores.length" class="border-t border-paper/10 bg-ink-light px-4 py-2 text-xs text-paper/40">
      Mostrando {{ competidores.length }} de {{ totalReal }} competidores reales
      {{ modo === 'radio' ? 'en el radio.' : 'del distrito.' }}
    </p>
  </div>
</template>