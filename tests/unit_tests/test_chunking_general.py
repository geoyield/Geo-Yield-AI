"""
Tests del chunker generalizado de normas generales
(backend/rag/chunking_general.py).

Los fixtures son texto real extraído con pdftotext de dos fuentes
distintas (Ordre INT/358/2011 del DOGC, Ley 1/2004 del BOE), compartidas
por el usuario -- el mismo parser, sin ninguna bandera de configuración
por fuente, tiene que resolver ambos formatos correctamente.
"""

from backend.rag.chunking_general import clean_boilerplate, parse_articulo_general


class TestParseArticuloGeneralFormatoDogc:
    """Formato DOGC: 'Artículo N' solo en su línea, título en la línea siguiente."""

    def test_parses_all_articles_in_sequence(self):
        text = """Artículo 1
Objeto y ámbito de aplicación
Esta Orden tiene como objeto regular los horarios.
Artículo 2
Hora de apertura y hora de inicio
2.1 Se entiende por hora de apertura el momento de acceso.
"""
        chunks = parse_articulo_general(text)
        assert [c.numero_articulo for c in chunks] == ["1", "2"]
        assert chunks[0].titulo == "Objeto y ámbito de aplicación"
        assert "Esta Orden" in chunks[0].contenido
        assert "Esta Orden" not in chunks[1].contenido

    def test_regression_does_not_match_inline_article_references(self):
        # Las referencias en minúscula tipo "el artículo 20 de la Ley..."
        # dentro de frases corridas no deben confundirse con un encabezado
        # real (que va con mayúscula y solo en su propia línea).
        text = """En virtud del artículo 20 de la Ley 11/2009 y del artículo 5.2.g),
se aprueba lo siguiente:
ORDENO:
Artículo 1
Objeto
Contenido real del artículo 1.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "1"
        assert "Contenido real" in chunks[0].contenido
        assert "ORDENO" not in chunks[0].contenido

    def test_regression_strips_dogc_header_footer_across_page_break(self):
        # Cabecera/pie repetidos 3+ veces (frecuencia), detectados sin
        # necesitar conocer de antemano el texto exacto del DOGC.
        text = """Diari Oicial de la Generalitat de Catalunya

Núm. 6030 – 22.12.2011

Artículo 1
Primer artículo, antes del salto de página.
Disposiciones
http://www.gencat.cat/dogc

ISSN 1988-298X
DL B-38015-2007


64597

Diari Oicial de la Generalitat de Catalunya

Núm. 6030 – 22.12.2011

Artículo 2
Segundo artículo, después del salto de página.
Diari Oicial de la Generalitat de Catalunya
Núm. 6030 – 22.12.2011
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 2
        for noise in ["Diari", "Núm.", "gencat.cat", "ISSN", "64597"]:
            assert noise not in chunks[0].contenido
            assert noise not in chunks[1].contenido


class TestParseArticuloGeneralFormatoBoe:
    """Formato BOE: 'Artículo N. Título.' todo en la misma línea, con índice a filtrar."""

    def test_regression_index_entries_are_not_treated_as_articles(self):
        # Regresión real: el índice del BOE usa el MISMO patrón textual
        # que los artículos reales ("Artículo N. Título."), pero con
        # puntos de relleno para alinear con el número de página. Sin
        # filtrarlo, se detectarían el doble de artículos de los que hay.
        text = """ÍNDICE
Artículo 1. Libertad de horarios. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
4
Artículo 2. Competencias autonómicas. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
4
Artículo 1. Libertad de horarios.
Contenido real del primer artículo.
Artículo 2. Competencias autonómicas.
Contenido real del segundo artículo.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 2
        assert chunks[0].titulo == "Libertad de horarios"
        assert chunks[0].contenido == "Contenido real del primer artículo."
        assert chunks[1].titulo == "Competencias autonómicas"

    def test_title_and_number_on_same_line(self):
        text = """Artículo 3. Horario global.
1. El horario global en que los comercios podrán desarrollar su actividad.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "3"
        assert chunks[0].titulo == "Horario global"
        assert chunks[0].contenido == "1. El horario global en que los comercios podrán desarrollar su actividad."

    def test_regression_index_entry_with_title_wrapped_before_dot_leader(self):
        # Bug real, encontrado al cargar Ley 11/2009 y Ley 22/2010: cuando
        # el título de una entrada del índice es largo, se parte en 2
        # líneas ANTES de llegar al relleno de puntos -- comprobar solo la
        # primera línea (donde no hay puntos todavía) dejaba pasar la
        # entrada del índice como si fuera un artículo real, con el mismo
        # número que el artículo real más adelante. Postgres rechazaba la
        # carga completa por "ON CONFLICT DO UPDATE command cannot affect
        # row a second time" al intentar insertar dos filas con la misma
        # clave (fuente_legal, numero_articulo) en el mismo lote.
        text = """ÍNDICE
Artículo 39. Licencia municipal o autorización de la Generalidad para los establecimientos abiertos al
público de régimen especial. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
Artículo 39. Licencia municipal o autorización de la Generalidad.
Contenido real y completo del artículo 39 de verdad.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert chunks[0].contenido == "Contenido real y completo del artículo 39 de verdad."

    def test_regression_index_entry_with_title_wrapped_three_lines(self):
        # Mismo bug, un escalón más largo: un título de índice puede
        # partirse en 3 líneas (no solo 2) antes del relleno de puntos --
        # encontrado al reintentar la carga de Ley 11/2009 tras el primer
        # arreglo (que solo cubría hasta 2 líneas de margen).
        text = """ÍNDICE
Artículo 7. Derechos y obligaciones de los artistas, intérpretes o ejecutantes y demás personal al
servicio de los establecimientos abiertos al público, de los espectáculos públicos y de las actividades
recreativas. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
Artículo 7. Derechos y obligaciones de los artistas.
Contenido real y completo del artículo 7 de verdad.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert chunks[0].contenido == "Contenido real y completo del artículo 7 de verdad."

    def test_regression_strips_boe_header_footer_by_frequency(self):
        # Cabecera/pie del BOE, distinta a la del DOGC -- detectada por
        # frecuencia (se repite 3+ veces), sin conocer su texto exacto
        # de antemano.
        boilerplate = "BOLETÍN OFICIAL DEL ESTADO\nLEGISLACIÓN CONSOLIDADA"
        text = f"""{boilerplate}

Página 1
Artículo 1. Primer artículo.
Contenido del primer artículo.
{boilerplate}

Página 2
Artículo 2. Segundo artículo.
Contenido del segundo artículo.
{boilerplate}

Página 3
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 2
        for noise in ["BOLETÍN OFICIAL", "LEGISLACIÓN CONSOLIDADA", "Página"]:
            assert noise not in chunks[0].contenido
            assert noise not in chunks[1].contenido

    def test_inline_lowercase_article_reference_not_matched(self):
        # "el artículo 149.1.13.ª de la Constitución" es una referencia
        # dentro de una frase, en minúscula -- no debe confundirse con un
        # encabezado real.
        text = """La presente Ley se dicta en el ejercicio de las competencias exclusivas del Estado en
materia de bases de la ordenación de la actividad económica que le reconoce el artículo
149.1.13.ª de la Constitución.
Artículo 1. Libertad de horarios.
Contenido real.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "1"


class TestParseArticuloGeneralNumeracionCompuesta:
    def test_regression_two_part_numbering_treated_as_distinct_articles(self):
        # Bug real, encontrado al cargar Ley 22/2010 (Código de Consumo de
        # Cataluña): usa numeración de dos partes tipo "Artículo 111-1",
        # "Artículo 111-2" -- la expresión regular original solo capturaba
        # "111" como número, dejando "-1"/"-2" colarse dentro del título.
        # Resultado: "111-1" y "111-2" (artículos DISTINTOS con contenido
        # distinto) se trataban como si fueran el mismo "111", chocando en
        # el INSERT.
        text = """Artículo 111-1. Objeto y ámbito.
Contenido del 111-1.
Artículo 111-2. Definiciones.
Contenido del 111-2.
"""
        chunks = parse_articulo_general(text)
        assert [c.numero_articulo for c in chunks] == ["111-1", "111-2"]
        assert chunks[0].contenido == "Contenido del 111-1."
        assert chunks[1].contenido == "Contenido del 111-2."


class TestDedupeKeepingLongest:
    def test_regression_duplicate_numero_articulo_keeps_longest_content(self):
        # Red de seguridad: si por cualquier motivo no anticipado (ya se
        # han visto dos formas distintas: títulos de índice partidos en
        # varias líneas, y una sub-numeración de cola de documento no
        # reconocida) dos artículos acaban con el mismo numero_articulo,
        # debe quedarse con el de contenido más largo -- el genuino -- en
        # vez de dejar que la carga completa reviente en Postgres con
        # "ON CONFLICT DO UPDATE command cannot affect row a second time".
        text = """Artículo 5. Título corto.
x
Artículo 5. Título real.
Contenido real y mucho más largo del artículo 5 de verdad, con texto sustancial.
"""
        chunks = parse_articulo_general(text)
        assert len(chunks) == 1
        assert "Contenido real y mucho más largo" in chunks[0].contenido


class TestCleanBoilerplateGenerico:
    def test_strips_standalone_page_numbers(self):
        text = "Contenido antes.\n64597\nContenido después."
        assert "64597" not in clean_boilerplate(text)

    def test_strips_urls(self):
        text = "Contenido antes.\nhttp://www.gencat.cat/dogc\nContenido después."
        assert "gencat.cat" not in clean_boilerplate(text)

    def test_does_not_strip_short_real_content_repeated_twice(self):
        # El umbral es 3+ repeticiones a propósito: una frase real que
        # por casualidad se repite 2 veces no debe tratarse como ruido.
        text = "Sí, se permite.\nOtro contenido.\nSí, se permite.\nMás contenido."
        cleaned = clean_boilerplate(text)
        assert cleaned.count("Sí, se permite.") == 2