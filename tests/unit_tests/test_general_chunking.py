"""
==============================================================================
UNIT TESTS: HEURISTIC NLP CHUNKER (GENERAL LAWS)
==============================================================================
File: tests/unit_tests/test_general_chunking.py

Tests the generalized legal NLP chunker (`backend/rag/general_chunking.py`).
The fixtures are synthetic texts designed to mimic real PDFs extracted via 
pdftotext from two different sources (Ordre INT/358/2011 from DOGC, Ley 1/2004 
from BOE). 

Architectural Goal:
Prove that a single Regex/Heuristic engine can correctly parse disparate 
document formats WITHOUT needing a specific configuration flag per institution.
"""

from backend.rag.general_chunking import clean_boilerplate, parse_articulo_general


class TestParseArticuloGeneralFormatoDogc:
    """Format: Regional DOGC ('Artículo N' on its own line, Title on the next)."""

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
        """
        Regression: Ensure lowercase inline references (e.g., 'en el artículo 20') 
        are not mistakenly parsed as new section headers.
        """
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
        """
        NLP Frequency Analysis: Header/Footer boilerplate repeated 3+ times 
        should be automatically detected and stripped without hardcoding the strings.
        """
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
    """Format: National BOE ('Artículo N. Título.' all on the same line)."""

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
        """
        Regression (Long Titles): If an index title is so long that it wraps to a 
        second line BEFORE the dot leaders start, the heuristic might miss it. 
        This caused fatal DB clashes (ON CONFLICT DO UPDATE).
        """
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
        """Same bug, but the title wraps across 3 lines before the dots."""
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
        """Proves the frequency analyzer works on BOE text (not just DOGC)."""
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
        """
        Regression: Catalan law uses compound numbering ('Artículo 111-1'). 
        The regex must capture the full compound number, otherwise '111-1' and 
        '111-2' will both be extracted as '111', causing a fatal DB overwrite.
        """
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
        """
        Safety Net / Defensive Programming:
        If parsing fails and extracts the same article twice, the ETL pipeline 
        must keep the chunk with the longest content (assuming the shorter one 
        is a spurious index stub). This prevents Postgres Upsert crashes.
        """
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
        """
        Threshold Validation: The algorithm strips lines repeated 3+ times. 
        A line repeated only 2 times must not be stripped, as it might just be 
        a naturally repeating legal phrase.
        """
        text = "Sí, se permite.\nOtro contenido.\nSí, se permite.\nMás contenido."
        cleaned = clean_boilerplate(text)
        assert cleaned.count("Sí, se permite.") == 2