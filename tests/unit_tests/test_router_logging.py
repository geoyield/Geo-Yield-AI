"""
The whole application logs through backend/observability.

Checks the logger hierarchy (which is what makes `filter logger like
/api.informes/` work in Logs Insights), that trace ids reach the modules
running inside a request, and that the notable failure paths are not silent.
"""

import pytest

from backend.api import api, deps
from backend.api.routers import articles, competitors, logs, reports
from backend.api.routers import geocoding as geocoding_router
from backend.geo import amb_identify, geocoding
from backend.ia import agent
from backend.observability import configure_logging, set_trace_id
from backend.observability.context import reset_trace_id
from backend.rag import gemini_adapter

ALL_MODULES = (
    api, deps, reports, articles, competitors, geocoding_router,
    geocoding, amb_identify, agent, gemini_adapter,
)

# The five flat names every module used to share, which made it impossible to
# filter by module or set a level for one subsystem.
OLD_FLAT_NAMES = {
    "geoyield_api", "geoyield_geocoding", "geoyield_agent",
    "geoyield_rag", "geoyield_etl",
}


@pytest.fixture
def production_logging(monkeypatch):
    """
    Returns a callable rather than configuring directly: pytest swaps
    sys.stdout per test phase, and StreamHandler captures the stream when it
    is built, so configuring during setup would write to a buffer that
    capsys.readouterr() no longer reads. Same trap as in test_logging.py.
    """
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("LOG_CLOUDWATCH_ENABLED", raising=False)
    monkeypatch.delenv("LOG_CLOUDWATCH_GROUP", raising=False)
    return lambda: configure_logging(force=True)


@pytest.mark.parametrize("module,expected", [
    (api, "geoyield.api"),
    (deps, "geoyield.api.deps"),
    (reports, "geoyield.api.informes"),
    (articles, "geoyield.api.articulos"),
    (competitors, "geoyield.api.competidores"),
    (geocoding_router, "geoyield.api.geocodificacion"),
    (geocoding, "geoyield.geo.geocoding"),
    (amb_identify, "geoyield.geo.amb_identify"),
    (agent, "geoyield.ia.agent"),
    (gemini_adapter, "geoyield.rag.gemini_adapter"),
])
def test_each_module_uses_a_namespaced_logger(module, expected):
    assert module.logger.name == expected


def test_the_logs_router_uses_the_frontend_namespace():
    assert logs.frontend_logger.name == "geoyield.frontend"


def test_no_module_still_uses_an_old_flat_logger_name():
    for module in ALL_MODULES:
        assert module.logger.name not in OLD_FLAT_NAMES


def test_every_logger_lives_under_the_geoyield_namespace():
    """A single setLevel on "geoyield" turns the whole application up or down."""
    for module in ALL_MODULES:
        assert module.logger.name.startswith("geoyield.")
    assert logs.frontend_logger.name.startswith("geoyield.")


def test_the_api_logger_is_the_parent_of_the_api_layer():
    for module in (deps, reports, articles, competitors, geocoding_router):
        assert module.logger.name.startswith(api.logger.name + ".")


def test_no_module_configures_handlers_of_its_own(production_logging, capsys):
    """
    They all inherit the root formatter, which is what keeps one schema
    across the whole service.
    """
    production_logging()
    for module in ALL_MODULES:
        assert module.logger.handlers == [], f"{module.__name__} must not add handlers"
        assert module.logger.propagate is True

    articles.logger.warning("reaches the root handler")
    assert '"logger": "geoyield.api.articulos"' in capsys.readouterr().out


def test_geo_and_rag_modules_inherit_the_request_trace_id(production_logging, capsys):
    """
    These run inside API requests, so their lines must carry the trace id the
    middleware pinned -- that is what ties a slow report to the RAG call
    behind it.
    """
    production_logging()
    token = set_trace_id("t-geo-1")
    try:
        geocoding.logger.warning("upstream geocoder failed")
        agent.logger.warning("retrieval returned nothing")
    finally:
        reset_trace_id(token)

    out = capsys.readouterr().out
    assert out.count('"trace_id": "t-geo-1"') == 2
    assert '"logger": "geoyield.geo.geocoding"' in out
    assert '"logger": "geoyield.ia.agent"' in out


def test_a_missing_cited_article_is_logged(production_logging, capsys):
    """A cited article that 404s signals a hallucinated citation."""
    production_logging()

    class _Result:
        def mappings(self):
            return self

        def first(self):
            return None

    class _Session:
        def execute(self, *_args, **_kwargs):
            return _Result()

    with pytest.raises(Exception) as excinfo:
        articles.obtener_articulo(
            fuente_legal="PGM 1976", numero_articulo="999", db=_Session()
        )

    assert getattr(excinfo.value, "status_code", None) == 404
    out = capsys.readouterr().out
    assert "articulo.no_encontrado" in out
    assert '"numero_articulo": "999"' in out


def test_report_failure_puts_district_in_context_not_the_message(production_logging, capsys):
    """
    Interpolating the district into the message would force a regex in Logs
    Insights; as a context field it can be filtered directly.
    """
    production_logging()
    try:
        raise RuntimeError("the model is unreachable")
    except RuntimeError:
        reports.logger.exception(
            "Report generation failed",
            extra={"context": {"codi_districte": 3, "zona_pgm": "13b"}},
        )

    out = capsys.readouterr().out
    assert '"message": "Report generation failed"' in out
    assert '"codi_districte": 3' in out
    assert '"type": "RuntimeError"' in out