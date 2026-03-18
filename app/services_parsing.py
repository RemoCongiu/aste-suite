from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.ocr_text import extract_text_from_pdf_ocr
from app.pdf_text import extract_text_from_pdf, extract_text_with_diagnostics


# =========================================================
# NORMALIZZAZIONE BASE
# =========================================================

def normalize_db_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {"nd", "n.d.", "null", "none", "-"}:
            return None
    return value


def clean_text_block(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).replace("\xa0", " ").strip()
    v = re.sub(r"\s+", " ", v)
    return v or None


def clean_tribunale_name(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).replace("\xa0", " ").strip()
    v = re.sub(r"\s+", " ", v)

    m = re.search(r"tribunale\s+di\s+([A-Za-zÀ-ÿ' -]+)", v, re.IGNORECASE)
    if not m:
        return None

    name = re.split(
        r"\b(sez\.?|sezione|soggetti|delegato|giudice|custode|lotto|rge|proc\.?|procedura|vendita)\b",
        m.group(1).strip(),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,.;:-")

    if not name:
        return None
    return f"Tribunale di {name.title()}"


def normalize_money_string(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).replace("€", " ").replace("euro", " ")
    v = v.replace("\xa0", " ")
    v = re.sub(r"\s+", " ", v).strip(" .;:-")
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)", v)
    if not m:
        return None

    num = m.group(1)
    try:
        normalized = float(num.replace(".", "").replace(",", "."))
        return f"€ {normalized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"€ {num}"


def normalize_date_string(value: str | None) -> str | None:
    if not value:
        return None

    v = re.sub(r"\s+", " ", str(value).strip())
    m = re.search(r"(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})", v)
    if m:
        gg = m.group(1).zfill(2)
        mm = m.group(2).zfill(2)
        aa = m.group(3)
        if len(aa) == 2:
            aa = "20" + aa
        return f"{gg}/{mm}/{aa}"

    months = {
        "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
        "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
        "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
    }
    m = re.search(r"(\d{1,2})\s+([A-Za-zà-ù]+)\s+(\d{4})", v, re.IGNORECASE)
    if not m:
        return v
    mese = months.get(m.group(2).lower())
    if not mese:
        return v
    return f"{m.group(1).zfill(2)}/{mese}/{m.group(3)}"


def normalize_subalterni(value: str | None) -> str | None:
    if not value:
        return None
    nums = re.findall(r"\d+", str(value))
    if not nums:
        return clean_text_block(value)
    seen: list[str] = []
    for n in nums:
        if n not in seen:
            seen.append(n)
    return ", ".join(seen)


# =========================================================
# LETTURA TESTO PDF
# =========================================================

def read_pdf_text_with_fallback(pdf_path: str | Path) -> str:
    pdf_path = Path(pdf_path)
    diag = extract_text_with_diagnostics(pdf_path)
    text = (diag.get("text") or "").strip() if isinstance(diag, dict) else ""
    quality = diag.get("quality") if isinstance(diag, dict) else None

    if text and quality == "good":
        return text

    ocr_result = extract_text_from_pdf_ocr(pdf_path)
    if isinstance(ocr_result, dict):
        ocr_text = (ocr_result.get("text") or "").strip()
        if ocr_result.get("status") == "ok" and ocr_text:
            return ocr_text
    elif isinstance(ocr_result, str) and ocr_result.strip():
        return ocr_result.strip()

    if text:
        return text

    try:
        return extract_text_from_pdf(pdf_path)
    except Exception:
        return ""


# =========================================================
# HELPERS PARSING
# =========================================================

def extract_money_near_labels(text: str, labels: list[str], window: int = 220) -> str | None:
    if not text:
        return None

    clean = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    amount_pattern = r"(?:€\s*|euro\s*)?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|(?:€\s*|euro\s*)?\d+(?:,\d{2})?"
    for label in labels:
        pattern = rf"{label}.{{0,{window}}}?({amount_pattern})"
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            val = normalize_money_string(m.group(1))
            if val:
                return val
    return None


# =========================================================
# AVVISO
# =========================================================

def extract_avviso_fields_from_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    def first(patterns):
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                return clean_text_block(m.group(1) if m.lastindex else m.group(0))
        return None

    def money_from_tabular_row(row_patterns, value_patterns):
        for row_pat in row_patterns:
            m = re.search(row_pat, clean, re.IGNORECASE)
            if not m:
                continue
            row_text = m.group(0)
            for vpat in value_patterns:
                vm = re.search(vpat, row_text, re.IGNORECASE)
                if vm:
                    val = normalize_money_string(vm.group(1))
                    if val:
                        return val
        return None

    rge = first([
        r"(?:r\.?\s*g\.?\s*e\.?\s*(?:n\.?)?\s*)(\d{1,6}\s*/\s*\d{2,4})",
        r"procedura\s+esecutiva\s*(\d{1,6}\s*/\s*\d{2,4})",
        r"fallimento\s*n\.?\s*(\d{1,6}\s*/\s*\d{2,4})",
    ])
    if rge:
        rge = rge.replace(" ", "")

    lotto = first([r"\blotto\s*(unico|\d+[A-Za-z]?)"])
    if lotto:
        lotto = "1" if lotto.lower() == "unico" else lotto

    tribunale = first([r"\btribunale(?:\s+ordinario)?\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,80})"])
    if tribunale:
        tribunale = clean_tribunale_name(f"Tribunale di {tribunale}") or tribunale

    data_asta = normalize_date_string(first([
        r"il\s+giorno\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})\s+alle",
        r"vendita\s+(?:senza\s+incanto\s+)?(?:avrà\s+luogo\s+)?il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{4})",
    ]))

    citta = first([
        r"unità\s+immobiliare.*?\bin\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+),\s*località",
        r"unità\s+immobiliare.*?\bin\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+),\s*(?:via|viale|piazza|corso)",
        r"comune\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+)",
    ])

    indirizzo = first([
        r"(località\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+\s+(?:via|viale|piazza|corso)\s+[A-Za-zÀ-ÿ0-9' .,\-]+?(?:n\.?\s*\d+|\d+))",
        r"((?:via|viale|piazza|corso)\s+[A-Za-zÀ-ÿ0-9' .,\-]+?(?:n\.?\s*\d+|\d+))",
    ])

    occupazione = first([
        r"stato\s+di\s+possesso\s*:\s*([A-Za-zÀ-ÿ ]+)",
        r"stato\s+occupativo\s*:\s*([A-Za-zÀ-ÿ ]+)",
        r"occupato\s+da\s+([A-Za-zÀ-ÿ ]+)",
    ])

    foglio = first([r"\bfoglio\s+(\d+)"])
    mappale = first([r"\bparticella\s+(\d+)", r"\bmappale\s+(\d+)", r"\bpart\.\s*(\d+)"])
    subalterno = normalize_subalterni(first([r"\bsubalterni?\s*:\s*([^.;]+)", r"\bsub\.\s*([^.;]+)"]))

    prezzo_base = (
        extract_money_near_labels(clean, [
            r"prezzo\s+base", r"prezzo\s+base\s+d[’']asta", r"prezzo\s+a\s+base\s+d[’']asta",
            r"base\s+d[’']asta", r"valore\s+d[’']asta", r"prezzo\s+di\s+vendita",
        ], window=260)
        or money_from_tabular_row(
            [r"(?:prezzo\s+base[^\.]{0,200})", r"(?:base\s+d[’']asta[^\.]{0,200})"],
            [r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"],
        )
    )

    offerta_minima = (
        extract_money_near_labels(clean, [
            r"offerta\s+minima\s+non\s+inferiore\s+a", r"offerta\s+minima", r"minima\s+offerta",
            r"offerta\s+irriducibile", r"offerta\s+minima\s+ammissibile", r"offerta\s+efficace\s+non\s+inferiore\s+a",
            r"offerta\s+pari\s+almeno\s+al", r"offerta\s+non\s+inferiore\s+a",
        ], window=260)
        or money_from_tabular_row(
            [r"(?:offerta\s+minima[^\.]{0,220})", r"(?:minima\s+offerta[^\.]{0,220})"],
            [r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"],
        )
    )

    rilancio_minimo = extract_money_near_labels(clean, [r"rilancio\s+minimo", r"aumento\s+minimo", r"rilancio\s+in\s+caso\s+di\s+gara"], window=180)
    deposito_cauzionale = extract_money_near_labels(clean, [r"deposito\s+cauzionale", r"\bcauzione"], window=180)
    prezzo_base_offerte_residuali = extract_money_near_labels(clean, [r"prezzo\s+base\s+per\s+le\s+offerte\s+residuali", r"base\s+d[’']asta\s+per\s+le\s+offerte\s+residuali"], window=220)
    valore_perizia = extract_money_near_labels(clean, [r"valore\s+di\s+stima", r"valore\s+di\s+mercato", r"valore\s+del\s+compendio", r"valore\s+peritale", r"stimato\s+in"], window=220)
    delegato = first([r"((?:avv|dott|notaio)\.\s+[A-Z][A-Za-zÀ-ÿ\s]+)"])
    descrizione_immobile = clean_text_block(first([
        r"oggetto\s+della\s+vendita\s*:\s*([^.;]{30,1000})",
        r"lotto\s+\w+\s*[:\-]\s*([^.;]{30,1000})",
        r"piena\s+proprietà\s+di\s*([^.;]{30,1000})",
    ]))

    categoria_catastale = first([r"categoria\s+catastale\s*([A-Z]\/\d+)", r"cat\.\s*([A-Z]\/\d+)", r"categoria\s*([A-Z]\/\d+)"])
    catasto = first([r"catasto\s+(fabbricati|terreni)"])
    if catasto:
        catasto = f"Catasto {catasto.title()}"

    if not offerta_minima and prezzo_base:
        m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", prezzo_base)
        if m:
            try:
                pb = float(m.group(1).replace(".", "").replace(",", "."))
                om = pb * 0.75
                offerta_minima = f"€ {om:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                pass

    return {
        "rge": rge,
        "lotto": lotto,
        "tribunale": tribunale,
        "data_asta": data_asta,
        "citta": citta,
        "indirizzo": indirizzo,
        "occupazione": occupazione,
        "foglio": foglio,
        "mappale": mappale,
        "subalterno": subalterno,
        "catasto": catasto,
        "categoria_catastale": categoria_catastale,
        "prezzo_base": prezzo_base,
        "offerta_minima": offerta_minima,
        "rilancio_minimo": rilancio_minimo,
        "deposito_cauzionale": deposito_cauzionale,
        "prezzo_base_offerte_residuali": prezzo_base_offerte_residuali,
        "valore_perizia": valore_perizia,
        "delegato": delegato,
        "descrizione_immobile": descrizione_immobile,
    }


# =========================================================
# PERIZIA
# =========================================================

def extract_structured_fields_from_perizia_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    def first(patterns):
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                return clean_text_block(m.group(1) if m.lastindex else m.group(0))
        return None

    rge = first([r"proc\.\s*r\.?\s*g\.?\s*n\.?\s*(\d{1,6}\s*/\s*\d{2,4})", r"r\.?\s*g\.?\s*e\.?\s*(?:n\.?)?\s*(\d{1,6}\s*/\s*\d{2,4})"])
    if rge:
        rge = rge.replace(" ", "")

    tribunale = first([r"tribunale\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,80})"])
    if tribunale:
        tribunale = clean_tribunale_name(f"Tribunale di {tribunale}") or tribunale

    lotto = first([r"lotto\s+(unico|\d+[A-Za-z]?)"])
    if lotto:
        lotto = "1" if lotto.lower() == "unico" else lotto

    citta = first([r"comune\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+)"])
    indirizzo = first([r"((?:via|viale|piazza|corso|località|loc\.)\s+[A-Za-zÀ-ÿ0-9' .,\-]+?(?:n\.?\s*\d+|\d+))"])
    foglio = first([r"\bfoglio\s+(\d+)"])
    mappale = first([r"\bparticella\s+(\d+)", r"\bmappale\s+(\d+)", r"\bpart\.\s*(\d+)"])
    subalterno = normalize_subalterni(first([r"\bsubalterni?\s*[: ]\s*([^.;\n]+)", r"\bsub\.\s*([^.;\n]+)"]))
    occupazione = first([r"stato\s+di\s+possesso[^.\n]{0,160}(libero|occupato)", r"stato\s+di\s+occupazione[^.\n]{0,160}(libero|occupato)", r"occupato\s+da\s+([^.\n]{5,200})"])
    valore_perizia = extract_money_near_labels(clean, [r"valore\s+di\s+mercato", r"valore\s+di\s+stima", r"valore\s+del\s+bene", r"valore\s+complessivo", r"stima\s+del\s+bene", r"valore\s+peritale", r"stimato\s+in"], window=260)
    prezzo_base = extract_money_near_labels(clean, [r"prezzo\s+base", r"base\s+d[’']asta", r"valore\s+di\s+asta"], window=180)
    catasto = first([r"catasto\s+(fabbricati|terreni)"])
    if catasto:
        catasto = f"Catasto {catasto.title()}"
    categoria_catastale = first([r"categoria\s+catastale\s*([A-Z]\/\d+)", r"cat\.\s*([A-Z]\/\d+)", r"categoria\s*([A-Z]\/\d+)"])

    return {
        "rge": rge,
        "tribunale": tribunale,
        "lotto": lotto,
        "citta": citta,
        "indirizzo": indirizzo,
        "foglio": foglio,
        "mappale": mappale,
        "subalterno": subalterno,
        "occupazione": occupazione,
        "valore_perizia": valore_perizia,
        "prezzo_base": prezzo_base,
        "catasto": catasto,
        "categoria_catastale": categoria_catastale,
    }


def parse_ai_json(asta) -> dict:
    if not getattr(asta, "ai_result_json", None):
        return {}
    try:
        return json.loads(asta.ai_result_json)
    except Exception:
        return {}
