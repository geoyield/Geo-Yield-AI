"""
==============================================================================
RAG PIPELINE: RAW PDF EXTRACTION
==============================================================================
File: backend/rag/pdf_extraction.py

This module extracts raw text from normative PDFs (Urban Planning articles).
It acts as a Python wrapper around the system-level `pdftotext` binary 
(part of the Linux `poppler-utils` package).

Design Note:
We intentionally run the tool in simple mode (without the `-layout` flag).
Empirical testing on real government PDFs showed that attempting to preserve 
visual columns broke the logical line breaks of long legal titles, which in 
turn broke the Regex parsing in `chunking.py`.
"""

import subprocess
from pathlib import Path


def extract_text_from_pdf(path: Path) -> str:
    """
    Extracts text from a PDF file using the OS binary `pdftotext`.

    Exception Handling Note:
    If `pdftotext` fails (e.g., corrupt PDF, or poppler-utils not installed), 
    `subprocess.run` usually raises a generic CalledProcessError. 
    In a batch processing pipeline, this generic error is extremely hard to debug.
    We manually check the return code and raise a custom RuntimeError that 
    includes the exact file path and the standard error (stderr) output.
    """
    # Execute the command: pdftotext /path/to/file.pdf - (output to stdout)
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        capture_output=True,
        text=True,
    )
    # 0 indicates the OS command ran successfully
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed while processing {path}: {result.stderr.strip()}")
    return result.stdout
