from __future__ import annotations

import re
import shutil
import logging
from datetime import datetime
from pathlib import Path

from app.services_pdf_classifier import classify_pdf_document
from app.services_parsing import (
    extract_avviso_fields_from_text,
    extract_structured_fields_from_perizia_text,
)
from app.ocr_text import extract_text_from_pdf_ocr


logger = logging.getLogger(__name__)
MIN_TEXT_FOR_AI_ANALYSIS = 900


def read_pdf_text_with_fallback(pdf_path: Path) -> str:
    """
    Lettura robusta testo PDF.
    - usa pypdf con diagnostica
    - forza OCR se testo vuoto o troppo corto
    """
    diag = None
    try:
        from app.pdf_text import extract_text_with_diagnostics

        diag = extract_text_with_diagnostics(pdf_path)
        text = (diag.get("text") or "").strip()
        quality = diag.get("quality")

        # MOD: se il testo è troppo corto lo consideriamo insufficiente e forziamo OCR.
        if text and quality == "good" and len(text) >= MIN_TEXT_FOR_AI_ANALYSIS:
            return text

        if not text:
            logger.warning("PDF senza testo da pypdf: %s", pdf_path)
        elif len(text) < MIN_TEXT_FOR_AI_ANALYSIS:
            logger.warning(
                "PDF con testo corto (%s chars), forzo OCR: %s",
                len(text),
                pdf_path,
            )
        else:
            logger.info("PDF quality=%s, provo OCR: %s", quality, pdf_path)
    except Exception:
        logger.exception("Errore estrazione pypdf: %s", pdf_path)

    try:
        ocr_result = extract_text_from_pdf_ocr(pdf_path)

        if isinstance(ocr_result, dict):
            ocr_text = (ocr_result.get("text") or "").strip()
            if ocr_result.get("status") == "ok" and ocr_text:
                return ocr_text
        elif isinstance(ocr_result, str):
            ocr_text = ocr_result.strip()
            if ocr_text:
                return ocr_text
    except Exception:
        logger.exception("Errore OCR su PDF: %s", pdf_path)

    try:
        if isinstance(diag, dict):
            return (diag.get("text") or "").strip()

        from app.pdf_text import extract_text_with_diagnostics
        fallback_diag = extract_text_with_diagnostics(pdf_path)
        return (fallback_diag.get("text") or "").strip()
    except Exception:
        logger.exception("Fallback finale estrazione testo fallito: %s", pdf_path)
        return ""


# =========================================================
# DIRECTORY
# =========================================================

def ensure_data_dirs(project_root: Path):
    perizie_dir = project_root / "data" / "perizie"
    avvisi_dir = project_root / "data" / "avvisi"

    perizie_dir.mkdir(parents=True, exist_ok=True)
    avvisi_dir.mkdir(parents=True, exist_ok=True)

    return perizie_dir, avvisi_dir


# =========================================================
# FILENAME
# =========================================================

def sanitize_filename_part(value):
    if not value:
        return ""

    value = str(value).strip()
    value = value.replace("/", "_")
    value = value.replace("\\", "_")
    value = value.replace(" ", "_")
    value = re.sub(r"[^\w\-_.]", "", value)

    return value.strip("_")


def build_manual_filename(asta, tipo: str):
    """
    Formato:
    Tribunale_Sassari_RGE_179_2021_Lotto_1_perizia.pdf
    Tribunale_Sassari_RGE_179_2021_Lotto_1_avviso.pdf
    """
    tribunale = sanitize_filename_part(getattr(asta, "tribunale", None))
    rge = sanitize_filename_part(
        getattr(asta, "rge", None) or getattr(asta, "numero_rge", None)
    )
    lotto = sanitize_filename_part(getattr(asta, "lotto", None))

    parts = []

    if tribunale:
        parts.append(f"Tribunale_{tribunale}")

    if rge:
        parts.append(f"RGE_{rge}")

    if lotto:
        parts.append(f"Lotto_{lotto}")

    parts.append(tipo)

    return "_".join(parts) + ".pdf"


def build_filename_from_extracted_fields(fields: dict, tipo: str) -> str:
    tribunale = sanitize_filename_part(fields.get("tribunale"))
    rge = sanitize_filename_part(fields.get("rge"))
    lotto = sanitize_filename_part(fields.get("lotto"))

    parts = []

    if tribunale:
        if tribunale.lower().startswith("tribunale_"):
            parts.append(tribunale)
        else:
            parts.append(f"Tribunale_{tribunale}")

    if rge:
        parts.append(f"RGE_{rge}")

    if lotto:
        parts.append(f"Lotto_{lotto}")

    if not parts:
        parts.append("Documento")

    parts.append(tipo)

    return "_".join(parts) + ".pdf"


def make_unique_path(dest: Path) -> Path:
    counter = 1
    final_dest = dest

    while final_dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        final_dest = dest.parent / f"{stem}_{counter}{suffix}"
        counter += 1

    return final_dest


# =========================================================
# CLASSIFICAZIONE E LETTURA CONTENUTO
# =========================================================

def classify_and_extract_fields(pdf_path: Path):
    """
    Restituisce:
    - tipo: "perizia" | "avviso" | "unknown"
    - fields: dict
    - text: str
    """
    text = read_pdf_text_with_fallback(pdf_path)
    text_lower = (text or "").lower()

    doc_type, score_perizia, score_avviso = classify_pdf_document(pdf_path)

    if doc_type == "avviso":
        fields = extract_avviso_fields_from_text(text)
        return "avviso", fields, text

    if doc_type == "perizia":
        fields = extract_structured_fields_from_perizia_text(text)
        return "perizia", fields, text

    # fallback testuale
    if "offerta minima" in text_lower or "vendita senza incanto" in text_lower:
        fields = extract_avviso_fields_from_text(text)
        return "avviso", fields, text

    if "stima del bene" in text_lower or "valore di mercato" in text_lower:
        fields = extract_structured_fields_from_perizia_text(text)
        return "perizia", fields, text

    # fallback a punteggio
    if score_avviso > score_perizia:
        fields = extract_avviso_fields_from_text(text)
        return "avviso", fields, text

    if score_perizia > score_avviso:
        fields = extract_structured_fields_from_perizia_text(text)
        return "perizia", fields, text

    return "unknown", {}, text


def classify_and_rename_pdf(pdf_path: Path) -> tuple[str, Path, dict]:
    """
    Classifica e rinomina un PDF in base al suo contenuto.
    Restituisce:
    - tipo
    - nuovo path
    - fields
    """
    tipo, fields, _text = classify_and_extract_fields(pdf_path)

    if tipo not in {"perizia", "avviso"}:
        return tipo, pdf_path, fields

    new_name = build_filename_from_extracted_fields(fields, tipo)
    new_path = make_unique_path(pdf_path.parent / new_name)

    if pdf_path.resolve() != new_path.resolve():
        shutil.move(str(pdf_path), str(new_path))
        return tipo, new_path, fields

    return tipo, pdf_path, fields


# =========================================================
# RINOMINA DOCUMENTI IN BASE AL DB
# =========================================================

def rename_asta_documents_from_db(asta_id, get_asta, update_asta_fields):
    asta = get_asta(asta_id)
    if not asta:
        return False, "Asta non trovata"

    project_root = Path(__file__).resolve().parents[1]
    perizie_dir, avvisi_dir = ensure_data_dirs(project_root)

    renamed = []

    perizia_rel = getattr(asta, "perizia_file_path", None)
    if perizia_rel:
        old_path = Path(perizia_rel)
        if not old_path.is_absolute():
            old_path = project_root / perizia_rel

        if old_path.exists():
            new_name = build_manual_filename(asta, "perizia")
            new_path = perizie_dir / new_name

            if old_path.resolve() != new_path.resolve():
                final_path = make_unique_path(new_path)
                shutil.move(str(old_path), str(final_path))
                update_asta_fields(
                    asta_id,
                    perizia_file_path=str(final_path.relative_to(project_root)),
                )
                renamed.append(f"{old_path.name} -> {final_path.name}")

    avviso_rel = getattr(asta, "avviso_file_path", None)
    if avviso_rel:
        old_path = Path(avviso_rel)
        if not old_path.is_absolute():
            old_path = project_root / avviso_rel

        if old_path.exists():
            new_name = build_manual_filename(asta, "avviso")
            new_path = avvisi_dir / new_name

            if old_path.resolve() != new_path.resolve():
                final_path = make_unique_path(new_path)
                shutil.move(str(old_path), str(final_path))
                update_asta_fields(
                    asta_id,
                    avviso_file_path=str(final_path.relative_to(project_root)),
                )
                renamed.append(f"{old_path.name} -> {final_path.name}")

    if renamed:
        return True, " | ".join(renamed)

    return True, "Nessuna rinomina necessaria"


# =========================================================
# DOWNLOADS
# =========================================================

def get_downloads_dir() -> Path:
    return Path.home() / "Downloads"


def is_pdf_download_complete(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    if file_path.suffix.lower() != ".pdf":
        return False
    if file_path.stat().st_size <= 0:
        return False

    age_seconds = datetime.now().timestamp() - file_path.stat().st_mtime
    if age_seconds < 2:
        return False

    return True


def collect_recent_pdf_candidates(
    minutes: int = 3,
    max_files: int = 10,
) -> list[Path]:
    downloads_dir = get_downloads_dir()
    if not downloads_dir.exists():
        return []

    now_ts = datetime.now().timestamp()
    window_seconds = minutes * 60
    candidates = []

    for file_path in downloads_dir.iterdir():
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() != ".pdf":
            continue

        name_lower = file_path.name.lower()
        if name_lower.endswith(".crdownload"):
            continue

        try:
            mtime = file_path.stat().st_mtime
        except Exception:
            continue

        age = now_ts - mtime
        if age < 0 or age > window_seconds:
            continue

        if not is_pdf_download_complete(file_path):
            continue

        candidates.append(file_path)

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:max_files]


# =========================================================
# CLASSIFICAZIONE PDF RECENTI
# =========================================================

def classify_recent_pdfs(pdf_paths: list[Path]):
    """
    Restituisce:
        (perizia_path, avviso_path, debug_message)
    """
    if not pdf_paths:
        return None, None, "Nessun PDF candidato trovato"

    perizia_path = None
    avviso_path = None
    debug_rows = []
    scored = []

    for pdf_path in pdf_paths:
        doc_type, score_perizia, score_avviso = classify_pdf_document(pdf_path)

        debug_rows.append(
            f"{pdf_path.name} => tipo={doc_type}, score_perizia={score_perizia}, score_avviso={score_avviso}"
        )

        scored.append((pdf_path, doc_type, score_perizia, score_avviso))

    for pdf_path, doc_type, score_perizia, score_avviso in scored:
        if doc_type == "perizia" and perizia_path is None:
            perizia_path = pdf_path
        elif doc_type == "avviso" and avviso_path is None:
            avviso_path = pdf_path

    if perizia_path is None or avviso_path is None:
        remaining = [row[0] for row in scored if row[0] not in {perizia_path, avviso_path}]
        remaining = sorted(remaining, key=lambda p: p.stat().st_size, reverse=True)

        if perizia_path is None and len(remaining) >= 1:
            perizia_path = remaining[0]
            debug_rows.append(f"Fallback dimensione perizia => {perizia_path.name}")

        remaining = [p for p in remaining if p != perizia_path]

        if avviso_path is None and len(remaining) >= 1:
            avviso_path = remaining[-1]
            debug_rows.append(f"Fallback dimensione avviso => {avviso_path.name}")

    return perizia_path, avviso_path, " | ".join(debug_rows)


# =========================================================
# IMPORT DOCUMENTI NEL PROGETTO
# =========================================================

def copy_recent_pdf_into_project(
    source_pdf: Path,
    destination_dir: Path,
    asta,
    tipo: str,
    project_root: Path,
) -> str:
    filename = build_manual_filename(asta, tipo)
    dest = destination_dir / filename
    final_dest = make_unique_path(dest)

    shutil.move(str(source_pdf), str(final_dest))
    return str(final_dest.relative_to(project_root))


def import_recent_downloaded_pdfs_for_asta(
    asta_id: int,
    get_asta,
    update_asta_fields,
    minutes: int = 3,
):
    asta = get_asta(asta_id)
    if not asta:
        return False, "Asta non trovata"

    project_root = Path(__file__).resolve().parents[1]
    perizie_dir, avvisi_dir = ensure_data_dirs(project_root)

    recent_pdfs = collect_recent_pdf_candidates(minutes=minutes, max_files=10)

    if len(recent_pdfs) < 2:
        found = len(recent_pdfs)
        return (
            False,
            f"Trovati solo {found} PDF negli ultimi {minutes} minuti nella cartella Download. "
            f"Scarica avviso e perizia, poi riprova.",
        )

    perizia_source, avviso_source, debug_message = classify_recent_pdfs(recent_pdfs)

    if not perizia_source or not avviso_source:
        return False, f"Impossibile classificare i PDF recenti. Debug: {debug_message}"

    # Copia/sposta nel progetto usando il naming DB-based iniziale
    perizia_rel_path = copy_recent_pdf_into_project(
        source_pdf=perizia_source,
        destination_dir=perizie_dir,
        asta=asta,
        tipo="perizia",
        project_root=project_root,
    )

    avviso_rel_path = copy_recent_pdf_into_project(
        source_pdf=avviso_source,
        destination_dir=avvisi_dir,
        asta=asta,
        tipo="avviso",
        project_root=project_root,
    )

    updates = {
        "perizia_file_path": perizia_rel_path,
        "perizia_status": "imported_from_downloads",
        "perizia_checked_at": datetime.utcnow(),
        "perizia_error": None,
        "avviso_file_path": avviso_rel_path,
        "avviso_status": "imported_from_downloads",
        "avviso_checked_at": datetime.utcnow(),
        "avviso_error": None,
    }

    update_asta_fields(asta_id, **updates)

    # Prova a classificare e leggere anche i documenti già spostati
    perizia_full_path = project_root / perizia_rel_path
    avviso_full_path = project_root / avviso_rel_path

    perizia_tipo, perizia_new_path, perizia_fields = classify_and_rename_pdf(perizia_full_path)
    avviso_tipo, avviso_new_path, avviso_fields = classify_and_rename_pdf(avviso_full_path)

    post_updates = {}

    if perizia_new_path.exists():
        post_updates["perizia_file_path"] = str(perizia_new_path.relative_to(project_root))

    if avviso_new_path.exists():
        post_updates["avviso_file_path"] = str(avviso_new_path.relative_to(project_root))

    # Integra solo i dati mancanti dell’asta con quelli letti dai PDF
    merged_fields = {}
    for key in ("tribunale", "rge", "lotto"):
        current_value = getattr(asta, key, None)
        candidate_value = (
            perizia_fields.get(key)
            or avviso_fields.get(key)
        )
        if (not current_value) and candidate_value:
            merged_fields[key] = candidate_value

    if merged_fields:
        post_updates.update(merged_fields)

    if post_updates:
        update_asta_fields(asta_id, **post_updates)

    imported_names = [
        f"Perizia: {Path(post_updates.get('perizia_file_path', perizia_rel_path)).name}",
        f"Avviso: {Path(post_updates.get('avviso_file_path', avviso_rel_path)).name}",
    ]

    return (
        True,
        "Import automatico completato da Download. "
        + " | ".join(imported_names)
        + f" | Debug: {debug_message}"
    )
