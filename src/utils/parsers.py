"""File parsing and text extraction utilities for SecondSelf."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import pypdf
from pypdf.errors import PdfReadError, FileNotDecryptedError


MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB cap


def parse_file(file_path: str) -> Tuple[str, str, dict]:
    """
    Parse a local document (.txt, .md, .pdf) and return (title, content, metadata).
    Handles edge cases: missing files, >25MB files, scanned PDFs, password protection.
    """
    # Clean leading/trailing quotes often copied from Windows paths
    clean_path = file_path.strip().strip("'\"")
    path = Path(clean_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {clean_path}")

    if path.is_dir():
        # List candidate files in folder to assist user
        candidates = [
            f.name for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in [".md", ".txt", ".pdf"]
        ][:5]
        hint = f" Example files inside: {', '.join(candidates)}" if candidates else ""
        raise ValueError(f"Path is a folder, not a file: {clean_path}. Please point to a specific file.{hint}")

    if not path.is_file():
        raise ValueError(f"Specified path is not a file: {clean_path}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of 25 MB."
        )

    if file_size == 0:
        raise ValueError(f"Cannot capture empty file (0 bytes): {path.name}")

    extension = path.suffix.lower()
    title = path.stem.replace("_", " ").replace("-", " ").title()
    metadata = {
        "file_name": path.name,
        "file_path": str(path),
        "file_size_bytes": file_size,
        "extension": extension,
        "warnings": [],
    }

    # 1. Plain Text and Markdown files
    if extension in [".txt", ".md", ".markdown", ".rst", ".json", ".csv"]:
        content = _read_text_file(path)
        # Try inferring better title from first Markdown H1
        first_line = content.strip().split("\n")[0]
        if first_line.startswith("# "):
            title = first_line.lstrip("# ").strip()
        return title, content, metadata

    # 2. PDF files
    elif extension == ".pdf":
        content, page_count, warnings = _read_pdf_file(path)
        metadata["page_count"] = page_count
        metadata["warnings"].extend(warnings)
        return title, content, metadata

    else:
        raise ValueError(
            f"Unsupported file format '{extension}'. Supported formats: .txt, .md, .pdf, .json, .csv"
        )


def _read_text_file(path: Path) -> str:
    """Read text file with multi-encoding fallback."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode text file {path.name} with standard UTF-8 or Latin-1 encodings.")


def _read_pdf_file(path: Path) -> Tuple[str, int, list[str]]:
    """Extract text from PDF pages with scanned PDF detection."""
    warnings = []
    try:
        reader = pypdf.PdfReader(str(path))
    except FileNotDecryptedError:
        raise ValueError(f"PDF is encrypted or password-protected: {path.name}")
    except PdfReadError as e:
        raise ValueError(f"Corrupted or invalid PDF file: {e}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError(f"PDF is encrypted with password protection: {path.name}")

    page_count = len(reader.pages)
    extracted_pages = []

    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(page_text.strip())
        except Exception as e:
            warnings.append(f"Failed to extract page {idx + 1}: {e}")

    full_text = "\n\n".join(extracted_pages)

    # Check for scanned / image-only PDF
    if len(full_text.strip()) < 50 and page_count > 0:
        warnings.append(
            "Scanned PDF detected: Less than 50 text characters extracted across pages. OCR required for full content."
        )
        if not full_text.strip():
            full_text = f"Document: {path.name}\n(Scanned PDF: Contains no selectable/extractable text layer.)"

    return full_text, page_count, warnings
