"""Birth-anchor rules independent of Tkinter."""
from uuid import uuid4


def new_identity_uuid():
    return str(uuid4())


def validate_birth_form(form):
    if form.get("source_family") != "NAS":
        return True, ""
    components = form.get("components", [])
    children = [c for c in components if c.get("type") == "PRI" and c.get("position_type") == "child"]
    births = [c for c in components if c.get("type") == "EVENT" and c.get("event_type") == "birth"]
    if len(children) != 1 or len(births) != 1:
        return False, "Ein NAS-Formular benötigt genau einen Abschnitt Neonato/a und ein Ereignis Nascita. Unbekannte Namen oder Eltern dürfen leer bleiben. Mehrlingsgeburten benötigen einen eigenen Erfassungsablauf."
    if children[0].get("repeatable") or births[0].get("repeatable"):
        return False, "Kind und Geburtsereignis dürfen im aktuellen NAS-Ablauf nicht wiederholbar sein. Mehrlinge werden noch nicht als gemeinsamer Akt unterstützt."
    return True, ""


def validate_birth_anchor(con, child_pri_id, birth_event_id):
    row = con.execute("""
        SELECT p.record_id AS child_record, t.code AS role,
               e.record_id AS event_record, et.code AS event_type, r.record_type
        FROM pri pr JOIN position_instance p ON p.position_id=pr.position_id
        JOIN position_type t ON t.position_type_id=p.position_type_id
        JOIN source_record r ON r.record_id=p.record_id
        JOIN event e ON e.event_id=?
        JOIN event_type et ON et.event_type_id=e.event_type_id
        WHERE pr.pri_id=?
    """, (birth_event_id, child_pri_id)).fetchone()
    if not row or row["role"] != "child" or row["event_type"] != "birth" or row["record_type"] != "NAS" or row["child_record"] != row["event_record"]:
        raise ValueError("Eine GID benötigt Kind und Geburtsereignis desselben NAS-Akts.")
