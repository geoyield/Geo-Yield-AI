<template>
  <div class="chat-interface">
    <!-- Messages Area -->
    <div class="messages-container" ref="messagesContainer">
      <div 
        v-for="(message, index) in messages" 
        :key="index"
        :class="['message', message.type]"
      >
        <div class="message-avatar">
          {{ message.type === 'user' ? 'M' : '🤖' }}
        </div>
        <div class="message-content">
          <p>{{ message.text }}</p>
          <span class="message-time">{{ message.time }}</span>
        </div>
      </div>
      
      <!-- TODO: Agregar indicador de "escribiendo..." cuando la IA esté procesando -->
      <!-- TODO: Agregar soporte para renderizar markdown en las respuestas -->
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <!-- TODO: Implementar sugerencias contextuales basadas en la ubicación -->
      <button 
        v-for="(action, index) in quickActions" 
        :key="index"
        @click="sendQuickAction(action)"
        class="action-tag"
      >
        {{ action }}
      </button>
    </div>

    <!-- Input Area -->
    <div class="input-area">
      <div class="input-wrapper">
        <input 
          v-model="inputMessage"
          @keyup.enter="sendMessage"
          type="text"
          placeholder="Pregunta sobre ubicaciones, competencia, movilidad..."
          class="chat-input"
        />
        <button 
          @click="sendMessage"
          :disabled="!inputMessage.trim() || isLoading"
          class="send-button"
        >
          <span v-if="!isLoading">Enviar</span>
          <span v-else class="loading-spinner">⌛</span>
        </button>
      </div>
      
      <!-- TODO: Agregar botón para subir archivos (PDFs de PGOU, etc.) -->
      <!-- TODO: Agregar botón de voz para input por speech-to-text -->
    </div>
  </div>
</template>

<script>
export default {
  name: 'ChatInterface',
  data() {
    return {
      messages: [
        {
          type: 'ai',
          text: 'Hola Manuel. Soy tu asistente de Location Intelligence. ¿En qué zona de la ciudad piloto quieres analizar la viabilidad de un nuevo local?',
          time: this.getCurrentTime()
        }
      ],
      inputMessage: '',
      isLoading: false,
      quickActions: [
        'Analizar zona centro',
        'Ver competencia cercana',
        'Datos de movilidad MITMA',
        'Normativa urbanística PGOU'
      ]
    }
  },
  methods: {
    getCurrentTime() {
      return new Date().toLocaleTimeString('es-ES', { 
        hour: '2-digit', 
        minute: '2-digit' 
      })
    },

    sendMessage() {
      if (!this.inputMessage.trim() || this.isLoading) return

      const userMessage = {
        type: 'user',
        text: this.inputMessage,
        time: this.getCurrentTime()
      }

      this.messages.push(userMessage)
      this.inputMessage = ''
      this.isLoading = true

      // TODO: Implementar llamada real al backend
      // TODO: Manejar streaming de respuestas si el backend lo soporta
      setTimeout(() => {
        const aiResponse = {
          type: 'ai',
          text: 'Estoy procesando tu consulta. Analizando datos de movilidad, competencia y normativa urbanística...',
          time: this.getCurrentTime()
        }
        this.messages.push(aiResponse)
        this.isLoading = false
        this.scrollToBottom()
      }, 1500)

      this.scrollToBottom()
    },

    sendQuickAction(action) {
      this.inputMessage = action
      this.sendMessage()
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    }
  },
  emits: ['query-submit', 'location-selected']
}
</script>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 400px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--color-bg-primary);
  border-radius: 12px;
  margin-bottom: 1rem;
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.ai {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.message.ai .message-avatar {
  background: var(--color-text-primary);
}

.message-content {
  background: var(--color-white);
  padding: 0.75rem 1rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.message.user .message-content {
  background: var(--color-accent);
  color: white;
}

.message-content p {
  margin-bottom: 0.25rem;
  line-height: 1.5;
}

.message-time {
  font-size: 0.75rem;
  opacity: 0.7;
}

.quick-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding: 0 0.5rem;
}

.action-tag {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--color-text-primary);
}

.action-tag:hover {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

.input-area {
  padding: 0 0.5rem;
}

.input-wrapper {
  display: flex;
  gap: 0.75rem;
}

.chat-input {
  flex: 1;
  padding: 0.875rem 1rem;
  border: 2px solid var(--color-border);
  border-radius: 12px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
  background: var(--color-white);
}

.chat-input:focus {
  border-color: var(--color-accent);
}

.send-button {
  padding: 0.875rem 1.5rem;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.send-button:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.send-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>