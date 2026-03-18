# Diagnosi tecnica approfondita – Aste Suite

## Scope analizzato
File prioritari analizzati:
- `app/main.py`
- `app/routes_aste.py`
- `app/routes_analysis.py`
- `app/services_documents.py`
- `app/pdf_text.py`
- `app/ocr_text.py`
- `app/ai_analyzer.py`
- `app/services_parsing.py`
- `app/services_pdf_classifier.py`
- `app/db.py`

Controlli aggiuntivi per flussi correlati:
- `app/extractor.py`
- `app/downloader.py`
- `app/routes_dashboard.py`

---

## 1) Lentezza analisi file

### Colli di bottiglia principali
1. **Lavorazione sincrona e lunga su endpoint HTTP**
   - `start_import_recent_pdfs_endpoint` esegue import PDF, classificazione, analisi, rinomina ed export Excel **nello stesso request cycle**.
   - Questo aumenta drasticamente il tempo di risposta e può far percepire il sistema come “bloccato”.

2. **Letture PDF ripetute più volte sugli stessi file**
   - Classificazione iniziale dei PDF recenti (`classify_recent_pdfs`) legge testo PDF per ogni candidato.
   - Subito dopo, i due PDF selezionati vengono di nuovo classificati/estratti (`classify_and_rename_pdf`).
   - Poi `analyze_perizia_for_asta` rilegge nuovamente avviso e perizia con fallback OCR.

3. **OCR costoso e fallback ripetuto**
   - OCR usa `pdf2image` + `pytesseract`, con conversione fino a `max_pages=12` e `dpi=220`.
   - In presenza di PDF “poor” o scannerizzati, l’OCR viene attivato in vari punti del flusso.

4. **Export Excel completo in coda a ogni analisi**
   - Dopo ogni import/analisi viene ricostruito l’Excel con `list_aste(limit=10000)` + `build_excel_export`.
   - Su dataset crescente, questa fase impatta in modo sensibile.

### Perché in alcuni casi sembra bloccarsi
- La pagina di progress polling aggiorna lo stato ogni secondo, ma la lavorazione server resta monolitica e CPU-heavy (OCR/parsing/export).
- Se l’ambiente gira con risorse limitate o pochi worker, le richieste concorrenti diventano lente.
- Le eccezioni in upload manuale sono silenziate (`except Exception: pass`), quindi lato utente può apparire comportamento incoerente/non deterministico.

### Parti più lente (ordine pratico)
1. OCR (`app/ocr_text.py`)
2. Letture/estrazioni PDF ripetute (`services_documents`, `routes_analysis`, `services_pdf_classifier`)
3. Export Excel completo post-analisi (`routes_aste`)
4. Parsing regex estensivo su testi lunghi (`services_parsing`, `routes_analysis`, `ai_analyzer` pre-selezione sezioni)

### Correzioni concrete suggerite (compatibili Windows)
- Introdurre **job queue locale** (anche semplice) per analisi asincrona; endpoint restituisce subito job id.
- Introdurre **cache per testo estratto** (hash file + mtime) per evitare tripla lettura.
- OCR:
  - ridurre `max_pages` iniziale (es. 6) + second pass solo se necessario;
  - valutare `dpi` dinamico (180/220).
- Evitare export full ad ogni analisi: batch periodico o export on-demand.
- Loggare tempi per fase (`extract`, `ocr`, `ai`, `merge`, `excel`) per benchmark oggettivo.

---

## 2) Errori nei dati estratti

### Cause probabili
1. **Moduli duplicati con definizioni duplicate e override non intenzionali**
   - In `services_parsing.py` ci sono funzioni duplicate (`normalize_money_string`, `normalize_date_string`, `extract_avviso_fields_from_text`, ecc.).
   - Le definizioni successive sovrascrivono le precedenti: comportamento difficile da prevedere.

2. **Parser duplicato tra file diversi**
   - Parser per perizia presente sia in `routes_analysis.py` (`_extract_structured_fields_from_perizia_text`) sia in `services_parsing.py` (`extract_structured_fields_from_perizia_text`).
   - Divergenze logiche aumentano incoerenze e bug.

3. **Fusione dati senza vera validazione conflitti**
   - Esiste una priorità fonti (pagina/db vs avviso vs perizia/AI), ma non una vera “cross-check matrix” con punteggio/confidenza.
   - In caso di mismatch forti (RGE, lotto, importi), il flusso tende a scegliere una fonte senza segnalazione strutturata.

4. **Normalizzazione denaro/data non unica**
   - Doppie implementazioni di `normalize_money_string` producono possibili formati diversi.

### Verifica cross-check attuale tra pagina asta / avviso / perizia
- **Parziale**: il flusso fonde i campi da più fonti in `analyze_perizia_for_asta`, ma non registra un controllo sistematico “OK / mismatch / missing” per campo.
- Non esiste una struttura persistita per audit dei conflitti tra le 3 fonti.

### Dati da confrontare sempre (obbligatori)
- tribunale
- RGE
- lotto
- prezzo base
- offerta minima
- indirizzo
- superficie
- occupazione
- data asta

### Sistema proposto di validazione/confronto
- Implementare `validate_sources(page, avviso, perizia_ai)` che ritorna:
  - `resolved_fields`
  - `conflicts[]`
  - `confidence_by_field`
  - `alerts[]`
- Regole minime:
  - **hard conflict**: RGE/lotto/tribunale diversi → `stato_pratica = "verifica_manuale"`.
  - **soft conflict**: importi discordanti oltre soglia (es. > 3%) → alert + campo “da confermare”.
  - **missing critical**: data asta o prezzo base assenti su tutte le fonti → alert bloccante.
- Persistenza:
  - aggiungere colonna JSON (es. `validation_report_json`) o tabella separata.
- UI:
  - evidenziare conflitti con badge e fonte scelta.

---

## 3) Utilizzo effettivo OpenAI

### Il progetto usa davvero OpenAI?
Sì. La chiamata API è implementata in `app/ai_analyzer.py` (`OpenAI`, `client.responses.create`) e richiamata in `app/routes_analysis.py` tramite `analyze_perizia_text(perizia_text)`.

### Dove è configurato/richiamato
- Configurazione:
  - `OPENAI_API_KEY` in `_client()`
  - `OPENAI_ASTE_MODEL` con default `gpt-4.1-mini`
- Richiamo:
  - `analyze_perizia_text` in `routes_analysis.py`

### Problemi a monte che degradano l’analisi AI
- Se estrazione testo è scarsa/rumorosa, AI riceve input di bassa qualità.
- `trimmed_text` è ritagliato euristicamente: buono per costo, ma può perdere contesto utile.
- Mancata tracciatura dell’input effettivo inviato (non viene salvato), quindi difficile fare debugging qualitativo.
- Campo DB `ai_model` esiste ma non viene valorizzato: audit incompleto.

### Correzioni concrete
- Salvare hash + anteprima testo inviato all’AI (`ai_input_excerpt`), rispettando limiti privacy.
- Salvare `ai_model` e tempi chiamata.
- In caso di OCR error o testo troppo corto, evitare chiamata AI e marcare causa esplicita.

---

## 4) Qualità insufficiente analisi testuale

### Perché urbanistica/abusi/pregiudizievoli/criticità legali risultano deboli
1. **Estrazione incompleta/sporca**
   - Sezione OCR limitata e dipendente da tool esterni presenti su Windows (`Tesseract`, `Poppler`): se assenti, ritorna errore e niente testo OCR.
2. **Prompt forte ma pipeline non robusta end-to-end**
   - Prompt è articolato, ma resa finale dipende dalla qualità del testo in ingresso e dai merge successivi.
3. **Parsing/merge post-AI non orientato alla qualità narrativa finale**
   - Vari campi vengono concatenati in blocchi; se input è rumoroso, output resta poco leggibile.
4. **Assenza di scoring di copertura sezioni critiche**
   - Non c’è un check “ho davvero trovato sezioni urbanistica/pregiudizievoli?” prima di generare commenti.

### Miglioramenti proposti (senza rifattorizzare tutto)
- Aggiungere `quality_gate` pre-AI:
  - lunghezza minima,
  - percentuale righe utili,
  - presenza keyword legali/urbanistiche.
- Prompt a 2 step leggeri:
  1) estrazione evidenze con citazioni testuali brevi;
  2) sintesi utente finale chiara.
- Parsing risposta AI con schema più restrittivo (validator).
- Rendering finale orientato all’utente:
  - “Rischi legali”, “Rischi urbanistici”, “Impatto economico”, “Azioni consigliate”.
- Inserire “assenza evidenze” esplicita (non confondere con assenza problemi).

---

## Funzioni/flussi inutilizzati o duplicati da segnalare

1. **Endpoint mancante rispetto alla UI**
- Dashboard posta su `/aste`, ma in `routes_aste.py` non esiste `@router.post("/aste")`.
- Rischio: feature “Nuova asta” non funzionante.

2. **Moduli apparentemente non usati**
- `app/downloader.py` e `app/extractor.py` non risultano richiamati dai router correnti.

3. **Duplicazioni ad alto rischio in `services_parsing.py`**
- Funzioni duplicate con override implicito.

4. **Campo DB non valorizzato**
- `ai_model` presente nel model ma non scritto nel flusso.

5. **Import probabilmente inutilizzato**
- `extract_text_from_pdf` importato in `routes_analysis.py` ma non usato.

---

## Piano di correzione incrementale consigliato (ordine)
1. **Stabilizzare parsing**: eliminare duplicati in `services_parsing.py` (prima causa di incoerenze).
2. **Cross-check strutturato**: introdurre validatore 3 fonti + report conflitti.
3. **Performance**: cache testo estratto + riduzione OCR ridondante.
4. **Trasparenza AI**: salvare modello usato, tempi, excerpt input.
5. **Qualità output**: quality gate + template finale leggibile per utente.

