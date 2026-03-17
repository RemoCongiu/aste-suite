from __future__ import annotations

import os
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path


def _get_tesseract_cmd() -> str | None:
    candidates = [
        os.getenv("TESSERACT_CMD"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def _get_poppler_path() -> str | None:
    candidates = [
        os.getenv("POPPLER_PATH"),
        r"C:\poppler\Library\bin",
        r"C:\poppler\bin",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def extract_text_from_pdf_ocr(
    pdf_path: Path,
    dpi: int = 220,
    lang: str = "ita",
    max_pages: int = 12,
) -> dict:
    """
    OCR fallback per PDF scannerizzati.
    Ritorna:
    {
        "text": str,
        "pages_processed": int,
        "engine": "tesseract",
        "status": "ok" | "error",
        "error": str | None
    }
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        return {
            "text": "",
            "pages_processed": 0,
            "engine": "tesseract",
            "status": "error",
            "error": f"PDF non trovato: {pdf_path}",
        }

    tesseract_cmd = _get_tesseract_cmd()
    if not tesseract_cmd:
        return {
            "text": "",
            "pages_processed": 0,
            "engine": "tesseract",
            "status": "error",
            "error": "Tesseract non trovato. Imposta TESSERACT_CMD o installa Tesseract.",
        }

    poppler_path = _get_poppler_path()
    if not poppler_path:
        return {
            "text": "",
            "pages_processed": 0,
            "engine": "tesseract",
            "status": "error",
            "error": "Poppler non trovato. Imposta POPPLER_PATH o installa Poppler.",
        }

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        images = convert_from_path(
            str(pdf_path),
            dpi=dpi,
            poppler_path=poppler_path,
            first_page=1,
            last_page=max_pages,
        )

        parts: list[str] = []
        pages_processed = 0

        for image in images:
            text = pytesseract.image_to_string(
    image,
    lang=lang,
    config="--oem 3 --psm 6"
) or ""
            text = text.strip()
            if text:
                parts.append(text)
            pages_processed += 1

        full_text = "\n\n".join(parts).strip()

        return {
            "text": full_text,
            "pages_processed": pages_processed,
            "engine": "tesseract",
            "status": "ok",
            "error": None,
        }

    except Exception as e:
        return {
            "text": "",
            "pages_processed": 0,
            "engine": "tesseract",
            "status": "error",
            "error": str(e),
        }