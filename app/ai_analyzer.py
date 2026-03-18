from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import OpenAI

from app.services_ai_input import prepare_perizia_text_for_ai


MODEL_NAME = os.getenv("OPENAI_ASTE_MODEL", "gpt-4.1-mini")

__all__ = ["MODEL_NAME", "analyze_perizia_text", "analyze_perizia_text_debug"]

KEY_SECTION_PATTERNS = [
    r"identificazione(?:\s+del)?\s+bene",
    r"descrizione(?:\s+del)?\s+bene",
    r"consistenza",
    r"confini",
    r"ubicazione",
    r"indirizzo",
    r"catasto",
    r"dati\s+catastali",
    r"foglio",
    r"mappale",
    r"particella",
    r"subalterno",
    r"categoria\s+catastale",
    r"classe\s+catastale",
    r"rendita\s+catastale",
    r"provenienza",
    r"titolo\s+di\s+provenienza",
    r"stato\s+di\s+possesso",
    r"stato\s+di\s+occupazione",
    r"occupazione",
    r"libero",
    r"occupato",
    r"contratto\s+di\s+locazione",
    r"regolarit[aà]\s+edilizia",
    r"regolarit[aà]\s+urbanistica",
    r"regolarit[aà]\s+catastale",
    r"conformit[aà]\s+urbanistica",
    r"conformit[aà]\s+catastale",
    r"agibilit[aà]",
    r"abitabilit[aà]",
    r"licenza\s+edilizia",
    r"concessione\s+edilizia",
    r"permesso\s+di\s+costruire",
    r"sanatoria",
    r"abusi?",
    r"difformit[aà]",
    r"formalit[aà]\s+pregiudizievoli",
    r"pregiudizievoli",
    r"ipoteca",
    r"ipoteche",
    r"pignoramento",
    r"pignoramenti",
    r"trascrizioni?",
    r"iscrizioni?",
    r"vincoli\s+e\s+oneri",
    r"oneri",
    r"servit[uù]",
    r"vincoli",
    r"spese\s+condominiali",
    r"condominio",
    r"stato\s+manutentivo",
    r"manutenzione",
    r"impianti",
    r"certificazione\s+energetica",
    r"\bape\b",
    r"stima(?:\s+del)?\s+bene",
    r"valore(?:\s+di)?\s+stima",
    r"criterio\s+di\s+stima",
    r"valutazione",
]


def _client() -> "OpenAI":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Variabile OPENAI_API_KEY non impostata.")

    try:
        from openai import OpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError("Pacchetto openai non installato.") from e

    return OpenAI(api_key=api_key)


def _safe_json_loads(text: str) -> dict[str, Any]:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        return json.loads(candidate)

    raise ValueError("Risposta AI non in formato JSON valido.")


def _normalize_scalar(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        v = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
        if v.lower() in {"", "null", "none", "-", "nd", "n.d.", "non disponibile"}:
            return None
        return v

    return value


def _normalize_multiline_scalar(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        v = value.replace("\xa0", " ").strip()
        v = re.sub(r"[ \t]+", " ", v)
        v = re.sub(r"\n{3,}", "\n\n", v)
        if v.lower() in {"", "null", "none", "-", "nd", "n.d.", "non disponibile"}:
            return None
        return v

    return value


def _ensure_list(value: Any) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, list):
        out = []
        for item in value:
            txt = _normalize_scalar(item)
            if txt:
                out.append(str(txt))
        return out or None

    if isinstance(value, str):
        txt = _normalize_scalar(value)
        if txt:
            return [str(txt)]

    return None


def _ensure_risk(value: Any) -> str | None:
    if value is None:
        return None

    v = str(value).strip().lower()
    if "basso" in v:
        return "basso"
    if "medio" in v:
        return "medio"
    if "alto" in v:
        return "alto"
    return None


def _clean_address(value: Any) -> str | None:
    v = _normalize_scalar(value)
    if not v:
        return None

    v = str(v)
    v = re.sub(r"\s+", " ", v)
    v = v.strip(" ,.;:-")
    return v or None


def _clean_tribunale(value: Any) -> str | None:
    v = _normalize_scalar(value)
    if not v:
        return None

    text = str(v)
    m = re.search(r"tribunale\s+di\s+([A-Za-zÀ-ÿ' -]+)", text, re.IGNORECASE)
    if not m:
        return text

    name = m.group(1).strip()
    name = re.split(
        r"\b(sez\.?|sezione|rge|lotto|procedura|proc\.|vendita|giudice|delegato|custode)\b",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,.;:-")

    if not name:
        return None

    return f"Tribunale di {name.title()}"


def _extract_relevant_sections(text: str) -> str:
    return prepare_perizia_text_for_ai(text)


def _post_process_detail_text(value: Any) -> str | None:
    v = _normalize_multiline_scalar(value)
    if not v:
        return None

    text = str(v)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def analyze_perizia_text_debug(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("Testo perizia vuoto.")

    client = _client()
    trimmed_text = _extract_relevant_sections(text)

    system_prompt = """
Sei un analista senior di aste immobiliari italiane specializzato in:
- perizie immobiliari
- esecuzioni immobiliari
- urbanistica e catasto
- formalità pregiudizievoli
- analisi del rischio per investitori immobiliari

Devi lavorare con rigore, prudenza e massima utilità operativa.

OBIETTIVO
Analizzare una perizia immobiliare e restituire:
1) dati documentali realmente presenti nel testo
2) una lettura critica molto utile per un investitore immobiliare

REGOLE FONDAMENTALI
- Non inventare dati.
- Non dare per certo ciò che è solo possibile o da verificare.
- Se il dato manca o non è chiaro, usa null.
- Se una criticità emerge solo in modo parziale, esplicitalo.
- Non confondere perizia e avviso di vendita.
- Se la data asta, il prezzo base o l'offerta minima non sono presenti nella perizia, usa null.
- Rispondi solo con JSON valido.
- Nessun markdown.
- Nessun testo fuori dal JSON.
- Scrivi in italiano.
- Non copiare frasi lunghe o paragrafi della perizia/OCR.
- Niente riversamento di testo OCR grezzo: sintetizza sempre.
- Distingui chiaramente tra fatto documentale, interpretazione, rischio e azione.

REGOLE SPECIFICHE IMPORTANTI
- Sii molto severo nell'analisi di:
  - abusi edilizi
  - difformità urbanistiche
  - difformità catastali
  - sanabilità / non sanabilità
  - formalità pregiudizievoli
  - ipoteche, pignoramenti, trascrizioni, iscrizioni
  - vincoli e oneri
  - occupazione del bene
  - spese condominiali o costi extra
- Se trovi elementi rilevanti su urbanistica, catasto o pregiudizievoli, valorizzali bene.
- Se non trovi criticità, non inventarle.
- "criticita_principali" deve contenere solo i punti davvero rilevanti.
- "costi_probabili" deve contenere costi o esborsi probabili ricavabili dal testo.
- "punti_di_attenzione_investitore" deve essere pratico e concreto.
- "valutazione_operativa" e "strategia_consigliata" devono essere utili per decidere se approfondire o meno.
- "fatto_documentale", "interpretazione_operativa", "livello_rischio" e "azione_consigliata" devono essere brevi e operativi.
- "punti_forti_operazione", "punti_deboli_operazione" e "verifiche_prioritarie" devono essere liste sintetiche.
- "giudizio_finale" e "azione_consigliata_finale" devono aiutare l'investitore a decidere il prossimo passo.

STILE DI SCRITTURA RICHIESTO
- Linguaggio chiaro, concreto e leggibile da un investitore non tecnico.
- Frasi brevi, niente tecnicismi inutili.
- Evidenzia in modo esplicito: rischi legali, rischi urbanistici e impatto economico.
"""

    user_prompt = f"""
Analizza la seguente perizia immobiliare.

TESTO PERIZIA:
{trimmed_text}

Restituisci un JSON valido con questa struttura esatta:

{{
  "dati_documentali": {{
    "rge": null,
    "tribunale": null,
    "lotto": null,
    "citta": null,
    "indirizzo": "via/piazza + numero civico se presente",
    "descrizione_immobile": null,
    "tipologia_immobile": null,
    "superficie": null,
    "catasto": null,
    "foglio": null,
    "mappale": null,
    "subalterno": null,
    "categoria_catastale": null,
    "classe_catastale": null,
    "rendita_catastale": null,
    "proprietario": null,
    "provenienza": null,
    "occupazione": null,
    "stato_occupazione_dettaglio": null,
    "valore_perizia": null,
    "creditore_procedente": null,
    "pregiudizievoli": null,
    "pregiudizievoli_dettaglio": null,
    "vincoli_oneri": null,
    "abusi": null,
    "abusi_dettaglio": null,
    "stato_urbanistico": null,
    "stato_catastale": null,
    "stato_manutentivo": null,
    "agibilita": null,
    "impianti": null,
    "debiti_condominiali": null,
    "conformita_catastale": null,
    "conformita_urbanistica": null,
    "spese_stimate_regolarizzazione": null,
    "data_asta": null,
    "prezzo_base": null,
    "offerta_minima": null
  }},
  "lettura_investitore": {{
    "sintesi": null,
    "riassunto_breve": null,
    "criticita_principali": [],
    "costi_probabili": [],
    "punti_di_attenzione_investitore": [],
    "valutazione_operativa": null,
    "strategia_consigliata": null,
    "rischio_operazione": null,
    "vendibilita_potenziale": null,
    "note_investitore": null,
    "rischi_legali": null,
    "rischi_urbanistici": null,
    "formalita_pregiudizievoli_commento": null,
    "fatto_documentale": null,
    "interpretazione_operativa": null,
    "livello_rischio": null,
    "azione_consigliata": null,
    "punti_forti_operazione": [],
    "punti_deboli_operazione": [],
    "verifiche_prioritarie": [],
    "giudizio_finale": null,
    "azione_consigliata_finale": null
  }}
}}

ISTRUZIONI AGGIUNTIVE IMPORTANTI:
- "pregiudizievoli" deve essere una sintesi breve ma sostanziale.
- "pregiudizievoli_dettaglio" deve contenere il maggior dettaglio utile disponibile.
- "abusi" deve essere una sintesi breve.
- "abusi_dettaglio" deve spiegare bene:
  - eventuali difformità
  - se risultano sanabili o non sanabili
  - se servono verifiche o pratiche edilizie/catastali
- "stato_urbanistico" deve sintetizzare il quadro urbanistico.
- "stato_catastale" deve sintetizzare il quadro catastale.
- "conformita_catastale" e "conformita_urbanistica" devono essere esplicite.
- "descrizione_immobile" deve essere concreta e leggibile.
- "criticita_principali" deve essere una lista di veri elementi di rischio.
- "costi_probabili" deve includere, se presenti o chiaramente probabili:
  - regolarizzazioni urbanistiche/catastali
  - liberazione immobile
  - debiti condominiali
  - lavori
  - impianti
- "rischio_operazione" può essere solo: "basso", "medio", "alto".
- "livello_rischio" deve essere uno tra: "basso", "medio", "alto".
- "fatto_documentale" = solo ciò che risulta dal testo.
- "interpretazione_operativa" = lettura sintetica utile per investitore.
- "azione_consigliata" = singola azione pratica immediata.
- "azione_consigliata_finale" = esito finale tipo approfondire / fare offerta prudente / evitare.
"""

    try:
        response = client.responses.create(
            model=MODEL_NAME,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
    except Exception as e:
        raise RuntimeError(f"Errore chiamata OpenAI: {e}") from e

    raw_text = response.output_text
    data = _safe_json_loads(raw_text)

    dati_documentali = data.get("dati_documentali", {}) or {}
    lettura_investitore = data.get("lettura_investitore", {}) or {}

    normalized: dict[str, Any] = {
        "rge": _normalize_scalar(dati_documentali.get("rge")),
        "tribunale": _clean_tribunale(dati_documentali.get("tribunale")),
        "lotto": _normalize_scalar(dati_documentali.get("lotto")),
        "data_asta": _normalize_scalar(dati_documentali.get("data_asta")),
        "citta": _normalize_scalar(dati_documentali.get("citta")),
        "indirizzo": _clean_address(dati_documentali.get("indirizzo")),
        "descrizione_immobile": _post_process_detail_text(dati_documentali.get("descrizione_immobile")),
        "tipologia_immobile": _normalize_scalar(dati_documentali.get("tipologia_immobile")),
        "superficie": _normalize_scalar(dati_documentali.get("superficie")),
        "catasto": _normalize_scalar(dati_documentali.get("catasto")),
        "foglio": _normalize_scalar(dati_documentali.get("foglio")),
        "mappale": _normalize_scalar(dati_documentali.get("mappale")),
        "subalterno": _normalize_scalar(dati_documentali.get("subalterno")),
        "categoria_catastale": _normalize_scalar(dati_documentali.get("categoria_catastale")),
        "classe_catastale": _normalize_scalar(dati_documentali.get("classe_catastale")),
        "rendita_catastale": _normalize_scalar(dati_documentali.get("rendita_catastale")),
        "proprietario": _normalize_scalar(dati_documentali.get("proprietario")),
        "provenienza": _normalize_scalar(dati_documentali.get("provenienza")),
        "occupazione": _normalize_scalar(dati_documentali.get("occupazione")),
        "stato_occupazione_dettaglio": _post_process_detail_text(dati_documentali.get("stato_occupazione_dettaglio")),
        "valore_perizia": _normalize_scalar(dati_documentali.get("valore_perizia")),
        "creditore_procedente": _normalize_scalar(dati_documentali.get("creditore_procedente")),
        "pregiudizievoli": _normalize_scalar(dati_documentali.get("pregiudizievoli")),
        "pregiudizievoli_dettaglio": _post_process_detail_text(dati_documentali.get("pregiudizievoli_dettaglio")),
        "vincoli_oneri": _post_process_detail_text(dati_documentali.get("vincoli_oneri")),
        "abusi": _normalize_scalar(dati_documentali.get("abusi")),
        "abusi_dettaglio": _post_process_detail_text(dati_documentali.get("abusi_dettaglio")),
        "stato_urbanistico": _post_process_detail_text(dati_documentali.get("stato_urbanistico")),
        "stato_catastale": _post_process_detail_text(dati_documentali.get("stato_catastale")),
        "stato_manutentivo": _normalize_scalar(dati_documentali.get("stato_manutentivo")),
        "agibilita": _normalize_scalar(dati_documentali.get("agibilita")),
        "impianti": _post_process_detail_text(dati_documentali.get("impianti")),
        "debiti_condominiali": _normalize_scalar(dati_documentali.get("debiti_condominiali")),
        "conformita_catastale": _normalize_scalar(dati_documentali.get("conformita_catastale")),
        "conformita_urbanistica": _normalize_scalar(dati_documentali.get("conformita_urbanistica")),
        "spese_stimate_regolarizzazione": _normalize_scalar(dati_documentali.get("spese_stimate_regolarizzazione")),
        "prezzo_base": _normalize_scalar(dati_documentali.get("prezzo_base")),
        "offerta_minima": _normalize_scalar(dati_documentali.get("offerta_minima")),
        "sintesi": _post_process_detail_text(lettura_investitore.get("sintesi")),
        "riassunto_breve": _normalize_scalar(lettura_investitore.get("riassunto_breve")),
        "criticita_principali": _ensure_list(lettura_investitore.get("criticita_principali")),
        "costi_probabili": _ensure_list(lettura_investitore.get("costi_probabili")),
        "punti_di_attenzione_investitore": _ensure_list(lettura_investitore.get("punti_di_attenzione_investitore")),
        "valutazione_operativa": _post_process_detail_text(lettura_investitore.get("valutazione_operativa")),
        "strategia_consigliata": _post_process_detail_text(lettura_investitore.get("strategia_consigliata")),
        "rischio_operazione": _ensure_risk(lettura_investitore.get("rischio_operazione")),
        "vendibilita_potenziale": _normalize_scalar(lettura_investitore.get("vendibilita_potenziale")),
        "note_investitore": _post_process_detail_text(lettura_investitore.get("note_investitore")),
        "rischi_legali": _post_process_detail_text(lettura_investitore.get("rischi_legali")),
        "rischi_urbanistici": _post_process_detail_text(lettura_investitore.get("rischi_urbanistici")),
        "formalita_pregiudizievoli_commento": _post_process_detail_text(lettura_investitore.get("formalita_pregiudizievoli_commento")),
        "fatto_documentale": _post_process_detail_text(lettura_investitore.get("fatto_documentale")),
        "interpretazione_operativa": _post_process_detail_text(lettura_investitore.get("interpretazione_operativa")),
        "livello_rischio": _ensure_risk(lettura_investitore.get("livello_rischio")),
        "azione_consigliata": _post_process_detail_text(lettura_investitore.get("azione_consigliata")),
        "punti_forti_operazione": _ensure_list(lettura_investitore.get("punti_forti_operazione")),
        "punti_deboli_operazione": _ensure_list(lettura_investitore.get("punti_deboli_operazione")),
        "verifiche_prioritarie": _ensure_list(lettura_investitore.get("verifiche_prioritarie")),
        "giudizio_finale": _post_process_detail_text(lettura_investitore.get("giudizio_finale")),
        "azione_consigliata_finale": _post_process_detail_text(lettura_investitore.get("azione_consigliata_finale")),
    }

    return {
        "data": normalized,
        "prompt": {
            "system": system_prompt.strip(),
            "user": user_prompt.strip(),
            "input_excerpt": trimmed_text,
        },
        "raw_response": raw_text,
    }


def analyze_perizia_text(text: str) -> dict:
    return analyze_perizia_text_debug(text)["data"]
