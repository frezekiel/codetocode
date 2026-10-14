-- CtC schema v0.4-alpha
-- Controlled-vibe-coding iteration after two real NAS capture passes.
--
-- Main additions:
-- * transcription_session remains first-class
-- * field_value gains provenance/origin metadata
-- * stable relational core still separates form metadata from captured values
--
-- This is still an alpha stress-test schema, not the frozen final schema.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transcription_session (
    session_id          INTEGER PRIMARY KEY,
    transcriber         TEXT NOT NULL,
    transcription_date  TEXT NOT NULL,
    project_collection  TEXT,
    session_note        TEXT,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS form_version (
    form_version_id   INTEGER PRIMARY KEY,
    form_code         TEXT NOT NULL UNIQUE,
    source_family     TEXT NOT NULL CHECK (source_family IN ('NAS','MAT','MOR','MIG')),
    label             TEXT NOT NULL,
    valid_from_year   INTEGER,
    valid_to_year     INTEGER,
    definition_json   TEXT NOT NULL,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_context (
    context_id       INTEGER PRIMARY KEY,
    source_family    TEXT NOT NULL CHECK (source_family IN ('NAS','MAT','MOR','MIG')),
    context_code     TEXT NOT NULL UNIQUE,
    label            TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_page (
    page_id           INTEGER PRIMARY KEY,
    context_id        INTEGER NOT NULL REFERENCES source_context(context_id) ON DELETE CASCADE,
    page_sequence_no  INTEGER,
    notes             TEXT,
    UNIQUE (context_id, page_sequence_no)
);

CREATE TABLE IF NOT EXISTS source_record (
    record_id         INTEGER PRIMARY KEY,
    session_id        INTEGER NOT NULL REFERENCES transcription_session(session_id) ON DELETE RESTRICT,
    context_id        INTEGER NOT NULL REFERENCES source_context(context_id) ON DELETE CASCADE,
    page_id           INTEGER REFERENCES source_page(page_id) ON DELETE SET NULL,
    form_version_id   INTEGER NOT NULL REFERENCES form_version(form_version_id) ON DELETE RESTRICT,
    record_type       TEXT NOT NULL CHECK (record_type IN ('NAS','MAT','MOR','MIG')),
    record_code       TEXT NOT NULL UNIQUE,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS position_type (
    position_type_id  INTEGER PRIMARY KEY,
    code              TEXT NOT NULL UNIQUE,
    label             TEXT NOT NULL,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS position_instance (
    position_id       INTEGER PRIMARY KEY,
    record_id         INTEGER NOT NULL REFERENCES source_record(record_id) ON DELETE CASCADE,
    position_type_id  INTEGER NOT NULL REFERENCES position_type(position_type_id),
    sequence_no       INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    UNIQUE (record_id, position_type_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS pri (
    pri_id             INTEGER PRIMARY KEY,
    position_id        INTEGER NOT NULL UNIQUE REFERENCES position_instance(position_id) ON DELETE CASCADE,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS event_type (
    event_type_id     INTEGER PRIMARY KEY,
    code              TEXT NOT NULL UNIQUE,
    label             TEXT NOT NULL,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS event (
    event_id           INTEGER PRIMARY KEY,
    record_id          INTEGER NOT NULL REFERENCES source_record(record_id) ON DELETE CASCADE,
    event_type_id      INTEGER NOT NULL REFERENCES event_type(event_type_id),
    sequence_no        INTEGER NOT NULL DEFAULT 1,
    notes              TEXT,
    UNIQUE (record_id, event_type_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS relation_type (
    relation_type_id  INTEGER PRIMARY KEY,
    code              TEXT NOT NULL UNIQUE,
    label             TEXT NOT NULL,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS pri_relation (
    pri_relation_id       INTEGER PRIMARY KEY,
    record_id             INTEGER NOT NULL REFERENCES source_record(record_id) ON DELETE CASCADE,
    subject_pri_id        INTEGER NOT NULL REFERENCES pri(pri_id) ON DELETE CASCADE,
    relation_type_id      INTEGER NOT NULL REFERENCES relation_type(relation_type_id),
    object_pri_id         INTEGER NOT NULL REFERENCES pri(pri_id) ON DELETE CASCADE,
    relation_raw          TEXT,
    relation_subtype_norm TEXT,
    explicit_in_source    INTEGER NOT NULL DEFAULT 1 CHECK (explicit_in_source IN (0,1)),
    inferred              INTEGER NOT NULL DEFAULT 0 CHECK (inferred IN (0,1)),
    notes                 TEXT,
    CHECK (subject_pri_id <> object_pri_id)
);

CREATE TABLE IF NOT EXISTS record_relation (
    record_relation_id  INTEGER PRIMARY KEY,
    pri_id              INTEGER NOT NULL REFERENCES pri(pri_id) ON DELETE CASCADE,
    relation_type_id    INTEGER NOT NULL REFERENCES relation_type(relation_type_id),
    record_id           INTEGER NOT NULL REFERENCES source_record(record_id) ON DELETE CASCADE,
    relation_raw        TEXT,
    explicit_in_source  INTEGER NOT NULL DEFAULT 1 CHECK (explicit_in_source IN (0,1)),
    inferred            INTEGER NOT NULL DEFAULT 0 CHECK (inferred IN (0,1)),
    notes               TEXT,
    UNIQUE (pri_id, relation_type_id, record_id)
);

CREATE TABLE IF NOT EXISTS place (
    place_id          INTEGER PRIMARY KEY,
    place_name_norm   TEXT NOT NULL,
    place_type        TEXT,
    parent_place_id   INTEGER REFERENCES place(place_id) ON DELETE SET NULL,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS supporting_document (
    document_id       INTEGER PRIMARY KEY,
    record_id         INTEGER NOT NULL REFERENCES source_record(record_id) ON DELETE CASCADE,
    sequence_no       INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    UNIQUE (record_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS field_catalog (
    field_code        TEXT PRIMARY KEY,
    label             TEXT NOT NULL,
    entity_type       TEXT NOT NULL CHECK (
        entity_type IN (
            'SOURCE_CONTEXT','PAGE_SHEET','RECORD','PRI',
            'EVENT','REL','SUPPORTING_DOCUMENT','PLACE','SYSTEM'
        )
    ),
    layer             TEXT NOT NULL CHECK (
        layer IN ('RAW','NORM','SYSTEM','SOURCE_DERIVED')
    ),
    semantic_type     TEXT NOT NULL,
    default_widget    TEXT,
    source_families   TEXT,
    repeatable        INTEGER NOT NULL DEFAULT 0 CHECK (repeatable IN (0,1)),
    place_linkable    INTEGER NOT NULL DEFAULT 0 CHECK (place_linkable IN (0,1)),
    form_selectable   INTEGER NOT NULL DEFAULT 1 CHECK (form_selectable IN (0,1)),
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS field_value (
    value_id          INTEGER PRIMARY KEY,
    field_code        TEXT NOT NULL REFERENCES field_catalog(field_code),
    owner_type        TEXT NOT NULL CHECK (
        owner_type IN (
            'SOURCE_CONTEXT','PAGE_SHEET','RECORD','PRI',
            'EVENT','REL','SUPPORTING_DOCUMENT','PLACE','SYSTEM'
        )
    ),
    owner_id          INTEGER NOT NULL,
    sequence_no       INTEGER NOT NULL DEFAULT 1,

    value_status      TEXT NOT NULL DEFAULT 'present'
                      CHECK (value_status IN ('present','blank','illegible','not_applicable')),

    -- RAW is what the source explicitly says.
    raw_value         TEXT,

    -- NORM may hold a normalized, inherited-resolved, or inferred value.
    norm_value        TEXT,

    -- Provenance of the value shown/stored at this owner.
    value_origin      TEXT NOT NULL DEFAULT 'explicit'
                      CHECK (value_origin IN ('explicit','inherited','inferred','default','system')),

    origin_owner_type TEXT,
    origin_owner_id   INTEGER,
    origin_field_code TEXT,

    place_id          INTEGER REFERENCES place(place_id) ON DELETE SET NULL,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (owner_type, owner_id, field_code, sequence_no)
);

CREATE TABLE IF NOT EXISTS mid (
    mid_id            INTEGER PRIMARY KEY,
    mid_code          TEXT NOT NULL UNIQUE,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pri_mid (
    pri_id            INTEGER PRIMARY KEY REFERENCES pri(pri_id) ON DELETE CASCADE,
    mid_id            INTEGER NOT NULL REFERENCES mid(mid_id) ON DELETE CASCADE,
    assigned_by       TEXT,
    assigned_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS gid (
    gid_id            INTEGER PRIMARY KEY,
    gid_code          TEXT NOT NULL UNIQUE,
    anchor_pri_id     INTEGER NOT NULL UNIQUE REFERENCES pri(pri_id) ON DELETE RESTRICT,
    anchor_event_id   INTEGER NOT NULL UNIQUE REFERENCES event(event_id) ON DELETE RESTRICT,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS pri_gid (
    pri_id            INTEGER PRIMARY KEY REFERENCES pri(pri_id) ON DELETE CASCADE,
    gid_id            INTEGER NOT NULL REFERENCES gid(gid_id) ON DELETE RESTRICT,
    link_role         TEXT NOT NULL DEFAULT 'linked'
                      CHECK (link_role IN ('anchor','linked')),
    linked_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS mid_gid (
    mid_id            INTEGER PRIMARY KEY REFERENCES mid(mid_id) ON DELETE CASCADE,
    gid_id            INTEGER NOT NULL UNIQUE REFERENCES gid(gid_id) ON DELETE RESTRICT,
    linked_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes             TEXT
);

CREATE INDEX IF NOT EXISTS idx_record_session ON source_record(session_id);
CREATE INDEX IF NOT EXISTS idx_record_context ON source_record(context_id);
CREATE INDEX IF NOT EXISTS idx_position_record ON position_instance(record_id);
CREATE INDEX IF NOT EXISTS idx_event_record ON event(record_id);
CREATE INDEX IF NOT EXISTS idx_field_value_owner ON field_value(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_field_value_code ON field_value(field_code);
CREATE INDEX IF NOT EXISTS idx_field_value_origin ON field_value(value_origin);
CREATE INDEX IF NOT EXISTS idx_pri_mid_mid ON pri_mid(mid_id);

-- Architectural rules:
-- * New historical variation should normally require form metadata, not ALTER TABLE.
-- * structurally absent is represented by the form definition, not by a value row.
-- * RAW is never overwritten.
-- * inherited/inferred/default values retain provenance.
-- * Position != relation.
-- * RECORD date/time/place != EVENT date/time/place.
-- * Every captured birth creates a GID.
