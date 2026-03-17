from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.ocr_text import extract_text_from_pdf_ocr
from app.pdf_text import extract_text_from_pdf


def normalize_db_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {"nd", "n.d.", "null", "none", "-"}:
            return None
        return value
    return value


def clean_text_block(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).replace("\xa0", " ").strip()
    v = re.sub(r"\s+", " ", v)
    return v or None


def prefer_value(*values):
    for v in values:
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.strip()
            if vv and vv.lower() not in {"-", "nd", "n.d.", "null", "none", "non disponibile"}:
                return vv
        else:
            return v
    return None


def clean_tribunale_name(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).replace("\xa0", " ").strip()
    v = re.sub(r"\s+", " ", v)

    m = re.search(r"tribunale\s+di\s+([A-Za-zÀ-ÿ' -]+)", v, re.IGNORECASE)
    if not m:
        return None

    name = m.group(1).strip()

    name = re.split(
        r"\b(sez\.?|sezione|soggetti|delegato|giudice|custode|lotto|rge|proc\.|procedura|vendita)\b",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,.;:-")

    if not name:
        return None

    return f"Tribunale di {name.title()}"


def normalize_money_string(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).strip()
    v = v.replace("\xa0", " ")
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"(?i)euro", "", v)
    v = v.replace("€", "")
    v = v.strip(" .;:-")

    m = re.search(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?", v)
    if not m:
        return None

    num = m.group(0)
    try:
        normalized = float(num.replace(".", "").replace(",", "."))
        return f"€ {normalized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return None


def normalize_date_string(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).strip()
    v = re.sub(r"\s+", " ", v)

    months = {
        "gennaio": "01",
        "febbraio": "02",
        "marzo": "03",
        "aprile": "04",
        "maggio": "05",
        "giugno": "06",
        "luglio": "07",
        "agosto": "08",
        "settembre": "09",
        "ottobre": "10",
        "novembre": "11",
        "dicembre": "12",
    }

    m = re.match(r"(\d{1,2})\s+([A-Za-zà-ù]+)\s+(\d{4})", v, re.IGNORECASE)
    if m:
        day = m.group(1).zfill(2)
        month_name = m.group(2).lower()
        year = m.group(3)
        month = months.get(month_name)
        if month:
            return f"{day}/{month}/{year}"

    for fmt_in in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            d = datetime.strptime(v, fmt_in)
            return d.strftime("%d/%m/%Y")
        except Exception:
            pass

    return v


def normalize_subalterni(value: str | None) -> str | None:
    if not value:
        return None

    v = str(value).strip()
    nums = re.findall(r"\d+", v)
    if not nums:
        return clean_text_block(v)

    uniq = []
    for n in nums:
        if n not in uniq:
            uniq.append(n)

    return ", ".join(uniq)


def extract_text_with_fallback(pdf_path: Path) -> str:
    try:
        text = extract_text_from_pdf(pdf_path)
        if text and text.strip():
            return text
    except Exception:
        pass

    try:
        ocr = extract_text_from_pdf_ocr(pdf_path)
        if isinstance(ocr, dict):
            text = ocr.get("text") or ""
            if text.strip():
                return text
        elif isinstance(ocr, tuple) and len(ocr) >= 1:
            text = ocr[0] or ""
            if text.strip():
                return text
        elif isinstance(ocr, str):
            if ocr.strip():
                return ocr
    except Exception:
        pass

    return ""


def read_pdf_text_with_fallback(pdf_path: Path) -> str:
    return extract_text_with_fallback(pdf_path)


def extract_avviso_fields_from_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    def first(patterns):
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                if m.lastindex:
                    return m.group(1).strip()
                return m.group(0).strip()
        return None

    def money_candidates_near(label_patterns, window=220):
        candidates = []
        amount_pattern = r"(?:€\s*|euro\s*)?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|(?:€\s*|euro\s*)?\d+(?:,\d{2})?"

        for label in label_patterns:
            pattern = rf"({label}).{{0,{window}}}?({amount_pattern})"
            for m in re.finditer(pattern, clean, re.IGNORECASE):
                value = normalize_money_string(m.group(2))
                if value:
                    candidates.append(value)

        return candidates

    def first_money_candidate(label_patterns, window=220):
        vals = money_candidates_near(label_patterns, window=window)
        return vals[0] if vals else None

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

    lotto = first([
        r"\blotto\s*(unico|\d+[A-Za-z]?)",
    ])
    if lotto:
        lotto = "1" if lotto.lower() == "unico" else lotto

    tribunale = first([
        r"\btribunale(?:\s+ordinario)?\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,80})",
    ])
    if tribunale:
        tribunale = clean_tribunale_name(f"Tribunale di {tribunale}") or tribunale

    data_asta = first([
        r"il\s+giorno\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})\s+alle",
        r"vendita\s+(?:senza\s+incanto\s+)?(?:avrà\s+luogo\s+)?il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{4})",
    ])
    data_asta = normalize_date_string(data_asta)

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

    foglio = first([
        r"\bfoglio\s+(\d+)",
    ])

    mappale = first([
        r"\bparticella\s+(\d+)",
        r"\bmappale\s+(\d+)",
        r"\bpart\.\s*(\d+)",
    ])

    subalterno_raw = first([
        r"\bsubalterni?\s*:\s*([^.;]+)",
        r"\bsub\.\s*([^.;]+)",
    ])
    subalterno = normalize_subalterni(subalterno_raw)

    prezzo_base = (
        first_money_candidate(
            [
                r"prezzo\s+base",
                r"prezzo\s+base\s+d[’']asta",
                r"prezzo\s+a\s+base\s+d[’']asta",
                r"base\s+d[’']asta",
                r"valore\s+d[’']asta",
                r"prezzo\s+di\s+vendita",
                r"lotto\s+\w+[^\.]{0,120}prezzo\s+base",
            ],
            window=260,
        )
        or money_from_tabular_row(
            [
                r"(?:prezzo\s+base[^\.]{0,200})",
                r"(?:base\s+d[’']asta[^\.]{0,200})",
            ],
            [
                r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            ],
        )
    )

    offerta_minima = (
        first_money_candidate(
            [
                r"offerta\s+minima\s+non\s+inferiore\s+a",
                r"offerta\s+minima",
                r"minima\s+offerta",
                r"offerta\s+irriducibile",
                r"offerta\s+minima\s+ammissibile",
                r"offerta\s+efficace\s+non\s+inferiore\s+a",
                r"offerta\s+pari\s+almeno\s+al",
                r"offerta\s+non\s+inferiore\s+a",
            ],
            window=260,
        )
        or money_from_tabular_row(
            [
                r"(?:offerta\s+minima[^\.]{0,220})",
                r"(?:minima\s+offerta[^\.]{0,220})",
            ],
            [
                r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            ],
        )
    )

    rilancio_minimo = first_money_candidate(
        [
            r"rilancio\s+minimo",
            r"aumento\s+minimo",
            r"rilancio\s+in\s+caso\s+di\s+gara",
            r"in\s+misura\s+non\s+inferiore\s+a",
        ],
        window=180,
    )

    deposito_cauzionale = first_money_candidate(
        [
            r"deposito\s+cauzionale",
            r"\bcauzione",
        ],
        window=180,
    )

    prezzo_base_offerte_residuali = first_money_candidate(
        [
            r"prezzo\s+base\s+per\s+le\s+offerte\s+residuali",
            r"base\s+d[’']asta\s+per\s+le\s+offerte\s+residuali",
        ],
        window=220,
    )

    valore_perizia = first_money_candidate(
        [
            r"valore\s+di\s+stima",
            r"valore\s+di\s+mercato",
            r"valore\s+del\s+compendio",
            r"valore\s+peritale",
            r"stimato\s+in",
        ],
        window=220,
    )

    delegato = first([
        r"((?:avv|dott|notaio)\.\s+[A-Z][A-Za-zÀ-ÿ\s]+)",
    ])

    descrizione_immobile = first([
        r"oggetto\s+della\s+vendita\s*:\s*([^.;]{30,1000})",
        r"lotto\s+\w+\s*[:\-]\s*([^.;]{30,1000})",
        r"piena\s+proprietà\s+di\s*([^.;]{30,1000})",
    ])
    descrizione_immobile = clean_text_block(descrizione_immobile)

    categoria_catastale = first([
        r"categoria\s+catastale\s*([A-Z]\/\d+)",
        r"cat\.\s*([A-Z]\/\d+)",
        r"categoria\s*([A-Z]\/\d+)",
    ])

    catasto = first([
        r"catasto\s+(fabbricati|terreni)",
    ])
    if catasto:
        catasto = f"Catasto {catasto.title()}"

    if not offerta_minima and prezzo_base:
        m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", prezzo_base)
        if m:
            num = m.group(1).replace(".", "").replace(",", ".")
            try:
                pb = float(num)
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

def normalize_db_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def parse_ai_json(asta) -> dict:
    if not getattr(asta, "ai_result_json", None):
        return {}
    try:
        return json.loads(asta.ai_result_json)
    except Exception:
        return {}


def is_missing_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {
        "",
        "-",
        "n.d.",
        "n/a",
        "nd",
        "non disponibile",
        "null",
        "none",
    }:
        return True
    return False


def first_non_empty(*values):
    for v in values:
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.strip()
            if vv and vv.lower() not in {"null", "none", "nd", "n.d."}:
                return vv
        elif v not in ("", [], {}, ()):
            return v
    return None


def merge_field(*values):
    return first_non_empty(*values)


def normalize_money_string(value: str | None) -> str | None:
    if not value:
        return None

    value = value.replace("€", " ").replace("euro", " ")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()

    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)", value)
    if not m:
        return None

    return f"€ {m.group(1)}"


def extract_money_near_labels(text: str, labels: list[str], window: int = 140) -> str | None:
    if not text:
        return None

    clean = text.replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", clean)
    amount_pattern = r"(?:€\s*)?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|(?:€\s*)?\d+(?:,\d{2})?"

    for label in labels:
        pattern = rf"{label}[^0-9€]{{0,{window}}}({amount_pattern})"
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return normalize_money_string(m.group(1))

    return None


def normalize_subalterni(value: str | None) -> str | None:
    if not value:
        return None

    nums = re.findall(r"\d+", value)
    if not nums:
        return None

    seen = []
    for n in nums:
        if n not in seen:
            seen.append(n)

    return ", ".join(seen)


def read_pdf_text_with_fallback(pdf_path: str | Path) -> str:
    pdf_path = Path(pdf_path)

    diag = extract_text_with_diagnostics(pdf_path)
    text = ""

    if isinstance(diag, dict):
        text = diag.get("text") or ""

        if diag.get("quality") in ("poor", "empty"):
            ocr_result = extract_text_from_pdf_ocr(pdf_path)
            if isinstance(ocr_result, dict):
                if ocr_result.get("status") == "ok" and (ocr_result.get("text") or "").strip():
                    return ocr_result["text"]
            elif isinstance(ocr_result, tuple) and len(ocr_result) >= 1:
                ocr_text = ocr_result[0] or ""
                if ocr_text.strip():
                    return ocr_text

        return text

    if isinstance(diag, tuple) and len(diag) >= 1:
        text = diag[0] or ""
        if text.strip():
            return text

    ocr_result = extract_text_from_pdf_ocr(pdf_path)
    if isinstance(ocr_result, dict):
        if ocr_result.get("status") == "ok" and (ocr_result.get("text") or "").strip():
            return ocr_result["text"]
    elif isinstance(ocr_result, tuple) and len(ocr_result) >= 1:
        ocr_text = ocr_result[0] or ""
        if ocr_text.strip():
            return ocr_text

    return text


def extract_structured_fields_from_perizia_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    def first(patterns):
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                if m.lastindex:
                    return m.group(1).strip()
                return m.group(0).strip()
        return None

    rge = first([
        r"proc\.\s*r\.?\s*g\.?\s*n\.?\s*(\d{1,6}\s*/\s*\d{2,4})",
        r"r\.?\s*g\.?\s*n\.?\s*(\d{1,6}\s*/\s*\d{2,4})",
    ])
    if rge:
        rge = rge.replace(" ", "")

    tribunale = first([
        r"tribunale\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,50})",
    ])
    if tribunale:
        tribunale = f"Tribunale di {tribunale.title()}"

    lotto = first([
        r"lotto\s+(unico|\d+[A-Za-z]?)",
    ])
    if lotto:
        lotto = "1" if lotto.lower() == "unico" else lotto

    citta = first([
        r"comune\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+)",
    ])

    indirizzo = first([
        r"((?:via|viale|piazza|corso|località|loc\.)\s+[A-Za-zÀ-ÿ0-9' .,\-]+?(?:n\.?\s*\d+|\d+))",
    ])

    foglio = first([
        r"\bfoglio\s+(\d+)",
    ])

    mappale = first([
        r"\bparticella\s+(\d+)",
        r"\bmappale\s+(\d+)",
        r"\bpart\.\s*(\d+)",
    ])

    subalterno_raw = first([
        r"\bsubalterni?\s*[: ]\s*([^.;]+)",
        r"\bsub\.\s*([^.;]+)",
    ])
    subalterno = normalize_subalterni(subalterno_raw)

    occupazione = first([
        r"stato\s+di\s+possesso.*?(libero|occupato)",
        r"\b(libero|occupato)\b",
    ])

    valore_perizia = extract_money_near_labels(
        clean,
        [
            r"valore\s+di\s+mercato",
            r"valore\s+di\s+stima",
            r"valore\s+del\s+bene",
            r"valore\s+complessivo",
            r"stima\s+del\s+bene",
            r"\[VM\]",
        ],
        window=180,
    )

    prezzo_base = extract_money_near_labels(
        clean,
        [
            r"prezzo\s+base",
            r"prezzo\s+base\s+d[’']asta",
            r"prezzo\s+a\s+base\s+d[’']asta",
            r"base\s+d[’']asta",
            r"valore\s+d[’']asta",
            r"valore\s+di\s+asta",
        ],
        window=180,
    )

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
    }


def normalize_date_string(v: str | None) -> str | None:
    if not v:
        return None

    v = v.strip()

    m = re.search(r"(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})", v)
    if m:
        gg = m.group(1).zfill(2)
        mm = m.group(2).zfill(2)
        aa = m.group(3)
        if len(aa) == 2:
            aa = "20" + aa
        return f"{gg}/{mm}/{aa}"

    mesi = {
        "gennaio": "01",
        "febbraio": "02",
        "marzo": "03",
        "aprile": "04",
        "maggio": "05",
        "giugno": "06",
        "luglio": "07",
        "agosto": "08",
        "settembre": "09",
        "ottobre": "10",
        "novembre": "11",
        "dicembre": "12",
    }

    m = re.search(r"(\d{1,2})\s+([A-Za-zà-ù]+)\s+(\d{4})", v, re.IGNORECASE)
    if not m:
        return v

    giorno = m.group(1).zfill(2)
    mese = mesi.get(m.group(2).lower())
    anno = m.group(3)

    if mese:
        return f"{giorno}/{mese}/{anno}"

    return v


def extract_avviso_fields_from_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    def first(patterns):
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                if m.lastindex:
                    return m.group(1).strip()
                return m.group(0).strip()
        return None

    def money_candidates_near(label_patterns, window=220):
        candidates = []
        amount_pattern = r"(?:€\s*|euro\s*)?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|(?:€\s*|euro\s*)?\d+(?:,\d{2})?"

        for label in label_patterns:
            pattern = rf"({label}).{{0,{window}}}?({amount_pattern})"
            for m in re.finditer(pattern, clean, re.IGNORECASE):
                value = normalize_money_string(m.group(2))
                if value:
                    candidates.append(value)

        return candidates

    def first_money_candidate(label_patterns, window=220):
        vals = money_candidates_near(label_patterns, window=window)
        return vals[0] if vals else None

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

    lotto = first([
        r"\blotto\s*(unico|\d+[A-Za-z]?)",
    ])
    if lotto:
        lotto = "1" if lotto.lower() == "unico" else lotto

    tribunale = first([
        r"\btribunale(?:\s+ordinario)?\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,50})",
    ])
    if tribunale:
        tribunale = f"Tribunale di {tribunale.title()}"

    data_asta = first([
        r"il\s+giorno\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})\s+alle",
        r"vendita\s+(?:senza\s+incanto\s+)?(?:avrà\s+luogo\s+)?il\s+(\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4})",
        r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{4})",
    ])
    data_asta = normalize_date_string(data_asta)

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
    ])

    foglio = first([
        r"\bfoglio\s+(\d+)",
    ])

    mappale = first([
        r"\bparticella\s+(\d+)",
        r"\bmappale\s+(\d+)",
        r"\bpart\.\s*(\d+)",
    ])

    subalterno_raw = first([
        r"\bsubalterni?\s*:\s*([^.;]+)",
        r"\bsub\.\s*([^.;]+)",
    ])
    subalterno = normalize_subalterni(subalterno_raw)

    prezzo_base = (
        first_money_candidate(
            [
                r"prezzo\s+base",
                r"prezzo\s+base\s+d[’']asta",
                r"prezzo\s+a\s+base\s+d[’']asta",
                r"base\s+d[’']asta",
                r"valore\s+d[’']asta",
                r"prezzo\s+di\s+vendita",
                r"lotto\s+\w+[^\.]{0,120}prezzo\s+base",
            ],
            window=260,
        )
        or money_from_tabular_row(
            [
                r"(?:prezzo\s+base[^\.]{0,200})",
                r"(?:base\s+d[’']asta[^\.]{0,200})",
            ],
            [
                r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            ],
        )
    )

    offerta_minima = (
        first_money_candidate(
            [
                r"offerta\s+minima\s+non\s+inferiore\s+a",
                r"offerta\s+minima",
                r"minima\s+offerta",
                r"offerta\s+irriducibile",
                r"offerta\s+minima\s+ammissibile",
                r"offerta\s+efficace\s+non\s+inferiore\s+a",
                r"offerta\s+pari\s+almeno\s+al",
                r"offerta\s+non\s+inferiore\s+a",
            ],
            window=260,
        )
        or money_from_tabular_row(
            [
                r"(?:offerta\s+minima[^\.]{0,220})",
                r"(?:minima\s+offerta[^\.]{0,220})",
            ],
            [
                r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
                r"euro\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            ],
        )
    )

    rilancio_minimo = first_money_candidate(
        [
            r"rilancio\s+minimo",
            r"aumento\s+minimo",
            r"rilancio\s+in\s+caso\s+di\s+gara",
        ],
        window=180,
    )

    deposito_cauzionale = first_money_candidate(
        [
            r"deposito\s+cauzionale",
            r"\bcauzione",
        ],
        window=180,
    )

    prezzo_base_offerte_residuali = first_money_candidate(
        [
            r"prezzo\s+base\s+per\s+le\s+offerte\s+residuali",
            r"base\s+d[’']asta\s+per\s+le\s+offerte\s+residuali",
        ],
        window=220,
    )

    valore_perizia = first_money_candidate(
        [
            r"valore\s+di\s+stima",
            r"valore\s+di\s+mercato",
            r"valore\s+del\s+compendio",
            r"valore\s+peritale",
        ],
        window=220,
    )

    delegato = first([
        r"((?:avv|dott|notaio)\.\s+[A-Z][A-Za-zÀ-ÿ\s]+)",
    ])

    # fallback intelligente:
    # se manca offerta minima ma esiste prezzo base,
    # alcuni avvisi indicano il 75% del prezzo base solo in forma testuale.
    if not offerta_minima and prezzo_base:
        m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", prezzo_base)
        if m:
            num = m.group(1).replace(".", "").replace(",", ".")
            try:
                pb = float(num)
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
        "prezzo_base": prezzo_base,
        "offerta_minima": offerta_minima,
        "rilancio_minimo": rilancio_minimo,
        "deposito_cauzionale": deposito_cauzionale,
        "prezzo_base_offerte_residuali": prezzo_base_offerte_residuali,
        "valore_perizia": valore_perizia,
        "delegato": delegato,
    }