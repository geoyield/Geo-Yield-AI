"""
Adaptador de Gemini para usar con backend.rag.query_engine.generate_answer().

Gemini es el proveedor definitivo del LLM en este MVP (se decidió no usar
la API de pago de Anthropic). Se mantiene la forma de interfaz de
anthropic.Anthropic() (`.messages.create(...)` -> objeto con
`.content[0].text`) por compatibilidad con el resto del pipeline.
"""

import os
import time

from backend.observability import get_logger

logger = get_logger("rag.gemini_adapter")

# Errores 5xx de Gemini (p. ej. 503 UNAVAILABLE por alta demanda) suelen ser
# picos transitorios, no un fallo real de la petición -- vale la pena
# reintentar un par de veces con una espera breve antes de rendirse.
MAX_REINTENTOS = 2
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 2


class _FakeContentBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeAnthropicResponse:
    def __init__(self, text: str):
        self.content = [_FakeContentBlock(text)]


class GeminiAsAnthropicAdapter:
    def __init__(self, api_key: str | None = None):
        from google import genai

        self._client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self.messages = self

    def create(self, model: str, max_tokens: int, system: str, messages: list[dict]) -> _FakeAnthropicResponse:
        from google.genai import errors as genai_errors
        from google.genai import types

        user_content = messages[0]["content"]
        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)

        intentos_totales = MAX_REINTENTOS + 1
        for intento in range(1, intentos_totales + 1):
            try:
                response = self._client.models.generate_content(model=model, contents=user_content, config=config)
                break
            except genai_errors.ServerError as exc:
                if intento == intentos_totales:
                    raise
                logger.warning(
                    f"Gemini devolvió un error de servidor (intento {intento}/{intentos_totales}): {exc}. "
                    f"Reintentando en {ESPERA_ENTRE_REINTENTOS_SEGUNDOS}s..."
                )
                time.sleep(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)

        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        if finish_reason is not None and finish_reason != types.FinishReason.STOP:
            logger.warning(
                f"Respuesta de Gemini incompleta (finish_reason={finish_reason}); "
                "considera subir max_tokens en generate_answer()."
            )
        return _FakeAnthropicResponse(response.text)

    def create_stream(self, model: str, max_tokens: int, system: str, messages: list[dict]):
        """
        Igual que create(), pero entrega el texto en fragmentos a medida que
        Gemini los genera, en vez de esperar a la respuesta completa. No
        lleva la misma lógica de reintento que create(): reintentar a mitad
        de un flujo ya iniciado duplicaría el texto ya entregado.
        """
        from google.genai import types

        user_content = messages[0]["content"]
        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)

        for chunk in self._client.models.generate_content_stream(model=model, contents=user_content, config=config):
            if chunk.text:
                yield chunk.text