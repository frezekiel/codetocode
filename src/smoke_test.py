from pathlib import Path
import sqlite3
import tempfile

import db
from app import derive_context_code

ROOT = Path(__file__).resolve().parents[1]
NAS_FORM = ROOT / "forms" / "nas_1809_alpha_v3.json"
MIG_FORM = ROOT / "forms" / "mig_manifest_starter_v1.json"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke.sqlite"
        db.init_db(db_path)
        nas_form = db.load_form(NAS_FORM)
        mig_form = db.load_form(MIG_FORM)

        nas_positions = {
            c.get("position_type")
            for c in nas_form["components"]
            if c.get("type") == "PRI"
        }
        assert "declarant" in nas_positions
        assert "father" in nas_positions
        assert "mother" in nas_positions
        assert "child" in nas_positions

        auto_context_code = derive_context_code(
            nas_form,
            {
                "comune_universita_raw": "Cortale",
                "register_year_raw": "1809",
            },
        )
        assert auto_context_code == "COR_NAS_1809"

        with db.connect(db_path) as con:
            session_id = db.create_session(
                con,
                "Test Transcriber",
                "2026-09-30"
            )

            nas_form_id = db.ensure_form_version(con, nas_form)
            db.ensure_form_version(con, mig_form)

            context_id = db.ensure_context(
                con,
                "NAS",
                "COR-NAS-1809"
            )

            db.save_value(
                con,
                "comune_universita_raw",
                "SOURCE_CONTEXT",
                context_id,
                raw_value="Cortale"
            )

            generated_code = db.next_record_code(con, "NAS")
            assert generated_code == "NAS-000001"

            record_id = db.create_record(
                con,
                session_id,
                context_id,
                nas_form_id,
                "NAS",
                generated_code
            )

            db.save_value(
                con,
                "record_place_raw",
                "RECORD",
                record_id,
                raw_value="",
                norm_value="Cortale",
                value_origin="inherited",
                origin_owner_type="SOURCE_CONTEXT",
                origin_owner_id=context_id,
                origin_field_code="comune_universita_raw"
            )

            declarant = db.create_pri(con, record_id, "declarant")
            child = db.create_pri(con, record_id, "child")
            birth = db.create_event(con, record_id, "birth")

            db.save_value(
                con,
                "surname_raw",
                "PRI",
                declarant,
                raw_value="Bilotta"
            )

            db.save_value(
                con,
                "surname_norm",
                "PRI",
                child,
                raw_value="",
                norm_value="Bilotta",
                value_origin="inferred",
                notes="child_surname_from_declarant_alpha"
            )

            _, gid_code = db.create_gid_for_birth(con, child, birth)
            con.commit()

            assert con.execute(
                "SELECT COUNT(*) FROM transcription_session"
            ).fetchone()[0] == 1

            assert con.execute(
                "SELECT COUNT(*) FROM gid"
            ).fetchone()[0] == 1

            inherited = con.execute(
                """
                SELECT raw_value, norm_value, value_origin
                FROM field_value
                WHERE owner_type='RECORD'
                  AND owner_id=?
                  AND field_code='record_place_raw'
                """,
                (record_id,)
            ).fetchone()

            assert inherited["raw_value"] == ""
            assert inherited["norm_value"] == "Cortale"
            assert inherited["value_origin"] == "inherited"

            inferred = con.execute(
                """
                SELECT norm_value, value_origin
                FROM field_value
                WHERE owner_type='PRI'
                  AND owner_id=?
                  AND field_code='surname_norm'
                """,
                (child,)
            ).fetchone()

            assert inferred["norm_value"] == "Bilotta"
            assert inferred["value_origin"] == "inferred"

            for field_code in (
                "departure_date_raw",
                "departure_port_raw",
                "arrival_date_raw",
                "arrival_port_raw",
            ):
                row = con.execute(
                    "SELECT entity_type, source_families FROM field_catalog WHERE field_code=?",
                    (field_code,)
                ).fetchone()
                assert row is not None
                assert row["entity_type"] == "SOURCE_CONTEXT"
                assert row["source_families"] == "MIG"

            assert any(
                c.get("type") == "PRI" and c.get("position_type") == "migrant"
                for c in mig_form["components"]
            )

        try:
            con.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            pass
        else:
            raise AssertionError("Database connection remained open after context exit")

        print("Smoke test passed")
        print("Database connection closure: OK")
        print("NAS declarant/father/mother separation: OK")
        print("Auto context code:", auto_context_code)
        print("Auto record code: OK")
        print("Created:", gid_code)
        print("Inherited provenance: OK")
        print("Inferred surname provenance: OK")
        print("MIG voyage context fields: OK")
        print("MIG starter migrant component: OK")


if __name__ == "__main__":
    main()
