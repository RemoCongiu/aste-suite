import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlmodel import Field, SQLModel, Session, create_engine, select


class Asta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # base
    url: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # dati principali
    rge: Optional[str] = Field(default=None, index=True)
    tribunale: Optional[str] = Field(default=None, index=True)
    data_asta: Optional[str] = Field(default=None, index=True)
    citta: Optional[str] = Field(default=None, index=True)
    indirizzo: Optional[str] = Field(default=None)

    # catasto
    catasto: Optional[str] = Field(default=None)
    foglio: Optional[str] = Field(default=None)
    mappale: Optional[str] = Field(default=None)
    subalterno: Optional[str] = Field(default=None)
    categoria_catastale: Optional[str] = Field(default=None)

    # valori
    occupazione: Optional[str] = Field(default=None, index=True)
    valore_perizia: Optional[str] = Field(default=None)
    prezzo_base: Optional[str] = Field(default=None)
    offerta_minima: Optional[str] = Field(default=None)
    rilancio_minimo: Optional[str] = Field(default=None)

    # altri dati
    creditore_procedente: Optional[str] = Field(default=None)
    descrizione_immobile: Optional[str] = Field(default=None)

    # criticità
    pregiudizievoli: Optional[str] = Field(default=None)
    abusi: Optional[str] = Field(default=None)
    sintesi: Optional[str] = Field(default=None)

    # compilazione manuale
    proprietario: Optional[str] = Field(default=None)
    note: Optional[str] = Field(default=None)
    note_operativi: Optional[str] = Field(default=None)
    stato_pratica: Optional[str] = Field(default=None, index=True)

    # perizia
    lotto: Optional[str] = Field(default=None, index=True)
    perizia_url: Optional[str] = Field(default=None, index=True)
    perizia_status: str = Field(default="pending", index=True)
    perizia_checked_at: Optional[datetime] = Field(default=None)
    perizia_error: Optional[str] = Field(default=None)
    perizia_file_path: Optional[str] = Field(default=None)
    perizia_downloaded_at: Optional[datetime] = Field(default=None)

    # avviso
    avviso_url: Optional[str] = Field(default=None, index=True)
    avviso_status: str = Field(default="pending", index=True)
    avviso_checked_at: Optional[datetime] = Field(default=None)
    avviso_error: Optional[str] = Field(default=None)
    avviso_file_path: Optional[str] = Field(default=None)
    avviso_downloaded_at: Optional[datetime] = Field(default=None)

    # AI
    ai_status: str = Field(default="pending", index=True)
    ai_model: Optional[str] = Field(default=None)
    ai_result_json: Optional[str] = Field(default=None)
    ai_summary: Optional[str] = Field(default=None)
    ai_prompt_text: Optional[str] = Field(default=None)
    ai_raw_response: Optional[str] = Field(default=None)
    avviso_parsed_json: Optional[str] = Field(default=None)
    perizia_parsed_json: Optional[str] = Field(default=None)
    ai_checked_at: Optional[datetime] = Field(default=None)
    ai_error: Optional[str] = Field(default=None)


engine = create_engine("sqlite:///aste.db")


def _normalize_db_field_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            joined = ", ".join(item.strip() for item in value if item and item.strip())
            return joined or None
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or normalized.lower() in {"nd", "n.d.", "null", "none", "-"}:
            return None
        return normalized

    return str(value).strip() or None


def _ensure_extra_columns() -> None:
    with engine.begin() as conn:
        existing_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(asta)")).fetchall()
        }

        extra_columns = {
            "note_operativi": "ALTER TABLE asta ADD COLUMN note_operativi VARCHAR",
            "stato_pratica": "ALTER TABLE asta ADD COLUMN stato_pratica VARCHAR",
            "categoria_catastale": "ALTER TABLE asta ADD COLUMN categoria_catastale VARCHAR",
            "rilancio_minimo": "ALTER TABLE asta ADD COLUMN rilancio_minimo VARCHAR",
            "descrizione_immobile": "ALTER TABLE asta ADD COLUMN descrizione_immobile VARCHAR",
            "ai_prompt_text": "ALTER TABLE asta ADD COLUMN ai_prompt_text VARCHAR",
            "ai_raw_response": "ALTER TABLE asta ADD COLUMN ai_raw_response VARCHAR",
            "avviso_parsed_json": "ALTER TABLE asta ADD COLUMN avviso_parsed_json VARCHAR",
            "perizia_parsed_json": "ALTER TABLE asta ADD COLUMN perizia_parsed_json VARCHAR",
        }

        for col_name, sql in extra_columns.items():
            if col_name not in existing_columns:
                conn.execute(text(sql))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_extra_columns()


def normalize_url(url: str) -> str:
    return (url or "").strip()


def get_asta_by_url(url: str) -> Optional[Asta]:
    normalized_url = normalize_url(url)
    if not normalized_url:
        return None

    with Session(engine) as session:
        statement = select(Asta).where(Asta.url == normalized_url).order_by(Asta.id.desc())
        return session.exec(statement).first()


def insert_asta(url: str) -> Asta:
    normalized_url = normalize_url(url)
    asta = Asta(url=normalized_url)

    with Session(engine) as session:
        session.add(asta)
        session.commit()
        session.refresh(asta)

    return asta


def get_or_create_asta(url: str) -> tuple[Asta, bool]:
    normalized_url = normalize_url(url)
    existing = get_asta_by_url(normalized_url)
    if existing:
        return existing, False

    created = insert_asta(normalized_url)
    return created, True


def get_asta(asta_id: int) -> Optional[Asta]:
    with Session(engine) as session:
        return session.get(Asta, asta_id)


def update_asta_fields(asta_id: int, **fields) -> Optional[Asta]:
    with Session(engine) as session:
        asta = session.get(Asta, asta_id)
        if not asta:
            return None

        for k, v in fields.items():
            if hasattr(asta, k):
                setattr(asta, k, _normalize_db_field_value(v))

        session.add(asta)
        session.commit()
        session.refresh(asta)
        return asta


def list_aste(limit: int = 50) -> list[Asta]:
    with Session(engine) as session:
        statement = select(Asta).order_by(Asta.id.desc()).limit(limit)
        return list(session.exec(statement).all())
