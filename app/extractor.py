from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from app.services_parsing import clean_tribunale_name

PERIZIA_KEYWORDS = [
    "perizia",
    "relazione di stima",
    "relazione",
    "stima",
    "ctu",
]

AVVISO_KEYWORDS = [
    "avviso di vendita",
    "avviso vendita",
    "avviso",
    "ordinanza di vendita",
    "vendita senza incanto",
]


@dataclass
class ExtractionResult:
    perizia_url: str | None
    avviso_url: str | None
    rge: str | None
    lotto: str | None
    tribunale: str | None
    data_asta: str | None
    citta: str | None
    indirizzo: str | None
    prezzo_base: str | None
    offerta_minima: str | None
    creditore_procedente: str | None


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _score_link(text: str, href: str, keywords: list[str]) -> int:
    t = (text or "").lower()
    h = (href or "").lower()
    score = 0

    if ".pdf" in h:
        score += 5

    for k in keywords:
        if k in t:
            score += 4
        if k in h:
            score += 3

    for bad in ["privacy", "cookie", "regolamento", "manuale", "guida"]:
        if bad in t or bad in h:
            score -= 5

    return score


def _extract_rge_and_lotto(text: str) -> tuple[str | None, str | None]:
    t = text.replace("\xa0", " ")

    rge = None
    m = re.search(r"(?:R\.?\s*G\.?\s*E\.?\s*[:\-]?\s*)?(\d{1,6}\s*/\s*\d{2,4})", t, flags=re.IGNORECASE)
    if m:
        rge = m.group(1).replace(" ", "")

    lotto = None
    m2 = re.search(r"lotto\s*(unico|\d+[a-zA-Z]?)", t, flags=re.IGNORECASE)
    if m2:
        val = m2.group(1).strip().lower()
        if val == "unico":
            lotto = "1"
        else:
            lotto = val.upper()

    return rge, lotto


def find_best_pdf_link(html: str, base_url: str, keywords: list[str]) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        abs_url = urljoin(base_url, href)
        text = a.get_text(" ", strip=True)
        text_lower = (text or "").lower()
        href_lower = href.lower()

        if ".pdf" in href_lower or any(k in text_lower or k in href_lower for k in keywords):
            candidates.append((_score_link(text, abs_url, keywords), abs_url))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_url = candidates[0]

    if best_score < 5:
        return None

    return best_url


def _extract_label_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{label}\s*[:\-]?\s*(.+?)(?=(?:\s+[A-Z][a-zà-ùA-Z0-9_/ ]+\s*:)|$)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            value = _norm_text(m.group(1))
            if value:
                return value
    return None


def _extract_money_near_labels(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{label}\s*[:\-]?\s*([€\s0-9\.\,]+)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            value = _norm_text(m.group(1))
            if value:
                return value
    return None


def _extract_date(text: str) -> str | None:
    patterns = [
        r"data asta\s*[:\-]?\s*(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})",
        r"asta\s*[:\-]?\s*(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})",
        r"vendita\s*[:\-]?\s*(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _extract_tribunale(text: str) -> str | None:
    patterns = [
        r"tribunale\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,80})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return clean_tribunale_name(f"Tribunale di {m.group(1)}")

    return None

def _extract_city_address(text: str) -> tuple[str | None, str | None]:
    m = re.search(
        r"\b(via|viale|piazza|p\.zza|corso|loc\.?|località|regione|strada)\s+([A-Za-zÀ-ÿ0-9'°/\-\. ]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        indirizzo = _norm_text(f"{m.group(1)} {m.group(2)}")
        city = None

        m2 = re.search(
            rf"([A-ZÀ-Ù][A-Za-zÀ-ÿ' ]+)\s*,?\s*{re.escape(indirizzo)}",
            text,
            flags=re.IGNORECASE,
        )
        if m2:
            city = _norm_text(m2.group(1))

        return city, indirizzo

    return None, None


def extract_from_asta_page(asta_url: str, timeout_sec: int = 20) -> ExtractionResult:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsteSuite/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout_sec) as client:
        r = client.get(asta_url)
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    page_text = _norm_text(page_text)

    rge, lotto = _extract_rge_and_lotto(page_text)
    perizia_url = find_best_pdf_link(html, asta_url, PERIZIA_KEYWORDS)
    avviso_url = find_best_pdf_link(html, asta_url, AVVISO_KEYWORDS)

    tribunale = _extract_tribunale(page_text)
    data_asta = _extract_date(page_text)

    citta, indirizzo = _extract_city_address(page_text)

    prezzo_base = _extract_money_near_labels(
        page_text,
        ["prezzo base", "base d'asta", "prezzo dell'asta", "valore base"],
    )
    offerta_minima = _extract_money_near_labels(
        page_text,
        ["offerta minima", "offerta minima ammissibile", "minima offerta"],
    )

    creditore_procedente = _extract_label_value(
        page_text,
        ["creditore procedente", "procedente", "creditore"],
    )

    return ExtractionResult(
        perizia_url=perizia_url,
        avviso_url=avviso_url,
        rge=rge,
        lotto=lotto,
        tribunale=tribunale,
        data_asta=data_asta,
        citta=citta,
        indirizzo=indirizzo,
        prezzo_base=prezzo_base,
        offerta_minima=offerta_minima,
        creditore_procedente=creditore_procedente,
    )