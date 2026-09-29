from pathlib import Path
import tempfile

import db

ROOT = Path(__file__).resolve().parents[1]
FORM_PATH = ROOT / "forms" / "nas_1809_alpha.json"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke.sqlite"
        db.init_db(db_path)

        form = db.load_form(FORM_PATH)

        with db.connect(db_path) as con:
            form_id = db.ensure_form_version(con, form)
            context_id = db.ensure_context(con, "NAS", "COR-NAS-1809")
            record_id = db.create_record(
                con, context_id, form_id, "NAS", "NAS-COR-1809-TEST"
            )

            child_pri = db.create_pri(con, record_id, "child")
            birth_event = db.create_event(con, record_id, "birth")

            db.save_value(con, "given_name_raw", "PRI", child_pri, "Giuseppe")
            db.save_value(con, "event_year_raw", "EVENT", birth_event, "1809")

            gid_id, gid_code = db.create_gid_for_birth(
                con, child_pri, birth_event
            )
            con.commit()

            counts = {}
            for table in [
                "source_context", "source_record", "pri",
                "event", "gid", "field_value"
            ]:
                counts[table] = con.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]

        print("Smoke test passed")
        print("Created:", gid_code)
        for table, count in counts.items():
            print(f"{table}: {count}")


if __name__ == "__main__":
    main()
