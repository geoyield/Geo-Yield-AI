"""
Agente orquestador de viabilidad de locales de hostelería en Barcelona.

Combina en un grafo de LangGraph dos fuentes de información en paralelo
(datos socioeconómicos del distrito y normativa legal aplicable) y las
sintetiza en un informe final con un veredicto tipo semáforo.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.rag.embeddings import EmbeddingFunction, embed_texts
from backend.rag.query_engine import DEFAULT_MODEL, generate_answer

logger = logging.getLogger("geoyield_agent")

Semaforo = Literal["verde", "ambar", "rojo"]

ZONA_PGM_NOMBRES = {
    "nucli_antic": "Nucli antic / Centre històric (p. ej. Ciutat Vella)",
    "densificacio_urbana": "Densificació urbana (p. ej. gran part de l'Eixample)",
    "industrial": "Zona industrial",
    "conservacio_estructura_urbana": "Conservació de l'estructura urbana i edificatòria",
    "ordenacio_volumetrica_especifica": "Ordenació volumètrica específica",
    "edificacio_aillada": "Edificació aïllada (unifamiliar o plurifamiliar)",
    "renovacio_urbana": "Renovació urbana",
}


def zonas_pgm_disponibles(session: Session) -> list[str]:
    """Obtiene la lista de zonas PGM que tienen normativa en la base de datos."""
    rows = session.execute(
        text("SELECT DISTINCT zona_pgm FROM legal_chunks WHERE zona_pgm IS NOT NULL")
    ).all()
    return sorted(r[0] for r in rows)


class ViabilityState(TypedDict):
    """Estado compartido que viaja entre los nodos del grafo de LangGraph."""
    codi_districte: int
    zona_pgm: str
    pregunta_especifica: NotRequired[str | None]
    datos_distrito: dict[str, Any] | None
    respuesta_legal: dict[str, Any] | None
    informe: dict[str, Any] | None


@dataclass
class ViabilityReport:
    """Estructura del informe final de viabilidad generado por el LLM."""
    semaforo: Semaforo
    resumen: str
    datos_distrito: dict[str, Any]
    respuesta_legal: str
    articulos_citados: list[dict[str, Any]]


SYNTHESIS_SYSTEM_PROMPT = """Eres un consultor de viabilidad para negocios de hostelería (bares, restaurantes) en Barcelona.

Recibes dos bloques de información ya verificados:
1. Datos socioeconómicos del distrito (renta, afluencia peatonal, saturación de competencia, y un índice de oportunidad de 0 a 100).
2. Una respuesta legal ya generada, que puede combinar normativa específica de la zona urbanística Y normativa general (horarios, consumo, etc.) que aplica en toda la ciudad, citando el artículo y la norma correspondiente.

Tu tarea es sintetizar AMBOS en un informe de viabilidad breve para el usuario final (el dueño del negocio, no un desarrollador). Estructura tu respuesta EXACTAMENTE así:

Primera línea: exactamente una palabra, en mayúsculas, sin ningún signo de puntuación al final (sin punto, sin dos puntos, nada) -- solo VERDE, AMBAR o ROJO, letra por letra, nada más en esa línea.
    - ROJO: la normativa prohíbe explícitamente el uso, o el contexto legal no da certeza suficiente.
    - AMBAR: el uso está permitido, pero con restricciones relevantes o riesgos socioeconómicos notables.
    - VERDE: el uso está permitido y las condiciones socioeconómicas son favorables.

Después, un resumen de 3-5 frases dirigido al dueño del negocio: explica el veredicto, cita la normativa relevante (zona y/o general), y menciona el dato socioeconómico más relevante.

No uses formato Markdown de ningún tipo (nada de **negrita**, encabezados con #, ni listas con - o *) en el resumen. La interfaz que lo muestra no interpreta Markdown, así que esos símbolos aparecerían tal cual, como ruido visible. Escribe en prosa corrida.

No inventes información que no esté en los dos bloques que recibes. Si falta algún dato, dilo explícitamente en vez de rellenar el hueco."""


def _construir_pregunta_legal(zona_pgm: str, pregunta_especifica: str | None = None) -> str:
    """Construye la pregunta al motor legal usando el nombre amigable de la zona."""
    nombre_zona = ZONA_PGM_NOMBRES.get(zona_pgm, zona_pgm)
    pregunta = (
        f"¿Se permite abrir un bar o restaurante (uso comercial/hostelería) "
        f"en una zona de tipo '{nombre_zona}'? ¿Con qué condiciones o límites?"
    )
    if pregunta_especifica:
        # Se refuerza aquí, en la pregunta misma, la misma instrucción que
        # ya existe en el SYSTEM_PROMPT del RAG ("si el contexto no
        # contiene información suficiente, dilo explícitamente en vez de
        # inventar") -- justo donde más importa: una pregunta concreta del
        # usuario (terrazas, horarios...) es donde más riesgo hay de que
        # el modelo rellene un hueco con seguridad no verificada.
        pregunta += (
            f" Además, el usuario pregunta específicamente sobre: {pregunta_especifica}. "
            f"Si el contexto no incluye normativa específica sobre esto, dilo explícitamente "
            f"en vez de responder con seguridad sobre algo que no está en el contexto."
        )
    return pregunta


def _construir_mensaje_sintesis(
    datos: dict[str, Any] | None,
    legal: dict[str, Any]
) -> tuple[str, list[dict[str, str]]]:
    """
    Arma el mensaje que se envía al LLM para la síntesis final.

    Devuelve una tupla con el texto del mensaje y la lista de artículos citados
    (con número de artículo y fuente legal).
    """
    if datos is None:
        bloque_datos = "No hay datos socioeconómicos disponibles para este distrito."
    else:
        bloque_datos = (
            f"Distrito: {datos['nom_districte']}\n"
            f"Renta media: {datos['renta_media']}€\n"
            f"Afluencia peatonal diaria: {datos['daily_foot_traffic']}\n"
            f"Competidores de hostelería en el distrito: {datos['total_competitors']}\n"
            f"Índice de oportunidad (0-100): {datos['opportunity_score']}"
        )

    articulos_citados = [
        {"numero_articulo": c.numero_articulo, "fuente_legal": c.fuente_legal}
        for c in legal["chunks_recuperados"]
    ]

    citas_texto = ", ".join(
        f"{a['fuente_legal']} Art. {a['numero_articulo']}"
        for a in articulos_citados
    )

    bloque_legal = f"{legal['respuesta']}\n\n(Artículos consultados: {citas_texto or 'ninguno'})"
    mensaje = f"DATOS SOCIOECONÓMICOS:\n{bloque_datos}\n\nRESPUESTA LEGAL:\n{bloque_legal}"

    return mensaje, articulos_citados


def _parsear_semaforo_y_resumen(texto: str) -> tuple[Semaforo, str]:
    """
    Extrae el semáforo y el resumen del texto de síntesis.

    Si la primera línea no es un semáforo válido, asume 'ambar'.
    """
    texto = texto.strip()
    primera_linea, *resto = texto.splitlines() or [""]
    # El LLM a veces añade puntuación al final de la palabra del
    # semáforo (p. ej. "AMBAR." en vez de "AMBAR", un hábito natural de
    # cerrar frases) -- se quita antes de comparar, para no caer en el
    # fallback por un simple punto de más. Bug real encontrado en producción.
    semaforo_texto = re.sub(r"[.!:;,]+$", "", primera_linea.strip().upper())

    if semaforo_texto not in ("VERDE", "AMBAR", "ROJO"):
        logger.warning(
            "El LLM no devolvió un semáforo reconocible en la primera línea: %r",
            primera_linea
        )
        return "ambar", texto

    # Usamos type ignore porque Python no asume estáticamente que semaforo_texto sea un Semaforo válido
    return semaforo_texto.lower(), "\n".join(resto).strip()  # type: ignore


def _crear_nodos_paralelos(
    session: Session,
    embed_fn: EmbeddingFunction,
    llm_client: Any,
    model: str
) -> tuple[Callable[[ViabilityState], dict[str, Any]], Callable[[ViabilityState], dict[str, Any]]]:
    """Crea las dos funciones de nodo que se ejecutan en paralelo."""

    def datos_socioeconomicos(state: ViabilityState) -> dict[str, Any]:
        with Session(session.get_bind()) as node_session:
            row = node_session.execute(
                text(
                    "SELECT codi_districte, nom_districte, renta_media, daily_foot_traffic, "
                    "total_competitors, opportunity_score "
                    "FROM district_scorecard WHERE codi_districte = :codi"
                ),
                {"codi": state["codi_districte"]},
            ).mappings().first()

        if row is None:
            logger.warning(
                "No hay datos en district_scorecard para el distrito %s",
                state["codi_districte"]
            )
            return {"datos_distrito": None}

        return {"datos_distrito": dict(row)}

    def normativa_legal(state: ViabilityState) -> dict[str, Any]:
        with Session(session.get_bind()) as node_session:
            pregunta = _construir_pregunta_legal(state["zona_pgm"], state.get("pregunta_especifica"))
            resultado = generate_answer(
                node_session,
                pregunta,
                embed_fn=embed_fn,
                llm_client=llm_client,
                model=model,
                zona_pgm=state["zona_pgm"],
            )
        return {"respuesta_legal": resultado}

    return datos_socioeconomicos, normativa_legal


def build_data_gathering_graph(
    session: Session,
    embed_fn: EmbeddingFunction = embed_texts,
    llm_client: Any = None,
    model: str = DEFAULT_MODEL,
) -> Any:
    """
    Construye el grafo reducido solo con los nodos de recopilación.

    Se utiliza para la variante de streaming, donde la síntesis final
    se realiza fuera del grafo principal.
    """
    datos_socioeconomicos, normativa_legal = _crear_nodos_paralelos(
        session, embed_fn, llm_client, model
    )

    graph = StateGraph(ViabilityState)
    graph.add_node("datos_socioeconomicos", datos_socioeconomicos)
    graph.add_node("normativa_legal", normativa_legal)

    graph.add_edge(START, "datos_socioeconomicos")
    graph.add_edge(START, "normativa_legal")
    graph.add_edge("datos_socioeconomicos", END)
    graph.add_edge("normativa_legal", END)

    return graph.compile()


def build_agent_graph(
    session: Session,
    embed_fn: EmbeddingFunction = embed_texts,
    llm_client: Any = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> Any:
    """Construye el grafo completo incluyendo el nodo de síntesis final."""
    datos_socioeconomicos, normativa_legal = _crear_nodos_paralelos(
        session, embed_fn, llm_client, model
    )

    def sintesis_final(state: ViabilityState) -> dict[str, Any]:
        from backend.rag.gemini_adapter import GeminiAsAnthropicAdapter

        client = llm_client if llm_client is not None else GeminiAsAnthropicAdapter()
        mensaje, articulos_citados = _construir_mensaje_sintesis(
            state["datos_distrito"],
            state["respuesta_legal"]  # type: ignore
        )

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": mensaje}],
        )

        semaforo, resumen = _parsear_semaforo_y_resumen(response.content[0].text)

        informe = ViabilityReport(
            semaforo=semaforo,
            resumen=resumen,
            datos_distrito=state["datos_distrito"] or {},
            respuesta_legal=state["respuesta_legal"]["respuesta"],  # type: ignore
            articulos_citados=articulos_citados,
        )
        return {"informe": informe.__dict__}

    graph = StateGraph(ViabilityState)
    graph.add_node("datos_socioeconomicos", datos_socioeconomicos)
    graph.add_node("normativa_legal", normativa_legal)
    graph.add_node("sintesis_final", sintesis_final)

    graph.add_edge(START, "datos_socioeconomicos")
    graph.add_edge(START, "normativa_legal")
    graph.add_edge("datos_socioeconomicos", "sintesis_final")
    graph.add_edge("normativa_legal", "sintesis_final")
    graph.add_edge("sintesis_final", END)

    return graph.compile()


def generar_informe_viabilidad(
    session: Session,
    codi_districte: int,
    zona_pgm: str,
    embed_fn: EmbeddingFunction = embed_texts,
    llm_client: Any = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    pregunta_especifica: str | None = None,
) -> dict[str, Any]:
    """Punto de entrada para generar el informe de viabilidad de forma síncrona."""
    app = build_agent_graph(
        session,
        embed_fn=embed_fn,
        llm_client=llm_client,
        model=model,
        max_tokens=max_tokens
    )
    resultado = app.invoke(
        {"codi_districte": codi_districte, "zona_pgm": zona_pgm, "pregunta_especifica": pregunta_especifica}
    )
    return resultado["informe"]


def generar_informe_viabilidad_stream(
    session: Session,
    codi_districte: int,
    zona_pgm: str,
    embed_fn: EmbeddingFunction = embed_texts,
    llm_client: Any = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    pregunta_especifica: str | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Genera el informe de viabilidad emitiendo fragmentos (chunks) progresivamente.

    Ideal para integraciones con Server-Sent Events (SSE). Genera eventos tipo
    diccionario listos para ser transmitidos por red.

    pregunta_especifica: si el usuario (p. ej. desde el chat) preguntó
    algo concreto además de "es viable" (terrazas, horarios...), se
    incorpora a la consulta legal -- si no hay normativa específica
    cargada sobre ello, el propio RAG debe decirlo explícitamente, nunca
    inventarlo.
    """
    from backend.rag.gemini_adapter import GeminiAsAnthropicAdapter

    grafo = build_data_gathering_graph(
        session, embed_fn=embed_fn, llm_client=llm_client, model=model
    )
    resultado = grafo.invoke(
        {"codi_districte": codi_districte, "zona_pgm": zona_pgm, "pregunta_especifica": pregunta_especifica}
    )

    datos = resultado.get("datos_distrito")
    legal = resultado["respuesta_legal"]
    mensaje, articulos_citados = _construir_mensaje_sintesis(datos, legal)

    yield {
        "type": "datos",
        "datos_distrito": datos or {},
        "respuesta_legal": legal["respuesta"],
        "articulos_citados": articulos_citados,
    }

    client = llm_client if llm_client is not None else GeminiAsAnthropicAdapter()
    texto_acumulado = ""

    for fragmento in client.messages.create_stream(
        model=model,
        max_tokens=max_tokens,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": mensaje}],
    ):
        texto_acumulado += fragmento
        yield {"type": "token", "text": fragmento}

    semaforo, resumen = _parsear_semaforo_y_resumen(texto_acumulado)
    yield {"type": "done", "semaforo": semaforo, "resumen": resumen}