from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_noise_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False

    # righe composte quasi solo da simboli
    if re.fullmatch(r"[\-_=~*#|.·,:;()\[\]\\/]+", line):
        return True

    lower = line.lower()

    # watermark e righe tipiche di portali/documenti ripetuti
    noise_patterns = [
        "astalegale.net - e' vietata la stampa",
        "pubblicazione eseguita giusta iscriz.",
        "elenco min. della giustizia",
    ]
    if any(p in lower for p in noise_patterns):
        return True

    return False


def _clean_extracted_text(text: str) -> str:
    """
    Pulisce il testo estratto dal PDF per renderlo più leggibile e stabile.
    """
    if not text:
        return ""

    text = _normalize_whitespace(text)

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()

        if not line:
            cleaned_lines.append("")
            continue

        if _is_noise_line(line):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _repetition_score(lines: list[str]) -> float:
    """
    Misura quanto il testo è composto da righe ripetute.
    1.0 = tutto ripetuto, 0.0 = nessuna ripetizione significativa.
    """
    normalized = [re.sub(r"\s+", " ", x.strip().lower()) for x in lines if x.strip()]
    if not normalized:
        return 1.0

    counts = Counter(normalized)
    repeated_items = sum(cnt for cnt in counts.values() if cnt > 1)
    return repeated_items / max(len(normalized), 1)


def _looks_like_good_text(text: str) -> bool:
    """
    Heuristica semplice per distinguere:
    - PDF testuale buono
    - PDF con testo povero/sporco
    - PDF dove pypdf prende solo watermark/righe ripetute
    """
    if not text:
        return False

    stripped = text.strip()
    if len(stripped) < 400:
        return False

    alnum_count = sum(ch.isalnum() for ch in stripped)
    printable_count = sum(ch.isprintable() and not ch.isspace() for ch in stripped)

    if printable_count == 0:
        return False

    alnum_ratio = alnum_count / max(printable_count, 1)
    if alnum_ratio < 0.45:
        return False

    words = re.findall(r"\b[\wÀ-ÿ'-]{2,}\b", stripped, flags=re.UNICODE)
    if len(words) < 80:
        return False

    lines = [x.strip() for x in stripped.splitlines() if x.strip()]
    if not lines:
        return False

    # Se troppe righe sono ripetute, è spesso watermark o rumore
    rep_score = _repetition_score(lines)
    if rep_score > 0.35:
        return False

    # Se le righe uniche sono troppo poche rispetto al totale, testo sospetto
    unique_ratio = len(set(lines)) / max(len(lines), 1)
    if unique_ratio < 0.30:
        return False

    return True


def extract_text_with_diagnostics(pdf_path: Path, max_chars: int = 120_000) -> dict:
    """
    Estrae testo dal PDF e restituisce anche metadati utili per capire
    se la qualità è sufficiente o se conviene attivare OCR.

    Ritorna un dict con:
    - text
    - pages_total
    - pages_with_text
    - raw_chars
    - cleaned_chars
    - quality ("good", "poor", "empty")
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF non trovato: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    pages_total = len(reader.pages)
    pages_with_text = 0
    current_len = 0

    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""

        txt = txt.strip()
        if txt:
            pages_with_text += 1
            parts.append(txt)
            current_len += len(txt)

        if current_len >= max_chars:
            break

    raw_text = "\n\n".join(parts).strip()
    cleaned_text = _clean_extracted_text(raw_text)
    cleaned_text = cleaned_text[:max_chars]

    if not cleaned_text:
        quality = "empty"
    elif _looks_like_good_text(cleaned_text):
        quality = "good"
    else:
        quality = "poor"

    return {
        "text": cleaned_text,
        "pages_total": pages_total,
        "pages_with_text": pages_with_text,
        "raw_chars": len(raw_text),
        "cleaned_chars": len(cleaned_text),
        "quality": quality,
    }


def extract_text_from_pdf(pdf_path: Path, max_chars: int = 120_000) -> str:
    """
    Compatibilità con il codice esistente.
    """
    result = extract_text_with_diagnostics(pdf_path=pdf_path, max_chars=max_chars)
    return result["text"]