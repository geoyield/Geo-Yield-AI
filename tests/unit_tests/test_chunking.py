"""
Tests del chunker de normativa legal (backend/rag/chunking.py).

Los fixtures de este módulo usan fragmentos reales copiados del portal
NUMAMB del AMB (compartidos por el usuario) o extraídos con pdftotext de
los PDF reales que subió — no texto inventado. Esto incluye las
inconsistencias reales de la fuente (ver tests de regresión abajo).
"""

from backend.rag.chunking import VersioArticle, parse_legal_chunks, select_current_versions


class TestParseLegalChunksWebFormat:
    """Formato 'copy-paste de la web': varios artículos seguidos, con 'Descarregar'."""

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
    Formato 'PDF exportado desde el navegador' (un único artículo, con sus
    versiones históricas apiladas). Fixtures basados en pdftotext real
    contra los PDF que subió el usuario (Article_302.pdf, Article_303.pdf).
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
        # Regresión real y grave: los títulos largos se parten en 2 líneas
        # al extraer el PDF. Comprobar solo la primera línea siguiente para
        # encontrar el ancla hacía que la versión CONSOLIDADA se descartara
        # en silencio, dejando la ORIGINAL (desactualizada) como única
        # opción — un error grave para un sistema legal.
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