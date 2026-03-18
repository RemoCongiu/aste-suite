from __future__ import annotations

import json
import re
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.ai_analyzer import MODEL_NAME, analyze_perizia_text
from app.db import get_asta, update_asta_fields
from app.ocr_text import extract_text_from_pdf_ocr
from app.services_parsing import (
    clean_text_block,
    clean_tribunale_name,
    extract_avviso_fields_from_text,
    normalize_date_string,
    normalize_money_string,
    normalize_subalterni,
)

router = APIRouter()
logger = logging.getLogger(__name__)
MIN_TEXT_FOR_ANALYSIS = 900

ANALYSIS_JOBS: dict[int, dict] = {}


def set_analysis_job(
    asta_id: int,
    *,
    progress: int,
    step: str,
    message: str,
    done: bool = False,
    error: str | None = None,
):
    ANALYSIS_JOBS[asta_id] = {
        "asta_id": asta_id,
        "progress": progress,
        "step": step,
        "message": message,
        "done": done,
        "error": error,
    }


def get_analysis_job(asta_id: int) -> dict:
    return ANALYSIS_JOBS.get(
        asta_id,
        {
            "asta_id": asta_id,
            "progress": 0,
            "step": "idle",
            "message": "Nessun job attivo",
            "done": False,
            "error": None,
        },
    )


@router.get("/aste/{asta_id}/analysis-status")
def analysis_status(asta_id: int):
    return get_analysis_job(asta_id)


def _norm_text(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        v = clean_text_block(value)
        if not v:
            return None
        if v.lower() in {"null", "none", "nd", "n.d.", "-", "non disponibile"}:
            return None
        return v

    return str(value).strip() if str(value).strip() else None


def _norm_multiline(value) -> str | None:
    v = _norm_text(value)
    if not v:
        return None
    v = str(v).replace("\r", "\n")
    v = re.sub(r"[ \t]+", " ", v)
    v = re.sub(r"\n{3,}", "\n\n", v)
    return v.strip()


def _first_non_empty(*values):
    for v in values:
        vv = _norm_text(v)
        if vv:
            return vv
    return None


def _prefer_existing_then_sources(existing, *sources):
    existing_v = _norm_text(existing)
    if existing_v:
        return existing_v
    return _first_non_empty(*sources)


def _prefer_sources_then_existing(*sources_and_existing):
    return _first_non_empty(*sources_and_existing)


def _ensure_list(value) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        out = []
        for item in value:
            txt = _norm_text(item)
            if txt:
                out.append(txt)
        return out

    txt = _norm_text(value)
    return [txt] if txt else []


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out = []
    seen = set()

    for item in items:
        txt = _norm_text(item)
        if not txt:
            continue
        key = txt.lower()
        if key not in seen:
            seen.add(key)
            out.append(txt)

    return out


def _join_bullets(items: list[str]) -> str | None:
    items = _dedupe_keep_order(items)
    if not items:
        return None
    return "\n".join(f"- {x}" for x in items)


def _join_paragraphs(parts: list[str]) -> str | None:
    cleaned = []
    seen = set()

    for p in parts:
        txt = _norm_multiline(p)
        if not txt:
            continue
        key = txt.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(txt)

    if not cleaned:
        return None

    return "\n\n".join(cleaned)


def _extract_section(text: str, labels: list[str], lookahead: int = 2400) -> str | None:
    if not text:
        return None

    raw = text.replace("\r", "\n")
    lower = raw.lower()

    matches = []
    for label in labels:
        for m in re.finditer(label, lower, re.IGNORECASE):
            start = m.start()
            end = min(len(raw), start + lookahead)
            chunk = raw[start:end].strip()
            if chunk:
                matches.append(chunk)

    if not matches:
        return None

    merged = "\n\n".join(matches[:4])
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return clean_text_block(merged)


def _extract_money_near(text: str, labels: list[str], window: int = 220) -> str | None:
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


def _extract_first(text: str, patterns: list[str]) -> str | None:
    if not text:
        return None

    clean = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()

    for p in patterns:
        m = re.search(p, clean, re.IGNORECASE)
        if m:
            if m.lastindex:
                return clean_text_block(m.group(1))
            return clean_text_block(m.group(0))
    return None


def _extract_descrizione_immobile(perizia_text: str) -> str | None:
    candidates = [
        _extract_first(
            perizia_text,
            [
                r"piena\s+proprietà\s+di\s+([^.;]{50,1400})",
                r"oggetto\s+della\s+stima\s*[:\-]\s*([^.;]{50,1400})",
                r"descrizione\s+(?:del\s+)?bene\s*[:\-]?\s*([^.;]{50,1400})",
            ],
        ),
        _extract_section(
            perizia_text,
            [
                r"descrizione\s+del\s+bene",
                r"identificazione\s+del\s+bene",
                r"consistenza",
                r"ubicazione",
                r"caratteristiche",
            ],
            lookahead=2200,
        ),
    ]

    for c in candidates:
        if c and len(c) > 40:
            return c

    return None


def _extract_dati_catastali(perizia_text: str) -> dict:
    catasto = _extract_first(
        perizia_text,
        [
            r"catasto\s+(fabbricati|terreni)",
        ],
    )
    if catasto:
        catasto = f"Catasto {catasto.title()}"

    foglio = _extract_first(perizia_text, [r"\bfoglio\s+(\d+)"])
    mappale = _extract_first(
        perizia_text,
        [
            r"\bparticella\s+(\d+)",
            r"\bmappale\s+(\d+)",
            r"\bpart\.\s*(\d+)",
        ],
    )
    sub_raw = _extract_first(
        perizia_text,
        [
            r"\bsubalterni?\s*[: ]\s*([^.;\n]+)",
            r"\bsub\.\s*([^.;\n]+)",
        ],
    )
    subalterno = normalize_subalterni(sub_raw)

    categoria = _extract_first(
        perizia_text,
        [
            r"categoria\s+catastale\s*([A-Z]\/\d+)",
            r"cat\.\s*([A-Z]\/\d+)",
            r"categoria\s*([A-Z]\/\d+)",
        ],
    )

    return {
        "catasto": catasto,
        "foglio": foglio,
        "mappale": mappale,
        "subalterno": subalterno,
        "categoria_catastale": categoria,
    }


def _extract_pregiudizievoli_text(perizia_text: str) -> str | None:
    section = _extract_section(
        perizia_text,
        [
            r"formalità\s+pregiudizievoli",
            r"pregiudizievoli",
            r"ipoteche?",
            r"pignorament[oi]",
            r"trascrizioni?",
            r"iscrizioni?",
            r"vincoli\s+e\s+oneri",
            r"gravami",
        ],
        lookahead=3200,
    )

    short_items = []

    for pattern in [
        r"(ipoteca[^.\n]{20,600})",
        r"(ipoteche[^.\n]{20,600})",
        r"(pignoramento[^.\n]{20,600})",
        r"(pignoramenti[^.\n]{20,600})",
        r"(trascrizion[^.\n]{20,600})",
        r"(iscrizion[^.\n]{20,600})",
        r"(vincoli[^.\n]{20,600})",
    ]:
        found = _extract_first(perizia_text, [pattern])
        if found:
            short_items.append(found)

    joined_short = _join_bullets(short_items)

    if section and joined_short:
        return _join_paragraphs([joined_short, section])
    if section:
        return section
    return joined_short


def _extract_abusi_text(perizia_text: str) -> str | None:
    section = _extract_section(
        perizia_text,
        [
            r"regolarità\s+edilizia",
            r"regolarità\s+urbanistica",
            r"conformità\s+urbanistica",
            r"conformità\s+catastale",
            r"abusi?",
            r"difformità",
            r"sanatoria",
            r"agibilità",
            r"abitabilità",
            r"titolo\s+edilizio",
        ],
        lookahead=3600,
    )

    short_items = []

    for pattern in [
        r"(difformit[aà][^.\n]{20,700})",
        r"(abus[oi][^.\n]{20,700})",
        r"(sanatoria[^.\n]{20,700})",
        r"(non\s+sanabile[^.\n]{10,400})",
        r"(pratica\s+edilizia[^.\n]{20,700})",
        r"(conformit[aà]\s+urbanistica[^.\n]{20,700})",
        r"(conformit[aà]\s+catastale[^.\n]{20,700})",
    ]:
        found = _extract_first(perizia_text, [pattern])
        if found:
            short_items.append(found)

    joined_short = _join_bullets(short_items)

    if section and joined_short:
        return _join_paragraphs([joined_short, section])
    if section:
        return section
    return joined_short


def _extract_structured_fields_from_perizia_text(text: str) -> dict:
    raw = (text or "").replace("\xa0", " ")
    clean = re.sub(r"\s+", " ", raw).strip()

    rge = _extract_first(
        clean,
        [
            r"proc\.\s*r\.?\s*g\.?\s*n\.?\s*(\d{1,6}\s*/\s*\d{2,4})",
            r"r\.?\s*g\.?\s*e\.?\s*(?:n\.?)?\s*(\d{1,6}\s*/\s*\d{2,4})",
        ],
    )
    if rge:
        rge = rge.replace(" ", "")

    tribunale = _extract_first(
        clean,
        [
            r"tribunale\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]{1,80})",
        ],
    )
    if tribunale:
        tribunale = clean_tribunale_name(f"Tribunale di {tribunale}") or tribunale

    lotto = _extract_first(clean, [r"lotto\s+(unico|\d+[A-Za-z]?)"])
    if lotto and lotto.lower() == "unico":
        lotto = "1"

    citta = _extract_first(
        clean,
        [
            r"comune\s+di\s+([A-ZÀ-Ù][A-Za-zÀ-ÿ' -]+)",
        ],
    )

    indirizzo = _extract_first(
        clean,
        [
            r"((?:via|viale|piazza|corso|località|loc\.)\s+[A-Za-zÀ-ÿ0-9' .,\-]+?(?:n\.?\s*\d+|\d+))",
        ],
    )

    occupazione = _extract_first(
        clean,
        [
            r"stato\s+di\s+possesso[^.\n]{0,160}(libero|occupato)",
            r"stato\s+di\s+occupazione[^.\n]{0,160}(libero|occupato)",
            r"occupato\s+da\s+([^.\n]{5,200})",
        ],
    )

    valore_perizia = _extract_money_near(
        clean,
        [
            r"valore\s+di\s+mercato",
            r"valore\s+di\s+stima",
            r"valore\s+del\s+bene",
            r"valore\s+complessivo",
            r"stima\s+del\s+bene",
            r"valore\s+peritale",
            r"stimato\s+in",
        ],
        window=260,
    )

    descrizione_immobile = _extract_descrizione_immobile(text)
    dati_catastali = _extract_dati_catastali(text)
    pregiudizievoli = _extract_pregiudizievoli_text(text)
    abusi = _extract_abusi_text(text)

    return {
        "rge": rge,
        "tribunale": tribunale,
        "lotto": lotto,
        "citta": citta,
        "indirizzo": indirizzo,
        "occupazione": occupazione,
        "valore_perizia": valore_perizia,
        "descrizione_immobile": descrizione_immobile,
        "pregiudizievoli": pregiudizievoli,
        "abusi": abusi,
        **dati_catastali,
    }


def _read_pdf_text_with_fallback(pdf_path: Path) -> tuple[str, str, dict]:
    diagnostics: dict = {}

    try:
        from app.pdf_text import extract_text_with_diagnostics

        diag = extract_text_with_diagnostics(pdf_path)
        diagnostics["pypdf"] = diag

        text = (diag.get("text") or "").strip()
        quality = diag.get("quality")

        # MOD: testo troppo corto => qualità insufficiente per analisi affidabile.
        if text and quality == "good" and len(text) >= MIN_TEXT_FOR_ANALYSIS:
            return text, "pypdf", diagnostics

        if not text:
            logger.warning("Nessun testo estratto da pypdf: %s", pdf_path)
        elif len(text) < MIN_TEXT_FOR_ANALYSIS:
            logger.warning(
                "Testo corto da pypdf (%s chars), forzo OCR: %s",
                len(text),
                pdf_path,
            )
        else:
            logger.info("Qualità pypdf=%s, provo OCR su: %s", quality, pdf_path)
    except Exception as e:
        diagnostics["pypdf_error"] = str(e)
        logger.exception("Errore pypdf su %s", pdf_path)

    try:
        ocr_result = extract_text_from_pdf_ocr(pdf_path)
        diagnostics["ocr"] = ocr_result

        if isinstance(ocr_result, dict):
            ocr_text = (ocr_result.get("text") or "").strip()
            if ocr_result.get("status") == "ok" and ocr_text:
                return ocr_text, "ocr", diagnostics
        elif isinstance(ocr_result, str):
            ocr_text = ocr_result.strip()
            if ocr_text:
                return ocr_text, "ocr", diagnostics
    except Exception as e:
        diagnostics["ocr_error"] = str(e)
        logger.exception("Errore OCR su %s", pdf_path)

    pypdf_text = (
        diagnostics.get("pypdf", {}).get("text", "")
        if isinstance(diagnostics.get("pypdf"), dict)
        else ""
    ).strip()

    if pypdf_text:
        return pypdf_text, "pypdf_poor", diagnostics

    return "", "empty", diagnostics

def _build_abusi_final(ai_data: dict, perizia_struct: dict, current_db_value) -> str | None:
    summary = _norm_text(ai_data.get("abusi"))
    detail = _norm_multiline(ai_data.get("abusi_dettaglio"))
    urban = _norm_multiline(ai_data.get("stato_urbanistico"))
    catasto = _norm_multiline(ai_data.get("stato_catastale"))
    conf_urb = _norm_text(ai_data.get("conformita_urbanistica"))
    conf_cat = _norm_text(ai_data.get("conformita_catastale"))
    spese_reg = _norm_text(ai_data.get("spese_stimate_regolarizzazione"))

    sections = []

    if summary:
        sections.append(f"Sintesi: {summary}")
    if conf_urb:
        sections.append(f"Conformità urbanistica: {conf_urb}")
    if conf_cat:
        sections.append(f"Conformità catastale: {conf_cat}")
    if urban:
        sections.append(f"Quadro urbanistico:\n{urban}")
    if catasto:
        sections.append(f"Quadro catastale:\n{catasto}")
    if detail:
        sections.append(f"Dettaglio criticità:\n{detail}")
    if spese_reg:
        sections.append(f"Spese stimate di regolarizzazione: {spese_reg}")

    final_text = _join_paragraphs(sections)
    return _prefer_sources_then_existing(final_text, current_db_value)


def _build_pregiudizievoli_final(ai_data: dict, perizia_struct: dict, current_db_value) -> str | None:
    summary = _norm_text(ai_data.get("pregiudizievoli"))
    detail = _norm_multiline(ai_data.get("pregiudizievoli_dettaglio"))
    vincoli = _norm_multiline(ai_data.get("vincoli_oneri"))
    debiti_cond = _norm_text(ai_data.get("debiti_condominiali"))

    sections = []

    if summary:
        sections.append(f"Sintesi: {summary}")
    if detail:
        sections.append(f"Dettaglio formalità:\n{detail}")
    if vincoli:
        sections.append(f"Vincoli e oneri:\n{vincoli}")
    if debiti_cond:
        sections.append(f"Debiti condominiali: {debiti_cond}")

    final_text = _join_paragraphs(sections)
    return _prefer_sources_then_existing(final_text, current_db_value)


def _build_descrizione_final(ai_data: dict, perizia_struct: dict, avviso_fields: dict, current_db_value) -> str | None:
    parts = [
        ai_data.get("descrizione_immobile"),
        avviso_fields.get("descrizione_immobile"),
        current_db_value,
    ]
    best = _first_non_empty(*parts)
    return _norm_multiline(best)


def _get_ai_objective_field(ai_data: dict, field: str) -> dict | None:
    campi = ai_data.get("campi_oggettivi")
    if not isinstance(campi, dict):
        return None
    value = campi.get(field)
    return value if isinstance(value, dict) else None


def _get_ai_objective_value(ai_data: dict, field: str):
    item = _get_ai_objective_field(ai_data, field)
    if not item:
        return None
    return _norm_text(item.get("valore"))


def _collect_ai_objective_warnings(ai_data: dict) -> list[str]:
    warnings = []
    campi = ai_data.get("campi_oggettivi")
    if not isinstance(campi, dict):
        return warnings

    for field, payload in campi.items():
        if not isinstance(payload, dict):
            continue
        warning = _norm_multiline(payload.get("warning"))
        value = _norm_text(payload.get("valore"))
        fonte = _norm_text(payload.get("fonte"))
        confidenza = _norm_text(payload.get("confidenza"))
        if warning:
            details = []
            if value:
                details.append(f"valore scelto={value}")
            if fonte:
                details.append(f"fonte={fonte}")
            if confidenza:
                details.append(f"confidenza={confidenza}")
            suffix = f" ({', '.join(details)})" if details else ""
            warnings.append(f"{field}: {warning}{suffix}")

    return warnings


def _build_ai_analysis_input(perizia_text: str, asta, avviso_fields: dict) -> str:
    context = {
        "pagina_o_db": {
            "tribunale": getattr(asta, "tribunale", None),
            "rge": getattr(asta, "rge", None),
            "lotto": getattr(asta, "lotto", None),
            "data_asta": getattr(asta, "data_asta", None),
            "prezzo_base": getattr(asta, "prezzo_base", None),
            "offerta_minima": getattr(asta, "offerta_minima", None),
            "rilancio_minimo": getattr(asta, "rilancio_minimo", None),
            "citta": getattr(asta, "citta", None),
            "indirizzo": getattr(asta, "indirizzo", None),
        },
        "avviso_parser": avviso_fields or {},
    }
    return (
        "CONTESTO STRUTTURATO AGGIUNTIVO (usa questo blocco per consolidare i campi oggettivi, "
        "risolvere conflitti tra fonti e scegliere il valore piu' attendibile):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "TESTO PERIZIA PULITO:\n"
        f"{perizia_text}"
    )


def _build_note_operativi(ai_data: dict, asta, prezzo_base, offerta_minima, rilancio_minimo) -> str | None:
    criticita = _ensure_list(ai_data.get("criticita_principali"))
    costi = _ensure_list(ai_data.get("costi_probabili"))
    attenzioni = _ensure_list(ai_data.get("punti_di_attenzione_investitore"))

    blocks = []

    if criticita:
        blocks.append("Criticità principali:\n" + _join_bullets(criticita))

    if costi:
        blocks.append("Costi probabili:\n" + _join_bullets(costi))

    if attenzioni:
        blocks.append("Punti di attenzione per investitore:\n" + _join_bullets(attenzioni))

    val_oper = _norm_multiline(ai_data.get("valutazione_operativa"))
    if val_oper:
        blocks.append("Valutazione operativa:\n" + val_oper)

    strategia = _norm_multiline(ai_data.get("strategia_consigliata"))
    if strategia:
        blocks.append("Strategia consigliata:\n" + strategia)

    rischio = _norm_text(ai_data.get("rischio_operazione"))
    if rischio:
        blocks.append(f"Rischio operazione: {rischio}")

    vendibilita = _norm_text(ai_data.get("vendibilita_potenziale"))
    if vendibilita:
        blocks.append(f"Vendibilità potenziale: {vendibilita}")

    # MOD: campi aggiuntivi per una lettura legale/urbanistica più chiara.
    rischi_legali = _norm_multiline(ai_data.get("rischi_legali"))
    if rischi_legali:
        blocks.append("Rischi legali:\n" + rischi_legali)

    rischi_urbanistici = _norm_multiline(ai_data.get("rischi_urbanistici"))
    if rischi_urbanistici:
        blocks.append("Rischi urbanistici:\n" + rischi_urbanistici)

    formalita_commento = _norm_multiline(ai_data.get("formalita_pregiudizievoli_commento"))
    if formalita_commento:
        blocks.append("Commento formalità pregiudizievoli:\n" + formalita_commento)

    if prezzo_base or offerta_minima or rilancio_minimo:
        economic_block = []
        if prezzo_base:
            economic_block.append(f"Prezzo base: {prezzo_base}")
        if offerta_minima:
            economic_block.append(f"Offerta minima: {offerta_minima}")
        if rilancio_minimo:
            economic_block.append(f"Rilancio minimo: {rilancio_minimo}")
        blocks.append("Dati economici:\n" + "\n".join(f"- {x}" for x in economic_block))

    return _join_paragraphs(blocks)


def _normalize_rge(value) -> str | None:
    v = _norm_text(value)
    if not v:
        return None
    m = re.search(r"(\d{1,6})\s*/\s*(\d{2,4})", v)
    if not m:
        return v
    return f"{m.group(1)}/{m.group(2)}"


def _normalize_field_for_validation(field: str, value):
    if field in {"prezzo_base", "offerta_minima", "valore_perizia", "rilancio_minimo"}:
        return normalize_money_string(_norm_text(value))
    if field == "data_asta":
        return normalize_date_string(_norm_text(value))
    if field == "tribunale":
        return clean_tribunale_name(_norm_text(value)) or _norm_text(value)
    if field == "rge":
        return _normalize_rge(value)
    if field == "lotto":
        v = _norm_text(value)
        if not v:
            return None
        return "1" if v.lower() == "unico" else v.upper()
    return _norm_text(value)


def _build_cross_source_warnings(asta, avviso_fields: dict, perizia_struct: dict, ai_data: dict) -> list[str]:
    # MOD: verifica incrociata su campi critici tra pagina/db, avviso, perizia/AI.
    fields_to_check = [
        "tribunale", "rge", "lotto", "data_asta", "prezzo_base", "offerta_minima",
        "indirizzo", "superficie", "occupazione",
    ]

    warnings = []
    for field in fields_to_check:
        page_val = _normalize_field_for_validation(field, getattr(asta, field, None))
        avviso_val = _normalize_field_for_validation(field, avviso_fields.get(field))
        perizia_val = _normalize_field_for_validation(
            field,
            perizia_struct.get(field) or ai_data.get(field),
        )

        values = {
            "pagina": page_val,
            "avviso": avviso_val,
            "perizia": perizia_val,
        }
        non_empty = {k: v for k, v in values.items() if _norm_text(v)}
        unique = {str(v).lower() for v in non_empty.values()}

        if len(unique) >= 2:
            warnings.append(
                f"{field}: incoerenza tra fonti -> "
                + ", ".join(f"{src}={val}" for src, val in non_empty.items())
            )

    return warnings


def analyze_perizia_for_asta(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        raise HTTPException(status_code=404, detail="Asta non trovata")

    set_analysis_job(
        asta_id,
        progress=5,
        step="start",
        message="Avvio analisi documentale",
        done=False,
        error=None,
    )

    project_root = Path(__file__).resolve().parents[1]

    avviso_text = ""
    perizia_text = ""
    avviso_source = None
    perizia_source = None
    avviso_fields = {}
    perizia_struct = {}

    # -------------------------
    # AVVISO
    # -------------------------
    if getattr(asta, "avviso_file_path", None):
        set_analysis_job(
            asta_id,
            progress=18,
            step="avviso",
            message="Lettura avviso di vendita",
            done=False,
            error=None,
        )

        avviso_pdf_path = project_root / asta.avviso_file_path
        if avviso_pdf_path.exists():
            avviso_text, avviso_source, _ = _read_pdf_text_with_fallback(avviso_pdf_path)
            if avviso_text.strip():
                avviso_fields = extract_avviso_fields_from_text(avviso_text)

    # -------------------------
    # PERIZIA
    # -------------------------
    if not getattr(asta, "perizia_file_path", None):
        update_asta_fields(
            asta_id,
            ai_status="error",
            ai_error="Percorso file perizia mancante nel database",
            perizia_status="error",
            perizia_error="Percorso file perizia mancante nel database",
        )
        set_analysis_job(
            asta_id,
            progress=100,
            step="errore",
            message="Percorso file perizia mancante",
            done=True,
            error="Percorso file perizia mancante nel database",
        )
        raise RuntimeError("Percorso file perizia mancante nel database")

    set_analysis_job(
        asta_id,
        progress=36,
        step="perizia",
        message="Lettura perizia",
        done=False,
        error=None,
    )

    perizia_pdf_path = project_root / asta.perizia_file_path
    if not perizia_pdf_path.exists():
        update_asta_fields(
            asta_id,
            ai_status="error",
            ai_error=f"File perizia non trovato: {perizia_pdf_path}",
            perizia_status="error",
            perizia_error=f"File perizia non trovato: {perizia_pdf_path}",
        )
        set_analysis_job(
            asta_id,
            progress=100,
            step="errore",
            message="File perizia non trovato",
            done=True,
            error=f"File perizia non trovato: {perizia_pdf_path}",
        )
        raise RuntimeError(f"File perizia non trovato: {perizia_pdf_path}")

    perizia_text, perizia_source, perizia_diag = _read_pdf_text_with_fallback(perizia_pdf_path)

    if not perizia_text.strip():
        ocr_error = None
        if isinstance(perizia_diag, dict):
            ocr_block = perizia_diag.get("ocr")
            if isinstance(ocr_block, dict):
                ocr_error = ocr_block.get("error")

        detail_msg = "Nessun testo utile estratto dalla perizia"
        if ocr_error:
            detail_msg += f" | OCR: {ocr_error}"

        update_asta_fields(
            asta_id,
            ai_status="empty_text",
            ai_error=detail_msg,
            perizia_status="empty_text",
            perizia_error=detail_msg,
        )
        set_analysis_job(
            asta_id,
            progress=100,
            step="errore",
            message=detail_msg,
            done=True,
            error=detail_msg,
        )
        raise RuntimeError(detail_msg)

    set_analysis_job(
        asta_id,
        progress=50,
        step="parser_perizia",
        message="Parsing strutturato della perizia",
        done=False,
        error=None,
    )

    perizia_struct = _extract_structured_fields_from_perizia_text(perizia_text)

    # -------------------------
    # AI
    # -------------------------
    set_analysis_job(
        asta_id,
        progress=72,
        step="ai",
        message="Analisi AI della perizia in corso",
        done=False,
        error=None,
    )

    result = analyze_perizia_text_debug(perizia_text)
    ai_data = result.get("data", {}) if isinstance(result, dict) else {}
    ai_prompt_data = result.get("prompt") if isinstance(result, dict) else None
    ai_raw_response = result.get("raw_response") if isinstance(result, dict) else None

    # -------------------------
    # FUSIONE DATI
    # -------------------------
    # Regola:
    # - pagina/db > avviso > altro per data/prezzo/offerta/rilancio
    # - perizia/ai > tutto il resto per valore_perizia, descrizione, urbanistica, catasto, pregiudizievoli

    final_tribunale = clean_tribunale_name(
        _prefer_sources_then_existing(
            perizia_struct.get("tribunale"),
            ai_data.get("tribunale"),
            avviso_fields.get("tribunale"),
            getattr(asta, "tribunale", None),
        )
    )

    final_rge = _prefer_sources_then_existing(
        perizia_struct.get("rge"),
        ai_data.get("rge"),
        avviso_fields.get("rge"),
        getattr(asta, "rge", None),
    )

    final_lotto = _prefer_sources_then_existing(
        perizia_struct.get("lotto"),
        ai_data.get("lotto"),
        avviso_fields.get("lotto"),
        getattr(asta, "lotto", None),
    )

    final_data_asta = normalize_date_string(
        _prefer_sources_then_existing(
            ai_data.get("data_asta"),
            avviso_fields.get("data_asta"),
            getattr(asta, "data_asta", None),
        )
    )

    final_citta = _prefer_sources_then_existing(
        perizia_struct.get("citta"),
        ai_data.get("citta"),
        avviso_fields.get("citta"),
        getattr(asta, "citta", None),
    )

    final_indirizzo = _prefer_sources_then_existing(
        perizia_struct.get("indirizzo"),
        ai_data.get("indirizzo"),
        avviso_fields.get("indirizzo"),
        getattr(asta, "indirizzo", None),
    )

    final_prezzo_base = normalize_money_string(
        _prefer_sources_then_existing(
            perizia_struct.get("prezzo_base"),
            ai_data.get("prezzo_base"),
            avviso_fields.get("prezzo_base"),
            getattr(asta, "prezzo_base", None),
        )
    )

    final_offerta_minima = normalize_money_string(
        _prefer_sources_then_existing(
            ai_data.get("offerta_minima"),
            avviso_fields.get("offerta_minima"),
            getattr(asta, "offerta_minima", None),
        )
    )

    final_rilancio_minimo = normalize_money_string(
        _prefer_sources_then_existing(
            _get_ai_objective_value(ai_data, "rilancio_minimo"),
            avviso_fields.get("rilancio_minimo"),
            getattr(asta, "rilancio_minimo", None),
        )
    )

    final_valore_perizia = normalize_money_string(
        _prefer_sources_then_existing(
            _get_ai_objective_value(ai_data, "valore_perizia"),
            ai_data.get("valore_perizia"),
            perizia_struct.get("valore_perizia"),
            avviso_fields.get("valore_perizia"),
            getattr(asta, "valore_perizia", None),
        )
    )

    final_occupazione = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "occupazione"),
        ai_data.get("occupazione"),
        ai_data.get("stato_occupazione_dettaglio"),
        perizia_struct.get("occupazione"),
        avviso_fields.get("occupazione"),
        getattr(asta, "occupazione", None),
    )

    final_catasto = _prefer_sources_then_existing(
        ai_data.get("catasto"),
        perizia_struct.get("catasto"),
        avviso_fields.get("catasto"),
        getattr(asta, "catasto", None),
    )

    final_foglio = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "foglio"),
        ai_data.get("foglio"),
        perizia_struct.get("foglio"),
        avviso_fields.get("foglio"),
        getattr(asta, "foglio", None),
    )

    final_mappale = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "particella"),
        _get_ai_objective_value(ai_data, "mappale"),
        ai_data.get("mappale"),
        perizia_struct.get("mappale"),
        avviso_fields.get("mappale"),
        getattr(asta, "mappale", None),
    )

    final_subalterno = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "subalterno"),
        ai_data.get("subalterno"),
        perizia_struct.get("subalterno"),
        avviso_fields.get("subalterno"),
        getattr(asta, "subalterno", None),
    )
    final_subalterno = normalize_subalterni(final_subalterno)

    final_categoria_catastale = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "categoria_catastale"),
        ai_data.get("categoria_catastale"),
        perizia_struct.get("categoria_catastale"),
        avviso_fields.get("categoria_catastale"),
        getattr(asta, "categoria_catastale", None),
    )

    final_descrizione = _build_descrizione_final(
        ai_data,
        perizia_struct,
        avviso_fields,
        getattr(asta, "descrizione_immobile", None),
    )

    final_pregiudizievoli = _build_pregiudizievoli_final(
        ai_data,
        perizia_struct,
        getattr(asta, "pregiudizievoli", None),
    )

    final_abusi = _build_abusi_final(
        ai_data,
        perizia_struct,
        getattr(asta, "abusi", None),
    )

    final_sintesi = _prefer_sources_then_existing(
        ai_data.get("interpretazione_operativa"),
        ai_data.get("sintesi"),
        ai_data.get("riassunto_breve"),
        getattr(asta, "sintesi", None),
    )

    final_note_operativi = _build_note_operativi(
        ai_data,
        asta,
        final_prezzo_base,
        final_offerta_minima,
        final_rilancio_minimo,
    )

    cross_warnings = _build_cross_source_warnings(asta, avviso_fields, perizia_struct, ai_data)
    if cross_warnings:
        warning_block = "Verifiche incrociate (warning):\n" + "\n".join(f"- {w}" for w in cross_warnings)
        final_note_operativi = _join_paragraphs([final_note_operativi or "", warning_block])

    final_proprietario = _prefer_sources_then_existing(
        _get_ai_objective_value(ai_data, "proprietario"),
        ai_data.get("proprietario"),
        getattr(asta, "proprietario", None),
    )

    final_creditore = _prefer_existing_then_sources(
        _get_ai_objective_value(ai_data, "creditore_procedente"),
        ai_data.get("creditore_procedente"),
        getattr(asta, "creditore_procedente", None),
    )

    objective_warnings = _collect_ai_objective_warnings(ai_data)
    if objective_warnings:
        final_note_operativi = _join_paragraphs([
            final_note_operativi or "",
            "Warning campi oggettivi scelti dall'AI:\n" + "\n".join(f"- {item}" for item in objective_warnings),
        ])

    update_fields = {
        "ai_status": "done",
        "ai_error": None,
        "ai_result_json": json.dumps(ai_data, ensure_ascii=False, indent=2),
        "ai_summary": _first_non_empty(ai_data.get("riassunto_breve"), ai_data.get("sintesi")),
        "ai_model": MODEL_NAME,
        "perizia_status": f"text_extracted:{perizia_source}" if perizia_source else "text_extracted",
        "perizia_error": None,

        "tribunale": final_tribunale,
        "rge": _norm_text(final_rge),
        "lotto": _norm_text(final_lotto),
        "data_asta": _norm_text(final_data_asta),
        "citta": _norm_text(final_citta),
        "indirizzo": _norm_text(final_indirizzo),

        "prezzo_base": _norm_text(final_prezzo_base),
        "offerta_minima": _norm_text(final_offerta_minima),
        "rilancio_minimo": _norm_text(final_rilancio_minimo),
        "valore_perizia": _norm_text(final_valore_perizia),

        "occupazione": _norm_multiline(final_occupazione),

        "catasto": _norm_text(final_catasto),
        "foglio": _norm_text(final_foglio),
        "mappale": _norm_text(final_mappale),
        "subalterno": _norm_text(final_subalterno),
        "categoria_catastale": _norm_text(final_categoria_catastale),

        "proprietario": _norm_text(final_proprietario),
        "creditore_procedente": _norm_text(final_creditore),

        "descrizione_immobile": _norm_multiline(final_descrizione),
        "pregiudizievoli": _norm_multiline(final_pregiudizievoli),
        "abusi": _norm_multiline(final_abusi),
        "sintesi": _norm_multiline(final_sintesi),
        "note_operativi": _norm_multiline(final_note_operativi),
    }

    # aggiorna note solo se vuote
    existing_note = _norm_multiline(getattr(asta, "note", None))
    if existing_note:
        update_fields["note"] = existing_note
    else:
        sources_note = []
        if avviso_source:
            sources_note.append(f"avviso:{avviso_source}")
        if perizia_source:
            sources_note.append(f"perizia:{perizia_source}")

        note_analisi = "Analisi perizia completata"
        if sources_note:
            note_analisi += " | " + ", ".join(sources_note)

        update_fields["note"] = note_analisi

    set_analysis_job(
        asta_id,
        progress=90,
        step="salvataggio",
        message="Salvataggio risultati in scheda",
        done=False,
        error=None,
    )

    update_asta_fields(asta_id, **update_fields)

    set_analysis_job(
        asta_id,
        progress=100,
        step="done",
        message="Analisi completata",
        done=True,
        error=None,
    )

    return ai_data
 
