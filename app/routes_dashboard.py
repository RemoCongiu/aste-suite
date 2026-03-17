from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

from app.db import list_aste
from app.excel_export import build_excel_export


router = APIRouter()


def get_operational_status(asta) -> str:
    if asta.ai_status == "done":
        return "Analisi completata"
    if asta.ai_status == "empty_text":
        return "Testo PDF non estratto"
    if asta.ai_status == "error":
        return "Errore AI"

    perizia_ok = bool(asta.perizia_file_path)
    avviso_ok = bool(getattr(asta, "avviso_file_path", None))

    if perizia_ok and avviso_ok:
        return "Documenti caricati"
    if perizia_ok and not avviso_ok:
        return "Manca avviso"
    if not perizia_ok and avviso_ok:
        return "Manca perizia"
    return "Inserita"


@router.get("/", response_class=HTMLResponse)
def dashboard():
    aste = list_aste(limit=200)

    rows = []
    for asta in aste:
        stato = get_operational_status(asta)
        perizia_flag = "✅" if asta.perizia_file_path else "❌"
        avviso_flag = "✅" if getattr(asta, "avviso_file_path", None) else "❌"

        rows.append(f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.id}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;"><a href="{asta.url}" target="_blank">link</a></td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.tribunale or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.rge or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.lotto or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.data_asta or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.prezzo_base or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{asta.offerta_minima or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{perizia_flag}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{avviso_flag}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{stato}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap;">
            <a href="/aste/{asta.id}">scheda</a> |
            <a href="/aste/{asta.id}/documenti">documenti</a> |
            <a href="/aste/{asta.id}/debug-avviso">debug avviso</a> |
            <a href="/aste/{asta.id}/debug-perizia">debug perizia</a>
          </td>
        </tr>
        """)

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Aste Suite Local</title>
      </head>
      <body style="font-family:Arial;margin:40px;max-width:1500px;">
        <h1>Aste Suite (locale)</h1>

        <div style="margin-bottom:28px;border:1px solid #ddd;border-radius:10px;padding:20px;">
          <h2 style="margin-top:0;">Nuova asta</h2>
          <form method="post" action="/aste">
            <input type="url" name="url" placeholder="Incolla URL asta" style="width:70%;padding:12px;font-size:14px;" required />
            <button type="submit" style="padding:12px 18px;font-size:14px;">Inserisci asta</button>
          </form>
          <p style="margin-top:10px;color:#666;">
            Estrae i dati principali dalla pagina. Perizia e avviso vanno poi caricati manualmente.
          </p>
        </div>

        <div style="margin-bottom:28px;">
          <a href="/export.xlsx">Esporta Excel</a>
        </div>

        <table style="border-collapse:collapse;width:100%;font-size:14px;">
          <thead>
            <tr style="background:#f5f5f5;">
              <th style="padding:8px;text-align:left;">ID</th>
              <th style="padding:8px;text-align:left;">URL</th>
              <th style="padding:8px;text-align:left;">Tribunale</th>
              <th style="padding:8px;text-align:left;">RGE</th>
              <th style="padding:8px;text-align:left;">Lotto</th>
              <th style="padding:8px;text-align:left;">Data asta</th>
              <th style="padding:8px;text-align:left;">Prezzo base</th>
              <th style="padding:8px;text-align:left;">Offerta minima</th>
              <th style="padding:8px;text-align:center;">Perizia</th>
              <th style="padding:8px;text-align:center;">Avviso</th>
              <th style="padding:8px;text-align:left;">Stato</th>
              <th style="padding:8px;text-align:left;">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows) if rows else '<tr><td colspan="12" style="padding:16px;">Nessuna asta presente</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """


@router.get("/export.xlsx")
def export_excel():
    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "data" / "export_aste.xlsx"
    build_excel_export(list_aste(limit=10000), output_path=output_path)
    return FileResponse(output_path, filename="export_aste.xlsx")