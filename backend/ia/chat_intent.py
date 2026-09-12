"""
Extracción de intención del chat conversacional.

Convierte una frase libre del usuario en los parámetros estructurados
que el resto del pipeline ya sabe manejar: una dirección a geocodificar,
y una pregunta específica opcional si el usuario mencionó algo concreto
más allá de "es viable o no" (terrazas, horarios, aforo...).

Es una única llamada al LLM, no un agente con herramientas ni memoria --
todo lo demás (geocodificación, identificación de zona, generación del
informe) se apoya en el pipeline ya existente y probado
(geocoding.py, amb_identify.py, agent.py), sin tocarlo.
"""

import json
import logging

logger = logging.getLogger("geoyield_chat")

EXTRACCION_SYSTEM_PROMPT = """Extraes información estructurada de un mensaje de un usuario que quiere evaluar la viabilidad de abrir un bar o restaurante en Barcelona.

Devuelve ÚNICAMENTE un objeto JSON con exactamente estas tres claves, sin texto adicional antes ni después, sin bloques de código Markdown:

{
  "direccion": "la dirección o calle mencionada, tal cual la escribió el usuario, o null si no menciona ninguna dirección o calle concreta",
  "distrito_mencionado": "el nombre EXACTO de uno de estos 10 distritos oficiales de Barcelona si el usuario lo menciona directamente (Ciutat Vella, Eixample, Sants-Montjuïc, Les Corts, Sarrià-Sant Gervasi, Gràcia, Horta-Guinardó, Nou Barris, Sant Andreu, Sant Martí), o null si no menciona ninguno de estos distritos",
  "pregunta_especifica": "si el usuario pregunta por algo concreto más allá de si es viable en general (p. ej. terrazas, horarios, aforo, ruido, licencias específicas), resume esa pregunta concreta en pocas palabras; o null si solo pregunta de forma genérica si es viable o le recomiendas el local"
}

No inventes una dirección ni un distrito si no aparecen en el mensaje. No inventes una pregunta específica si el usuario solo pregunta genéricamente "es viable" o "me lo recomiendas"."""


def extraer_intencion(mensaje: str, llm_client=None, model: str | None = None) -> dict:
    """
    Devuelve {"direccion": str | None, "distrito_mencionado": str | None,
    "pregunta_especifica": str | None}.

    distrito_mencionado cubre el caso de alguien que conoce la zona
    general pero no da una calle exacta (p. ej. "conozco Les Corts, qué
    me recomiendas ahí") -- sin esto, esos mensajes no tendrían ninguna
    ubicación que extraer, aunque el usuario sí haya dado información
    real y utilizable.

    Si el LLM no devuelve un JSON válido o falla la llamada, se asume que
    no se pudo extraer nada -- nunca se inventa una dirección o distrito
    para forzar que el flujo continúe; el llamador debe pedir aclaración
    en ese caso.
    """
    from backend.rag.gemini_adapter import GeminiAsAnthropicAdapter
    from backend.rag.query_engine import DEFAULT_MODEL

    client = llm_client if llm_client is not None else GeminiAsAnthropicAdapter()
    modelo = model if model is not None else DEFAULT_MODEL

    try:
        response = client.messages.create(
            model=modelo,
            max_tokens=2048,
            system=EXTRACCION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": mensaje}],
        )
        texto = response.content[0].text.strip()
    except Exception:
        logger.exception("Error llamando al LLM para extraer intención del chat")
        return {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    # El LLM a veces envuelve el JSON en bloques de Markdown pese a que
    # se le pide explícitamente que no lo haga.
    texto = texto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        logger.warning("El LLM no devolvió JSON válido al extraer intención: %r", texto)
        return {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    return {
        "direccion": datos.get("direccion") or None,
        "distrito_mencionado": datos.get("distrito_mencionado") or None,
        "pregunta_especifica": datos.get("pregunta_especifica") or None,
    }