# Checklist test manuali locali – verifica modifiche recenti

Questa checklist serve a validare localmente le modifiche introdotte su:
- import PDF da Download
- analisi asincrona con job status
- fallback OCR
- warning di validazione incrociata tra fonti
- qualità dell'output AI su urbanistica, abusi e pregiudizievoli

> Nota: i test sono pensati per ambiente locale Windows-compatibile, coerente con il progetto.

---

## 1) Import ultimi PDF da Download

### Test 1.1 – Import automatico con 2 PDF validi recenti
**Azione da fare**
1. Avvia il progetto localmente.
2. Apri una scheda asta esistente con ID noto.
3. Scarica nella cartella `Downloads` un PDF di perizia e un PDF di avviso negli ultimi 3 minuti.
4. Apri `/aste/<asta_id>/import-progress`.
5. Verifica che parta la chiamata a `POST /aste/<asta_id>/start-import-recent-pdfs`.
6. Attendi il completamento.

**Risultato atteso**
- La pagina mostra avanzamento progressivo.
- I due PDF vengono importati nel progetto.
- I campi `perizia_file_path` e `avviso_file_path` risultano valorizzati.
- Lo stato finale del job risulta completato senza errori.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/services_documents.py`
- `app/routes_analysis.py`

### Test 1.2 – Import automatico con meno di 2 PDF disponibili
**Azione da fare**
1. Assicurati che in `Downloads` ci sia solo un PDF recente o nessuno.
2. Apri `/aste/<asta_id>/import-progress`.
3. Attendi l'esito del job.

**Risultato atteso**
- Il job termina in errore controllato.
- `analysis_status` mostra `step="errore"`.
- Il messaggio segnala che sono stati trovati meno di 2 PDF utili.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/services_documents.py`

### Test 1.3 – Import automatico con asta inesistente
**Azione da fare**
1. Esegui `POST /aste/999999/start-import-recent-pdfs` con un ID non presente.

**Risultato atteso**
- Risposta HTTP 404.
- Nessun job avviato.

**File/moduli coinvolti**
- `app/routes_aste.py`

---

## 2) Analisi asincrona

### Test 2.1 – Analisi manuale asincrona dopo upload perizia
**Azione da fare**
1. Apri `/aste/<asta_id>/documenti`.
2. Carica manualmente almeno una perizia PDF valida.
3. Salva il form.
4. Controlla subito `/aste/<asta_id>/analysis-status`.

**Risultato atteso**
- La richiesta di upload ritorna rapidamente senza attendere tutta l'analisi.
- Il job passa per stati tipo `queued`, `analisi_perizia`, `excel_export`, `completato`.
- La UI non resta bloccata durante OCR/AI/export.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/routes_analysis.py`

### Test 2.2 – Avvio analisi con endpoint dedicato
**Azione da fare**
1. Assicurati che l'asta abbia già `perizia_file_path` valorizzato.
2. Esegui `POST /aste/<asta_id>/start-analysis`.
3. Interroga periodicamente `GET /aste/<asta_id>/analysis-status`.

**Risultato atteso**
- L'endpoint risponde subito con conferma di accodamento.
- `analysis_status` si aggiorna durante la lavorazione.
- A fine analisi compare `done=true`.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/routes_analysis.py`

### Test 2.3 – Avvio analisi senza perizia
**Azione da fare**
1. Usa un'asta senza `perizia_file_path`.
2. Esegui `POST /aste/<asta_id>/start-analysis`.

**Risultato atteso**
- Risposta HTTP 400.
- Messaggio esplicito: impossibile analizzare senza perizia.

**File/moduli coinvolti**
- `app/routes_aste.py`

---

## 3) Fallback OCR

### Test 3.1 – PDF scannerizzato con poco/no testo estraibile da pypdf
**Azione da fare**
1. Carica una perizia scannerizzata (immagini, non testo nativo).
2. Avvia l'analisi.
3. Controlla log applicativi e risultato finale.

**Risultato atteso**
- Il sistema rileva testo vuoto o insufficiente da pypdf.
- Viene tentato OCR automaticamente.
- Nei log compare un messaggio di fallback OCR.
- Se OCR è configurato correttamente, il testo viene estratto e l'analisi prosegue.

**File/moduli coinvolti**
- `app/services_documents.py`
- `app/routes_analysis.py`
- `app/ocr_text.py`
- `app/pdf_text.py`

### Test 3.2 – OCR non configurato (Tesseract/Poppler mancanti)
**Azione da fare**
1. Disabilita o rimuovi `TESSERACT_CMD` / `POPPLER_PATH` in ambiente locale.
2. Analizza un PDF scannerizzato.

**Risultato atteso**
- Il fallback OCR fallisce in modo controllato.
- Il job termina con errore leggibile oppure con dettaglio diagnostico chiaro sul problema OCR.
- Nessun crash non gestito del server.

**File/moduli coinvolti**
- `app/ocr_text.py`
- `app/routes_analysis.py`

### Test 3.3 – Testo troppo corto ma non vuoto
**Azione da fare**
1. Usa un PDF con testo nativo molto corto o rumoroso (es. poche righe, watermark, frontespizio).
2. Avvia l'analisi.

**Risultato atteso**
- Il sistema considera il testo insufficiente.
- Viene forzato OCR anche se pypdf ha restituito qualche carattere.
- Nei log compare un warning su testo troppo corto.

**File/moduli coinvolti**
- `app/services_documents.py`
- `app/routes_analysis.py`

---

## 4) Warning di validazione incrociata

### Test 4.1 – Dati coerenti tra pagina, avviso e perizia
**Azione da fare**
1. Prepara un'asta con dati pagina coerenti (`tribunale`, `rge`, `lotto`, `data_asta`, `prezzo_base`).
2. Carica avviso e perizia contenenti gli stessi valori.
3. Avvia analisi.
4. Controlla il campo note operative / scheda finale.

**Risultato atteso**
- Nessun warning di incoerenza.
- `note_operativi` non contiene il blocco “Verifiche incrociate (warning)” oppure lo contiene vuoto.

**File/moduli coinvolti**
- `app/routes_analysis.py`
- `app/services_parsing.py`

### Test 4.2 – RGE incoerente tra fonti
**Azione da fare**
1. Imposta nella pagina asta un `rge`.
2. Carica un avviso con `rge` diverso o perizia con `rge` differente.
3. Avvia analisi.

**Risultato atteso**
- In `note_operativi` compare un warning del tipo `rge: incoerenza tra fonti`.
- Il warning elenca almeno le fonti discordanti (`pagina`, `avviso`, `perizia`).

**File/moduli coinvolti**
- `app/routes_analysis.py`

### Test 4.3 – Prezzo base o offerta minima incoerenti
**Azione da fare**
1. Carica documenti con importi diversi tra avviso e perizia oppure tra DB e documenti.
2. Avvia l'analisi.

**Risultato atteso**
- Viene generato warning su `prezzo_base` e/o `offerta_minima`.
- Il warning è salvato dentro `note_operativi` e visibile in scheda o nel DB.

**File/moduli coinvolti**
- `app/routes_analysis.py`
- `app/services_parsing.py`

---

## 5) Qualità output AI – urbanistica, abusi, pregiudizievoli

### Test 5.1 – Perizia con difformità urbanistiche esplicite
**Azione da fare**
1. Usa una perizia che contenga frasi tipo:
   - difformità urbanistica
   - pratica edilizia mancante
   - sanatoria necessaria / non sanabile
2. Avvia l'analisi.
3. Controlla i campi `abusi`, `note_operativi`, `ai_result_json`.

**Risultato atteso**
- L'AI produce commenti chiari su:
  - presenza o assenza di abusi;
  - sanabilità / non sanabilità;
  - impatto operativo per l'investitore.
- I campi urbanistici non devono essere generici o vuoti se le evidenze sono presenti nel testo.

**File/moduli coinvolti**
- `app/ai_analyzer.py`
- `app/routes_analysis.py`

### Test 5.2 – Perizia con formalità pregiudizievoli dettagliate
**Azione da fare**
1. Usa una perizia con sezioni su ipoteche, pignoramenti, trascrizioni, vincoli.
2. Avvia l'analisi.
3. Controlla i campi `pregiudizievoli`, `note_operativi`, `ai_result_json`.

**Risultato atteso**
- L'AI produce una sintesi comprensibile e un dettaglio utile.
- Se presenti, i nuovi campi AI (`formalita_pregiudizievoli_commento`, `rischi_legali`) vengono valorizzati.
- `note_operativi` mostra una lettura utile per decisione investimento.

**File/moduli coinvolti**
- `app/ai_analyzer.py`
- `app/routes_analysis.py`

### Test 5.3 – Perizia con occupazione e rischi legali
**Azione da fare**
1. Usa una perizia con immobile occupato, contratto, opposizioni o aspetti legali dubbi.
2. Avvia l'analisi.

**Risultato atteso**
- L'output AI include osservazioni in `rischi_legali`.
- `note_operativi` evidenzia chiaramente il rischio e il possibile impatto economico/temporale.

**File/moduli coinvolti**
- `app/ai_analyzer.py`
- `app/routes_analysis.py`

### Test 5.4 – Perizia “pulita” senza criticità rilevanti
**Azione da fare**
1. Usa una perizia completa ma senza abusi o formalità critiche.
2. Avvia l'analisi.

**Risultato atteso**
- L'AI non inventa criticità.
- I campi restano coerenti con assenza evidenze o riportano chiaramente che non emergono elementi critici dal testo.

**File/moduli coinvolti**
- `app/ai_analyzer.py`
- `app/routes_analysis.py`

---

## 6) Regressioni e compatibilità flusso esistente

### Test 6.1 – Debug avviso e debug perizia
**Azione da fare**
1. Apri `/aste/<asta_id>/debug-avviso` e `/aste/<asta_id>/debug-perizia` dopo import/caricamento documenti.

**Risultato atteso**
- Le pagine debug continuano a mostrare il testo estratto.
- Nessun errore 500 su file presenti.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/pdf_text.py`

### Test 6.2 – Export Excel dopo analisi completata
**Azione da fare**
1. Completa un'analisi.
2. Scarica `/export.xlsx` oppure verifica il file `data/export_aste.xlsx`.

**Risultato atteso**
- Il file Excel viene generato/aggiornato.
- Non ci sono regressioni sulla fase finale della pipeline.

**File/moduli coinvolti**
- `app/routes_aste.py`
- `app/routes_dashboard.py`
- `app/excel_export.py`

### Test 6.3 – Compatibilità con scheda asta esistente
**Azione da fare**
1. Apri una scheda asta già presente e una appena creata.
2. Verifica che la UI continui a mostrare i dati principali senza errori anche se i nuovi campi AI sono assenti.

**Risultato atteso**
- Nessuna regressione per aste storiche.
- I nuovi campi AI non rompono il rendering del dettaglio.

**File/moduli coinvolti**
- `app/main.py`
- `app/ui_detail.py`
- `app/db.py`

---

## 7) Controlli pratici consigliati durante i test

### Test 7.1 – Verifica stato job da browser o API
**Azione da fare**
1. Durante import/analisi, richiama `GET /aste/<asta_id>/analysis-status` più volte.

**Risultato atteso**
- I campi `progress`, `step`, `message`, `done`, `error` cambiano in modo coerente con la fase.

**File/moduli coinvolti**
- `app/routes_analysis.py`
- `app/routes_aste.py`

### Test 7.2 – Verifica persistenza dati finali
**Azione da fare**
1. Dopo analisi completata, controlla la scheda asta o il DB.
2. Verifica in particolare:
   - `ai_status`
   - `ai_model`
   - `ai_result_json`
   - `note_operativi`
   - `prezzo_base`
   - `offerta_minima`
   - `tribunale`
   - `rge`

**Risultato atteso**
- I dati finali sono coerenti e persistiti.
- I warning di validazione, se presenti, risultano salvati in `note_operativi`.

**File/moduli coinvolti**
- `app/routes_analysis.py`
- `app/db.py`

