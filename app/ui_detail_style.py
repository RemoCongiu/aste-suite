from __future__ import annotations

DETAIL_STYLE = r"""
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
"""
