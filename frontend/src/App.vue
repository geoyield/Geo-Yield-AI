<template>
  <div id="app">
    <!-- Header minimalista -->
    <header class="header">
      <div class="logo">
        <div class="logo-icon">🛰️</div>
        <h1>Geo-Yield AI</h1>
      </div>
      <div class="user-info">
        <!-- TODO: Implementar autenticación de usuario -->
        <span class="status-badge">Manuel</span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Sección de Chat -->
      <section class="chat-section">
        <ChatInterface 
          @location-selected="handleLocationSelected"
          @query-submit="handleQuerySubmit"
        />
      </section>

      <!-- Sección de Mapa -->
      <section class="map-section">
        <MapComponent 
          :selected-location="selectedLocation"
          :heatmap-data="heatmapData"
          @marker-click="handleMarkerClick"
        />
      </section>
    </main>
  </div>
</template>

<script>
import ChatInterface from './components/ChatInterface.vue'
import MapComponent from './components/MapComponent.vue'

export default {
  name: 'App',
  components: {
    ChatInterface,
    MapComponent
  },
  data() {
    return {
      selectedLocation: null,
      heatmapData: [],
      // TODO: Configurar WebSocket para actualizaciones en tiempo real
      wsConnection: null
    }
  },
  methods: {
    handleLocationSelected(location) {
      this.selectedLocation = location
      // TODO: Llamar al backend para obtener análisis de la ubicación
      // this.fetchLocationAnalysis(location)
    },
    
    async handleQuerySubmit(query) {
      // TODO: Implementar llamada a la API del backend
      // const response = await fetch('http://localhost:8000/recommend', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ query })
      // })
      console.log('Query enviada:', query)
    },

    handleMarkerClick(marker) {
      // TODO: Mostrar detalles del negocio/competidor seleccionado
      console.log('Marker clicked:', marker)
    }

    // TODO: Implementar método fetchLocationAnalysis
    // TODO: Implementar conexión WebSocket para actualizaciones en tiempo real
    // TODO: Agregar manejo de errores y loading states
  },
  mounted() {
    // TODO: Inicializar conexión WebSocket
    // TODO: Cargar datos iniciales del mapa
  }
}
</script>

<style>
/* Variables de color basadas en la imagen */
:root {
  --color-bg-primary: #F5F1EB;
  --color-bg-secondary: #EBE5DD;
  --color-text-primary: #1A1A1A;
  --color-text-secondary: #6B6B6B;
  --color-accent: #E07A5F;
  --color-accent-hover: #D46A50;
  --color-border: #DCD5CD;
  --color-white: #FFFFFF;
  --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.08);
  --shadow-medium: 0 8px 30px rgba(0, 0, 0, 0.12);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--color-bg-primary);
  background-image: 
    linear-gradient(var(--color-bg-secondary) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-bg-secondary) 1px, transparent 1px);
  background-size: 20px 20px;
  color: var(--color-text-primary);
  line-height: 1.6;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header */
.header {
  background: var(--color-white);
  border-bottom: 1px solid var(--color-border);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow-soft);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-icon {
  font-size: 1.5rem;
}

.logo h1 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.status-badge {
  background: var(--color-accent);
  color: var(--color-white);
  padding: 0.4rem 1rem;
  border-radius: 20px;
  font-size: 0.875rem;
  font-weight: 500;
}

/* Main Content */
.main-content {
  flex: 1;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.chat-section {
  background: var(--color-white);
  border-radius: 16px;
  padding: 1.5rem;
  box-shadow: var(--shadow-soft);
}

.map-section {
  background: var(--color-white);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--shadow-medium);
  min-height: 500px;
}

/* Responsive */
@media (max-width: 768px) {
  .main-content {
    grid-template-rows: auto auto;
    padding: 1rem;
  }
  
  .header {
    padding: 1rem;
  }
}
</style>