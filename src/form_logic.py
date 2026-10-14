"""GUI-independent form definition identity."""
import hashlib
import json


def definition_payload(form):
    return json.dumps(form, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def definition_hash(form):
    return hashlib.sha256(definition_payload(form).encode("utf-8")).hexdigest()
