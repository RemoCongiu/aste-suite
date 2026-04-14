from __future__ import annotations

from app.ui_detail_helpers import e, hero_value, render_text, severity_class, ta, v
from app.ui_detail_style import DETAIL_STYLE


def render_asta_detail(asta) -> str:
    tribunale = e(asta.tribunale) or "Tribunale di ..."
    titolo = tribunale

    abusi_class = severity_class(v(asta.abusi))
    preg_class = severity_class(v(asta.pregiudizievoli))
    note_op_class = severity_class(v(asta.note_operativi))

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>{titolo}</title>
        <style>
{DETAIL_STYLE}
        </style>
      </head>

      <body>
        <div class="wrap">

          <div class="hero">
            <div class="hero-top">
              <div>
                <h1>{tribunale}</h1>
                <div class="sub">
                  RGE <b>{e(asta.rge) or "-"}</b> · Lotto <b>{e(asta.lotto) or "-"}</b> · Data asta <b>{e(asta.data_asta) or "-"}</b>
                </div>
                <div class="sub">
                  {e(asta.citta) or "-"} · {e(asta.indirizzo) or "-"}
                </div>
              </div>

              <div class="hero-actions">
                <a class="btn btn-light" href="/">Dashboard</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/documenti">Documenti</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/export-scheda.pdf">Scarica scheda PDF</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-perizia">Debug perizia</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-avviso">Debug avviso</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-perizia.txt">Scarica debug perizia TXT</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-avviso.txt">Scarica debug avviso TXT</a>
              </div>
            </div>

            <div class="hero-kpis">
              <div class="hero-kpi">
                <div class="label">Valore di perizia</div>
                <div class="value">{hero_value(asta.valore_perizia)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Prezzo base</div>
                <div class="value">{hero_value(asta.prezzo_base)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Offerta minima</div>
                <div class="value">{hero_value(asta.offerta_minima)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Rilancio minimo</div>
                <div class="value">{hero_value(asta.rilancio_minimo)}</div>
              </div>
            </div>
          </div>

          <div class="grid-main">
            <div class="card">
              <h2>Dati principali</h2>
              <div class="kv">
                <div class="label">Tribunale</div><div>{e(asta.tribunale) or "-"}</div>
                <div class="label">RGE</div><div>{e(asta.rge) or "-"}</div>
                <div class="label">Lotto</div><div>{e(asta.lotto) or "-"}</div>
                <div class="label">Data asta</div><div>{e(asta.data_asta) or "-"}</div>
                <div class="label">Città</div><div>{e(asta.citta) or "-"}</div>
                <div class="label">Indirizzo</div><div>{e(asta.indirizzo) or "-"}</div>
                <div class="label">Valore di perizia</div><div><span class="highlight">{e(asta.valore_perizia) or "-"}</span></div>
                <div class="label">Prezzo base</div><div><span class="highlight">{e(asta.prezzo_base) or "-"}</span></div>
                <div class="label">Offerta minima</div><div><span class="highlight">{e(asta.offerta_minima) or "-"}</span></div>
                <div class="label">Rilancio minimo</div><div><span class="highlight">{e(asta.rilancio_minimo) or "-"}</span></div>
                <div class="label">Occupazione</div><div>{render_text(asta.occupazione)}</div>
                <div class="label">Creditore procedente</div><div>{e(asta.creditore_procedente) or "-"}</div>
                <div class="label">Proprietario</div><div>{e(asta.proprietario) or "-"}</div>
              </div>
            </div>

            <div class="card">
              <h2>Dati catastali</h2>
              <div class="section-note">
                Testo pulito dei riferimenti catastali utili alla valutazione del bene.
              </div>
              <div class="kv">
                <div class="label">Catasto</div><div>{e(asta.catasto) or "-"}</div>
                <div class="label">Foglio</div><div>{e(asta.foglio) or "-"}</div>
                <div class="label">Mappale / Particella</div><div>{e(asta.mappale) or "-"}</div>
                <div class="label">Subalterno</div><div>{e(asta.subalterno) or "-"}</div>
                <div class="label">Categoria catastale</div><div>{e(asta.categoria_catastale) or "-"}</div>
              </div>
            </div>
          </div>

          <div class="card">
            <h2>Descrizione immobile</h2>
            <div class="section-note">
              Descrizione accurata del bene emersa da perizia, avviso e analisi.
            </div>
            <div class="text">{render_text(asta.descrizione_immobile)}</div>
          </div>

          <div class="grid-3" style="margin-top:20px;">
            <div class="panel {preg_class}">
              <div class="title">Pregiudizievoli</div>
              <div class="text">{render_text(asta.pregiudizievoli)}</div>
            </div>

            <div class="panel {abusi_class}">
              <div class="title">Abusi / Urbanistica</div>
              <div class="text">{render_text(asta.abusi)}</div>
            </div>

            <div class="panel {note_op_class}">
              <div class="title">Note operative</div>
              <div class="text">{render_text(asta.note_operativi)}</div>
            </div>
          </div>

          <div class="grid-2">
            <div class="card">
              <h2>Sintesi</h2>
              <div class="text">{render_text(asta.sintesi)}</div>
            </div>

            <div class="card">
              <h2>Note</h2>
              <div class="text">{render_text(asta.note)}</div>
            </div>
          </div>

          <div class="card form-card">
            <h2>Modifica scheda</h2>
            <div class="section-note">
              Puoi correggere i dati estratti, completare i campi mancanti e salvare la scheda.
            </div>

            <form method="post" action="/aste/{asta.id}/salva-scheda">
              <div class="form-grid">

                <div>
                  <label>Tribunale</label>
                  <input type="text" name="tribunale" value="{e(asta.tribunale)}">
                </div>

                <div>
                  <label>RGE</label>
                  <input type="text" name="rge" value="{e(asta.rge)}">
                </div>

                <div>
                  <label>Lotto</label>
                  <input type="text" name="lotto" value="{e(asta.lotto)}">
                </div>

                <div>
                  <label>Data asta</label>
                  <input type="text" name="data_asta" value="{e(asta.data_asta)}">
                </div>

                <div>
                  <label>Città</label>
                  <input type="text" name="citta" value="{e(asta.citta)}">
                </div>

                <div>
                  <label>Indirizzo</label>
                  <input type="text" name="indirizzo" value="{e(asta.indirizzo)}">
                </div>

                <div>
                  <label>Valore di perizia</label>
                  <input type="text" name="valore_perizia" value="{e(asta.valore_perizia)}">
                </div>

                <div>
                  <label>Prezzo base</label>
                  <input type="text" name="prezzo_base" value="{e(asta.prezzo_base)}">
                </div>

                <div>
                  <label>Offerta minima</label>
                  <input type="text" name="offerta_minima" value="{e(asta.offerta_minima)}">
                </div>

                <div>
                  <label>Rilancio minimo</label>
                  <input type="text" name="rilancio_minimo" value="{e(asta.rilancio_minimo)}">
                </div>

                <div>
                  <label>Occupazione</label>
                  <input type="text" name="occupazione" value="{e(asta.occupazione)}">
                </div>

                <div>
                  <label>Catasto</label>
                  <input type="text" name="catasto" value="{e(asta.catasto)}">
                </div>

                <div>
                  <label>Foglio</label>
                  <input type="text" name="foglio" value="{e(asta.foglio)}">
                </div>

                <div>
                  <label>Mappale / Particella</label>
                  <input type="text" name="mappale" value="{e(asta.mappale)}">
                </div>

                <div>
                  <label>Subalterno</label>
                  <input type="text" name="subalterno" value="{e(asta.subalterno)}">
                </div>

                <div>
                  <label>Categoria catastale</label>
                  <input type="text" name="categoria_catastale" value="{e(asta.categoria_catastale)}">
                </div>

                <div>
                  <label>Proprietario</label>
                  <input type="text" name="proprietario" value="{e(asta.proprietario)}">
                </div>

                <div class="full">
                  <label>Descrizione immobile</label>
                  <textarea name="descrizione_immobile">{ta(asta.descrizione_immobile)}</textarea>
                </div>

                <div class="full">
                  <label>Pregiudizievoli</label>
                  <textarea name="pregiudizievoli">{ta(asta.pregiudizievoli)}</textarea>
                </div>

                <div class="full">
                  <label>Abusi / Urbanistica</label>
                  <textarea name="abusi">{ta(asta.abusi)}</textarea>
                </div>

                <div class="full">
                  <label>Note</label>
                  <textarea name="note">{ta(asta.note)}</textarea>
                </div>

              </div>

              <div class="save-row">
                <button class="save-btn" type="submit">Salva scheda</button>
              </div>
            </form>
          </div>

        </div>
      </body>
    </html>
    """
