"""
Tests del adaptador de Gemini (backend/rag/gemini_adapter.py).

Todos usan un cliente de Gemini simulado (MagicMock) -- no hacen ninguna
llamada real a la API, ni gastan cuota.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.rag.gemini_adapter import ESPERA_ENTRE_REINTENTOS_SEGUNDOS, MAX_REINTENTOS, GeminiAsAnthropicAdapter


def _fake_genai_response(text="respuesta de prueba", finish_reason=None):
    response = MagicMock()
    response.text = text
    if finish_reason is not None:
        candidato = MagicMock()
        candidato.finish_reason = finish_reason
        response.candidates = [candidato]
    else:
        response.candidates = []
    return response


@pytest.fixture
def adapter():
    with patch("google.genai.Client"):
        return GeminiAsAnthropicAdapter(api_key="fake-key")


class TestGeminiAsAnthropicAdapter:
    def test_exposes_anthropic_shaped_interface(self, adapter):
        assert adapter.messages is adapter
        assert hasattr(adapter, "create")

    def test_translates_parameters_correctly(self, adapter):
        adapter._client.models.generate_content.return_value = _fake_genai_response("hola")
        response = adapter.create(
            model="gemini-2.5-flash", max_tokens=100, system="system prompt",
            messages=[{"role": "user", "content": "pregunta"}],
        )
        assert response.content[0].text == "hola"
        _, kwargs = adapter._client.models.generate_content.call_args
        assert kwargs["model"] == "gemini-2.5-flash"
        assert kwargs["contents"] == "pregunta"

    def test_regression_warns_but_does_not_crash_on_truncated_response(self, adapter, caplog):
        from google.genai import types

        adapter._client.models.generate_content.return_value = _fake_genai_response(
            "texto cortado", finish_reason=types.FinishReason.MAX_TOKENS
        )
        response = adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])
        assert response.content[0].text == "texto cortado"
        assert "incompleta" in caplog.text


class TestReintentoAnteErroresDeServidor:
    def test_regression_retries_on_transient_server_error_then_succeeds(self, adapter, caplog):
        # Regresión real: Gemini devolvió un 503 UNAVAILABLE por alta
        # demanda (transitorio), y antes de este fix, ese fallo se
        # propagaba directo como un 502 al usuario sin ningún reintento.
        from google.genai import errors as genai_errors

        error_503 = genai_errors.ServerError(503, {"error": {"message": "high demand"}}, MagicMock())
        adapter._client.models.generate_content.side_effect = [error_503, _fake_genai_response("ok tras reintentar")]

        with patch("time.sleep") as fake_sleep:
            response = adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])

        assert response.content[0].text == "ok tras reintentar"
        assert adapter._client.models.generate_content.call_count == 2
        fake_sleep.assert_called_once_with(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)
        assert "Reintentando" in caplog.text

    def test_gives_up_after_max_retries_and_raises(self, adapter):
        from google.genai import errors as genai_errors

        error_503 = genai_errors.ServerError(503, {"error": {"message": "high demand"}}, MagicMock())
        adapter._client.models.generate_content.side_effect = error_503

        with patch("time.sleep"):
            with pytest.raises(genai_errors.ServerError):
                adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])

        # intento inicial + MAX_REINTENTOS reintentos = MAX_REINTENTOS + 1 llamadas
        assert adapter._client.models.generate_content.call_count == MAX_REINTENTOS + 1