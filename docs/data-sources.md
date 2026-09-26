# Data Sources Catalog

This document outlines the official data sources ingested by the ETL pipelines (Phase 1) and the Legal RAG engine (Phase 2 & 4). Establishing clear **Data Lineage** is a core requirement for transparency and auditing in this AI-driven architecture.

## 1. Geospatial and Socioeconomic Data (Phase 1)

These datasets populate the PostGIS relational database, forming the baseline for the `district_scorecard` metrics.

*   **Open Data BCN (Ajuntament de Barcelona):**
    *   **Dataset:** *Cens comercial de la ciutat de Barcelona*.
    *   **Usage:** Geolocation of existing competitors (bars, restaurants, cafes) to calculate market saturation.
    *   **Format:** CSV / GeoJSON.
*   **INE (Instituto Nacional de Estadística):**
    *   **Dataset:** *Atlas de Distribución de Renta de los Hogares (ADRH)*.
    *   **Usage:** Extraction of the average net income per household (`renta_media`) aggregated at the district level.
*   **MITMA (Ministerio de Transportes, Movilidad y Agenda Urbana):**
    *   **Dataset:** *Estudio de Movilidad con Big Data*.
    *   **Usage:** Mobile phone tracking data used to estimate the daily foot traffic (`daily_foot_traffic`) floating population in each district.

## 2. Legal and Regulatory Corpus (Phases 2 & 4)

These documents populate the Vector Database (`pgvector`) used by the AI Agent to evaluate commercial viability.

*   **NUMAMB (Normativa Urbanística Metropolitana):**
    *   **Source:** Àrea Metropolitana de Barcelona (AMB).
    *   **Usage:** Specific Urban Zoning regulations from the *Pla General Metropolità (PGM)*. Extracted via web browser PDF exports, capturing versions (Original, Modified, Consolidated).
*   **DOGC (Diari Oficial de la Generalitat de Catalunya):**
    *   **Usage:** Regional regulations (Orders and Decrees) that apply to the entire city (e.g., General opening hours for musical and recreational activities, like *Ordre INT/358/2011*).
*   **BOE (Boletín Oficial del Estado):**
    *   **Usage:** National laws applying to commercial activities across Spain.

## Data Governance Note
The AI Agent is strictly sandboxed. It does not browse the live internet for answers. It exclusively reasons over the immutable, verified institutional data listed above.