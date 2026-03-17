from __future__ import annotations

import html


def _v(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _e(value) -> str:
    return html.escape(_v(value))


def _ta(value) -> str:
    return html.escape(_v(value))


def _render_text(value, empty: str = "Non disponibile") -> str:
    text = _v(value)
    if not text:
        return f'<span class="empty">{html.escape(empty)}</span>'
    return html.escape(text).replace("\n", "<br>")


def _severity_class(text: str) -> str:
    t = _v(text).lower()

    high_terms = [
        "abuso",
        "abusi",
        "difform",
        "non sanabile",
        "ordine di demolizione",
        "occupato",
        "ipoteca",
        "ipoteche",
        "pignoramento",
        "pignoramenti",
        "vincolo",
        "vincoli",
        "pregiudizievole",
        "pregiudizievoli",
        "trascrizione",
        "trascrizioni",
        "iscrizione",
        "iscrizioni",
        "gravame",
        "gravami",
        "debiti condominiali",
    ]

    medium_terms = [
        "sanatoria",
        "sanabile",
        "regolarizzazione",
        "regolarizzare",
        "conformità catastale",
        "conformità urbanistica",
        "verifica",
        "da verificare",
        "criticità",
        "attenzione",
    ]

    if any(x in t for x in high_terms):
        return "danger"
    if any(x in t for x in medium_terms):
        return "warning"
    return "soft"


def _hero_value(value) -> str:
    v = _v(value)
    return html.escape(v) if v else "-"


def render_asta_detail(asta) -> str:
    tribunale = _e(asta.tribunale) or "Tribunale di ..."
    titolo = tribunale

    abusi_class = _severity_class(_v(asta.abusi))
    preg_class = _severity_class(_v(asta.pregiudizievoli))
    note_op_class = _severity_class(_v(asta.note_operativi))

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>{titolo}</title>
        <style>
          :root {{
            --bg: #f3f6fb;
            --card: #ffffff;
            --line: #d9e2ef;
            --text: #102033;
            --muted: #64748b;
            --primary: #173b78;
            --primary-2: #214d9c;
            --primary-3: #0f2f63;

            --soft-bg: #eef4fb;
            --soft-line: #d9e5f3;

            --danger-bg: #fff2f2;
            --danger-line: #f2c8c8;
            --danger-title: #8a1f1f;

            --warn-bg: #fff8ee;
            --warn-line: #efd7ad;
            --warn-title: #8a5816;

            --shadow: 0 12px 30px rgba(16, 32, 51, 0.06);
            --radius-xl: 24px;
            --radius-lg: 20px;
            --radius-md: 16px;
          }}

          * {{
            box-sizing: border-box;
          }}

          body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background:
              radial-gradient(circle at top left, rgba(33,77,156,0.10), transparent 25%),
              radial-gradient(circle at top right, rgba(23,59,120,0.08), transparent 20%),
              var(--bg);
            color: var(--text);
          }}

          .wrap {{
            max-width: 1540px;
            margin: 0 auto;
            padding: 26px;
          }}

          .hero {{
            background: linear-gradient(135deg, #102a5c 0%, #183f85 100%);
            color: white;
            border-radius: 28px;
            padding: 32px;
            margin-bottom: 22px;
            box-shadow: 0 16px 34px rgba(16,42,92,0.18);
          }}

          .hero-top {{
            display: flex;
            justify-content: space-between;
            gap: 20px;
            align-items: flex-start;
            flex-wrap: wrap;
          }}

          .hero h1 {{
            margin: 0;
            font-size: 40px;
            line-height: 1.08;
            letter-spacing: -0.02em;
          }}

          .hero .sub {{
            margin-top: 10px;
            font-size: 15px;
            color: rgba(255,255,255,0.86);
          }}

          .hero-actions {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
          }}

          .btn {{
            display: inline-block;
            text-decoration: none;
            padding: 11px 15px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 14px;
            border: 1px solid transparent;
          }}

          .btn-light {{
            background: white;
            color: var(--primary);
          }}

          .btn-outline {{
            background: rgba(255,255,255,0.08);
            color: white;
            border-color: rgba(255,255,255,0.20);
          }}

          .hero-kpis {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-top: 24px;
          }}

          .hero-kpi {{
            background: rgba(255,255,255,0.11);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 18px;
            padding: 16px;
            backdrop-filter: blur(5px);
          }}

          .hero-kpi .label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: rgba(255,255,255,0.74);
            margin-bottom: 8px;
          }}

          .hero-kpi .value {{
            font-size: 24px;
            font-weight: 800;
            line-height: 1.2;
          }}

          .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
          }}

          .grid-3 {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
          }}

          .grid-main {{
            display: grid;
            grid-template-columns: 0.95fr 1.05fr;
            gap: 20px;
            margin-bottom: 20px;
          }}

          .card {{
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: var(--radius-lg);
            padding: 22px;
            box-shadow: var(--shadow);
          }}

          .card h2 {{
            margin: 0 0 16px 0;
            font-size: 24px;
            letter-spacing: -0.01em;
          }}

          .kv {{
            display: grid;
            grid-template-columns: 220px 1fr;
            gap: 12px 14px;
          }}

          .kv .label {{
            color: var(--muted);
            font-weight: 700;
          }}

          .panel {{
            border-radius: 18px;
            padding: 20px;
            min-height: 240px;
            border: 1px solid;
          }}

          .panel.danger {{
            background: var(--danger-bg);
            border-color: var(--danger-line);
          }}

          .panel.warning {{
            background: var(--warn-bg);
            border-color: var(--warn-line);
          }}

          .panel.soft {{
            background: var(--soft-bg);
            border-color: var(--soft-line);
          }}

          .panel .title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: .06em;
            font-weight: 800;
            margin-bottom: 12px;
          }}

          .panel.danger .title {{
            color: var(--danger-title);
          }}

          .panel.warning .title {{
            color: var(--warn-title);
          }}

          .panel.soft .title {{
            color: #2b4b74;
          }}

          .text {{
            line-height: 1.72;
            font-size: 15px;
            white-space: normal;
          }}

          .text strong {{
            color: var(--primary-3);
          }}

          .empty {{
            color: var(--muted);
            font-style: italic;
          }}

          .section-note {{
            color: var(--muted);
            font-size: 14px;
            margin-top: -6px;
            margin-bottom: 14px;
          }}

          .form-card {{
            background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
          }}

          form label {{
            display: block;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 6px;
            color: #39506a;
          }}

          input[type="text"],
          textarea {{
            width: 100%;
            border: 1px solid #cad6e4;
            border-radius: 12px;
            padding: 11px 12px;
            font-size: 14px;
            background: white;
            color: var(--text);
          }}

          textarea {{
            min-height: 140px;
            resize: vertical;
            line-height: 1.6;
          }}

          .form-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
          }}

          .full {{
            grid-column: 1 / -1;
          }}

          .save-row {{
            margin-top: 18px;
            display: flex;
            justify-content: flex-end;
          }}

          .save-btn {{
            background: linear-gradient(135deg, var(--primary-2) 0%, var(--primary) 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 8px 18px rgba(33,77,156,0.22);
          }}

          .highlight {{
            display: inline-block;
            padding: 7px 12px;
            border-radius: 999px;
            background: #e8f0fd;
            color: var(--primary);
            font-size: 13px;
            font-weight: 800;
          }}

          @media (max-width: 1200px) {{
            .hero-kpis,
            .grid-main,
            .grid-2,
            .grid-3,
            .form-grid {{
              grid-template-columns: 1fr 1fr;
            }}
          }}

          @media (max-width: 820px) {{
            .hero-kpis,
            .grid-main,
            .grid-2,
            .grid-3,
            .form-grid {{
              grid-template-columns: 1fr;
            }}

            .kv {{
              grid-template-columns: 1fr;
            }}

            .hero h1 {{
              font-size: 30px;
            }}
          }}
        </style>
      </head>

      <body>
        <div class="wrap">

          <div class="hero">
            <div class="hero-top">
              <div>
                <h1>{tribunale}</h1>
                <div class="sub">
                  RGE <b>{_e(asta.rge) or "-"}</b> · Lotto <b>{_e(asta.lotto) or "-"}</b> · Data asta <b>{_e(asta.data_asta) or "-"}</b>
                </div>
                <div class="sub">
                  {_e(asta.citta) or "-"} · {_e(asta.indirizzo) or "-"}
                </div>
              </div>

              <div class="hero-actions">
                <a class="btn btn-light" href="/">Dashboard</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/documenti">Documenti</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-perizia">Debug perizia</a>
                <a class="btn btn-outline" href="/aste/{asta.id}/debug-avviso">Debug avviso</a>
              </div>
            </div>

            <div class="hero-kpis">
              <div class="hero-kpi">
                <div class="label">Valore di perizia</div>
                <div class="value">{_hero_value(asta.valore_perizia)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Prezzo base</div>
                <div class="value">{_hero_value(asta.prezzo_base)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Offerta minima</div>
                <div class="value">{_hero_value(asta.offerta_minima)}</div>
              </div>
              <div class="hero-kpi">
                <div class="label">Rilancio minimo</div>
                <div class="value">{_hero_value(asta.rilancio_minimo)}</div>
              </div>
            </div>
          </div>

          <div class="grid-main">
            <div class="card">
              <h2>Dati principali</h2>
              <div class="kv">
                <div class="label">Tribunale</div><div>{_e(asta.tribunale) or "-"}</div>
                <div class="label">RGE</div><div>{_e(asta.rge) or "-"}</div>
                <div class="label">Lotto</div><div>{_e(asta.lotto) or "-"}</div>
                <div class="label">Data asta</div><div>{_e(asta.data_asta) or "-"}</div>
                <div class="label">Città</div><div>{_e(asta.citta) or "-"}</div>
                <div class="label">Indirizzo</div><div>{_e(asta.indirizzo) or "-"}</div>
                <div class="label">Valore di perizia</div><div><span class="highlight">{_e(asta.valore_perizia) or "-"}</span></div>
                <div class="label">Prezzo base</div><div><span class="highlight">{_e(asta.prezzo_base) or "-"}</span></div>
                <div class="label">Offerta minima</div><div><span class="highlight">{_e(asta.offerta_minima) or "-"}</span></div>
                <div class="label">Rilancio minimo</div><div><span class="highlight">{_e(asta.rilancio_minimo) or "-"}</span></div>
                <div class="label">Occupazione</div><div>{_render_text(asta.occupazione)}</div>
                <div class="label">Creditore procedente</div><div>{_e(asta.creditore_procedente) or "-"}</div>
                <div class="label">Proprietario</div><div>{_e(asta.proprietario) or "-"}</div>
              </div>
            </div>

            <div class="card">
              <h2>Dati catastali</h2>
              <div class="section-note">
                Testo pulito dei riferimenti catastali utili alla valutazione del bene.
              </div>
              <div class="kv">
                <div class="label">Catasto</div><div>{_e(asta.catasto) or "-"}</div>
                <div class="label">Foglio</div><div>{_e(asta.foglio) or "-"}</div>
                <div class="label">Mappale / Particella</div><div>{_e(asta.mappale) or "-"}</div>
                <div class="label">Subalterno</div><div>{_e(asta.subalterno) or "-"}</div>
                <div class="label">Categoria catastale</div><div>{_e(asta.categoria_catastale) or "-"}</div>
              </div>
            </div>
          </div>

          <div class="card">
            <h2>Descrizione immobile</h2>
            <div class="section-note">
              Descrizione accurata del bene emersa da perizia, avviso e analisi.
            </div>
            <div class="text">{_render_text(asta.descrizione_immobile)}</div>
          </div>

          <div class="grid-3" style="margin-top:20px;">
            <div class="panel {preg_class}">
              <div class="title">Pregiudizievoli</div>
              <div class="text">{_render_text(asta.pregiudizievoli)}</div>
            </div>

            <div class="panel {abusi_class}">
              <div class="title">Abusi / Urbanistica</div>
              <div class="text">{_render_text(asta.abusi)}</div>
            </div>

            <div class="panel {note_op_class}">
              <div class="title">Note operative</div>
              <div class="text">{_render_text(asta.note_operativi)}</div>
            </div>
          </div>

          <div class="grid-2">
            <div class="card">
              <h2>Sintesi</h2>
              <div class="text">{_render_text(asta.sintesi)}</div>
            </div>

            <div class="card">
              <h2>Note</h2>
              <div class="text">{_render_text(asta.note)}</div>
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
                  <input type="text" name="tribunale" value="{_e(asta.tribunale)}">
                </div>

                <div>
                  <label>RGE</label>
                  <input type="text" name="rge" value="{_e(asta.rge)}">
                </div>

                <div>
                  <label>Lotto</label>
                  <input type="text" name="lotto" value="{_e(asta.lotto)}">
                </div>

                <div>
                  <label>Data asta</label>
                  <input type="text" name="data_asta" value="{_e(asta.data_asta)}">
                </div>

                <div>
                  <label>Città</label>
                  <input type="text" name="citta" value="{_e(asta.citta)}">
                </div>

                <div>
                  <label>Indirizzo</label>
                  <input type="text" name="indirizzo" value="{_e(asta.indirizzo)}">
                </div>

                <div>
                  <label>Valore di perizia</label>
                  <input type="text" name="valore_perizia" value="{_e(asta.valore_perizia)}">
                </div>

                <div>
                  <label>Prezzo base</label>
                  <input type="text" name="prezzo_base" value="{_e(asta.prezzo_base)}">
                </div>

                <div>
                  <label>Offerta minima</label>
                  <input type="text" name="offerta_minima" value="{_e(asta.offerta_minima)}">
                </div>

                <div>
                  <label>Rilancio minimo</label>
                  <input type="text" name="rilancio_minimo" value="{_e(asta.rilancio_minimo)}">
                </div>

                <div>
                  <label>Occupazione</label>
                  <input type="text" name="occupazione" value="{_e(asta.occupazione)}">
                </div>

                <div>
                  <label>Catasto</label>
                  <input type="text" name="catasto" value="{_e(asta.catasto)}">
                </div>

                <div>
                  <label>Foglio</label>
                  <input type="text" name="foglio" value="{_e(asta.foglio)}">
                </div>

                <div>
                  <label>Mappale / Particella</label>
                  <input type="text" name="mappale" value="{_e(asta.mappale)}">
                </div>

                <div>
                  <label>Subalterno</label>
                  <input type="text" name="subalterno" value="{_e(asta.subalterno)}">
                </div>

                <div>
                  <label>Categoria catastale</label>
                  <input type="text" name="categoria_catastale" value="{_e(asta.categoria_catastale)}">
                </div>

                <div>
                  <label>Proprietario</label>
                  <input type="text" name="proprietario" value="{_e(asta.proprietario)}">
                </div>

                <div class="full">
                  <label>Descrizione immobile</label>
                  <textarea name="descrizione_immobile">{_ta(asta.descrizione_immobile)}</textarea>
                </div>

                <div class="full">
                  <label>Pregiudizievoli</label>
                  <textarea name="pregiudizievoli">{_ta(asta.pregiudizievoli)}</textarea>
                </div>

                <div class="full">
                  <label>Abusi / Urbanistica</label>
                  <textarea name="abusi">{_ta(asta.abusi)}</textarea>
                </div>

                <div class="full">
                  <label>Note</label>
                  <textarea name="note">{_ta(asta.note)}</textarea>
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