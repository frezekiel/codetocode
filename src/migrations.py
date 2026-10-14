"""Transactional, backed-up migration of the v0.4 form version table."""
from datetime import datetime
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import uuid

from form_logic import definition_hash

SCHEMA_VERSION = 2


def migrate(con, db_path):
    current = con.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError("This database was created by a newer CtC version.")
    columns = {r[1] for r in con.execute("PRAGMA table_info(form_version)")}
    if not columns or "definition_hash" in columns:
        return
    rows = con.execute("SELECT * FROM form_version ORDER BY form_version_id").fetchall()
    # Parse all definitions before touching the source database.
    hashes = [definition_hash(json.loads(r["definition_json"])) for r in rows]
    path = Path(db_path)
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.stem}_before_v1_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.sqlite"
    with closing(sqlite3.connect(backup_path)) as backup:
        con.backup(backup)
    con.execute("PRAGMA foreign_keys = OFF")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE form_version_new (
            form_version_id INTEGER PRIMARY KEY,
            form_code TEXT NOT NULL,
            version_no INTEGER NOT NULL DEFAULT 1,
            definition_hash TEXT NOT NULL,
            source_family TEXT NOT NULL CHECK(source_family IN ('NAS','MAT','MOR','MIG')),
            label TEXT NOT NULL, valid_from_year INTEGER, valid_to_year INTEGER,
            definition_json TEXT NOT NULL, notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(form_code, version_no), UNIQUE(form_code, definition_hash))""")
        for row, digest in zip(rows, hashes):
            con.execute("""INSERT INTO form_version_new VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["form_version_id"], row["form_code"], digest,
                 row["source_family"], row["label"], row["valid_from_year"],
                 row["valid_to_year"], row["definition_json"], row["notes"], row["created_at"]))
        con.execute("DROP TABLE form_version")
        con.execute("ALTER TABLE form_version_new RENAME TO form_version")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Migration failed foreign-key validation; original database retained.")
        con.execute("PRAGMA user_version = 1")
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys = ON")


def protect_versions(con):
    con.executescript("""
        CREATE TRIGGER IF NOT EXISTS immutable_form_update
        BEFORE UPDATE ON form_version BEGIN
            SELECT RAISE(ABORT, 'Form versions are immutable; create a new version');
        END;
        CREATE TRIGGER IF NOT EXISTS immutable_form_delete
        BEFORE DELETE ON form_version BEGIN
            SELECT RAISE(ABORT, 'Form versions cannot be deleted');
        END;
    """)
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def migrate_identity(con, db_path, backup_required=False):
    columns = {r[1] for r in con.execute("PRAGMA table_info(gid)")}
    if "identity_uuid" in columns:
        return
    if backup_required:
        path = Path(db_path)
        directory = path.parent / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        backup_path = directory / f"{path.stem}_before_v2_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.sqlite"
        with closing(sqlite3.connect(backup_path)) as backup:
            con.backup(backup)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("ALTER TABLE gid ADD COLUMN identity_uuid TEXT")
        for row in con.execute("SELECT gid_id FROM gid").fetchall():
            con.execute("UPDATE gid SET identity_uuid=? WHERE gid_id=?", (str(uuid.uuid4()), row[0]))
        con.execute("CREATE UNIQUE INDEX idx_gid_uuid ON gid(identity_uuid)")
        con.execute("""CREATE TRIGGER require_gid_uuid BEFORE INSERT ON gid
            WHEN NEW.identity_uuid IS NULL OR length(NEW.identity_uuid) != 36
            BEGIN SELECT RAISE(ABORT, 'A permanent GID UUID is required'); END""")
        con.execute("""CREATE TRIGGER immutable_gid_identity
            BEFORE UPDATE OF gid_id, gid_code, identity_uuid, anchor_pri_id, anchor_event_id ON gid
            BEGIN SELECT RAISE(ABORT, 'GID identity and birth anchors are immutable'); END""")
        con.execute("""CREATE TRIGGER preserve_gid BEFORE DELETE ON gid
            BEGIN SELECT RAISE(ABORT, 'Birth anchors cannot be deleted'); END""")
        con.execute("""CREATE TRIGGER validate_gid_birth BEFORE INSERT ON gid
            WHEN NOT EXISTS (
                SELECT 1 FROM pri pr JOIN position_instance p ON p.position_id=pr.position_id
                JOIN position_type t ON t.position_type_id=p.position_type_id
                JOIN source_record r ON r.record_id=p.record_id
                JOIN event e ON e.event_id=NEW.anchor_event_id AND e.record_id=r.record_id
                JOIN event_type et ON et.event_type_id=e.event_type_id
                WHERE pr.pri_id=NEW.anchor_pri_id AND t.code='child'
                  AND et.code='birth' AND r.record_type='NAS')
            BEGIN SELECT RAISE(ABORT, 'GID must anchor a child and birth in the same NAS record'); END""")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Identity migration failed foreign-key validation.")
        con.execute("PRAGMA user_version = 2")
        con.commit()
    except BaseException:
        con.rollback()
        raise
