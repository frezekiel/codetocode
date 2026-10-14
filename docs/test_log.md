# CtC test log

## Alpha v0.1 → v0.2

### Observation
The application opened directly into NAS 1809.

**Classification:** workflow / form-selection problem.

**Decision:** three-stage wizard:
Session → Source/Form → Capture.

### Observation
Legibility defaulted to 4.

**Classification:** metadata / UI problem.

**Decision:** no default; descriptive scale 1–5.

### Observation
Transcription metadata were missing.

**Classification:** provenance / schema problem.

**Decision:** add first-class `transcription_session`.

---

## Alpha v0.2 → v0.3

### Observation
The existing Form Builder could only remove fields from the already-defined NAS structure. It could not create a structurally different source family such as MIG.

**Classification:** Form Builder / architecture problem.

**Decision:** add a structure builder that can:
- create a blank form version;
- choose NAS / MAT / MOR / MIG;
- add/remove/reorder PRI, EVENT and SUPPORTING_DOCUMENT components;
- choose position/event types;
- set repeatability and default instances;
- assign fields from the master field catalog;
- reorder fields;
- set simple field defaults.

### Observation
The atto could only be changed by returning to the source/form page.

**Classification:** capture workflow problem.

**Decision:** add `Edit atto form…` directly on the capture page. Current unsaved values are preserved when the form is edited and re-rendered.

### Observation
`record_place_raw = Cortale` was really inherited from the register context rather than explicitly written as that raw value in the individual record.

**Classification:** provenance problem.

**Decision:** support field-level origin:
`explicit / inherited / inferred / default / system`.

For inherited values, RAW can remain blank while the resolved value is stored separately with provenance.

### Observation
The child's surname may be inferred rather than explicitly written.

**Classification:** RAW vs inference problem.

**Decision:** keep `surname_raw` empty unless explicitly present. The NAS alpha can create `surname_norm` as an inferred value from the declarant surname, with a visible toggle and provenance. This is an alpha rule and remains revisable.

### Observation
Child sex must not be preselected.

**Classification:** form-default problem.

**Decision:** blank initial choice; `maschio` / `femmina` selectable.

### Observation
Witness age unit appeared as `mesi` despite the intended default `anni`.

**Classification:** UI / combobox-scroll problem.

**Decision:** `anni` remains the form default; controlled comboboxes are readonly and mouse-wheel changes are blocked to avoid accidental value changes while scrolling.

### Observation
`Save & next` left the user at the bottom of the form.

**Classification:** serial-capture UX problem.

**Decision:** after save, clear record values, retain session/context, scroll to the top, and focus the first record field.


---

## Alpha v0.3 → v0.4

### Observation
A newly created MIG form could contain only source context and record fields, while the interface looked as though another passenger-entry screen should follow.

**Classification:** Form Builder / validation problem.

**Decision:** blank MIG forms receive a starter scaffold and capture is blocked unless a migrant component with fields exists.

### Observation
Departure/arrival dates and ports belong to the voyage/manifest context rather than every passenger row.

**Classification:** source-context modeling problem.

**Decision:** add voyage-level MIG source-context fields for departure/arrival dates and ports.

### Observation
Back-navigation and keyboard-only capture were incomplete.

**Classification:** navigation / serial-capture UX problem.

**Decision:** preserve drafts across Back/Forward, use Enter for page progression and field progression where appropriate, and allow direct 1–5 legibility selection.

### Observation
Field-by-field selection in the Form Builder is inefficient.

**Classification:** Form Builder efficiency problem.

**Decision:** extended selection with Ctrl/Shift/Ctrl+A and batch Add/Remove.

### Observation
The historian could type a technical `record_code`, creating UNIQUE collisions.

**Classification:** system-ID vs source-ID problem.

**Decision:** generate technical record codes automatically; source identifiers remain RAW source fields.

### Observation
Save actions were visually and semantically generic.

**Classification:** UI semantics / layout problem.

**Decision:** source-specific save labels at bottom right.

## Alpha v0.4.1 → v0.4.2

### Observation
Plain Enter was overloaded for navigation, while the desired capture workflow is keyboard-stable: Tab moves between fields; continuation is explicit.

**Classification:** keyboard workflow / UX.

**Decision:**
- Tab / Shift+Tab move between fields, including multiline text widgets.
- Plain Enter no longer advances ordinary form fields.
- Ctrl+Enter is the explicit shortcut for `Continue` / `Start capture`.
- Ctrl+S saves the current record; in Form Builder it saves the form version.

### Observation
The Components list could visually retain two selected rows and required a second click before the editor followed the intended component.

**Classification:** Form Builder selection bug.

**Decision:** Components are strictly single-select (`browse` mode), prior selection is cleared explicitly, and component settings are persisted without reselecting the old row.

### Observation
Only MIG had a useful starter structure. New NAS/MOR/MAT forms could contain only SOURCE_CONTEXT + RECORD, which hid the person and event model and encouraged invalid/mixed structures.

**Classification:** Form Builder scaffold / source-family problem.

**Decision:** add editable starter structures for all four families:
- NAS: register, birth atto, officer, declarant, child, birth event, witnesses.
- MOR: register, death atto, officer, deceased, declarant(s), death event, witnesses.
- MAT: register, marriage atto, officer, two spouses, four parent positions, marriage event, repeatable publications, witnesses, repeatable supporting documents.
- MIG: manifest/voyage context, passenger row, migrant, home contact, US contact.

### Observation
Changing Source family could leave the previous family's structure in place (for example MAT selected while a Migration manifest structure remained).

**Classification:** Form Builder state bug.

**Decision:** family changes now explicitly ask whether to reset to the new family's starter, keep the current structure deliberately, or cancel.

### Observation
`Default value` and `Widget override` are expert settings and cluttered the primary field-selection workflow.

**Classification:** information architecture / UI.

**Decision:** move them behind a collapsed `Advanced field settings` control and rename them to `Prefill / default` and `Input control override`.

### Observation
`Verification / authorization raw` was unclear and looked like a normal MOR starter field.

**Classification:** field-label / scope clarity.

**Decision:** rename to `Verification / authorization note raw`, keep it optional in the catalog, and remove it from the default MOR starter.

### Observation
Form Builder save could fail silently from the user's perspective when `Valid from` or `Valid to` contained non-numeric test text. The uncaught integer conversion error left the modal builder open, so the workflow could not continue.

**Classification:** blocking validation / navigation bug.

**Decision:** validate year inputs with a friendly message; on successful save release/destroy the modal builder before refreshing the caller page. Keyboard convention remains `Ctrl+Enter` = continue and `Ctrl+S` = save.

### Observation
NAS capture must not equate the declarant/comparso with the father. A birth act can be declared by another person, and mother/father data must remain independently capturable.

**Classification:** source-structure / position-vs-relation problem.

**Decision:** NAS starter now contains separate Declarant, Father, Mother and Child PRI components. Declarant and Father may later resolve to the same historical person, but remain distinct form positions.

### Observation
`context_code` is a CtC system identifier, not a historical source value, and manual typing is unnecessary and error-prone.

**Classification:** system-ID vs source-data problem.

**Decision:** generate context code automatically from source context; civil example `Cortale + NAS + 1809 -> COR_NAS_1809`. Display read-only.

## Polish pass — 2026-10-05

- Scoped mouse-wheel bindings to each window and to the scroll panel under the pointer. Destroying a panel removes its own binding; text/list/choice controls keep their wheel behavior.
- Added a consistent Segoe UI base font and more generous button/tab spacing, with the native Vista theme when available.
- SQLite context managers now commit/roll back and close the connection. Previously the smoke test left its database locked during Windows cleanup. The smoke test now explicitly checks closure.
- Windows launcher quotes the project path, supports `py -3` and `python`, and explains missing Python/startup failures.
- Replaced the placeholder README with the current workflow, keyboard reference, runtime database path, backup guidance and project map.

Validation: smoke test passed including temporary database cleanup; Python syntax compilation passed; isolated transaction rollback and connection closure passed; Tkinter startup and repeated wheel-binding creation/destruction passed. Visual layout and end-to-end manual capture remain to be checked. Existing custom forms and runtime research data were not rewritten.

## Stabilization v0.5 — 2026-10-05

Form definitions now have immutable database versions identified by logical form code, version number and canonical definition hash. Form Builder retains the logical code and saves a new JSON file instead of overwriting a previous definition. New pure-Python form_logic.py owns definition identity; migrations.py owns backed-up transactional schema migration. Database triggers guard stored definitions against UPDATE/DELETE. Year-range validation prevents saving inverted validity ranges.

Added schema_v0_5_alpha.sql and migration level 1 via SQLite user_version. The active database path is unchanged. The migration preserves original form IDs and references, creates a SQLite backup before changing schema and checks foreign keys before commit. Earlier overwritten definitions cannot be recovered automatically.

Validation: four version/migration regressions, existing smoke test, syntax compilation and an isolated Tkinter Form Builder save/callback test. A copy of the real current database was migrated and all original columns/rows compared across all 22 tables. The active database was then migrated with backup: 1 record and 4 form definitions retained, foreign-key check clean. OCR/HTR/linking and changes to value-level uncertainty or source-family constraints are deferred.

## v0.6.1 UI rebuild — 2026-10-05

Added builder_wizard.py (four-step workflow with fixed footer), scan_view.py (threaded scan loading, image zoom/pan and PDF page selection) and ui_labels.py (Italian field display labels). Updated app.py to use the new panes and metadata action; added scan_url_raw to the field catalog. Database schema remains at migration level 1; immutable versions and previous identity/provenance rules are preserved.

Fixed a previously untested MAT save bug: duplicate father/mother components used sequence 1 for the same role. Saving now allocates distinct sequence numbers across all components of each role/event type, while retaining each component's owner mapping.

Tests: version migration tests, smoke test, local image/PDF reader tests and GUI workflow across NAS/MAT/MOR/MIG including save-and-next and per-record URL persistence. Footer accessibility checked at 900x600. HTTP authentication/JavaScript portals are not embedded. The broader modular rewrite, full localization of expert settings, linking and OCR/HTR/NEL remain future work.

## Identity stabilization v0.7 — 2026-10-06

Added identity.py for NAS structure and birth-anchor validation, a permanent UUID per GID, migration level 2 and backup before upgrading existing GID rows. Existing GID IDs/codes/anchors remain intact. Database triggers protect GID identifiers/anchors against mutation or deletion and validate new GID anchors. Unknown names are permitted; the current capture workflow requires exactly one non-repeatable child and birth event. Multi-child acts require a dedicated later workflow.

Added duplicate warning for exact RAW act-number match in the same NAS context. This is a user-reviewed warning, not complete duplicate detection. Added a read-only birth-anchor table to the session page with UUID copying. Existing normalization/linking structures are not changed.

Validation: six identity tests, four immutable-version tests, smoke test, two scan tests, four-family GUI workflow including duplicate cancellation and GID overview. Migration was tested on a copy of the current database: all original values in 22 tables retained. Active version migrated: 1 record and 1 GID retained, foreign-key check clean.

## v0.9 — repeated source wording — 2026-10-06

Added capture_defaults.py. Configured record-place inheritance is now shown as editable prefill and preserved as context-derived data. Explicit Sindaco retention keeps repeated transcribed wording across Save & Next; retained RAW values have default provenance pointing to the preceding officer PRI, overrides remain explicit. Retention is session-local and context-specific.

Fixed cross-source draft contamination by matching draft context_id and form_code before restoring it; other drafts remain cached in memory for return. Persistent drafts, profile storage and comprehensive validation remain future work.

GUI regression covers six records: original officer Cefali explicit, retained Cefali default, overridden Altro explicit; NAS place Cortale inherited; Father = Declarant, father_of, come sopra and mese sudetto remain intact. Domain relation, GID, immutable version, smoke and scan tests pass. No database schema change in v0.8 or v0.9; relation vocabulary seeded on startup.
