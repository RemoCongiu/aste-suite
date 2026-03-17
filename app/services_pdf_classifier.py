from pathlib import Path
import re
from typing import Tuple, Optional

from app.pdf_text import extract_text_from_pdf


# ---------------------------------------------------------
# KEYWORDS
# ---------------------------------------------------------

PERIZIA_KEYWORDS = [
    r"relazione\s+di\s+stima",
    r"perito",
    r"consulente\s+tecnico",
    r"esperto\s+stimatore",
    r"stima\s+del\s+bene",
]

AVVISO_KEYWORDS = [
    r"avviso\s+di\s+vendita",
    r"offerta\s+minima",
    r"prezzo\s+base",
    r"gara\s+telematica",
    r"delegato\s+alla\s+vendita",
]


# ---------------------------------------------------------
# UTILS
# ---------------------------------------------------------

def _normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _match_keywords(text: str, patterns) -> int:
    score = 0
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            score += 1
    return score


# ---------------------------------------------------------
# CLASSIFIER
# ---------------------------------------------------------

def classify_pdf_document(pdf_path: Path) -> Tuple[Optional[str], int, int]:
    """
    Restituisce:
        ("perizia" | "avviso" | None, score_perizia, score_avviso)
    """

    try:
        text = extract_text_from_pdf(pdf_path)
    except Exception:
        return None, 0, 0

    text = _normalize(text[:4000])  # bastano le prime pagine

    score_perizia = _match_keywords(text, PERIZIA_KEYWORDS)
    score_avviso = _match_keywords(text, AVVISO_KEYWORDS)

    if score_perizia > score_avviso and score_perizia > 0:
        return "perizia", score_perizia, score_avviso

    if score_avviso > score_perizia and score_avviso > 0:
        return "avviso", score_perizia, score_avviso

    return None, score_perizia, score_avviso