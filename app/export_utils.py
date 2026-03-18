from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.routes_analysis import _read_pdf_text_with_fallback
from app.services_parsing import normalize_date_string, normalize_money_string


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _v(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_abs_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    p = Path(path_value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def _fmt_section(title: str, content: str) -> str:
    return f"\n{'=' * 24}\n{title}\n{'=' * 24}\n{content}\n"




def _load_json_text(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value

def _json_dump(data) -> str:
    if data is None:
        return "Non disponibile"
    try:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(data)


def build_asta_detail_text(asta) -> str:
    sections = [
        "SCHEDA FINALE ASTA",
        f"ID asta: {asta.id}",
        f"Tribunale: {_v(getattr(asta, 'tribunale', None)) or '-'}",
        f"RGE: {_v(getattr(asta, 'rge', None)) or '-'}",
        f"Lotto: {_v(getattr(asta, 'lotto', None)) or '-'}",
        f"Data asta: {_v(getattr(asta, 'data_asta', None)) or '-'}",
        f"Città: {_v(getattr(asta, 'citta', None)) or '-'}",
        f"Indirizzo: {_v(getattr(asta, 'indirizzo', None)) or '-'}",
        "",
        "DATI ECONOMICI",
        f"Valore di perizia: {_v(getattr(asta, 'valore_perizia', None)) or '-'}",
        f"Prezzo base: {_v(getattr(asta, 'prezzo_base', None)) or '-'}",
        f"Offerta minima: {_v(getattr(asta, 'offerta_minima', None)) or '-'}",
        f"Rilancio minimo: {_v(getattr(asta, 'rilancio_minimo', None)) or '-'}",
        "",
        "DATI PRINCIPALI",
        f"Occupazione: {_v(getattr(asta, 'occupazione', None)) or '-'}",
        f"Creditore procedente: {_v(getattr(asta, 'creditore_procedente', None)) or '-'}",
        f"Proprietario: {_v(getattr(asta, 'proprietario', None)) or '-'}",
        "",
        "DATI CATASTALI",
        f"Catasto: {_v(getattr(asta, 'catasto', None)) or '-'}",
        f"Foglio: {_v(getattr(asta, 'foglio', None)) or '-'}",
        f"Mappale / Particella: {_v(getattr(asta, 'mappale', None)) or '-'}",
        f"Subalterno: {_v(getattr(asta, 'subalterno', None)) or '-'}",
        f"Categoria catastale: {_v(getattr(asta, 'categoria_catastale', None)) or '-'}",
        "",
        "DESCRIZIONE IMMOBILE",
        _v(getattr(asta, 'descrizione_immobile', None)) or "Non disponibile",
        "",
        "PREGIUDIZIEVOLI",
        _v(getattr(asta, 'pregiudizievoli', None)) or "Non disponibile",
        "",
        "ABUSI / URBANISTICA",
        _v(getattr(asta, 'abusi', None)) or "Non disponibile",
        "",
        "NOTE OPERATIVE",
        _v(getattr(asta, 'note_operativi', None)) or "Non disponibile",
        "",
        "SINTESI",
        _v(getattr(asta, 'sintesi', None)) or "Non disponibile",
        "",
        "NOTE",
        _v(getattr(asta, 'note', None)) or "Non disponibile",
    ]
    return "\n".join(sections).strip() + "\n"


def _wrap_text_lines(lines: Iterable[str], width: int = 95) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line:
            out.append("")
            continue
        wrapped = textwrap.wrap(line, width=width, replace_whitespace=False, drop_whitespace=False)
        out.extend(wrapped or [""])
    return out


def _pdf_escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _to_pdf_text(value: str) -> str:
    return value.encode("latin-1", errors="replace").decode("latin-1")


def build_simple_pdf_bytes(title: str, body_text: str) -> bytes:
    # PDF minimale, senza dipendenze esterne, compatibile con viewer standard.
    page_width = 595
    page_height = 842
    margin_left = 40
    margin_top = 50
    line_height = 14
    usable_lines = 52

    all_lines = [title, ""] + _wrap_text_lines(body_text.splitlines(), width=100)
    pages = [all_lines[i:i + usable_lines] for i in range(0, len(all_lines), usable_lines)] or [[title]]

    objects: list[bytes] = []

    def add_object(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    font_obj = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    content_ids: list[int] = []

    for page_lines in pages:
        commands = [b"BT", b"/F1 10 Tf"]
        y = page_height - margin_top
        for idx, line in enumerate(page_lines):
            text = _pdf_escape(_to_pdf_text(line))
            cmd = f"1 0 0 1 {margin_left} {y - idx * line_height} Tm ({text}) Tj".encode("latin-1", errors="replace")
            commands.append(cmd)
        commands.append(b"ET")
        stream = b"\n".join(commands)
        content_id = add_object(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_ids.append(content_id)
        page_ids.append(0)

    pages_kids_placeholder = "KIDS_PLACEHOLDER"
    pages_obj_index = add_object(f"<< /Type /Pages /Kids {pages_kids_placeholder} /Count {len(pages)} >>".encode())

    for i, content_id in enumerate(content_ids):
        page_obj = (
            f"<< /Type /Page /Parent {pages_obj_index} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        page_ids[i] = add_object(page_obj)

    kids = "[ " + " ".join(f"{pid} 0 R" for pid in page_ids) + " ]"
    objects[pages_obj_index - 1] = objects[pages_obj_index - 1].replace(pages_kids_placeholder.encode(), kids.encode())

    catalog_obj = add_object(f"<< /Type /Catalog /Pages {pages_obj_index} 0 R >>".encode())

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode())
    return bytes(pdf)


def _file_info(path: Path | None) -> tuple[str, str]:
    if not path:
        return "Non disponibile", "Non disponibile"
    if not path.exists():
        return str(path), "File non trovato"
    return str(path), str(path.stat().st_size)


def build_avviso_debug_txt(asta) -> str:
    path = _to_abs_path(getattr(asta, "avviso_file_path", None))
    path_str, file_size = _file_info(path)
    text = ""
    source = "Non disponibile"
    diagnostics = None
    fields = _load_json_text(getattr(asta, "avviso_parsed_json", None))
    warning_lines: list[str] = []
    error = None

    if path and path.exists():
        try:
            text, source, diagnostics = _read_pdf_text_with_fallback(path)
            if not text:
                warning_lines.append("Testo estratto vuoto dall'avviso.")
        except Exception as exc:
            error = str(exc)

    normalized = {
        "tribunale": fields.get("tribunale") if fields else None,
        "rge": fields.get("rge") if fields else None,
        "lotto": fields.get("lotto") if fields else None,
        "data_asta": normalize_date_string(fields.get("data_asta")) if fields else None,
        "prezzo_base": normalize_money_string(fields.get("prezzo_base")) if fields else None,
        "offerta_minima": normalize_money_string(fields.get("offerta_minima")) if fields else None,
    }
    final_db_values = {
        "tribunale": getattr(asta, "tribunale", None),
        "rge": getattr(asta, "rge", None),
        "lotto": getattr(asta, "lotto", None),
        "data_asta": getattr(asta, "data_asta", None),
        "prezzo_base": getattr(asta, "prezzo_base", None),
        "offerta_minima": getattr(asta, "offerta_minima", None),
        "indirizzo": getattr(asta, "indirizzo", None),
    }

    parts = [
        _fmt_section("METADATI", "\n".join([
            f"ID asta: {asta.id}",
            f"Tribunale: {_v(getattr(asta, 'tribunale', None)) or '-'}",
            f"RGE: {_v(getattr(asta, 'rge', None)) or '-'}",
            f"Lotto: {_v(getattr(asta, 'lotto', None)) or '-'}",
            f"Timestamp export: {datetime.now().isoformat(timespec='seconds')}",
            f"Path file avviso: {path_str}",
            f"Dimensione file bytes: {file_size}",
            f"Metodo di lettura usato: {source}",
        ])),
        _fmt_section("DIAGNOSTICA LETTURA", _json_dump(diagnostics) if diagnostics else "Non disponibile"),
        _fmt_section("CAMPI ESTRATTI DALL'AVVISO", _json_dump(fields) if fields is not None else "Non disponibile"),
        _fmt_section("DATI NORMALIZZATI", _json_dump(normalized)),
        _fmt_section("DATI FINALI SALVATI DERIVANTI DALL'AVVISO", _json_dump(final_db_values)),
        _fmt_section("WARNING", "\n".join(warning_lines) if warning_lines else "Nessun warning disponibile"),
        _fmt_section("ERRORI", error or _v(getattr(asta, 'avviso_error', None)) or "Nessun errore disponibile"),
        _fmt_section("TESTO ESTRATTO COMPLETO", text or "Non disponibile"),
    ]
    return "".join(parts)


def build_perizia_debug_txt(asta) -> str:
    path = _to_abs_path(getattr(asta, "perizia_file_path", None))
    path_str, file_size = _file_info(path)
    text = ""
    source = "Non disponibile"
    diagnostics = None
    error = None
    warning_lines: list[str] = []
    ai_raw = getattr(asta, "ai_raw_response", None)
    ai_prompt = getattr(asta, "ai_prompt_text", None)
    ai_fields = _load_json_text(getattr(asta, "ai_result_json", None))
    perizia_parsed = _load_json_text(getattr(asta, "perizia_parsed_json", None))

    if path and path.exists():
        try:
            text, source, diagnostics = _read_pdf_text_with_fallback(path)
            if not text:
                warning_lines.append("Testo estratto vuoto dalla perizia.")
        except Exception as exc:
            error = str(exc)

    if getattr(asta, "ai_result_json", None) and ai_fields is None:
        warning_lines.append("ai_result_json non parseabile come JSON.")

    normalized = {
        "tribunale": getattr(asta, "tribunale", None),
        "rge": getattr(asta, "rge", None),
        "lotto": getattr(asta, "lotto", None),
        "data_asta": getattr(asta, "data_asta", None),
        "valore_perizia": getattr(asta, "valore_perizia", None),
        "prezzo_base": getattr(asta, "prezzo_base", None),
        "offerta_minima": getattr(asta, "offerta_minima", None),
    }
    final_values = {
        "descrizione_immobile": getattr(asta, "descrizione_immobile", None),
        "pregiudizievoli": getattr(asta, "pregiudizievoli", None),
        "abusi": getattr(asta, "abusi", None),
        "note_operativi": getattr(asta, "note_operativi", None),
        "sintesi": getattr(asta, "sintesi", None),
        "ai_status": getattr(asta, "ai_status", None),
        "ai_model": getattr(asta, "ai_model", None),
    }

    parts = [
        _fmt_section("METADATI", "\n".join([
            f"ID asta: {asta.id}",
            f"Tribunale: {_v(getattr(asta, 'tribunale', None)) or '-'}",
            f"RGE: {_v(getattr(asta, 'rge', None)) or '-'}",
            f"Lotto: {_v(getattr(asta, 'lotto', None)) or '-'}",
            f"Timestamp export: {datetime.now().isoformat(timespec='seconds')}",
            f"Path file perizia: {path_str}",
            f"Dimensione file bytes: {file_size}",
            f"Metodo di lettura usato: {source}",
            f"Uso OCR: {'sì' if source == 'ocr' else 'no' if source != 'Non disponibile' else 'non disponibile'}",
        ])),
        _fmt_section("DIAGNOSTICA LETTURA", _json_dump(diagnostics) if diagnostics else "Non disponibile"),
        _fmt_section("PROMPT OPENAI INVIATO", ai_prompt or "Non disponibile nel flusso attuale"),
        _fmt_section("RISPOSTA AI GREZZA", ai_raw or "Non disponibile nel flusso attuale"),
        _fmt_section("PARSING ORIGINALE PERIZIA", _json_dump(perizia_parsed) if perizia_parsed is not None else "Non disponibile"),
        _fmt_section("CAMPI AI ESTRATTI", _json_dump(ai_fields) if ai_fields is not None else "Non disponibile"),
        _fmt_section("DATI NORMALIZZATI", _json_dump(normalized)),
        _fmt_section("NOTE OPERATIVE FINALI", _v(getattr(asta, 'note_operativi', None)) or "Non disponibile"),
        _fmt_section("DATI FINALI SALVATI DERIVANTI DALLA PERIZIA", _json_dump(final_values)),
        _fmt_section("WARNING", "\n".join(warning_lines) if warning_lines else "Nessun warning disponibile"),
        _fmt_section("ERRORI", error or _v(getattr(asta, 'perizia_error', None)) or _v(getattr(asta, 'ai_error', None)) or "Nessun errore disponibile"),
        _fmt_section("TESTO ESTRATTO COMPLETO", text or "Non disponibile"),
    ]
    return "".join(parts)
