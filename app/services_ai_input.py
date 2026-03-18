from __future__ import annotations

import re


NOISE_LINE_PATTERNS = [
    r"^pagina\s+\d+(\s+di\s+\d+)?$",
    r"^pag\.\s*\d+(\s*/\s*\d+)?$",
    r"^tribunale\s+di\s+.+$",
    r"^proc(?:edura)?\s+(esecutiva|immobiliare).+$",
    r"^r\.?g\.?e\.?.+$",
    r"^geom\.?.+$",
    r"^ing\.?.+$",
    r"^arch\.?.+$",
    r"^dott\.?.+$",
    r"^tel\.?.+$",
    r"^cell\.?.+$",
    r"^fax\.?.+$",
    r"^e-?mail[:\s].+$",
    r"^pec[:\s].+$",
    r"^www\..+$",
    r"^https?://.+$",
    r"^c\.f\..+$",
    r"^p\.iva.+$",
    r"^il\s+sottoscritto\s+c\.?t\.?u\.?.+$",
    r"^relazione\s+di\s+consulenza\s+tecnica.+$",
    r"^quesito\s+n\.?\s*\d+.*$",
    r"^allegat[oi]\b.*$",
    r"^document[oi]\s+\d+.*$",
]

REDUCED_BLOCK_PATTERNS = [
    r"il\s+sottoscritto\s+c\.?t\.?u\.?",
    r"quesiti?\s+del\s+giudice",
    r"relazione\s+di\s+consulenza\s+tecnica",
    r"elenco\s+allegati",
    r"richiami?\s+normativi",
]

SECTION_PATTERNS = [
    r"identificazione(?:\s+del)?\s+bene",
    r"descrizione(?:\s+del)?\s+bene",
    r"ubicazione",
    r"indirizzo",
    r"dati\s+catastali",
    r"catasto",
    r"foglio",
    r"mappale",
    r"subalterno",
    r"provenienza",
    r"stato\s+di\s+occupazione",
    r"occupazione",
    r"regolarit[aà]\s+urbanistica",
    r"regolarit[aà]\s+catastale",
    r"conformit[aà]\s+urbanistica",
    r"conformit[aà]\s+catastale",
    r"abusi?",
    r"sanatoria",
    r"vincoli",
    r"oneri",
    r"pregiudizievoli",
    r"ipotec",
    r"pignorament",
    r"spese\s+condominiali",
    r"stato\s+manutentivo",
    r"impianti",
    r"agibilit[aà]",
    r"stima",
    r"valore\s+di\s+mercato",
]


def clean_ocr_text_for_ai(text: str) -> str:
    if not text or not text.strip():
        return ""

    text = text.replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines: list[str] = []
    seen_short_lines: set[str] = set()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        lower_line = line.lower()
        if any(re.match(pattern, lower_line, flags=re.IGNORECASE) for pattern in NOISE_LINE_PATTERNS):
            continue

        if re.fullmatch(r"[-_ ]{3,}", line):
            continue

        if len(line) <= 90:
            normalized_key = re.sub(r"\W+", "", lower_line)
            if normalized_key in seen_short_lines:
                continue
            seen_short_lines.add(normalized_key)

        lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    for pattern in REDUCED_BLOCK_PATTERNS:
        cleaned = re.sub(
            rf"(?is){pattern}.*?(?:\n\n|\Z)",
            "\n",
            cleaned,
        )

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _extract_key_sections(text: str) -> str:
    if not text:
        return ""

    lower_text = text.lower()
    windows: list[tuple[int, int]] = []

    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, lower_text, flags=re.IGNORECASE):
            start = max(0, match.start() - 1200)
            end = min(len(text), match.end() + 7000)
            windows.append((start, end))

    head = text[:18000]
    tail = text[-12000:] if len(text) > 12000 else ""

    if not windows:
        return "\n\n".join(part for part in [head, tail] if part).strip()

    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    chunks = [text[start:end].strip() for start, end in merged if end > start]

    ordered_parts: list[str] = []
    seen_parts: set[str] = set()
    for part in [head, *chunks, tail]:
        normalized = re.sub(r"\W+", "", (part or "").lower())
        if not part or not normalized or normalized in seen_parts:
            continue
        seen_parts.add(normalized)
        ordered_parts.append(part)

    combined = "\n\n".join(ordered_parts)
    return re.sub(r"\n{3,}", "\n\n", combined).strip()


def prepare_perizia_text_for_ai(text: str) -> str:
    cleaned = clean_ocr_text_for_ai(text)
    if not cleaned:
        return ""

    selected = _extract_key_sections(cleaned)
    selected = re.sub(r"\n{3,}", "\n\n", selected).strip()

    if len(selected) <= 180000:
        return selected

    return selected[:180000]
