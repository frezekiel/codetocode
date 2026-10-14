"""Regression tests for immutable definitions and lossless migration."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import db


class FormVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "test.sqlite"
        self.form = db.load_form(db.ROOT / "forms/nas_1809_alpha_v3.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_versions_and_record_reference(self):
        db.init_db(self.path)
        with db.connect(self.path) as con:
            first = db.ensure_form_version(con, self.form)
            # Dictionary ordering must not manufacture a new revision.
            self.assertEqual(first, db.ensure_form_version(con, dict(reversed(list(self.form.items())))))
            session = db.create_session(con, "test", "2026-10-05")
            context = db.ensure_context(con, "NAS", "TEST")
            record = db.create_record(con, session, context, first, "NAS", "NAS-TEST")
            changed = copy.deepcopy(self.form)
            changed["components"][0]["fields"].append({"field_code": "street_raw"})
            second = db.ensure_form_version(con, changed)
            self.assertNotEqual(first, second)
            self.assertEqual(first, con.execute("SELECT form_version_id FROM source_record WHERE record_id=?", (record,)).fetchone()[0])
            self.assertEqual(self.form, json.loads(con.execute("SELECT definition_json FROM form_version WHERE form_version_id=?", (first,)).fetchone()[0]))
            self.assertEqual([1, 2], [r[0] for r in con.execute("SELECT version_no FROM form_version ORDER BY version_no")])
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE form_version SET label='changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM form_version")

    def test_legacy_migration_preserves_every_table(self):
        with db.connect(self.path) as con:
            con.executescript((db.ROOT / "schema/schema_v0_4_alpha.sql").read_text(encoding="utf-8"))
            db.seed_field_catalog(con)
            db.seed_vocabularies(con)
            con.execute("INSERT INTO form_version(form_version_id,form_code,source_family,label,definition_json) VALUES (42,?,?,?,?)", (self.form["form_code"], "NAS", self.form["label"], json.dumps(self.form)))
            session = db.create_session(con, "test", "2026-10-05")
            context = db.ensure_context(con, "NAS", "LEGACY")
            db.create_record(con, session, context, 42, "NAS", "NAS-LEGACY")
        db.init_db(self.path)
        backups = list((self.root / "backups").glob("*.sqlite"))
        self.assertEqual(1, len(backups))
        with db.connect(self.path) as con, db.connect(backups[0]) as old:
            tables = [r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                if table == "form_version":
                    columns = [r[1] for r in old.execute("PRAGMA table_info(form_version)")]
                    query = "SELECT " + ",".join(columns) + " FROM form_version"
                else:
                    query = f'SELECT * FROM "{table}"'
                self.assertEqual([tuple(r) for r in old.execute(query)], [tuple(r) for r in con.execute(query)], table)
            self.assertFalse(con.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual(42, db.ensure_form_version(con, self.form))
        db.init_db(self.path)
        self.assertEqual(1, len(list((self.root / "backups").glob("*.sqlite"))))

    def test_json_revisions_do_not_overwrite(self):
        db.init_db(self.path)
        original_connect = db.connect
        with patch.object(db, "ROOT", self.root), patch.object(db, "connect", lambda: original_connect(self.path)):
            first = db.save_form_revision(self.form)
            original = first.read_bytes()
            self.assertEqual(first, db.save_form_revision(self.form))
            changed = copy.deepcopy(self.form)
            changed["label"] += " revised"
            second = db.save_form_revision(changed)
            self.assertNotEqual(first, second)
            self.assertEqual(original, first.read_bytes())

    def test_failed_migration_rolls_back(self):
        with db.connect(self.path) as con:
            con.executescript((db.ROOT / "schema/schema_v0_4_alpha.sql").read_text(encoding="utf-8"))
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("INSERT INTO source_record(session_id,context_id,form_version_id,record_type,record_code) VALUES (999,999,999,'NAS','broken')")
        with self.assertRaises(RuntimeError):
            db.init_db(self.path)
        with db.connect(self.path) as con:
            self.assertNotIn("definition_hash", [r[1] for r in con.execute("PRAGMA table_info(form_version)")])
            self.assertEqual("broken", con.execute("SELECT record_code FROM source_record").fetchone()[0])
            self.assertEqual(0, con.execute("PRAGMA user_version").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
