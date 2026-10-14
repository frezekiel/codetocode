import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import UUID

import db
from identity import validate_birth_form


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.sqlite"
        self.form = db.load_form(db.ROOT / "forms/nas_1809_alpha_v3.json")

    def tearDown(self):
        self.tmp.cleanup()

    def make_birth(self, con, code="NAS-TEST", role="child"):
        form_id = db.ensure_form_version(con, self.form)
        session = db.create_session(con, "test", "2026-10-06")
        context = db.ensure_context(con, "NAS", "TEST")
        record = db.create_record(con, session, context, form_id, "NAS", code)
        child = db.create_pri(con, record, role)
        birth = db.create_event(con, record, "birth")
        return record, child, birth, context

    def test_unknown_names_allowed_and_anchor_idempotent(self):
        db.init_db(self.path)
        with db.connect(self.path) as con:
            _, child, birth, _ = self.make_birth(con)
            first = db.create_gid_for_birth(con, child, birth)
            self.assertEqual(first, db.create_gid_for_birth(con, child, birth))
            row = con.execute("SELECT * FROM gid").fetchone()
            self.assertEqual(4, UUID(row["identity_uuid"]).version)
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE gid SET identity_uuid=?", (str(UUID(int=1)),))
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM gid")

    def test_wrong_record_and_role_rejected(self):
        db.init_db(self.path)
        with db.connect(self.path) as con:
            _, child, birth, _ = self.make_birth(con, "NAS-A")
            _, father, other_birth, _ = self.make_birth(con, "NAS-B", "father")
            for pri, event in [(child, other_birth), (father, birth)]:
                with self.assertRaises(ValueError):
                    db.create_gid_for_birth(con, pri, event)
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO gid(gid_code,anchor_pri_id,anchor_event_id,identity_uuid) VALUES ('bad',?,?,?)", (father, birth, str(UUID(int=2))))

    def test_form_structure_not_name_validation(self):
        self.assertTrue(validate_birth_form(self.form)[0])
        changed = copy.deepcopy(self.form)
        changed["components"] = [c for c in changed["components"] if c.get("position_type") != "child"]
        self.assertFalse(validate_birth_form(changed)[0])
        changed["source_family"] = "MOR"
        self.assertTrue(validate_birth_form(changed)[0])

    def test_duplicate_lookup(self):
        db.init_db(self.path)
        with db.connect(self.path) as con:
            record, _, _, context = self.make_birth(con)
            db.save_value(con, "record_number_raw", "RECORD", record, raw_value="8")
            self.assertEqual(record, db.matching_birth_records(con, context, " 8 ")[0]["record_id"])
            self.assertFalse(db.matching_birth_records(con, context, "9"))
            self.assertFalse(db.matching_birth_records(con, context, ""))

    def test_uuid_survives_copy(self):
        db.init_db(self.path)
        clone = self.path.parent / "copy.sqlite"
        with db.connect(self.path) as con:
            _, child, birth, _ = self.make_birth(con)
            db.create_gid_for_birth(con, child, birth)
        with db.connect(self.path) as con, db.connect(clone) as target:
            con.backup(target)
            original = con.execute("SELECT identity_uuid FROM gid").fetchone()[0]
        db.init_db(clone)
        with db.connect(clone) as con:
            self.assertEqual(original, con.execute("SELECT identity_uuid FROM gid").fetchone()[0])

    def test_existing_gid_migration_preserves_anchor(self):
        with db.connect(self.path) as con:
            con.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
            db.seed_field_catalog(con); db.seed_vocabularies(con)
            _, child, birth, _ = self.make_birth(con)
            con.execute("INSERT INTO gid(gid_id,gid_code,anchor_pri_id,anchor_event_id) VALUES (7,'GID-000007',?,?)", (child, birth))
            con.execute("INSERT INTO pri_gid VALUES (?,7,'anchor',CURRENT_TIMESTAMP,NULL)", (child,))
            con.execute("PRAGMA user_version=1")
        db.init_db(self.path)
        with db.connect(self.path) as con:
            row = con.execute("SELECT * FROM gid").fetchone()
            self.assertEqual((7, "GID-000007", child, birth), tuple(row[key] for key in ["gid_id", "gid_code", "anchor_pri_id", "anchor_event_id"]))
            original_uuid = row["identity_uuid"]
            self.assertFalse(con.execute("PRAGMA foreign_key_check").fetchall())
        db.init_db(self.path)
        with db.connect(self.path) as con:
            self.assertEqual(original_uuid, con.execute("SELECT identity_uuid FROM gid").fetchone()[0])
        self.assertEqual(1, len(list((self.path.parent / "backups").glob("*before_v2*.sqlite"))))


if __name__ == "__main__":
    unittest.main()
