# From Code to Code (CtC)

**Applied Programming Projects · HS 2026 · University of Basel**

CtC is a configurable data-entry system for extracting research-relevant information from historical records directly into a relational SQLite database.

The core idea is to **bypass spreadsheet-based intermediate workflows**: instead of first transcribing records into Excel and later restructuring the data, CtC is intended to capture persons, events, places and relations in structured form at the moment of reading the source.

## Research context

The longer-term research goal is the reconstruction of populations and transatlantic migration networks between Southern Italy and the United States.

The main source families are:

- **NAS** — birth records
- **MAT** — marriage records
- **MOR** — death records
- **MIG** — passenger manifests / migration records

The seminar project focuses on the **capture pipeline**, not yet on the final historical analysis.

## Why configurable forms?

Historical administrative records are structured, but their forms are not static.

Fields can appear, disappear, move, or become repeatable across different form versions. CtC therefore distinguishes between:

- a field that exists but is left blank;
- a field that does not exist in a particular form version.

Instead of hard-coding one interface for every year or source type, CtC stores form definitions as metadata and uses them to generate the corresponding input interface.

## Core workflow

```text
historical record
    ↓
select / define form version
    ↓
generated capture interface
    ↓
structured data entry
    ↓
SQLite
    ↓
later: person linking, population reconstruction, network analysis
```

The current version assumes **human reading of the historical source**. OCR/HTR and AI-assisted extraction are possible future extensions, but they are deliberately outside the current seminar core.

## Current alpha features

The current alpha includes:

- transcription-session setup;
- configurable form versions;
- generated capture interfaces;
- source/register context;
- support for NAS, MAT, MOR and MIG structures;
- direct saving to SQLite;
- separation of record and historical event;
- source-bound person references and relations;
- RAW source values kept separate from derived/resolved values;
- inherited context and reusable defaults for serial capture;
- scan/image/PDF display alongside the capture form;
- keyboard-oriented workflow;
- basic identity and relation tests.

This is still an **alpha research prototype**. The immediate goal is to simplify and stabilize the workflow around fast, research-oriented structured capture.

## Run CtC

### Windows

Python 3.10+ is required.

The recommended start is:

```text
run_ctc.bat
```

Double-click `run_ctc.bat`.

On first use, CtC creates a local `.venv` if needed and installs the scan-view dependencies listed in `requirements.txt`.

Alternative:

```bash
python src/app.py
```

## Tests

From the project folder, using the local virtual environment:

```powershell
.\.venv\Scripts\python.exe src\test_versions.py
.\.venv\Scripts\python.exe src\smoke_test.py
.\.venv\Scripts\python.exe src\test_scans.py
.\.venv\Scripts\python.exe src\test_identity.py
.\.venv\Scripts\python.exe src\test_relations.py
.\.venv\Scripts\python.exe src\test_workflow.py
```

Some GUI tests require a graphical Windows session.

## Repository structure

```text
codetocode/
├── docs/          development notes and test log
├── forms/         form-version definitions
├── schema/        SQLite schema versions
├── seed/          field catalogues and controlled vocabularies
├── src/           application code and tests
├── runtime/       local databases and runtime data (not committed)
├── README.md
├── requirements.txt
└── run_ctc.bat
```

## Data and Git

The repository contains code, configuration and documentation.

Local research data should not be committed. In particular:

- SQLite runtime databases;
- scans / archival images;
- private data;
- API keys or credentials;
- local virtual environments.

These are excluded through `.gitignore` where appropriate.

## Development approach

CtC is developed iteratively with real historical records. The basic cycle is:

```text
read a real record
→ identify a capture problem
→ make the smallest useful change
→ test the same record again
→ continue
```

AI is used as a programming and conceptual sparring partner, but the historical source remains the reference for modelling decisions.

## Next steps

For the seminar, the priority is:

1. simplify and stabilize direct structured capture;
2. define the minimum research-relevant fields for population and network reconstruction;
3. improve fast keyboard-driven serial entry;
4. test representative NAS, MAT, MOR and MIG records;
5. add a small person-linking experiment only if the capture pipeline is stable.

Possible later extensions include OCR/HTR, AI-assisted field extraction and larger-scale record linkage.
