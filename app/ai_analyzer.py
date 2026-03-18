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

OBJECTIVE_FIELD_NAMES = {
    "tribunale",
    "rge",
    "lotto",
    "data_asta",
    "valore_perizia",
    "prezzo_base",
    "offerta_minima",
    "rilancio_minimo",
    "comune",
    "citta",
    "indirizzo",
    "foglio",
    "particella",
    "mappale",
    "subalterno",
    "categoria_catastale",
    "occupazione",
    "creditore_procedente",
    "proprietario",
}

AI_COPY_PATTERNS = [
    r"il\s+sottoscritto\s+c\.?t\.?u\.?",
    r"si\s+riportano\s+le\s+risultanze",
    r"relazione\s+di\s+consulenza\s+tecnica",
    r"\bquesito\b",
    r"\ballegat[oi]\b",
    r"\bsommario\b",
    r"\bindice\b",
    r"firma\s+digitale",
    r"\bpec\b",
    r"\btel\.?\b",
    r"\bfax\b",
]

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
    if "CONTESTO STRUTTURATO AGGIUNTIVO" in text and "TESTO PERIZIA PULITO:" in text:
        prepared = text.replace("\r", "\n")
        prepared = re.sub(r"\n{3,}", "\n\n", prepared).strip()
        return prepared
    return prepare_perizia_text_for_ai(text)


def _post_process_detail_text(value: Any) -> str | None:
    v = _normalize_multiline_scalar(value)
    if not v:
        return None

    text = str(v)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_confidence(value: Any) -> str | None:
    if value is None:
        return None

    v = str(value).strip().lower()
    if "alta" in v:
        return "alta"
    if "media" in v:
        return "media"
    if "bassa" in v:
        return "bassa"
    return None


def _normalize_source(value: Any) -> str | None:
    v = _normalize_scalar(value)
    if not v:
        return None
    text = str(v).lower()
    allowed = {"avviso", "perizia", "entrambi", "parser", "inferenza"}
    return text if text in allowed else text


def _sanitize_ai_narrative_text(value: Any) -> str | None:
    text = _post_process_detail_text(value)
    if not text:
        return None

    lowered = text.lower()
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in AI_COPY_PATTERNS):
        cleaned = text
        for pattern in AI_COPY_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip(" \n:;-")
        text = cleaned or None

    if text and len(text.splitlines()) >= 8 and len(re.findall(r"(?:^|\n)- ", text)) >= 5:
        return None

    return text


def _normalize_objective_struct(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    normalized = {
        "valore": _normalize_scalar(value.get("valore")),
        "fonte": _normalize_source(value.get("fonte")),
        "confidenza": _normalize_confidence(value.get("confidenza")),
        "warning": _sanitize_ai_narrative_text(value.get("warning")),
    }
    if not any(normalized.values()):
        return None
    return normalized


def _normalize_qualitative_block(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    normalized = {
        "fatto_documentale": _sanitize_ai_narrative_text(value.get("fatto_documentale")),
        "analisi_professionale": _sanitize_ai_narrative_text(value.get("analisi_professionale")),
        "rischio": _sanitize_ai_narrative_text(value.get("rischio")),
        "impatto_operativo": _sanitize_ai_narrative_text(value.get("impatto_operativo")),
        "azione_consigliata": _sanitize_ai_narrative_text(value.get("azione_consigliata")),
    }
    if not any(normalized.values()):
        return None
    return normalized


def _compose_qualitative_text(block: dict[str, Any] | None) -> str | None:
    if not isinstance(block, dict):
        return None

    sections = []
    if block.get("fatto_documentale"):
        sections.append(f"Fatto documentale: {block['fatto_documentale']}")
    if block.get("analisi_professionale"):
        sections.append(f"Analisi professionale: {block['analisi_professionale']}")
    if block.get("rischio"):
        sections.append(f"Rischio: {block['rischio']}")
    if block.get("impatto_operativo"):
        sections.append(f"Impatto operativo: {block['impatto_operativo']}")
    if block.get("azione_consigliata"):
        sections.append(f"Azione consigliata: {block['azione_consigliata']}")

    return "\n".join(sections) if sections else None


class AIAnalyzerError(RuntimeError):
    def __init__(self, message: str, *, prompt: dict[str, Any] | None = None, raw_response: str | None = None):
        super().__init__(message)
        self.prompt = prompt
        self.raw_response = raw_response


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
Analizzare la documentazione di un'asta immobiliare (avviso + perizia + contesto strutturato) e restituire:
1) campi oggettivi consolidati, scegliendo il valore più attendibile
2) una vera analisi professionale utile per investitore immobiliare
3) un giudizio operativo finale

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
- Se il testo contiene un contesto strutturato aggiuntivo (avviso, pagina, parser), usalo per decidere il valore migliore.
- In caso di conflitto tra fonti, scegli il valore più attendibile, indica la fonte scelta, la confidenza e un warning breve solo se davvero utile.

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
- I campi oggettivi devono includere sempre: valore, fonte, confidenza, warning.
- L'analisi qualitativa deve essere divisa per temi e usare linguaggio professionale, non scolastico.

STILE DI SCRITTURA RICHIESTO
- Linguaggio chiaro, concreto e leggibile da un investitore non tecnico.
- Frasi brevi, niente tecnicismi inutili.
- Evidenzia in modo esplicito: rischi legali, rischi urbanistici e impatto economico.
"""

    user_prompt = f"""
Analizza la seguente documentazione immobiliare d'asta.

TESTO DOCUMENTI:
{trimmed_text}

Restituisci un JSON valido con questa struttura esatta:

{{
  "campi_oggettivi": {{
    "tribunale": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "rge": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "lotto": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "data_asta": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "valore_perizia": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "prezzo_base": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "offerta_minima": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "rilancio_minimo": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "comune": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "indirizzo": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "foglio": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "particella": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "subalterno": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "categoria_catastale": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "occupazione": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "creditore_procedente": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}},
    "proprietario": {{"valore": null, "fonte": null, "confidenza": null, "warning": null}}
  }},
  "analisi_qualitativa": {{
    "descrizione_immobile": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}},
    "stato_manutentivo": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}},
    "urbanistica_catasto": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}},
    "abusi_difformita_sanabilita": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}},
    "pregiudizievoli": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}},
    "occupazione_liberazione": {{"fatto_documentale": null, "analisi_professionale": null, "rischio": null, "impatto_operativo": null, "azione_consigliata": null}}
  }},
  "giudizio_investitore": {{
    "punti_forti_operazione": [],
    "punti_deboli_operazione": [],
    "verifiche_prioritarie": [],
    "giudizio_finale": null,
    "azione_consigliata_finale": null,
    "livello_rischio": null
  }}
}}

ISTRUZIONI AGGIUNTIVE IMPORTANTI:
- Devi anche valorizzare campi legacy coerenti con questa analisi, quando utili, ma senza copiare testo grezzo.
- In "analisi_qualitativa" ogni sezione deve distinguere fatto, analisi, rischio, impatto e azione.
- Se una sezione non è supportata dal testo, lasciala null.
- "livello_rischio" deve essere uno tra: "basso", "medio", "alto".
- "azione_consigliata_finale" = esito finale tipo approfondire / fare offerta prudente / evitare.
- Se il dato è dubbio o conflittuale: scegli il migliore, assegna confidenza media o bassa e compila "warning".
"""

    prompt_payload = {
        "system": system_prompt.strip(),
        "user": user_prompt.strip(),
        "input_excerpt": trimmed_text,
    }

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
        raise AIAnalyzerError(f"Errore chiamata OpenAI: {e}", prompt=prompt_payload) from e

    raw_text = response.output_text or ""
    if not raw_text.strip():
        try:
            raw_text = json.dumps(response.model_dump(), ensure_ascii=False)
        except Exception:
            raw_text = str(response)
    try:
        data = _safe_json_loads(raw_text)
    except Exception as e:
        raise AIAnalyzerError(
            f"Risposta AI non valida: {e}",
            prompt=prompt_payload,
            raw_response=raw_text,
        ) from e

    dati_documentali = data.get("dati_documentali", {}) or {}
    lettura_investitore = data.get("lettura_investitore", {}) or {}
    campi_oggettivi = data.get("campi_oggettivi", {}) or {}
    analisi_qualitativa = data.get("analisi_qualitativa", {}) or {}
    giudizio_investitore = data.get("giudizio_investitore", {}) or {}

    normalized_objective_fields = {
        field: _normalize_objective_struct(campi_oggettivi.get(field))
        for field in OBJECTIVE_FIELD_NAMES
    }

    normalized_qualitative = {
        name: _normalize_qualitative_block(analisi_qualitativa.get(name))
        for name in (
            "descrizione_immobile",
            "stato_manutentivo",
            "urbanistica_catasto",
            "abusi_difformita_sanabilita",
            "pregiudizievoli",
            "occupazione_liberazione",
        )
    }

    livello_rischio = (
        _ensure_risk(giudizio_investitore.get("livello_rischio"))
        or _ensure_risk(lettura_investitore.get("livello_rischio"))
        or _ensure_risk(lettura_investitore.get("rischio_operazione"))
    )

    descrizione_block = normalized_qualitative.get("descrizione_immobile")
    manutentivo_block = normalized_qualitative.get("stato_manutentivo")
    urbanistica_block = normalized_qualitative.get("urbanistica_catasto")
    abusi_block = normalized_qualitative.get("abusi_difformita_sanabilita")
    pregiudizievoli_block = normalized_qualitative.get("pregiudizievoli")
    occupazione_block = normalized_qualitative.get("occupazione_liberazione")

    normalized: dict[str, Any] = {
        "campi_oggettivi": normalized_objective_fields,
        "analisi_qualitativa": normalized_qualitative,
        "giudizio_investitore": {
            "punti_forti_operazione": _ensure_list(giudizio_investitore.get("punti_forti_operazione")),
            "punti_deboli_operazione": _ensure_list(giudizio_investitore.get("punti_deboli_operazione")),
            "verifiche_prioritarie": _ensure_list(giudizio_investitore.get("verifiche_prioritarie")),
            "giudizio_finale": _sanitize_ai_narrative_text(giudizio_investitore.get("giudizio_finale")),
            "azione_consigliata_finale": _sanitize_ai_narrative_text(giudizio_investitore.get("azione_consigliata_finale")),
            "livello_rischio": livello_rischio,
        },
        "rge": _normalize_scalar((normalized_objective_fields.get("rge") or {}).get("valore") or dati_documentali.get("rge")),
        "tribunale": _clean_tribunale((normalized_objective_fields.get("tribunale") or {}).get("valore") or dati_documentali.get("tribunale")),
        "lotto": _normalize_scalar((normalized_objective_fields.get("lotto") or {}).get("valore") or dati_documentali.get("lotto")),
        "data_asta": _normalize_scalar((normalized_objective_fields.get("data_asta") or {}).get("valore") or dati_documentali.get("data_asta")),
        "citta": _normalize_scalar((normalized_objective_fields.get("comune") or {}).get("valore") or (normalized_objective_fields.get("citta") or {}).get("valore") or dati_documentali.get("citta")),
        "indirizzo": _clean_address((normalized_objective_fields.get("indirizzo") or {}).get("valore") or dati_documentali.get("indirizzo")),
        "descrizione_immobile": _sanitize_ai_narrative_text(dati_documentali.get("descrizione_immobile")) or _compose_qualitative_text(descrizione_block),
        "tipologia_immobile": _normalize_scalar(dati_documentali.get("tipologia_immobile")),
        "superficie": _normalize_scalar(dati_documentali.get("superficie")),
        "catasto": _normalize_scalar(dati_documentali.get("catasto")),
        "foglio": _normalize_scalar((normalized_objective_fields.get("foglio") or {}).get("valore") or dati_documentali.get("foglio")),
        "mappale": _normalize_scalar((normalized_objective_fields.get("mappale") or {}).get("valore") or (normalized_objective_fields.get("particella") or {}).get("valore") or dati_documentali.get("mappale")),
        "subalterno": _normalize_scalar((normalized_objective_fields.get("subalterno") or {}).get("valore") or dati_documentali.get("subalterno")),
        "categoria_catastale": _normalize_scalar((normalized_objective_fields.get("categoria_catastale") or {}).get("valore") or dati_documentali.get("categoria_catastale")),
        "classe_catastale": _normalize_scalar(dati_documentali.get("classe_catastale")),
        "rendita_catastale": _normalize_scalar(dati_documentali.get("rendita_catastale")),
        "proprietario": _normalize_scalar((normalized_objective_fields.get("proprietario") or {}).get("valore") or dati_documentali.get("proprietario")),
        "provenienza": _normalize_scalar(dati_documentali.get("provenienza")),
        "occupazione": _normalize_scalar((normalized_objective_fields.get("occupazione") or {}).get("valore") or dati_documentali.get("occupazione")),
        "stato_occupazione_dettaglio": _sanitize_ai_narrative_text(dati_documentali.get("stato_occupazione_dettaglio")),
        "valore_perizia": _normalize_scalar((normalized_objective_fields.get("valore_perizia") or {}).get("valore") or dati_documentali.get("valore_perizia")),
        "creditore_procedente": _normalize_scalar((normalized_objective_fields.get("creditore_procedente") or {}).get("valore") or dati_documentali.get("creditore_procedente")),
        "pregiudizievoli": _sanitize_ai_narrative_text(dati_documentali.get("pregiudizievoli")) or _compose_qualitative_text(pregiudizievoli_block),
        "pregiudizievoli_dettaglio": _sanitize_ai_narrative_text(dati_documentali.get("pregiudizievoli_dettaglio")) or _compose_qualitative_text(pregiudizievoli_block),
        "vincoli_oneri": _sanitize_ai_narrative_text(dati_documentali.get("vincoli_oneri")),
        "abusi": _sanitize_ai_narrative_text(dati_documentali.get("abusi")) or _compose_qualitative_text(abusi_block),
        "abusi_dettaglio": _sanitize_ai_narrative_text(dati_documentali.get("abusi_dettaglio")) or _compose_qualitative_text(abusi_block),
        "stato_urbanistico": _sanitize_ai_narrative_text(dati_documentali.get("stato_urbanistico")) or _compose_qualitative_text(urbanistica_block),
        "stato_catastale": _sanitize_ai_narrative_text(dati_documentali.get("stato_catastale")),
        "stato_manutentivo": _sanitize_ai_narrative_text(dati_documentali.get("stato_manutentivo")) or _compose_qualitative_text(manutentivo_block),
        "agibilita": _normalize_scalar(dati_documentali.get("agibilita")),
        "impianti": _sanitize_ai_narrative_text(dati_documentali.get("impianti")),
        "debiti_condominiali": _normalize_scalar(dati_documentali.get("debiti_condominiali")),
        "conformita_catastale": _normalize_scalar(dati_documentali.get("conformita_catastale")),
        "conformita_urbanistica": _normalize_scalar(dati_documentali.get("conformita_urbanistica")),
        "spese_stimate_regolarizzazione": _normalize_scalar(dati_documentali.get("spese_stimate_regolarizzazione")),
        "prezzo_base": _normalize_scalar((normalized_objective_fields.get("prezzo_base") or {}).get("valore") or dati_documentali.get("prezzo_base")),
        "offerta_minima": _normalize_scalar((normalized_objective_fields.get("offerta_minima") or {}).get("valore") or dati_documentali.get("offerta_minima")),
        "rilancio_minimo": _normalize_scalar((normalized_objective_fields.get("rilancio_minimo") or {}).get("valore")),
        "sintesi": _sanitize_ai_narrative_text(lettura_investitore.get("sintesi")) or _compose_qualitative_text(descrizione_block),
        "riassunto_breve": _normalize_scalar(lettura_investitore.get("riassunto_breve")),
        "criticita_principali": _ensure_list(lettura_investitore.get("criticita_principali")),
        "costi_probabili": _ensure_list(lettura_investitore.get("costi_probabili")),
        "punti_di_attenzione_investitore": _ensure_list(lettura_investitore.get("punti_di_attenzione_investitore")),
        "valutazione_operativa": _sanitize_ai_narrative_text(lettura_investitore.get("valutazione_operativa")),
        "strategia_consigliata": _sanitize_ai_narrative_text(lettura_investitore.get("strategia_consigliata")),
        "rischio_operazione": livello_rischio or _ensure_risk(lettura_investitore.get("rischio_operazione")),
        "vendibilita_potenziale": _normalize_scalar(lettura_investitore.get("vendibilita_potenziale")),
        "note_investitore": _sanitize_ai_narrative_text(lettura_investitore.get("note_investitore")),
        "rischi_legali": _sanitize_ai_narrative_text(lettura_investitore.get("rischi_legali")),
        "rischi_urbanistici": _sanitize_ai_narrative_text(lettura_investitore.get("rischi_urbanistici")),
        "formalita_pregiudizievoli_commento": _sanitize_ai_narrative_text(lettura_investitore.get("formalita_pregiudizievoli_commento")),
        "fatto_documentale": _sanitize_ai_narrative_text(lettura_investitore.get("fatto_documentale")) or ((descrizione_block or {}).get("fatto_documentale")),
        "interpretazione_operativa": _sanitize_ai_narrative_text(lettura_investitore.get("interpretazione_operativa")) or ((descrizione_block or {}).get("analisi_professionale")),
        "analisi_professionale": _sanitize_ai_narrative_text(lettura_investitore.get("analisi_professionale")) or ((urbanistica_block or {}).get("analisi_professionale")),
        "impatto_operativo": _sanitize_ai_narrative_text(lettura_investitore.get("impatto_operativo")) or ((abusi_block or {}).get("impatto_operativo")),
        "livello_rischio": livello_rischio,
        "azione_consigliata": _sanitize_ai_narrative_text(lettura_investitore.get("azione_consigliata")) or ((occupazione_block or {}).get("azione_consigliata")),
        "punti_forti_operazione": _ensure_list(giudizio_investitore.get("punti_forti_operazione")) or _ensure_list(lettura_investitore.get("punti_forti_operazione")),
        "punti_deboli_operazione": _ensure_list(giudizio_investitore.get("punti_deboli_operazione")) or _ensure_list(lettura_investitore.get("punti_deboli_operazione")),
        "verifiche_prioritarie": _ensure_list(giudizio_investitore.get("verifiche_prioritarie")) or _ensure_list(lettura_investitore.get("verifiche_prioritarie")),
        "giudizio_finale": _sanitize_ai_narrative_text(giudizio_investitore.get("giudizio_finale")) or _sanitize_ai_narrative_text(lettura_investitore.get("giudizio_finale")),
        "azione_consigliata_finale": _sanitize_ai_narrative_text(giudizio_investitore.get("azione_consigliata_finale")) or _sanitize_ai_narrative_text(lettura_investitore.get("azione_consigliata_finale")),
    }

    return {
        "data": normalized,
        "prompt": prompt_payload,
        "raw_response": raw_text,
    }


def analyze_perizia_text(text: str) -> dict:
    return analyze_perizia_text_debug(text)["data"]
