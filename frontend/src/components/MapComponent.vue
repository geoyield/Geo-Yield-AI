<template>
  <div class="map-container">
    <!-- Mapa Leaflet con vue-leaflet -->
    <l-map
      ref="map"
      v-model:zoom="zoom"
      :center="center"
      :bounds="bounds"
      :options="mapOptions"
      class="map-wrapper"
      @click="onMapClick"
    >
      <!-- Capa base de OpenStreetMap -->
      <l-tile-layer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        layer-type="base"
        name="OpenStreetMap"
        :attribution="attribution"
      />

      <!-- Capa de movilidad (simulada) -->
      <l-tile-layer
        v-if="activeLayers.includes('mobility')"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        :opacity="0.2"
        name="Movilidad"
      />

      <!-- Marcadores de competidores -->
      <l-marker
        v-for="competitor in competitors"
        :key="competitor.id"
        :lat-lng="competitor.coords"
        @click="onMarkerClick(competitor)"
      >
        <l-popup>
          <div class="popup-content">
            <h4>{{ competitor.name }}</h4>
            <p>{{ competitor.type }}</p>
            <p class="popup-distance">A {{ competitor.distance }}m</p>
          </div>
        </l-popup>
      </l-marker>

      <!-- Marcador de ubicación seleccionada -->
      <l-marker
        v-if="selectedLocation"
        :lat-lng="selectedLocation.coords"
      >
        <l-popup>
          <div class="popup-content selected">
            <h4>📍 Ubicación Analizada</h4>
            <p>{{ selectedLocation.name }}</p>
          </div>
        </l-popup>
      </l-marker>
    </l-map>

    <!-- Overlay de información -->
    <div v-if="selectedLocation" class="location-overlay">
      <div class="overlay-header">
        <h3>{{ selectedLocation.name }}</h3>
        <button @click="clearSelection" class="close-btn">×</button>
      </div>
      <div class="overlay-content">
        <div class="metric">
          <span class="metric-label">Score de Viabilidad</span>
          <span class="metric-value" :class="scoreClass">{{ viabilityScore }}/100</span>
        </div>
        <div class="metric">
          <span class="metric-label">Competencia Cercana</span>
          <span class="metric-value">{{ nearbyCompetitors }} locales</span>
        </div>
        <div class="metric">
          <span class="metric-label">Flujo Peatonal</span>
          <span class="metric-value">{{ footTraffic }} personas/día</span>
        </div>
        <!-- TODO: Agregar gráfico de movilidad horaria -->
        <!-- TODO: Agregar alertas de normativa urbanística PGOU -->
      </div>
      <button class="analyze-btn" @click="analyzeLocation">
        Analizar en detalle
      </button>
    </div>

    <!-- Controles del mapa -->
    <div class="map-controls">
      <button 
        v-for="layer in mapLayers" 
        :key="layer.id"
        @click="toggleLayer(layer.id)"
        :class="['layer-toggle', { active: activeLayers.includes(layer.id) }]"
      >
        {{ layer.icon }} {{ layer.label }}
      </button>
    </div>
  </div>
</template>

<script>
import { LMap, LTileLayer, LMarker, LPopup } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'

export default {
  name: 'MapComponent',
  components: {
    LMap,
    LTileLayer,
    LMarker,
    LPopup
  },
  props: {
    selectedLocation: {
      type: Object,
      default: null
    },
    heatmapData: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      // Centro de Barcelona
      center: [41.3851, 2.1734],
      zoom: 13,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      
      // Límites del área metropolitana de Barcelona
      bounds: [
        [41.25, 1.95],  // Suroeste
        [41.60, 2.45]   // Noreste
      ],
      
      mapOptions: {
        zoomControl: true,
        minZoom: 10,
        maxZoom: 18,
        maxBounds: [
          [41.20, 1.90],
          [41.65, 2.50]
        ],
        maxBoundsViscosity: 0.8
      },
      
      activeLayers: ['competition'],
      mapLayers: [
        { id: 'mobility', label: 'Movilidad MITMA', icon: '📊' },
        { id: 'competition', label: 'Competencia', icon: '🏪' },
        { id: 'demographics', label: 'Demografía', icon: '👥' },
        { id: 'normative', label: 'Normativa PGOU', icon: '📋' }
      ],
      
      viabilityScore: 0,
      nearbyCompetitors: 0,
      footTraffic: 0,
      
      // Competidores de ejemplo en Barcelona
      competitors: [
        {
          id: 1,
          name: 'Bar La Barceloneta',
          type: 'Restaurante',
          coords: [41.3784, 2.1925],
          distance: 150
        },
        {
          id: 2,
          name: 'Café Central',
          type: 'Cafetería',
          coords: [41.3874, 2.1686],
          distance: 300
        },
        {
          id: 3,
          name: 'Pizzería Gràcia',
          type: 'Restaurante',
          coords: [41.4036, 2.1586],
          distance: 450
        },
        {
          id: 4,
          name: 'Tapas Eixample',
          type: 'Bar de tapas',
          coords: [41.3948, 2.1637],
          distance: 200
        },
        {
          id: 5,
          name: 'Restaurante Sants',
          type: 'Restaurante',
          coords: [41.3751, 2.1380],
          distance: 600
        }
      ]
    }
  },
  computed: {
    scoreClass() {
      if (this.viabilityScore >= 75) return 'high'
      if (this.viabilityScore >= 50) return 'medium'
      return 'low'
    }
  },
  methods: {
    onMapClick(event) {
      const location = {
        name: `Ubicación (${event.latlng.lat.toFixed(4)}, ${event.latlng.lng.toFixed(4)})`,
        coords: [event.latlng.lat, event.latlng.lng]
      }
      this.$emit('update:selectedLocation', location)
      this.updateLocationMetrics(location)
    },
    
    onMarkerClick(competitor) {
      console.log('Competidor seleccionado:', competitor)
      this.$emit('marker-click', competitor)
    },
    
    toggleLayer(layerId) {
      const index = this.activeLayers.indexOf(layerId)
      if (index > -1) {
        this.activeLayers.splice(index, 1)
      } else {
        this.activeLayers.push(layerId)
      }
      console.log('Capas activas:', this.activeLayers)
    },
    
    updateLocationMetrics(location) {
      // TODO: Llamar al backend para obtener métricas reales
      this.viabilityScore = Math.floor(Math.random() * 40) + 60
      this.nearbyCompetitors = Math.floor(Math.random() * 15) + 5
      this.footTraffic = Math.floor(Math.random() * 5000) + 2000
    },
    
    analyzeLocation() {
      console.log('Analizando ubicación:', this.selectedLocation)
      this.$emit('analyze', this.selectedLocation)
    },
    
    clearSelection() {
      this.$emit('update:selectedLocation', null)
    }
  },
  emits: ['marker-click', 'update:selectedLocation', 'analyze']
}
</script>

<style scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
}

.map-wrapper {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  z-index: 1;
}

.location-overlay {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: var(--color-white);
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: var(--shadow-medium);
  max-width: 320px;
  z-index: 1000;
}

.overlay-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.overlay-header h3 {
  font-size: 1.125rem;
  color: var(--color-text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  line-height: 1;
  padding: 0 0.5rem;
}

.close-btn:hover {
  color: var(--color-accent);
}

.overlay-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}

.metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-label {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.metric-value {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--color-text-primary);
}

.metric-value.high {
  color: #2ECC71;
}

.metric-value.medium {
  color: #F39C12;
}

.metric-value.low {
  color: #E74C3C;
}

.analyze-btn {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.analyze-btn:hover {
  background: var(--color-accent-hover);
}

.map-controls {
  position: absolute;
  bottom: 1.5rem;
  left: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 1000;
}

.layer-toggle {
  background: var(--color-white);
  border: 2px solid var(--color-border);
  padding: 0.625rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
  box-shadow: var(--shadow-soft);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.layer-toggle:hover {
  border-color: var(--color-accent);
}

.layer-toggle.active {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

.popup-content {
  min-width: 150px;
}

.popup-content h4 {
  margin-bottom: 0.25rem;
  color: var(--color-text-primary);
}

.popup-content p {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  margin-bottom: 0.25rem;
}

.popup-distance {
  font-weight: 600;
  color: var(--color-accent);
}

.popup-content.selected {
  border-left: 3px solid var(--color-accent);
  padding-left: 0.5rem;
}

/* Ajustes para Leaflet */
:deep(.leaflet-container) {
  font-family: inherit;
  border-radius: 12px;
}

:deep(.leaflet-popup-content-wrapper) {
  border-radius: 8px;
  box-shadow: var(--shadow-soft);
}

:deep(.leaflet-popup-content) {
  margin: 0.75rem 1rem;
}
</style>