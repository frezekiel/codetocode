# CtC alpha v0.1 – first vertical slice

This bundle is intentionally a **working alpha**, not the frozen final database.

The purpose is to test the CtC architecture by entering real historical records and discovering where the model or UI needs adjustment.

## What already works

- creates a new SQLite database automatically;
- imports the Week 1 field catalog;
- imports position / event / relation vocabularies;
- loads a form definition from JSON;
- generates a Tkinter capture interface from that JSON;
- supports repeatable witnesses;
- stores context, record, PRI and event field values;
- automatically creates a GID for every captured birth;
- stores basic PRI-to-record relations such as `officiates`, `declarant_of`, and `witness_of`.

## What is deliberately missing

- person-to-person relation editing;
- mother/father conditional logic;
- MID creation and record linkage;
- normalization rules;
- place authority control;
- MAT, MOR and MIG forms;
- OCR / HTR;
- polished UI.

Those are exactly the things we will add only when real capture shows that they are needed.

## Run on Windows

From the repository root:

```text
python src\app.py
```

or double-click `run_ctc.bat`.

The runtime database is created at:

```text
runtime\ctc_alpha.sqlite
```

Do **not** commit that working database to Git.

## Smoke test

```text
python src\smoke_test.py
```

Expected result includes:

```text
Smoke test passed
Created: GID-000001
```

## Suggested Git commit

```text
Build first end-to-end NAS capture alpha
```

## Testing principle

Do not judge this alpha by visual polish. Enter real sources.

For every problem, classify it as:

1. **field problem** – field catalog needs another field;
2. **vocabulary problem** – position/event/relation type is missing;
3. **form problem** – form JSON needs different order/default/repeatability;
4. **UI problem** – capture workflow is awkward;
5. **schema problem** – the information cannot be represented without changing the relational core.

Only category 5 is a serious schema warning.
