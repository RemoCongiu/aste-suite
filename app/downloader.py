from __future__ import annotations

import os
from pathlib import Path
import httpx


def sanitize(text: str | None) -> str:
    """
    Pulisce il testo per essere usato nei nomi file
    """
    if not text:
        return ""

    text = text.lower()
    text = text.replace("/", "_")
    text = text.replace(" ", "_")
    text = text.replace(".", "")
    text = text.replace(",", "")
    text = text.replace(":", "")
    text = text.replace(";", "")
    text = text.replace("__", "_")

    return text.strip("_")


def build_filename(
    tribunale: str | None,
    rge: str | None,
    lotto: str | None,
    doc_type: str,
    asta_id: int
) -> str:
    """
    Costruisce il nome file dei documenti.

    Esempio output:
    tempio_pausania_rge_159_13_lotto1_perizia.pdf
    tempio_pausania_rge_159_13_lotto1_avviso.pdf
    """

    tribunale_safe = sanitize(tribunale)
    rge_safe = sanitize(rge)
    lotto_safe = sanitize(lotto) or "1"

    if tribunale_safe and rge_safe:
        return f"{tribunale_safe}_rge_{rge_safe}_lotto{lotto_safe}_{doc_type}.pdf"

    return f"asta_{asta_id}_{doc_type}.pdf"


def ensure_data_dirs(project_root: Path) -> Path:
    """
    Crea la cartella dove salvare i PDF se non esiste.
    """
    data_dir = project_root / "data"

    perizie_dir = data_dir / "perizie"
    avvisi_dir = data_dir / "avvisi"

    perizie_dir.mkdir(parents=True, exist_ok=True)
    avvisi_dir.mkdir(parents=True, exist_ok=True)

    return data_dir


def download_pdf(url: str, dest_path: Path, timeout_sec: int = 40) -> None:
    """
    Scarica un PDF da URL e lo salva su disco.
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsteSuite/1.0"
    }

    with httpx.Client(
        follow_redirects=True,
        headers=headers,
        timeout=timeout_sec
    ) as client:

        response = client.get(url)
        response.raise_for_status()

        dest_path.write_bytes(response.content)