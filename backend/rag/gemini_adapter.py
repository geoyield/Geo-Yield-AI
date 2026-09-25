"""
==============================================================================
RAG PIPELINE: LLM ADAPTER PATTERN (GEMINI AS ANTHROPIC)
==============================================================================
File: backend/rag/gemini_adapter.py

This module implements the Gang of Four (GoF) 'Adapter' Design Pattern. 
The core RAG engine was originally built expecting the Anthropic (Claude) API 
interface. To switch to Google Gemini (to utilize the free tier during the MVP) 
without rewriting the core engine, this class wraps the Gemini SDK so it 
perfectly mimics the Anthropic SDK signatures.
"""

import logging
import os
import time

logger = logging.getLogger("geoyield_rag")

# Resilience Settings: Cloud LLMs often throw transient 5xx errors due to quota 
# or server load. We implement a simple retry mechanism before failing.
MAX_REINTENTOS = 2
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 2

# ------------------------------------------------------------------------------
# MOCK ANTHROPIC CLASSES
# ------------------------------------------------------------------------------
# These classes mock the exact data structure returned by the official 
# Anthropic Python SDK: response.content[0].text
class _FakeContentBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeAnthropicResponse:
    def __init__(self, text: str):
        self.content = [_FakeContentBlock(text)]


class GeminiAsAnthropicAdapter:
    def __init__(self, api_key: str | None = None):
        # Lazy import to prevent failing if the user hasn't installed the SDK
        from google import genai

        self._client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        # Mimic Anthropic's `.messages` attribute
        self.messages = self

    def create(self, model: str, max_tokens: int, system: str, messages: list[dict]) -> _FakeAnthropicResponse:
        """
        Mimics `anthropic.Anthropic().messages.create(...)`.
        Includes robustness logic (retries) and token truncation warnings.
        """
        from google.genai import errors as genai_errors
        from google.genai import types

        # Translate Anthropic format to Gemini format
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

        # Truncation Detection: If the LLM stopped because it hit `max_tokens` 
        # (FinishReason.MAX_TOKENS) instead of naturally finishing (FinishReason.STOP), 
        # we log a warning so the developer knows the context window is too small.
        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        if finish_reason is not None and finish_reason != types.FinishReason.STOP:
            logger.warning(
                f"Respuesta de Gemini incompleta (finish_reason={finish_reason}); "
                "considera subir max_tokens en generate_answer()."
            )

        # Return the response wrapped in our fake Anthropic objects
        return _FakeAnthropicResponse(response.text)

    def create_stream(self, model: str, max_tokens: int, system: str, messages: list[dict]):
        """
        Streaming generation (Server-Sent Events).
        
        Design Note: We intentionally omit the Retry logic here. 
        If a stream fails halfway, retrying would restart the generation, 
        sending duplicated or conflicting tokens to the frontend client.
        """
        from google.genai import types

        user_content = messages[0]["content"]
        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)

        for chunk in self._client.models.generate_content_stream(model=model, contents=user_content, config=config):
            if chunk.text:
                yield chunk.text