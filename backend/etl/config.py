"""
==============================================================================
ETL CONFIGURATION & PATH MANAGEMENT
==============================================================================
File: backend/etl/config.py

This module centralizes file paths and global constants for the ETL pipeline.
It acts as a single source of truth, preventing hardcoded values ("magic strings") 
from being scattered across the transformation scripts (income.py, mobility.py).
"""

from pathlib import Path

# ------------------------------------------------------------------------------
# DYNAMIC PATH RESOLUTION
# ------------------------------------------------------------------------------
# Using pathlib to dynamically resolve the project root. This ensures the 
# pipeline works seamlessly across different operating systems (Windows/Linux)
# without relying on hardcoded absolute paths.
# backend/etl/config.py -> backend/etl -> backend -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"

# ------------------------------------------------------------------------------
# DATA SOURCES (ZERO-FRICTION NAMING CONVENTION)
# ------------------------------------------------------------------------------
# We deliberately keep the raw filenames exactly as provided by the government 
# sources (MITMA, Open Data BCN, INE) instead of renaming them to 'clean' names.
# Why? This reduces human friction. When an analyst downloads next year's 
# update, they can just drop the file into the folder without remembering to 
# rename it manually, preventing pipeline crashes.
PATH_CENSCOMER = RAW_DATA_DIR / "241021_censcomercialbcn_opendata_2024_v5.csv"
PATH_INE_RENTA = RAW_DATA_DIR / "30896.csv"

# Note on GZIP: The MITMA dataset is massive, so they distribute it compressed (.csv.gz). 
# Pandas' read_csv detects the compression automatically by the file extension.
PATH_MITMA_MOBILITY = RAW_DATA_DIR / "20251015_Viajes_distritos.csv.gz"

# ------------------------------------------------------------------------------
# GLOBAL BUSINESS CONSTANTS
# ------------------------------------------------------------------------------
# INE Code for Barcelona municipality (Province 08 + Municipality 019).
# All geographical filtering in Phase 1 revolves around this constant. 
# Centralizing it here respects the DRY (Don't Repeat Yourself) principle.
BARCELONA_MUNICIPIO_CODE = "08019"