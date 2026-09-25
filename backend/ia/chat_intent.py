"""
==============================================================================
NATURAL LANGUAGE UNDERSTANDING (NLU): INTENT EXTRACTION
==============================================================================
File: backend/ia/chat_intent.py

Converts a free-text user message into structured, deterministic parameters (JSON).
Architectural Note (Extraction vs. Autonomous Agent):
This is a single, stateless LLM call. It does NOT use tools or conversational 
memory. It simply translates human language into a dictionary format that the 
pre-existing, battle-tested geospatial pipeline (geocoding, amb_identify, RAG) 
can consume natively.
"""

import json
import logging

logger = logging.getLogger("geoyield_chat")

# Prompt Engineering: Strict Output Formatting & Anti-Hallucination Directives
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
    Returns {"direccion": str | None, "distrito_mencionado": str | None, "pregunta_especifica": str | None}.

    Note on `distrito_mencionado`: Handles cases where the user provides general 
    location context but no exact street (e.g., "I know Les Corts, what do you recommend?").

    Fail-Safe Design: 
    If the LLM fails to return valid JSON, the function safely degrades by returning 
    None for all fields, forcing the downstream Orchestrator to ask for clarification 
    rather than hallucinating an address to force the workflow to continue.
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

    # Defensive Parsing: LLMs frequently hallucinate Markdown syntax even when 
    # explicitly instructed not to. This cleanly strips the syntax before parsing.
    texto = texto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        logger.warning("El LLM no devolvió JSON válido al extraer intención: %r", texto)
        return {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    # Enforces the deterministic schema, defaulting missing keys to None
    return {
        "direccion": datos.get("direccion") or None,
        "distrito_mencionado": datos.get("distrito_mencionado") or None,
        "pregunta_especifica": datos.get("pregunta_especifica") or None,
    }