"""
Módulo básico para el seguimiento de métricas de la API.

Para esta versión inicial del Trabajo Fin de Máster (MVP), estamos 
utilizando un enfoque sencillo en memoria para contar el tráfico básico.

Se ha dejado diseñado y documentado en este archivo el plan de métricas 
avanzadas que sería necesario implementar en una futura fase de producción 
para monitorizar la infraestructura, el uso de la API y el rendimiento 
del modelo de Inteligencia Artificial (RAG).
"""

# Diccionario global en memoria para almacenar las métricas actuales.
# Nota: Al reiniciar el contenedor, este contador vuelve a cero. Para un 
# entorno de producción real, esto debería conectarse a una base de datos 
# temporal (como Redis) o a un sistema de métricas como Prometheus.
metrics = {"total_requests": 0}


# =====================================================================
# HOJA DE RUTA (ROADMAP): Métricas propuestas para trabajo futuro
# =====================================================================
#
# 1. Métricas de Infraestructura (Rendimiento del servidor):
#    - Uso de CPU y Memoria RAM.
#    - Lectura/Escritura (I/O) en disco y uso de red.
#    - Tiempo de actividad del contenedor (Uptime).
#
# 2. Métricas de uso de la API:
#    - Tiempo de respuesta y rendimiento (Throughput).
#    - Tasa de errores (porcentaje de peticiones que fallan).
#    - Valoración del usuario sobre la respuesta (feedback).
#    - Agrupación (clustering) y clasificación de las consultas para 
#      entender qué busca más la gente y optimizar esos procesos.
#
# 3. Métricas del Agente IA / Motor RAG:
#    - Número total de informes de viabilidad generados.
#    - Latencia del retriever (tiempo que tarda la búsqueda vectorial).
#    - Latencia del LLM (tiempo que tarda el modelo en generar el texto).
#    - Número de fragmentos legales (chunks) recuperados por consulta.
#    - Precisión de las citas normativas (citas devueltas vs. verificadas).
# =====================================================================