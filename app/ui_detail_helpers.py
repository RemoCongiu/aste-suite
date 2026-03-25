from __future__ import annotations

import html


def v(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def e(value) -> str:
    return html.escape(v(value))


def ta(value) -> str:
    return html.escape(v(value))


def render_text(value, empty: str = "Non disponibile") -> str:
    text = v(value)
    if not text:
        return f'<span class="empty">{html.escape(empty)}</span>'
    return html.escape(text).replace("\n", "<br>")


def severity_class(text: str) -> str:
    t = v(text).lower()

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


def hero_value(value) -> str:
    vv = v(value)
    return html.escape(vv) if vv else "-"
