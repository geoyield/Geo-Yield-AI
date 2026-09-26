"""
==============================================================================
UNIT TESTS: NLU INTENT EXTRACTION
==============================================================================
File: tests/unit_tests/test_chat_intent.py

Tests the `chat_intent.py` logic.
Uses a custom mock LLM client to simulate API responses (both successful JSON 
and hallucinations/errors) deterministically, without hitting the real Gemini API.
"""

from backend.ia.chat_intent import extraer_intencion

# ----------------------------------------------------------------------------
# MOCK LLM INFRASTRUCTURE
# ----------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, texto):
        self.content = [type("Bloque", (), {"text": texto})()]


class FakeLLMClient:
    """
    Simulates the LLM API client via Dependency Injection.
    Allows forcing specific JSON outputs or API exceptions on demand.
    """
    def __init__(self, texto_respuesta=None, lanza_excepcion=False):
        self.texto_respuesta = texto_respuesta
        self.lanza_excepcion = lanza_excepcion
        self.messages = self

    def create(self, model, max_tokens, system, messages):
        if self.lanza_excepcion:
            raise RuntimeError("fallo simulado del proveedor")
        return FakeResponse(self.texto_respuesta)

# ----------------------------------------------------------------------------
# TEST CASES
# ----------------------------------------------------------------------------
class TestExtraerIntencion:
    def test_extracts_direccion_and_pregunta_especifica(self):
        """HAPPY PATH: Extracts a specific street and a targeted question."""
        client = FakeLLMClient(
            '{"direccion": "Carrer de Sant Pau 1", "distrito_mencionado": null, "pregunta_especifica": "terrazas"}'
        )
        resultado = extraer_intencion(
            "Quiero abrir un bar en Carrer de Sant Pau 1, ¿puedo poner terraza?", llm_client=client
        )
        assert resultado == {
            "direccion": "Carrer de Sant Pau 1",
            "distrito_mencionado": None,
            "pregunta_especifica": "terrazas",
        }

    def test_generic_question_returns_null_pregunta_especifica(self):
        client = FakeLLMClient(
            '{"direccion": "Passeig de Gràcia 50", "distrito_mencionado": null, "pregunta_especifica": null}'
        )
        resultado = extraer_intencion("¿Me recomiendas abrir en Passeig de Gràcia 50?", llm_client=client)
        assert resultado["direccion"] == "Passeig de Gràcia 50"
        assert resultado["pregunta_especifica"] is None

    def test_no_direccion_mentioned_returns_null(self):
        client = FakeLLMClient('{"direccion": null, "distrito_mencionado": null, "pregunta_especifica": null}')
        resultado = extraer_intencion("¿Qué normativa hay sobre terrazas?", llm_client=client)
        assert resultado == {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    def test_regression_extrae_distrito_mencionado_sin_direccion_exacta(self):
        """
        REGRESSION TEST (Use Case):
        A user knows the district but has no specific street ("I know Les Corts...").
        The system must capture this to allow the Frontend to handle it gracefully,
        rather than discarding the input entirely.
        """
        client = FakeLLMClient(
            '{"direccion": null, "distrito_mencionado": "Les Corts", "pregunta_especifica": null}'
        )
        resultado = extraer_intencion(
            "Quiero abrir un bar para jóvenes, conozco el distrito de Les Corts, ¿qué me recomiendas?",
            llm_client=client,
        )
        assert resultado["direccion"] is None
        assert resultado["distrito_mencionado"] == "Les Corts"

    def test_regression_strips_markdown_code_block_wrapper(self):
        """
        REGRESSION TEST (Defensive Parsing):
        LLMs often wrap JSON in Markdown (```json) despite strict system prompts.
        This test proves the parser successfully strips the syntax and prevents 
        a JSONDecodeError.
        """
        client = FakeLLMClient(
            '```json\n{"direccion": "Gran Via 1", "distrito_mencionado": null, "pregunta_especifica": null}\n```'
        )
        resultado = extraer_intencion("En Gran Via 1", llm_client=client)
        assert resultado["direccion"] == "Gran Via 1"

    def test_regression_invalid_json_does_not_invent_direccion(self):
        """
        FAIL-SAFE ENFORCEMENT:
        If the LLM hallucinates unparseable garbage, the system MUST catch the 
        JSONDecodeError, return None, and ask the user for clarification, rather 
        than crashing or guessing.
        """
        client = FakeLLMClient("esto no es JSON en absoluto")
        resultado = extraer_intencion("cualquier mensaje", llm_client=client)
        assert resultado == {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    def test_regression_llm_exception_does_not_crash(self):
        """
        NETWORK RESILIENCE:
        If the LLM provider (Google/Anthropic) goes down, the function must catch 
        the Exception and return None smoothly.
        """
        client = FakeLLMClient(lanza_excepcion=True)
        resultado = extraer_intencion("cualquier mensaje", llm_client=client)
        assert resultado == {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}