from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "schema_v0_2_alpha.sql"
FIELD_CATALOG_PATH = ROOT / "seed" / "field_catalog_v0_1.csv"
VOCAB_PATH = ROOT / "seed" / "vocabularies_v0_1.csv"
RUNTIME_DIR = ROOT / "runtime"
DB_PATH = RUNTIME_DIR / "ctc_alpha.sqlite"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        seed_field_catalog(con)
        seed_vocabularies(con)


def _yn(value: str) -> int:
    return 1 if (value or "").strip().lower() == "yes" else 0


def _entity(entity: str) -> str:
    mapping = {
        "SOURCE_CONTEXT": "SOURCE_CONTEXT",
        "PAGE/SHEET": "PAGE_SHEET",
        "RECORD": "RECORD",
        "PRI": "PRI",
        "EVENT": "EVENT",
        "REL": "REL",
        "SUPPORTING_DOCUMENT": "SUPPORTING_DOCUMENT",
        "PLACE": "PLACE",
        "SYSTEM": "SYSTEM",
    }
    return mapping[entity]


def seed_field_catalog(con: sqlite3.Connection) -> None:
    with FIELD_CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        for row in rows:
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
                    row["field_code"],
                    row["label"],
                    _entity(row["entity"]),
                    row["layer"],
                    row["semantic_type"],
                    row["default_widget"],
                    row["source_families"],
                    _yn(row["repeatable"]),
                    _yn(row["place_linkable"]),
                    _yn(row["form_selectable"]),
                    row["notes"],
                ),
            )


def seed_vocabularies(con: sqlite3.Connection) -> None:
    with VOCAB_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        for row in rows:
            vocab = row["vocabulary"]
            value = row["value"]
            notes = row["notes"]

            if vocab == "position_type":
                con.execute(
                    "INSERT OR IGNORE INTO position_type(code, label, notes) VALUES (?, ?, ?)",
                    (value, value.replace("_", " ").title(), notes),
                )
            elif vocab == "event_type":
                con.execute(
                    "INSERT OR IGNORE INTO event_type(code, label, notes) VALUES (?, ?, ?)",
                    (value, value.replace("_", " ").title(), notes),
                )
            elif vocab == "relation_type":
                con.execute(
                    "INSERT OR IGNORE INTO relation_type(code, label, notes) VALUES (?, ?, ?)",
                    (value, value.replace("_", " ").title(), notes),
                )


def load_form(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_form_version(con: sqlite3.Connection, form: dict) -> int:
    payload = json.dumps(form, ensure_ascii=False)
    con.execute(
        """
        INSERT INTO form_version (
            form_code, source_family, label, valid_from_year,
            valid_to_year, definition_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(form_code) DO UPDATE SET
            label=excluded.label,
            valid_from_year=excluded.valid_from_year,
            valid_to_year=excluded.valid_to_year,
            definition_json=excluded.definition_json
        """,
        (
            form["form_code"],
            form["source_family"],
            form["label"],
            form.get("valid_from_year"),
            form.get("valid_to_year"),
            payload,
        ),
    )
    return con.execute(
        "SELECT form_version_id FROM form_version WHERE form_code=?",
        (form["form_code"],),
    ).fetchone()[0]


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
        "relation_type": "relation_type_id",
    }[table]
    row = con.execute(
        f"SELECT {id_col} FROM {table} WHERE code=?",
        (code,),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown {table}: {code}")
    return row[0]


def create_record(
    con: sqlite3.Connection,
    context_id: int,
    form_version_id: int,
    record_type: str,
    record_code: str,
) -> int:
    cur = con.execute(
        """
        INSERT INTO source_record(
            context_id, form_version_id, record_type, record_code
        )
        VALUES (?, ?, ?, ?)
        """,
        (context_id, form_version_id, record_type, record_code),
    )
    return cur.lastrowid


def create_pri(
    con: sqlite3.Connection,
    record_id: int,
    position_code: str,
    sequence_no: int = 1,
) -> int:
    position_type_id = get_type_id(con, "position_type", position_code)
    cur = con.execute(
        """
        INSERT INTO position_instance(record_id, position_type_id, sequence_no)
        VALUES (?, ?, ?)
        """,
        (record_id, position_type_id, sequence_no),
    )
    position_id = cur.lastrowid
    return con.execute(
        "INSERT INTO pri(position_id) VALUES (?) RETURNING pri_id",
        (position_id,),
    ).fetchone()[0]


def create_event(
    con: sqlite3.Connection,
    record_id: int,
    event_code: str,
    sequence_no: int = 1,
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


def save_value(
    con: sqlite3.Connection,
    field_code: str,
    owner_type: str,
    owner_id: int,
    raw_value,
    sequence_no: int = 1,
    status: str | None = None,
) -> None:
    if isinstance(raw_value, bool):
        raw_value = "1" if raw_value else "0"
    elif raw_value is None:
        raw_value = ""
    else:
        raw_value = str(raw_value)

    if status is None:
        status = "present" if raw_value.strip() else "blank"

    con.execute(
        """
        INSERT INTO field_value(
            field_code, owner_type, owner_id, sequence_no,
            value_status, raw_value
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(owner_type, owner_id, field_code, sequence_no)
        DO UPDATE SET
            value_status=excluded.value_status,
            raw_value=excluded.raw_value,
            updated_at=CURRENT_TIMESTAMP
        """,
        (field_code, owner_type, owner_id, sequence_no, status, raw_value),
    )


def add_record_relation(
    con: sqlite3.Connection,
    pri_id: int,
    relation_code: str,
    record_id: int,
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
    birth_event_id: int,
) -> tuple[int, str]:
    existing = con.execute(
        "SELECT gid_id, gid_code FROM gid WHERE anchor_pri_id=?",
        (child_pri_id,),
    ).fetchone()
    if existing:
        return existing["gid_id"], existing["gid_code"]

    next_id = con.execute(
        "SELECT COALESCE(MAX(gid_id), 0) + 1 FROM gid"
    ).fetchone()[0]
    code = f"GID-{next_id:06d}"

    con.execute(
        """
        INSERT INTO gid(gid_id, gid_code, anchor_pri_id, anchor_event_id)
        VALUES (?, ?, ?, ?)
        """,
        (next_id, code, child_pri_id, birth_event_id),
    )
    con.execute(
        """
        INSERT INTO pri_gid(pri_id, gid_id, link_role)
        VALUES (?, ?, 'anchor')
        """,
        (child_pri_id, next_id),
    )
    return next_id, code


def field_meta(con: sqlite3.Connection, field_code: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT * FROM field_catalog WHERE field_code=?",
        (field_code,),
    ).fetchone()
    if not row:
        raise KeyError(f"Field not in catalog: {field_code}")
    return row
