# CtC Week 1 — Scope Freeze v0.1

## Core deliverable
A configurable capture pipeline:

`Field Catalog -> Form Version / Form Builder -> Renderer -> Capture UI -> SQLite`

Record linkage is optional and only enters Stage 2 if the capture core is stable.

## Source families
- **NAS** — births
- **MAT** — marriages
- **MOR** — deaths
- **MIG** — Ellis Island passenger manifests, 1892–1914

Civil-status material begins in South Italy in 1809. The seminar prototype uses representative form versions rather than exhaustive year-by-year coverage.

## Core data objects
- `SOURCE_CONTEXT`
- `PAGE/SHEET`
- `RECORD`
- `POSITION`
- `PRI`
- `REL`
- `EVENT`
- `PLACE`
- `SUPPORTING_DOCUMENT`

No new core object should be added unless a real source case requires it.

## Form variation
`FORM_VERSION` controls:
- field availability
- field order
- position
- defaults
- repeatability
- simple conditional rules
- structural absence

A field that is structurally absent in a form version is not treated as a record-level missing value.

## Epistemic rules
- Raw source wording is preserved.
- Normalized values are stored separately and never overwrite RAW.
- `RECORD` context is distinct from the historical `EVENT`.
- Structural `POSITION` is distinct from social/genealogical `REL`.
- Missing-value states distinguish **blank/not stated** and **illegible**; **structurally absent** belongs to `FORM_VERSION`.

## Identity layer
- **PRI** = one source-bound occurrence/reference of a person.
- **MID / MetaID** = revisable grouping of PRIs judged to refer to the same historical person.
- **GID / GlobalID** = stable birth-anchored identity.
- Every captured birth creates a GID automatically, anchored to the child PRI and birth event.
- GIDs are not merged. Wrong identifications are corrected at PRI/MID linkage level.

## Repeatability
The model must support repeatable:
- persons/positions, e.g. witnesses or declarants
- events, e.g. marriage publications
- supporting documents

Repeatability is represented structurally rather than through duplicated hard-coded field names.

## Normalization in the seminar prototype
Keep normalization minimal:
- dates and times
- age value/unit
- relation types
- simple confirmed name rules

Full authority control for names and places is deferred.

## OCR / HTR
OCR/HTR is outside the first prototype. The project's main problem is data modelling, not text recognition. OCR/HTR could later become an input layer feeding the same capture and validation workflow.

## Explicitly out of scope for the seminar core
- full corpus capture
- exhaustive implementation of every historical form version
- production web deployment
- multi-user platform
- machine learning
- fully automatic record linkage
- public/open-source publication as a requirement

## Week 1 definition of done
Week 1 is complete when:
1. this scope freeze is accepted;
2. the master field catalog v0.1 exists;
3. initial controlled vocabularies exist;
4. future changes to the core architecture require a concrete source-based reason.
