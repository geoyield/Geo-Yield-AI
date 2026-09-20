"""
Tests de backend/ia/chat_intent.py. Usa un cliente LLM simulado -- sin
llamadas reales a Gemini.
"""

from backend.ia.chat_intent import extraer_intencion


class FakeResponse:
    def __init__(self, texto):
        self.content = [type("Bloque", (), {"text": texto})()]


class FakeLLMClient:
    def __init__(self, texto_respuesta=None, lanza_excepcion=False):
        self.texto_respuesta = texto_respuesta
        self.lanza_excepcion = lanza_excepcion
        self.messages = self

    def create(self, model, max_tokens, system, messages):
        if self.lanza_excepcion:
            raise RuntimeError("fallo simulado del proveedor")
        return FakeResponse(self.texto_respuesta)


class TestExtraerIntencion:
    def test_extracts_direccion_and_pregunta_especifica(self):
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
        # Regresión real: un usuario que conoce el distrito pero no da
        # una calle exacta ("conozco Les Corts, qué me recomiendas ahí")
        # debe reconocerse como información utilizable, no como "no
        # identifiqué nada" -- este caso concreto se probó en producción
        # y fallaba antes de este campo.
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
        # Regresión: el LLM a veces envuelve el JSON en ```json pese a
        # que el prompt le pide explícitamente no hacerlo.
        client = FakeLLMClient(
            '```json\n{"direccion": "Gran Via 1", "distrito_mencionado": null, "pregunta_especifica": null}\n```'
        )
        resultado = extraer_intencion("En Gran Via 1", llm_client=client)
        assert resultado["direccion"] == "Gran Via 1"

    def test_regression_invalid_json_does_not_invent_direccion(self):
        # Regresión: si el LLM devuelve basura no parseable, no debe
        # inventarse una dirección para forzar que el flujo continúe --
        # debe devolver None y dejar que el llamador pida aclaración.
        client = FakeLLMClient("esto no es JSON en absoluto")
        resultado = extraer_intencion("cualquier mensaje", llm_client=client)
        assert resultado == {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}

    def test_regression_llm_exception_does_not_crash(self):
        client = FakeLLMClient(lanza_excepcion=True)
        resultado = extraer_intencion("cualquier mensaje", llm_client=client)
        assert resultado == {"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None}