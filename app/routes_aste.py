from __future__ import annotations

import html
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_asta, get_or_create_asta, list_aste, update_asta_fields
from app.excel_export import build_excel_export
from app.pdf_text import extract_text_from_pdf
from app.routes_analysis import analyze_perizia_for_asta, set_analysis_job
from app.services_documents import (
    import_recent_downloaded_pdfs_for_asta,
    rename_asta_documents_from_db,
)

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _to_abs_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    p = Path(path_value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


@router.get("/intake-from-browser")
def intake_from_browser(url: str = Query(...)):
    try:
        asta, _created = get_or_create_asta(url)
        return RedirectResponse(url=f"/aste/{asta.id}/documenti", status_code=303)
    except Exception as e:
        return HTMLResponse(f"Errore intake: {html.escape(str(e))}", status_code=500)


@router.get("/aste/{asta_id}/documenti", response_class=HTMLResponse)
def documenti_page(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        raise HTTPException(status_code=404, detail="Asta non trovata")

    tribunale = html.escape(getattr(asta, "tribunale", "") or "")
    rge = html.escape(getattr(asta, "rge", "") or "")
    lotto = html.escape(getattr(asta, "lotto", "") or "")

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Documenti asta {asta_id}</title>
    </head>
    <body style="font-family:Arial,sans-serif;padding:24px;max-width:900px;margin:auto;">
        <h1>Documenti Asta {asta_id}</h1>

        <div style="margin:24px 0;padding:18px;border:1px solid #ddd;border-radius:12px;background:#f8fafc;">
            <h2 style="margin-top:0;">Metodo consigliato</h2>
            <p>Scarica avviso e perizia dal browser, poi clicca qui entro 3 minuti.</p>
            <p>
                <a href="/aste/{asta_id}/import-progress"
                   style="display:inline-block;padding:12px 18px;background:#1d4ed8;color:#fff;text-decoration:none;border-radius:10px;">
                   Importa ultimi 2 PDF da Download
                </a>
            </p>
        </div>

        <div style="margin:24px 0;padding:18px;border:1px solid #ddd;border-radius:12px;background:#ffffff;">
            <h2 style="margin-top:0;">Caricamento manuale</h2>
            <form action="/aste/{asta_id}/documenti" method="post" enctype="multipart/form-data">
                <p>Tribunale<br><input name="tribunale_manual" value="{tribunale}" style="width:360px;"></p>
                <p>RGE<br><input name="rge_manual" value="{rge}" style="width:360px;"></p>
                <p>Lotto<br><input name="lotto_manual" value="{lotto}" style="width:360px;"></p>

                <p>Perizia PDF<br><input type="file" name="perizia_pdf_file"></p>
                <p>Avviso PDF<br><input type="file" name="avviso_pdf_file"></p>

                <p><button type="submit">Carica manualmente</button></p>
            </form>
        </div>

        <p><a href="/aste/{asta_id}">← Torna alla scheda asta</a></p>
    </body>
    </html>
    """


@router.post("/aste/{asta_id}/documenti")
async def upload_documenti(
    asta_id: int,
    tribunale_manual: str = Form(None),
    rge_manual: str = Form(None),
    lotto_manual: str = Form(None),
    perizia_pdf_file: UploadFile = File(None),
    avviso_pdf_file: UploadFile = File(None),
):
    asta = get_asta(asta_id)
    if not asta:
        raise HTTPException(status_code=404, detail="Asta non trovata")

    perizie_dir = PROJECT_ROOT / "data" / "perizie"
    avvisi_dir = PROJECT_ROOT / "data" / "avvisi"
    perizie_dir.mkdir(parents=True, exist_ok=True)
    avvisi_dir.mkdir(parents=True, exist_ok=True)

    updates: dict = {}

    if tribunale_manual:
        updates["tribunale"] = tribunale_manual.strip()
    if rge_manual:
        updates["rge"] = rge_manual.strip()
    if lotto_manual:
        updates["lotto"] = lotto_manual.strip()

    if perizia_pdf_file and perizia_pdf_file.filename:
        perizia_name = f"manual_perizia_{asta_id}.pdf"
        perizia_path = perizie_dir / perizia_name
        with open(perizia_path, "wb") as buffer:
            shutil.copyfileobj(perizia_pdf_file.file, buffer)
        updates["perizia_file_path"] = str(perizia_path.relative_to(PROJECT_ROOT))
        updates["perizia_status"] = "uploaded_manual"
        updates["perizia_error"] = None

    if avviso_pdf_file and avviso_pdf_file.filename:
        avviso_name = f"manual_avviso_{asta_id}.pdf"
        avviso_path = avvisi_dir / avviso_name
        with open(avviso_path, "wb") as buffer:
            shutil.copyfileobj(avviso_pdf_file.file, buffer)
        updates["avviso_file_path"] = str(avviso_path.relative_to(PROJECT_ROOT))
        updates["avviso_status"] = "uploaded_manual"
        updates["avviso_error"] = None

    if updates:
        update_asta_fields(asta_id, **updates)

    # Se c'è almeno la perizia, lancia subito l'analisi completa
    asta_after = get_asta(asta_id)
    if asta_after and getattr(asta_after, "perizia_file_path", None):
        try:
            analyze_perizia_for_asta(asta_id)
            rename_asta_documents_from_db(asta_id, get_asta, update_asta_fields)
            excel_output_path = PROJECT_ROOT / "data" / "export_aste.xlsx"
            build_excel_export(list_aste(limit=10000), output_path=excel_output_path)
        except Exception:
            pass

    return RedirectResponse(url=f"/aste/{asta_id}", status_code=303)


@router.get("/aste/{asta_id}/import-progress", response_class=HTMLResponse)
def import_progress_page(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        raise HTTPException(status_code=404, detail="Asta non trovata")

    html_content = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Importazione documenti asta #{asta_id}</title>
      </head>
      <body style="font-family:Arial,sans-serif;background:#f3f4f6;margin:0;padding:0;color:#111827;">
        <div style="max-width:780px;margin:60px auto;background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:32px;">
          <h1 style="margin-top:0;font-size:34px;">Importazione e analisi in corso</h1>
          <p style="color:#4b5563;font-size:18px;">Il software sta elaborando i documenti dell’asta #{asta_id}.</p>

          <div style="margin-top:28px;">
            <div style="height:24px;background:#e5e7eb;border-radius:999px;overflow:hidden;">
              <div id="progress-bar" style="height:24px;width:0%;background:#2563eb;transition:width 0.4s;"></div>
            </div>
            <div id="progress-text" style="margin-top:12px;font-size:16px;color:#374151;">0%</div>
          </div>

          <div style="margin-top:20px;padding:18px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;">
            <div style="font-size:14px;color:#6b7280;margin-bottom:8px;">Fase</div>
            <div id="step-text" style="font-size:18px;color:#111827;font-weight:600;">Preparazione...</div>
          </div>

          <div style="margin-top:20px;padding:18px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;">
            <div style="font-size:14px;color:#6b7280;margin-bottom:8px;">Stato lavorazione</div>
            <div id="message-text" style="font-size:18px;color:#111827;font-weight:600;">Preparazione...</div>
          </div>

          <div id="error-box" style="display:none;margin-top:20px;background:#fee2e2;border:1px solid #fecaca;border-radius:12px;padding:16px;color:#991b1b;"></div>

          <p style="margin-top:28px;color:#6b7280;">
            La pagina si aggiorna automaticamente. Al completamento verrai reindirizzato alla scheda asta.
          </p>

          <p style="margin-top:24px;">
            <a href="/aste/{asta_id}" style="color:#4f46e5;text-decoration:none;font-weight:600;">← Torna alla scheda asta</a>
          </p>
        </div>

        <script>
          let started = false;

          async function startJob() {{
            if (started) return;
            started = true;

            try {{
              await fetch("/aste/{asta_id}/start-import-recent-pdfs", {{
                method: "POST"
              }});
            }} catch (e) {{
              const box = document.getElementById("error-box");
              box.style.display = "block";
              box.innerText = "Errore nell'avvio della lavorazione.";
            }}
          }}

          async function refreshStatus() {{
            try {{
              const res = await fetch("/aste/{asta_id}/analysis-status");
              const data = await res.json();

              const progress = Number(data.progress || 0);
              const step = data.step || "working";
              const message = data.message || "Lavorazione in corso";
              const done = Boolean(data.done);
              const error = data.error || null;

              document.getElementById("progress-bar").style.width = progress + "%";
              document.getElementById("progress-text").innerText = progress + "%";
              document.getElementById("step-text").innerText = step;
              document.getElementById("message-text").innerText = message;

              if (error) {{
                const box = document.getElementById("error-box");
                box.style.display = "block";
                box.innerText = error;
              }}

              if (done && !error) {{
                window.location.href = "/aste/{asta_id}";
                return;
              }}
            }} catch (e) {{
              const box = document.getElementById("error-box");
              box.style.display = "block";
              box.innerText = "Errore nel recupero dello stato di avanzamento.";
            }}
          }}

          startJob();
          refreshStatus();
          setInterval(refreshStatus, 1000);
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/aste/{asta_id}/start-import-recent-pdfs")
def start_import_recent_pdfs_endpoint(asta_id: int):
    set_analysis_job(
        asta_id,
        progress=5,
        step="inizializzazione",
        message="Preparazione della lavorazione",
        done=False,
        error=None,
    )

    try:
        ok, message = import_recent_downloaded_pdfs_for_asta(
            asta_id=asta_id,
            get_asta=get_asta,
            update_asta_fields=update_asta_fields,
            minutes=3,
        )

        if not ok:
            set_analysis_job(
                asta_id,
                progress=100,
                step="errore",
                message="Importazione non riuscita",
                done=True,
                error=message,
            )
            return {"ok": False, "error": message}

        set_analysis_job(
            asta_id,
            progress=35,
            step="import_pdf",
            message=message,
            done=False,
            error=None,
        )

        set_analysis_job(
            asta_id,
            progress=70,
            step="analisi_perizia",
            message="Analisi documentale in corso",
            done=False,
            error=None,
        )
        analyze_perizia_for_asta(asta_id)

        rename_asta_documents_from_db(asta_id, get_asta, update_asta_fields)

        set_analysis_job(
            asta_id,
            progress=90,
            step="excel_export",
            message="Aggiornamento del file Excel",
            done=False,
            error=None,
        )

        excel_output_path = PROJECT_ROOT / "data" / "export_aste.xlsx"
        build_excel_export(list_aste(limit=10000), output_path=excel_output_path)

        set_analysis_job(
            asta_id,
            progress=100,
            step="completato",
            message="Analisi completata con successo",
            done=True,
            error=None,
        )
        return {"ok": True}

    except Exception as e:
        set_analysis_job(
            asta_id,
            progress=100,
            step="errore",
            message="Errore durante la lavorazione",
            done=True,
            error=str(e),
        )
        return {"ok": False, "error": str(e)}


@router.post("/aste/{asta_id}/import-recent-pdfs")
def import_recent_pdfs_endpoint(asta_id: int):
    ok, message = import_recent_downloaded_pdfs_for_asta(
        asta_id=asta_id,
        get_asta=get_asta,
        update_asta_fields=update_asta_fields,
        minutes=3,
    )

    if not ok:
        raise HTTPException(status_code=400, detail=message)

    return {"ok": True, "message": message}


@router.get("/aste/{asta_id}/debug-avviso", response_class=HTMLResponse)
def debug_avviso(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        return HTMLResponse("Asta non trovata", status_code=404)

    avviso_file_path = getattr(asta, "avviso_file_path", None)
    if not avviso_file_path:
        return HTMLResponse("Avviso non disponibile", status_code=404)

    full_path = _to_abs_path(avviso_file_path)
    if not full_path or not full_path.exists():
        return HTMLResponse(f"File avviso non trovato: {html.escape(str(full_path))}", status_code=404)

    try:
        text = extract_text_from_pdf(full_path) or ""
    except Exception as e:
        return HTMLResponse(f"Errore lettura avviso: {html.escape(str(e))}", status_code=500)

    escaped_text = html.escape(text[:30000])

    return HTMLResponse(
        f"""
        <html>
        <head><meta charset="utf-8"><title>Debug Avviso {asta_id}</title></head>
        <body style="font-family:Arial,sans-serif;padding:24px;">
            <h1>Debug avviso - Asta {asta_id}</h1>
            <p><strong>File:</strong> {html.escape(str(full_path))}</p>
            <p><a href="/aste/{asta_id}">← Torna alla scheda asta</a></p>
            <pre style="white-space:pre-wrap;background:#f5f5f5;padding:16px;border:1px solid #ddd;border-radius:8px;">{escaped_text}</pre>
        </body>
        </html>
        """
    )


@router.get("/aste/{asta_id}/debug-perizia", response_class=HTMLResponse)
def debug_perizia(asta_id: int):
    asta = get_asta(asta_id)
    if not asta:
        return HTMLResponse("Asta non trovata", status_code=404)

    perizia_file_path = getattr(asta, "perizia_file_path", None)
    if not perizia_file_path:
        return HTMLResponse("Perizia non disponibile", status_code=404)

    full_path = _to_abs_path(perizia_file_path)
    if not full_path or not full_path.exists():
        return HTMLResponse(f"File perizia non trovato: {html.escape(str(full_path))}", status_code=404)

    try:
        text = extract_text_from_pdf(full_path) or ""
    except Exception as e:
        return HTMLResponse(f"Errore lettura perizia: {html.escape(str(e))}", status_code=500)

    escaped_text = html.escape(text[:50000])

    return HTMLResponse(
        f"""
        <html>
        <head><meta charset="utf-8"><title>Debug Perizia {asta_id}</title></head>
        <body style="font-family:Arial,sans-serif;padding:24px;">
            <h1>Debug perizia - Asta {asta_id}</h1>
            <p><strong>File:</strong> {html.escape(str(full_path))}</p>
            <p><a href="/aste/{asta_id}">← Torna alla scheda asta</a></p>
            <pre style="white-space:pre-wrap;background:#f5f5f5;padding:16px;border:1px solid #ddd;border-radius:8px;">{escaped_text}</pre>
        </body>
        </html>
        """
    )