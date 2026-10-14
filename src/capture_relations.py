"""Explicit in-record identity, parent relationships and field references."""
import db


def add_relation(con, record_id, subject, relation, target, note):
    for pri in (subject, target):
        row = con.execute("SELECT p.record_id FROM pri pr JOIN position_instance p ON p.position_id=pr.position_id WHERE pr.pri_id=?", (pri,)).fetchone()
        if not row or row[0] != record_id:
            raise ValueError("Beziehungen dieses Akts müssen auf Personenpositionen desselben Akts verweisen.")
    role = db.get_type_id(con, "relation_type", relation)
    con.execute("""INSERT INTO pri_relation(
        record_id, subject_pri_id, relation_type_id, object_pri_id,
        explicit_in_source, inferred, notes
    ) VALUES (?, ?, ?, ?, 1, 0, ?)""", (record_id, subject, role, target, note))


def save_parent_relations(con, record_id, owners, father_is_declarant, father_confirmed, mother_confirmed):
    child = owners.get("child")
    if father_is_declarant:
        if not all(isinstance(owners.get(key), int) for key in ("father", "declarant", "child")):
            raise ValueError("Padre = Dichiarante benötigt die Abschnitte Padre, Dichiarante und Neonato/a.")
        add_relation(con, record_id, owners["father"], "same_person_in_record", owners["declarant"], "Identity explicitly confirmed during transcription; documentary positions retained.")
        father_confirmed = True
    for component, relation, confirmed in [("father", "father_of", father_confirmed), ("mother", "mother_of", mother_confirmed)]:
        if confirmed:
            if not isinstance(child, int) or not isinstance(owners.get(component), int):
                raise ValueError("Eine bestätigte Elternbeziehung benötigt Eltern- und Kindabschnitt.")
            add_relation(con, record_id, owners[component], relation, child, "Parent-child relationship explicitly confirmed from the source.")


def resolve_references(values, references):
    """Resolve explicit pointers, reject missing targets and cycles."""
    resolved = {}
    visiting = set()
    def visit(key):
        if key not in values:
            raise ValueError("Ein Feldbezug zeigt auf ein nicht vorhandenes Feld.")
        if key in visiting:
            raise ValueError("Feldbezüge bilden einen Kreis. Bitte den Bezug korrigieren.")
        if key in resolved:
            return resolved[key]
        visiting.add(key)
        source = references.get(key)
        value = visit(source) if source is not None else values[key]
        visiting.remove(key)
        if source is not None and not str(value or "").strip():
            raise ValueError("Das Bezugsfeld ist leer. Bitte den Ausgangswert erfassen oder den Bezug entfernen.")
        resolved[key] = value
        return value
    for key in references:
        visit(key)
    return resolved


def save_references(con, components, owners, fields, references):
    values = {(component, code): raw for component, entries in fields.items() for code, raw in entries.items()}
    resolved = resolve_references(values, references)
    types = {c["id"]: c["type"] for c in components}
    for target, source in references.items():
        comp, code = target
        source_comp, source_code = source
        if not isinstance(owners.get(comp), int) or not isinstance(owners.get(source_comp), int):
            raise ValueError("Feldbezüge auf wiederholbare Abschnitte sind noch nicht unterstützt.")
        db.save_value(con, code, types[comp], owners[comp],
            raw_value=values[target], norm_value=resolved[target], value_origin="inherited",
            origin_owner_type=types[source_comp], origin_owner_id=owners[source_comp],
            origin_field_code=source_code, notes="Explicit field reference selected by transcriber; RAW wording retained.")
