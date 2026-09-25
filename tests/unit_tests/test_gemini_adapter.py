"""
==============================================================================
UNIT TESTS: LLM ADAPTER (GEMINI)
==============================================================================
File: tests/unit_tests/test_gemini_adapter.py

Tests the logic of the `GeminiAsAnthropicAdapter` class.
Uses Python's `unittest.mock` to simulate the Google Gemini SDK. 
This ensures the test suite runs instantly, at zero cost, and without 
requiring internet access or real API keys.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.rag.gemini_adapter import ESPERA_ENTRE_REINTENTOS_SEGUNDOS, MAX_REINTENTOS, GeminiAsAnthropicAdapter


def _fake_genai_response(text="respuesta de prueba", finish_reason=None):
    """Helper method to construct a fake Google GenAI response object."""
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
    """
    Fixture: Mocks the Google GenAI Client at instantiation.
    Using `@patch` prevents the adapter from trying to validate the fake API key.
    """
    with patch("google.genai.Client"):
        return GeminiAsAnthropicAdapter(api_key="fake-key")


class TestGeminiAsAnthropicAdapter:
    def test_exposes_anthropic_shaped_interface(self, adapter):
        """Verifies the GoF Adapter Pattern: It must look exactly like the Anthropic SDK."""
        assert adapter.messages is adapter
        assert hasattr(adapter, "create")

    def test_translates_parameters_correctly(self, adapter):
        """Verifies that Anthropic parameters are correctly translated to Gemini format."""
        adapter._client.models.generate_content.return_value = _fake_genai_response("hola")

        # Call using the Anthropic interface
        response = adapter.create(
            model="gemini-2.5-flash", max_tokens=100, system="system prompt",
            messages=[{"role": "user", "content": "pregunta"}],
        )

        # Verify the returned shape matches Anthropic
        assert response.content[0].text == "hola"

        # Verify the underlying call was made using the Gemini interface
        _, kwargs = adapter._client.models.generate_content.call_args
        assert kwargs["model"] == "gemini-2.5-flash"
        assert kwargs["contents"] == "pregunta"

    def test_regression_warns_but_does_not_crash_on_truncated_response(self, adapter, caplog):
        """
        Observability Test: If the LLM hits the token limit, it must not crash, 
        but it MUST log a warning. Pytest's `caplog` fixture intercepts system logs.
        """
        from google.genai import types

        adapter._client.models.generate_content.return_value = _fake_genai_response(
            "texto cortado", finish_reason=types.FinishReason.MAX_TOKENS
        )
        response = adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])
        assert response.content[0].text == "texto cortado"
        assert "incompleta" in caplog.text


class TestReintentoAnteErroresDeServidor:
    def test_regression_retries_on_transient_server_error_then_succeeds(self, adapter, caplog):
        """
        Regression Test (Resilience):
        Simulates a cloud outage where Gemini returns a 503 UNAVAILABLE on the 
        first call, but succeeds on the second try. The adapter must hide this 
        failure from the user and recover automatically.
        """
        from google.genai import errors as genai_errors

        error_503 = genai_errors.ServerError(503, {"error": {"message": "high demand"}}, MagicMock())

        # side_effect allows us to define a sequence of responses: 
        # First call -> Throws 503 Error. Second call -> Returns "ok"
        adapter._client.models.generate_content.side_effect = [error_503, _fake_genai_response("ok tras reintentar")]

        # We also mock time.sleep so the test doesn't actually wait 2 seconds
        with patch("time.sleep") as fake_sleep:
            response = adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])

        # Assertions
        assert response.content[0].text == "ok tras reintentar"
        assert adapter._client.models.generate_content.call_count == 2
        fake_sleep.assert_called_once_with(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)
        assert "Reintentando" in caplog.text

    def test_gives_up_after_max_retries_and_raises(self, adapter):
        """
        Ensures the retry loop is not infinite. If the server is truly down, 
        it must raise the exception after MAX_REINTENTOS.
        """
        from google.genai import errors as genai_errors

        error_503 = genai_errors.ServerError(503, {"error": {"message": "high demand"}}, MagicMock())
        adapter._client.models.generate_content.side_effect = error_503

        with patch("time.sleep"):
            with pytest.raises(genai_errors.ServerError):
                adapter.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "p"}])

        # Initial Attempt (1) + Retries = MAX_REINTENTOS + 1
        assert adapter._client.models.generate_content.call_count == MAX_REINTENTOS + 1