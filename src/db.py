from __future__ import annotations

import csv
import json
import sqlite3

from form_logic import definition_hash, definition_payload
from migrations import migrate, protect_versions, migrate_identity
from identity import new_identity_uuid, validate_birth_anchor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "schema_v0_5_alpha.sql"
FIELD_CATALOG_PATH = ROOT / "seed" / "field_catalog_v0_2.csv"
VOCAB_PATH = ROOT / "seed" / "vocabularies_v0_1.csv"
RUNTIME_DIR = ROOT / "runtime"
DB_PATH = RUNTIME_DIR / "ctc_alpha_v0_4.sqlite"


class ManagedConnection(sqlite3.Connection):
    """Commit or roll back a transaction, then release the database handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(db_path, factory=ManagedConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as con:
        columns = {r[1] for r in con.execute("PRAGMA table_info(form_version)")}
        backup_identity = "definition_hash" in columns
        migrate(con, db_path)
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        migrate_identity(con, db_path, backup_required=backup_identity)
        protect_versions(con)
        seed_field_catalog(con)
        seed_vocabularies(con)


def _yn(value: str) -> int:
    return 1 if (value or "").strip().lower() == "yes" else 0


def _entity(entity: str) -> str:
    return {
        "SOURCE_CONTEXT": "SOURCE_CONTEXT",
        "PAGE/SHEET": "PAGE_SHEET",
        "RECORD": "RECORD",
        "PRI": "PRI",
        "EVENT": "EVENT",
        "REL": "REL",
        "SUPPORTING_DOCUMENT": "SUPPORTING_DOCUMENT",
        "PLACE": "PLACE",
        "SYSTEM": "SYSTEM",
    }[entity]


def source_family_matches(catalog_value: str, family: str) -> bool:
    value = (catalog_value or "").strip().upper()
    family = family.upper()
    if value == "ALL":
        return True
    return family in {part.strip() for part in value.split("/") if part.strip()}


def seed_field_catalog(con: sqlite3.Connection) -> None:
    with FIELD_CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            con.execute(
                """
                INSERT INTO field_catalog (
                    field_code, label, entity_type, layer, semantic_type,
                    default_widget, source_families, repeatable,
                    place_linkable, form_selectable, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(field_code) DO UPDATE SET
                    label=excluded.label,
                    entity_type=excluded.entity_type,
                    layer=excluded.layer,
                    semantic_type=excluded.semantic_type,
                    default_widget=excluded.default_widget,
                    source_families=excluded.source_families,
                    repeatable=excluded.repeatable,
                    place_linkable=excluded.place_linkable,
                    form_selectable=excluded.form_selectable,
                    notes=excluded.notes
                """,
                (
                    row["field_code"], row["label"], _entity(row["entity"]),
                    row["layer"], row["semantic_type"], row["default_widget"],
                    row["source_families"], _yn(row["repeatable"]),
                    _yn(row["place_linkable"]), _yn(row["form_selectable"]),
                    row["notes"],
                ),
            )


def seed_vocabularies(con: sqlite3.Connection) -> None:
    with VOCAB_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            vocab, value, notes = row["vocabulary"], row["value"], row["notes"]
            table = {
                "position_type": "position_type",
                "event_type": "event_type",
                "relation_type": "relation_type"
            }.get(vocab)
            if table:
                con.execute(
                    f"INSERT OR IGNORE INTO {table}(code, label, notes) VALUES (?, ?, ?)",
                    (value, value.replace("_", " ").title(), notes),
                )


def list_forms() -> list[Path]:
    return sorted((ROOT / "forms").glob("*.json"))


def load_form(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_form(path: Path, form: dict) -> None:
    path.write_text(json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_form_version(con: sqlite3.Connection, form: dict) -> int:
    digest = definition_hash(form)
    existing = con.execute(
        "SELECT form_version_id FROM form_version WHERE form_code=? AND definition_hash=?",
        (form["form_code"], digest),
    ).fetchone()
    if existing:
        return existing[0]
    version = con.execute(
        "SELECT COALESCE(MAX(version_no), 0) + 1 FROM form_version WHERE form_code=?",
        (form["form_code"],),
    ).fetchone()[0]
    return con.execute(
        """INSERT INTO form_version(
            form_code, version_no, definition_hash, source_family, label,
            valid_from_year, valid_to_year, definition_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING form_version_id""",
        (form["form_code"], version, digest, form["source_family"], form["label"],
         form.get("valid_from_year"), form.get("valid_to_year"), definition_payload(form)),
    ).fetchone()[0]


def save_form_revision(form: dict) -> Path:
    """Save an immutable DB definition and a new, never-overwritten JSON file."""
    import re
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", form["form_code"]).strip("_").lower()
    if not safe:
        raise ValueError("Form code must contain at least one letter or digit.")
    forms_dir = ROOT / "forms"
    forms_dir.mkdir(exist_ok=True)
    with connect() as con:
        version_id = ensure_form_version(con, form)
        version = con.execute(
            "SELECT version_no FROM form_version WHERE form_version_id=?", (version_id,)
        ).fetchone()[0]
        path = forms_dir / f"{safe}__v{version}.json"
        if path.exists():
            if definition_hash(load_form(path)) == definition_hash(form):
                return path
            path = forms_dir / f"{safe}__v{version}_{definition_hash(form)[:12]}.json"
        # Exclusive creation prevents overwriting any existing form file.
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(form, ensure_ascii=False, indent=2))
        return path


def create_session(
    con: sqlite3.Connection,
    transcriber: str,
    transcription_date: str,
    project_collection: str = "",
    session_note: str = ""
) -> int:
    return con.execute(
        """
        INSERT INTO transcription_session(
            transcriber, transcription_date, project_collection, session_note
        )
        VALUES (?, ?, ?, ?)
        RETURNING session_id
        """,
        (transcriber, transcription_date, project_collection, session_note),
    ).fetchone()[0]



def update_session(
    con: sqlite3.Connection,
    session_id: int,
    transcriber: str,
    transcription_date: str,
    project_collection: str = "",
    session_note: str = ""
) -> None:
    con.execute(
        """
        UPDATE transcription_session
        SET transcriber=?,
            transcription_date=?,
            project_collection=?,
            session_note=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE session_id=?
        """,
        (
            transcriber,
            transcription_date,
            project_collection,
            session_note,
            session_id,
        ),
    )


def ensure_context(con: sqlite3.Connection, source_family: str, context_code: str) -> int:
    con.execute(
        """
        INSERT INTO source_context(source_family, context_code, label)
        VALUES (?, ?, ?)
        ON CONFLICT(context_code) DO NOTHING
        """,
        (source_family, context_code, context_code),
    )
    return con.execute(
        "SELECT context_id FROM source_context WHERE context_code=?",
        (context_code,),
    ).fetchone()[0]


def get_type_id(con: sqlite3.Connection, table: str, code: str) -> int:
    id_col = {
        "position_type": "position_type_id",
        "event_type": "event_type_id",
        "relation_type": "relation_type_id"
    }[table]
    row = con.execute(
        f"SELECT {id_col} FROM {table} WHERE code=?",
        (code,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown {table}: {code}")
    return row[0]


def list_type_codes(con: sqlite3.Connection, table: str) -> list[str]:
    return [
        row["code"]
        for row in con.execute(f"SELECT code FROM {table} ORDER BY code").fetchall()
    ]


def list_catalog_fields(
    con: sqlite3.Connection,
    entity_type: str,
    source_family: str,
    selectable_only: bool = True
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM field_catalog WHERE entity_type=?"
    params = [entity_type]
    if selectable_only:
        sql += " AND form_selectable=1"
    sql += " ORDER BY label"

    rows = con.execute(sql, params).fetchall()
    return [
        row for row in rows
        if source_family_matches(row["source_families"], source_family)
    ]



def next_record_code(con: sqlite3.Connection, source_family: str) -> str:
    next_record_id = con.execute(
        "SELECT COALESCE(MAX(record_id), 0) + 1 FROM source_record"
    ).fetchone()[0]
    return f"{source_family.upper()}-{next_record_id:06d}"


def create_record(
    con: sqlite3.Connection,
    session_id: int,
    context_id: int,
    form_version_id: int,
    record_type: str,
    record_code: str
) -> int:
    return con.execute(
        """
        INSERT INTO source_record(
            session_id, context_id, form_version_id, record_type, record_code
        )
        VALUES (?, ?, ?, ?, ?)
        RETURNING record_id
        """,
        (session_id, context_id, form_version_id, record_type, record_code),
    ).fetchone()[0]


def create_pri(
    con: sqlite3.Connection,
    record_id: int,
    position_code: str,
    sequence_no: int = 1
) -> int:
    position_type_id = get_type_id(con, "position_type", position_code)
    position_id = con.execute(
        """
        INSERT INTO position_instance(record_id, position_type_id, sequence_no)
        VALUES (?, ?, ?)
        RETURNING position_id
        """,
        (record_id, position_type_id, sequence_no),
    ).fetchone()[0]
    return con.execute(
        "INSERT INTO pri(position_id) VALUES (?) RETURNING pri_id",
        (position_id,)
    ).fetchone()[0]


def create_event(
    con: sqlite3.Connection,
    record_id: int,
    event_code: str,
    sequence_no: int = 1
) -> int:
    event_type_id = get_type_id(con, "event_type", event_code)
    return con.execute(
        """
        INSERT INTO event(record_id, event_type_id, sequence_no)
        VALUES (?, ?, ?)
        RETURNING event_id
        """,
        (record_id, event_type_id, sequence_no),
    ).fetchone()[0]


def create_supporting_document(
    con: sqlite3.Connection,
    record_id: int,
    sequence_no: int = 1
) -> int:
    return con.execute(
        """
        INSERT INTO supporting_document(record_id, sequence_no)
        VALUES (?, ?)
        RETURNING document_id
        """,
        (record_id, sequence_no),
    ).fetchone()[0]


def save_value(
    con: sqlite3.Connection,
    field_code: str,
    owner_type: str,
    owner_id: int,
    raw_value=None,
    norm_value=None,
    sequence_no: int = 1,
    status: str | None = None,
    value_origin: str = "explicit",
    origin_owner_type: str | None = None,
    origin_owner_id: int | None = None,
    origin_field_code: str | None = None,
    notes: str | None = None,
) -> None:
    if isinstance(raw_value, bool):
        raw_value = "1" if raw_value else "0"
    elif raw_value is None:
        raw_value = ""
    else:
        raw_value = str(raw_value)

    if norm_value is not None:
        norm_value = str(norm_value)

    if status is None:
        status = "present" if (raw_value.strip() or (norm_value or "").strip()) else "blank"

    con.execute(
        """
        INSERT INTO field_value(
            field_code, owner_type, owner_id, sequence_no,
            value_status, raw_value, norm_value, value_origin,
            origin_owner_type, origin_owner_id, origin_field_code, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owner_type, owner_id, field_code, sequence_no)
        DO UPDATE SET
            value_status=excluded.value_status,
            raw_value=excluded.raw_value,
            norm_value=excluded.norm_value,
            value_origin=excluded.value_origin,
            origin_owner_type=excluded.origin_owner_type,
            origin_owner_id=excluded.origin_owner_id,
            origin_field_code=excluded.origin_field_code,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            field_code, owner_type, owner_id, sequence_no,
            status, raw_value, norm_value, value_origin,
            origin_owner_type, origin_owner_id, origin_field_code, notes
        ),
    )


def add_record_relation(
    con: sqlite3.Connection,
    pri_id: int,
    relation_code: str,
    record_id: int
) -> None:
    relation_type_id = get_type_id(con, "relation_type", relation_code)
    con.execute(
        """
        INSERT OR IGNORE INTO record_relation(
            pri_id, relation_type_id, record_id
        )
        VALUES (?, ?, ?)
        """,
        (pri_id, relation_type_id, record_id),
    )


def create_gid_for_birth(
    con: sqlite3.Connection,
    child_pri_id: int,
    birth_event_id: int
) -> tuple[int, str]:
    validate_birth_anchor(con, child_pri_id, birth_event_id)
    row = con.execute(
        "SELECT gid_id, gid_code, anchor_event_id FROM gid WHERE anchor_pri_id=?",
        (child_pri_id,),
    ).fetchone()
    if row:
        if row["anchor_event_id"] != birth_event_id:
            raise ValueError("This child already has a different birth anchor.")
        return row["gid_id"], row["gid_code"]

    next_id = con.execute(
        "SELECT COALESCE(MAX(gid_id),0)+1 FROM gid"
    ).fetchone()[0]

    code = f"GID-{next_id:06d}"

    con.execute(
        """
        INSERT INTO gid(gid_id, gid_code, anchor_pri_id, anchor_event_id, identity_uuid)
        VALUES (?, ?, ?, ?, ?)
        """,
        (next_id, code, child_pri_id, birth_event_id, new_identity_uuid()),
    )

    con.execute(
        """
        INSERT INTO pri_gid(pri_id, gid_id, link_role)
        VALUES (?, ?, 'anchor')
        """,
        (child_pri_id, next_id),
    )

    return next_id, code


def matching_birth_records(con, context_id, record_number):
    if not str(record_number or "").strip():
        return []
    return con.execute("""
        SELECT DISTINCT r.record_id, r.record_code FROM source_record r
        JOIN field_value v ON v.owner_type='RECORD' AND v.owner_id=r.record_id
        WHERE r.context_id=? AND r.record_type='NAS'
          AND v.field_code='record_number_raw' AND trim(v.raw_value)=?
        ORDER BY r.record_id
    """, (context_id, str(record_number).strip())).fetchall()


def field_meta(con: sqlite3.Connection, field_code: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT * FROM field_catalog WHERE field_code=?",
        (field_code,)
    ).fetchone()
    if not row:
        raise KeyError(f"Field not in catalog: {field_code}")
    return row
