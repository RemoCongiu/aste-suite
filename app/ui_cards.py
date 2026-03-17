import html

from fastapi.responses import HTMLResponse


def render_documenti_page(asta, message: str = "") -> HTMLResponse:
    def v(x):
        return x if x not in (None, "") else "-"

    perizia_status = asta.perizia_status or "-"
    avviso_status = getattr(asta, "avviso_status", None) or "-"
    perizia_error = asta.perizia_error or "-"
    avviso_error = getattr(asta, "avviso_error", None) or "-"

    perizia_link = (
        f'<a href="{asta.perizia_url}" target="_blank">{asta.perizia_url}</a>'
        if asta.perizia_url else "-"
    )
    avviso_link = (
        f'<a href="{asta.avviso_url}" target="_blank">{asta.avviso_url}</a>'
        if getattr(asta, "avviso_url", None) else "-"
    )

    current_tribunale = asta.tribunale or ""
    current_rge = asta.rge or ""
    current_lotto = asta.lotto or ""

    page_html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Documenti asta #{asta.id}</title>
      </head>
      <body style="font-family:Arial;margin:40px;max-width:1500px;">
        <h1>Documenti asta #{asta.id}</h1>
        <p>Questa pagina gestisce in un unico punto sia la perizia sia l’avviso di vendita.</p>

        {f'<div style="background:#fff8e1;border:1px solid #f0d98a;padding:14px;border-radius:8px;margin-bottom:22px;white-space:pre-wrap;">{html.escape(message)}</div>' if message else ''}

        <div style="background:#f8f8f8;border:1px solid #ddd;padding:20px;border-radius:10px;margin-bottom:24px;">
          <p><b>ID asta:</b> {asta.id}</p>
          <p><b>URL asta:</b> <a href="{asta.url}" target="_blank">{asta.url}</a></p>
          <p><b>Tribunale:</b> {v(asta.tribunale)}</p>
          <p><b>RGE:</b> {v(asta.rge)}</p>
          <p><b>Lotto:</b> {v(asta.lotto)}</p>
          <p><b>Data asta:</b> {v(asta.data_asta)}</p>
          <p><b>Città:</b> {v(asta.citta)}</p>
          <p><b>Indirizzo:</b> {v(asta.indirizzo)}</p>
          <p><b>Prezzo base:</b> {v(asta.prezzo_base)}</p>
          <p><b>Offerta minima:</b> {v(asta.offerta_minima)}</p>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;">
          <div style="border:1px solid #ddd;border-radius:10px;padding:20px;">
            <h2 style="margin-top:0;">Perizia</h2>
            <p><b>Stato:</b> {v(perizia_status)}</p>
            <p><b>Errore:</b> {v(perizia_error)}</p>
            <p><b>Link trovato online:</b> {perizia_link}</p>
            <p><b>File locale:</b> {v(asta.perizia_file_path)}</p>
            <p>
              <a href="/aste/{asta.id}/debug-perizia">debug perizia</a>
              {" | <a href='/aste/%d/analyze-perizia'>analizza perizia</a>" % asta.id if asta.perizia_file_path else ""}
            </p>
          </div>

          <div style="border:1px solid #ddd;border-radius:10px;padding:20px;">
            <h2 style="margin-top:0;">Avviso di vendita</h2>
            <p><b>Stato:</b> {v(avviso_status)}</p>
            <p><b>Errore:</b> {v(avviso_error)}</p>
            <p><b>Link trovato online:</b> {avviso_link}</p>
            <p><b>File locale:</b> {v(getattr(asta, "avviso_file_path", None))}</p>
            <p><a href="/aste/{asta.id}/debug-avviso">debug avviso</a></p>
          </div>
        </div>

        <div style="border:1px solid #ddd;border-radius:10px;padding:24px;">
          <h2 style="margin-top:0;">Caricamento manuale documenti</h2>
          <p style="color:#555;">
            In questa versione il flusso standard è manuale: carica perizia e avviso dal PC.
            I link trovati online restano visibili solo come riferimento.
          </p>

          <form method="post" action="/aste/{asta.id}/documenti" enctype="multipart/form-data">
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px;">
              <div>
                <label><b>Tribunale</b></label><br><br>
                <input type="text" name="tribunale_manual" value="{html.escape(current_tribunale)}" style="width:100%;padding:12px;font-size:14px;" />
              </div>
              <div>
                <label><b>RGE</b></label><br><br>
                <input type="text" name="rge_manual" value="{html.escape(current_rge)}" style="width:100%;padding:12px;font-size:14px;" />
              </div>
              <div>
                <label><b>Lotto</b></label><br><br>
                <input type="text" name="lotto_manual" value="{html.escape(current_lotto)}" style="width:100%;padding:12px;font-size:14px;" />
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">
              <div style="border:1px solid #eee;border-radius:10px;padding:20px;">
                <h3 style="margin-top:0;">Perizia</h3>
                <label><b>Carica PDF perizia</b></label><br><br>
                <input type="file" name="perizia_pdf_file" accept="application/pdf,.pdf" style="width:100%;padding:12px;font-size:14px;" />
              </div>

              <div style="border:1px solid #eee;border-radius:10px;padding:20px;">
                <h3 style="margin-top:0;">Avviso di vendita</h3>
                <label><b>Carica PDF avviso</b></label><br><br>
                <input type="file" name="avviso_pdf_file" accept="application/pdf,.pdf" style="width:100%;padding:12px;font-size:14px;" />
              </div>
            </div>

            <br>
            <button type="submit" style="padding:12px 20px;font-size:15px;cursor:pointer;">
              Salva documenti e analizza
            </button>
          </form>

          <form method="get" action="/aste/{asta.id}/import-progress" style="margin-top:20px;">
            <button type="submit" style="padding:12px 20px;font-size:15px;cursor:pointer;background:#2c7be5;color:white;border:none;border-radius:6px;">
              Importa ultimi 2 PDF da Download
            </button>
          </form>

          <div style="margin-top:30px;">
            <h3 style="margin-bottom:10px;">Stato analisi</h3>
            <div style="background:#eee;border-radius:6px;height:24px;width:100%;overflow:hidden;">
              <div id="progressbar" style="background:#2c7be5;height:24px;width:0%;transition:width 0.4s;color:white;text-align:center;line-height:24px;font-size:12px;">
                0%
              </div>
            </div>
            <p id="progress-text" style="margin-top:8px;color:#444;">In attesa...</p>
          </div>
        </div>

        <p style="margin-top:24px;">
          <a href="/">Torna alla dashboard</a>
        </p>

        <script>
        function updateProgress() {{
            fetch("/aste/{asta.id}/analysis-status")
              .then(r => r.json())
              .then(data => {{
                  const bar = document.getElementById("progressbar");
                  const txt = document.getElementById("progress-text");

                  if (!bar || !txt) return;

                  bar.style.width = data.progress + "%";
                  bar.innerText = data.progress + "%";
                  txt.innerText = data.message || "In attesa...";

                  if (!data.done) {{
                      setTimeout(updateProgress, 1000);
                  }}
              }})
              .catch(() => {{
                  const txt = document.getElementById("progress-text");
                  if (txt) txt.innerText = "Errore nel recupero stato analisi";
              }});
        }}

        updateProgress();
        </script>
      </body>
    </html>
    """

    return HTMLResponse(page_html)