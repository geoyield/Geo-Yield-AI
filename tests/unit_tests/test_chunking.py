"""
==============================================================================
UNIT TESTS: LEGAL RAG CHUNKER
==============================================================================
File: tests/unit_tests/test_chunking.py

Tests the semantic segmentation logic defined in `backend/rag/chunking.py`.

Testing Strategy:
The string fixtures used in these tests are NOT fake 'Lorem Ipsum' text. 
They are literal copy-pastes of the raw `pdftotext` output from real 
government Urban Planning (PGM) documents. This guarantees the Regex 
engine is tested against the actual formatting inconsistencies of the source.
"""

from backend.rag.chunking import VersioArticle, parse_legal_chunks, select_current_versions


class TestParseLegalChunksWebFormat:
    """Tests the parsing logic against the format obtained by copy-pasting the web."""

    def test_parses_simple_article(self):
        text = """Article 278. Ús comercial


Descarregar
Expedient: 1985/000604
És l'ús corresponent a locals oberts al públic destinats al comerç.
Llegir més
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "278"
        assert chunks[0].titulo == "Ús comercial"
        assert chunks[0].expedient == "1985/000604"
        assert chunks[0].versio == VersioArticle.ORIGINAL
        assert "Llegir més" not in chunks[0].contenido

    def test_regression_missing_closing_parenthesis(self):
        """
        Regression Test: Real-world typos in the government portal.
        Article 302 was missing a closing parenthesis in 'consolidat'.
        The Regex must be robust enough to handle these institutional typos.
        """
        text = """Article 302 (consolidat. Zona de nucli antic


Descarregar
Darrera modificació: 14.12.2018
Text consolidat que incorpora les modificacions dels expedients anteriors

Comercial. S'admet en edificis exclusius sense limitació.

Article 302 (modificació). Zona de nucli antic

Article 302. Zona de nucli antic

Llegir més
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "302"
        assert chunks[0].versio == VersioArticle.CONSOLIDAT

    def test_regression_multiline_trailing_navigation_noise(self):
        """Ensures that internal UI navigation links are not embedded as legal text."""
        text = """Article 225 (consolidat). Planta baixa


Descarregar
Darrera modificació: 02.03.1999
Text consolidat que incorpora les modificacions dels expedients anteriors

La planta baixa es defineix per als diferents tipus d'ordenació.

Article 225 (modificació). Planta baixa

Article 225. Planta baixa

Llegir més
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        content = chunks[0].contenido
        assert content == "La planta baixa es defineix per als diferents tipus d'ordenació."
        assert "Article 225" not in content

    def test_parses_multiple_articles_in_sequence(self):
        """Ensures the regex accurately finds boundaries between adjacent articles."""
        text = """Article 311. Zona industrial


Descarregar
Expedient: 1985/000604
S'admeten les cafeteries, restaurants, bars i similars.
Llegir més
Article 312. Zones de remodelació


Descarregar
Expedient: 1985/000604
Comercial. Es permet.
Llegir més
"""
        chunks = parse_legal_chunks(text)
        assert [c.numero_articulo for c in chunks] == ["311", "312"]
        assert "cafeteries" in chunks[0].contenido
        assert "cafeteries" not in chunks[1].contenido

    def test_article_with_letter_suffix(self):
        """Verifies that article numbers with letters (e.g., 285bis) are parsed."""
        text = """Article 285bis. Habitatge assequible


Descarregar
Expedient: 2018/067588
Article incorporat íntegrament amb posterioritat a l'aprovació del PGM

Es consideren habitatge assequible els habitatges de protecció pública.
Llegir més
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "285bis"


class TestParseLegalChunksPdfFormat:
    """
    Tests the parsing logic against the format obtained by exporting the 
    browser page to PDF (which stacks historical versions on top of each other).
    """

    def test_pdf_format_has_no_descarregar(self):
        text = """Article 311. Zona industrial
Expedient: 1985/000604
1. Els usos permesos a la zona industrial són els següents:
S'admeten les cafeteries, restaurants, bars i similars.
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].numero_articulo == "311"
        assert "Descarregar" not in text

    def test_regression_title_wraps_across_lines(self):
        """
        CRITICAL REGRESSION TEST:
        Long titles wrap to a new line in the PDF output. Originally, this caused 
        the parser to completely miss the 'Consolidated' version, leaving the LLM 
        with the outdated 1985 original law. This test ensures the Regex allows 
        for multiline matching without losing the title anchor.
        """
        text = """Article 302 (consolidat. Zona de nucli antic: de substitució de
l'edificació antiga i de conservació del Centre històric
Darrera modificació: 14.12.2018
Text consolidat que incorpora les modificacions dels expedients anteriors
En aquesta zona es permeten els usos següents:
3. Comercial. S'admet en edificis exclusius sense limitació.
"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].versio == VersioArticle.CONSOLIDAT
        assert chunks[0].titulo == (
            "Zona de nucli antic: de substitució de l'edificació antiga i de "
            "conservació del Centre històric"
        )

    def test_selects_consolidat_over_original_when_both_present(self):
        """
        Compliance Verification:
        Guarantees the system drops the repealed law and keeps the active one.
        """
        text = """Article 303 (consolidat). Zones en densificació urbana (intensiva i
semiintensiva)
Darrera modificació: 14.12.2018
Text consolidat que incorpora les modificacions dels expedients anteriors
Comercial. S'admet.
Article 303. Zones en densificació urbana (intensiva i semiintensiva)
Expedient: 1985/000604
Comercial. Text original, ya no vigente.
"""
        all_versions = parse_legal_chunks(text)
        assert {c.versio for c in all_versions} == {VersioArticle.CONSOLIDAT, VersioArticle.ORIGINAL}

        current = select_current_versions(all_versions)
        assert len(current) == 1
        assert current[0].versio == VersioArticle.CONSOLIDAT
        assert "ya no vigente" not in current[0].contenido

    def test_selects_original_when_no_consolidat_exists(self):
        text = """Article 311. Zona industrial
Expedient: 1985/000604
S'admeten les cafeteries, restaurants, bars i similars.
"""
        current = select_current_versions(parse_legal_chunks(text))
        assert len(current) == 1
        assert current[0].versio == VersioArticle.ORIGINAL

    def test_modificacio_parcial_never_selected(self):
        """
        Compliance Verification:
        Guarantees that incomplete '[...]' partial modifications are NEVER 
        passed to the LLM, as they lack the full context of the law.
        """
        text = """Article 302 (consolidat). Zona de nucli antic
Darrera modificació: 14.12.2018
Text consolidat que incorpora les modificacions dels expedients anteriors
Comercial. Texto consolidado vigente.
Article 302 (modificació). Zona de nucli antic
Darrera modificació: 14.12.2018
Amplia apartat únic
Comercial. [...] fragmento parcial de la modificación.
Article 302. Zona de nucli antic
Expedient: 1985/000604
Comercial. Texto original desactualizado.
"""
        all_versions = parse_legal_chunks(text)
        assert len(all_versions) == 3
        current = select_current_versions(all_versions)
        assert len(current) == 1
        assert current[0].versio == VersioArticle.CONSOLIDAT

    def test_strips_page_header_and_footer_boilerplate(self):
        """Verifies that visual PDF artifacts do not pollute the text embedding."""
        text = """13/8/26, 23:02

Índex normes urbanístiques - Territori - Àrea Metropolitana de Barcelona

Article 311. Zona industrial
Expedient: 1985/000604
1. Els usos permesos a la zona industrial són els següents:
S'admeten les cafeteries, restaurants, bars i similars.

https://www.amb.cat/web/territori/gestio-i-organitzacio/numamb/index-normes-urbanistiques

1/1

"""
        chunks = parse_legal_chunks(text)
        assert len(chunks) == 1
        content = chunks[0].contenido
        for noise in ["23:02", "Índex normes urbanístiques", "amb.cat", "1/1"]:
            assert noise not in content