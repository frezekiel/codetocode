from __future__ import annotations

if __name__ == "__main__":
    from startup import ensure_environment
    ensure_environment()

from datetime import date
from pathlib import Path
import copy
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox

import db
from builder_wizard import BuilderWizard
from scan_view import ScanPane
from ui_labels import field_label, component_label
from identity import validate_birth_form
from reference_controls import ReferenceControls
from capture_relations import save_parent_relations, save_references
from capture_defaults import CaptureDefaults

ROOT = Path(__file__).resolve().parents[1]

LEGIBILITY = [
    "",
    "1 — gar nicht lesbar",
    "2 — sehr schwer lesbar",
    "3 — mit Aufwand lesbar",
    "4 — gut lesbar",
    "5 — sehr gut lesbar",
]

AUTO_CHOICES = {
    "age_unit_raw": ["anni", "mesi", "giorni"],
    "sex_raw": ["", "maschio", "femmina"],
}

ROLE_RELATIONS = {
    "officer": "officiates",
    "declarant": "declarant_of",
    "witness": "witness_of",
}


FAMILY_DEFAULT_LABELS = {
    "NAS": "Birth record",
    "MAT": "Marriage record",
    "MOR": "Death record",
    "MIG": "Migration manifest",
}


def civil_context_fields():
    return [
        {"field_code": "source_reference"},
        {"field_code": "source_url"},
        {"field_code": "provincia_raw"},
        {"field_code": "distretto_raw"},
        {"field_code": "comune_universita_raw"},
        {"field_code": "quartiere_raw"},
        {"field_code": "register_year_raw"},
        {"field_code": "register_type_raw"},
    ]


def civil_record_fields():
    return [
        {"field_code": "record_number_raw"},
        {"field_code": "record_day_raw"},
        {"field_code": "record_month_raw"},
        {"field_code": "record_year_raw"},
        {"field_code": "record_time_raw"},
        {
            "field_code": "record_place_raw",
            "inherit_from": {
                "component_id": "context",
                "field_code": "comune_universita_raw",
            },
        },
        {"field_code": "record_note_raw"},
    ]


def officer_component():
    return {
        "id": "officer",
        "type": "PRI",
        "title": "Officer / Sindaco",
        "position_type": "officer",
        "fields": [
            {"field_code": "honorific_raw"},
            {"field_code": "given_name_raw"},
            {"field_code": "surname_raw"},
        ],
    }


def witness_component(default_instances=2):
    return {
        "id": "witness",
        "type": "PRI",
        "title": "Witness",
        "position_type": "witness",
        "repeatable": True,
        "default_instances": default_instances,
        "fields": [
            {"field_code": "given_name_raw"},
            {"field_code": "surname_raw"},
            {"field_code": "age_text_raw"},
            {
                "field_code": "age_unit_raw",
                "widget": "Combobox",
                "choices": ["anni", "mesi", "giorni"],
                "default": "anni",
                "skip_tab": True,
            },
            {"field_code": "occupation_raw"},
            {"field_code": "domicile_raw"},
            {"field_code": "signature_present", "widget": "Checkbox"},
        ],
    }


def nas_parent_component(kind):
    """Separate NAS parent positions; declarant is never assumed to be father."""
    kind = kind.lower()
    if kind not in {"father", "mother"}:
        raise ValueError(f"Unsupported NAS parent kind: {kind}")
    return {
        "id": kind,
        "type": "PRI",
        "title": kind.capitalize(),
        "position_type": kind,
        "fields": [
            {"field_code": "honorific_raw"},
            {"field_code": "given_name_raw"},
            {"field_code": "surname_raw"},
            {"field_code": "age_text_raw"},
            {
                "field_code": "age_unit_raw",
                "widget": "Combobox",
                "choices": ["anni", "mesi", "giorni"],
                "default": "anni",
                "skip_tab": True,
            },
            {"field_code": "occupation_raw"},
            {"field_code": "domicile_raw"},
            {"field_code": "street_raw"},
            {"field_code": "genealogical_marker_raw"},
        ],
    }


def _context_token(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(value or "").upper())
    return cleaned[:3] if cleaned else fallback


def derive_context_code(form, context_values):
    """Generate a stable human-readable source-context code from entered context."""
    family = str(form.get("source_family") or "CTX").upper()

    if family in {"NAS", "MAT", "MOR"}:
        place = context_values.get("comune_universita_raw", "")
        year = context_values.get("register_year_raw", "") or form.get("valid_from_year", "")
        place_token = _context_token(place, "CTX")
        year_token = re.sub(r"\D", "", str(year or ""))[:4] or "YEAR"
        return f"{place_token}_{family}_{year_token}"

    if family == "MIG":
        ship = context_values.get("ship_name_raw", "")
        date_value = context_values.get("arrival_date_raw", "") or context_values.get("departure_date_raw", "")
        year_match = re.search(r"(?:18|19|20)\d{2}", str(date_value or ""))
        year_token = year_match.group(0) if year_match else "YEAR"
        ship_token = _context_token(ship, "SHP")
        return f"MIG_{ship_token}_{year_token}"

    return f"{family}_CONTEXT"


def starter_components(family):
    """Return an editable, source-family-specific starter structure."""
    family = family.upper()

    if family == "NAS":
        return [
            {
                "id": "context",
                "type": "SOURCE_CONTEXT",
                "title": "Register context",
                "fields": civil_context_fields(),
            },
            {
                "id": "record",
                "type": "RECORD",
                "title": "Birth act / atto",
                "fields": civil_record_fields(),
            },
            officer_component(),
            {
                "id": "declarant",
                "type": "PRI",
                "title": "Declarant / Comparso",
                "position_type": "declarant",
                "fields": [
                    {"field_code": "honorific_raw"},
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "occupation_raw"},
                    {"field_code": "age_text_raw"},
                    {
                        "field_code": "age_unit_raw",
                        "widget": "Combobox",
                        "choices": ["anni", "mesi", "giorni"],
                        "default": "anni",
                        "skip_tab": True,
                    },
                    {"field_code": "domicile_raw"},
                    {"field_code": "street_raw"},
                    {"field_code": "house_number_raw"},
                    {"field_code": "signature_present", "widget": "Checkbox"},
                ],
            },
            nas_parent_component("father"),
            nas_parent_component("mother"),
            {
                "id": "child",
                "type": "PRI",
                "title": "Child",
                "position_type": "child",
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {
                        "field_code": "sex_raw",
                        "widget": "Combobox",
                        "choices": ["", "maschio", "femmina"],
                    },
                ],
            },
            {
                "id": "birth",
                "type": "EVENT",
                "title": "Birth event",
                "event_type": "birth",
                "fields": [
                    {"field_code": "event_day_raw"},
                    {"field_code": "event_month_raw"},
                    {"field_code": "event_year_raw"},
                    {"field_code": "event_time_raw"},
                    {
                        "field_code": "event_place_raw",
                        "inherit_from": {
                            "component_id": "context",
                            "field_code": "comune_universita_raw",
                        },
                    },
                ],
            },
            witness_component(2),
        ]

    if family == "MOR":
        return [
            {
                "id": "context",
                "type": "SOURCE_CONTEXT",
                "title": "Register context",
                "fields": civil_context_fields(),
            },
            {
                "id": "record",
                "type": "RECORD",
                "title": "Death act / atto",
                "fields": civil_record_fields(),
            },
            officer_component(),
            {
                "id": "deceased",
                "type": "PRI",
                "title": "Deceased",
                "position_type": "deceased",
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "sex_raw", "widget": "Combobox", "choices": ["", "maschio", "femmina"]},
                    {"field_code": "age_text_raw"},
                    {"field_code": "age_unit_raw", "widget": "Combobox", "choices": ["anni", "mesi", "giorni"], "default": "anni", "skip_tab": True},
                    {"field_code": "occupation_raw"},
                    {"field_code": "domicile_raw"},
                    {"field_code": "street_raw"},
                    {"field_code": "marital_status_raw", "widget": "Entry"},
                    {"field_code": "genealogical_marker_raw"},
                ],
            },
            {
                "id": "declarant",
                "type": "PRI",
                "title": "Declarant",
                "position_type": "declarant",
                "repeatable": True,
                "default_instances": 1,
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "age_text_raw"},
                    {"field_code": "age_unit_raw", "widget": "Combobox", "choices": ["anni", "mesi", "giorni"], "default": "anni", "skip_tab": True},
                    {"field_code": "occupation_raw"},
                    {"field_code": "domicile_raw"},
                    {"field_code": "street_raw"},
                    {"field_code": "genealogical_marker_raw"},
                    {"field_code": "signature_present", "widget": "Checkbox"},
                ],
            },
            {
                "id": "death",
                "type": "EVENT",
                "title": "Death event",
                "event_type": "death",
                "fields": [
                    {"field_code": "event_day_raw"},
                    {"field_code": "event_month_raw"},
                    {"field_code": "event_year_raw"},
                    {"field_code": "event_time_raw"},
                    {"field_code": "event_place_raw"},
                    {"field_code": "event_note_raw"},
                ],
            },
            witness_component(2),
        ]

    if family == "MAT":
        spouse_fields = [
            {"field_code": "honorific_raw"},
            {"field_code": "given_name_raw"},
            {"field_code": "surname_raw"},
            {"field_code": "age_text_raw"},
            {"field_code": "age_unit_raw", "widget": "Combobox", "choices": ["anni", "mesi", "giorni"], "default": "anni", "skip_tab": True},
            {"field_code": "occupation_raw"},
            {"field_code": "domicile_raw"},
            {"field_code": "nativo_raw"},
            {"field_code": "marital_status_raw", "widget": "Entry"},
            {"field_code": "genealogical_marker_raw"},
            {"field_code": "signature_present", "widget": "Checkbox"},
        ]
        parent_fields = [
            {"field_code": "given_name_raw"},
            {"field_code": "surname_raw"},
            {"field_code": "occupation_raw"},
            {"field_code": "domicile_raw"},
            {"field_code": "genealogical_marker_raw"},
        ]
        return [
            {
                "id": "context",
                "type": "SOURCE_CONTEXT",
                "title": "Register context",
                "fields": civil_context_fields(),
            },
            {
                "id": "record",
                "type": "RECORD",
                "title": "Marriage act / atto",
                "fields": civil_record_fields(),
            },
            officer_component(),
            {"id": "spouse_1", "type": "PRI", "title": "Spouse 1", "position_type": "spouse_1", "fields": copy.deepcopy(spouse_fields)},
            {"id": "spouse_2", "type": "PRI", "title": "Spouse 2", "position_type": "spouse_2", "fields": copy.deepcopy(spouse_fields)},
            {"id": "spouse_1_father", "type": "PRI", "title": "Spouse 1 — father", "position_type": "father", "fields": copy.deepcopy(parent_fields)},
            {"id": "spouse_1_mother", "type": "PRI", "title": "Spouse 1 — mother", "position_type": "mother", "fields": copy.deepcopy(parent_fields)},
            {"id": "spouse_2_father", "type": "PRI", "title": "Spouse 2 — father", "position_type": "father", "fields": copy.deepcopy(parent_fields)},
            {"id": "spouse_2_mother", "type": "PRI", "title": "Spouse 2 — mother", "position_type": "mother", "fields": copy.deepcopy(parent_fields)},
            {
                "id": "marriage",
                "type": "EVENT",
                "title": "Marriage event",
                "event_type": "marriage",
                "fields": [
                    {"field_code": "event_day_raw"},
                    {"field_code": "event_month_raw"},
                    {"field_code": "event_year_raw"},
                    {"field_code": "event_time_raw"},
                    {"field_code": "event_place_raw"},
                ],
            },
            {
                "id": "publication",
                "type": "EVENT",
                "title": "Marriage publication",
                "event_type": "marriage_publication",
                "repeatable": True,
                "default_instances": 2,
                "fields": [
                    {"field_code": "event_day_raw"},
                    {"field_code": "event_month_raw"},
                    {"field_code": "event_year_raw"},
                    {"field_code": "event_place_raw"},
                    {"field_code": "event_note_raw"},
                ],
            },
            witness_component(2),
            {
                "id": "supporting_document",
                "type": "SUPPORTING_DOCUMENT",
                "title": "Supporting document",
                "repeatable": True,
                "default_instances": 1,
                "fields": [
                    {"field_code": "document_type_raw"},
                    {"field_code": "document_date_raw"},
                    {"field_code": "document_place_raw"},
                    {"field_code": "document_reference_raw"},
                    {"field_code": "document_note_raw"},
                ],
            },
        ]

    if family == "MIG":
        return [
            {
                "id": "context",
                "type": "SOURCE_CONTEXT",
                "title": "Manifest / voyage context",
                "fields": [
                    {"field_code": "source_reference"},
                    {"field_code": "source_url"},
                    {"field_code": "manifest_list_no_raw"},
                    {"field_code": "ship_name_raw"},
                    {"field_code": "shipping_line_raw"},
                    {"field_code": "departure_date_raw"},
                    {"field_code": "departure_port_raw"},
                    {"field_code": "arrival_date_raw"},
                    {"field_code": "arrival_port_raw"},
                ],
            },
            {
                "id": "record",
                "type": "RECORD",
                "title": "Passenger row",
                "fields": [
                    {"field_code": "record_number_raw"},
                    {"field_code": "passenger_class_raw"},
                    {"field_code": "record_note_raw"},
                ],
            },
            {
                "id": "migrant",
                "type": "PRI",
                "title": "Migrant / passenger",
                "position_type": "migrant",
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "sex_raw", "widget": "Combobox", "choices": ["", "male", "female"]},
                    {"field_code": "age_text_raw"},
                    {"field_code": "occupation_raw"},
                    {"field_code": "marital_status_raw", "widget": "Entry"},
                    {"field_code": "nationality_raw"},
                    {"field_code": "last_residence_country_raw"},
                    {"field_code": "last_residence_place_raw"},
                    {"field_code": "destination_state_raw"},
                    {"field_code": "destination_place_raw"},
                    {"field_code": "passage_paid_by_raw"},
                    {"field_code": "money_raw"},
                ],
            },
            {
                "id": "home_contact",
                "type": "PRI",
                "title": "Home contact",
                "position_type": "home_contact",
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "address_raw"},
                    {"field_code": "person_note_raw"},
                ],
            },
            {
                "id": "us_contact",
                "type": "PRI",
                "title": "US contact",
                "position_type": "us_contact",
                "fields": [
                    {"field_code": "given_name_raw"},
                    {"field_code": "surname_raw"},
                    {"field_code": "address_raw"},
                    {"field_code": "person_note_raw"},
                ],
            },
        ]

    raise ValueError(f"Unknown source family: {family}")


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.inner = ttk.Frame(self.canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(
                self.window, width=e.width
            )
        )

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self._wheel_host = self.winfo_toplevel()
        self._wheel_binding = self._wheel_host.bind(
            "<MouseWheel>", self._wheel, add="+"
        )
        self.bind("<Destroy>", self._cleanup_wheel, add="+")

    def _cleanup_wheel(self, event):
        if event.widget is self and self._wheel_binding:
            self._wheel_host.unbind("<MouseWheel>", self._wheel_binding)
            self._wheel_binding = None

    def _wheel(self, event):
        # Scroll only the panel under the pointer; preserve controls that have
        # their own wheel behavior (text, lists, and choice fields).
        target = self.winfo_containing(event.x_root, event.y_root)
        if target is None or target.winfo_class() in {
            "Text", "Listbox", "TCombobox", "Spinbox", "TSpinbox"
        }:
            return
        while target is not None:
            if target is self:
                if event.delta:
                    steps = max(1, abs(event.delta) // 120)
                    self.canvas.yview_scroll(
                        -steps if event.delta > 0 else steps, "units"
                    )
                    return "break"
                return
            target = target.master


class FormBuilder(BuilderWizard, tk.Toplevel):
    """
    Alpha structure builder.

    It can:
    - create a form version from scratch;
    - choose source family;
    - add/remove/reorder PRI, EVENT and DOCUMENT components;
    - configure repeatability/default instances;
    - assign/reorder fields from the master field catalog;
    - set simple defaults and widget overrides.

    Conditions are deliberately deferred to a later iteration.
    """

    def __init__(self, master, source_form=None, on_saved=None, focus_atto=False):
        super().__init__(master)
        self.title("CtC Form Builder — immutable versions")
        self.geometry("1120x740")
        self.minsize(920, 620)
        self.transient(master)
        self.grab_set()

        self.on_saved = on_saved
        self.source_form = copy.deepcopy(source_form) if source_form else None
        self.is_new_form = source_form is None

        if source_form:
            self.form = copy.deepcopy(source_form)
        else:
            self.form = {
                "form_code": "",
                "source_family": "NAS",
                "label": FAMILY_DEFAULT_LABELS["NAS"],
                "valid_from_year": None,
                "valid_to_year": None,
                "default_context_code": "",
                "components": starter_components("NAS"),
            }

        self._active_family = self.form.get("source_family", "NAS")
        self.current_index = None
        self._build_ui()

        initial_index = 1 if focus_atto and len(self.form["components"]) > 1 else 0
        self.refresh_component_list(select_index=initial_index)

    def _build_ui(self):
        self.wizard_start()
        meta = ttk.LabelFrame(self.steps[0], text="Formularversion")
        meta.pack(fill="x", padx=8, pady=12)

        self.family_var = tk.StringVar(value=self.form.get("source_family", "NAS"))
        self.code_var = tk.StringVar(value=self.form.get("form_code", ""))
        self.label_var = tk.StringVar(value=self.form.get("label", ""))
        self.from_var = tk.StringVar(
            value="" if self.form.get("valid_from_year") is None
            else str(self.form.get("valid_from_year"))
        )
        self.to_var = tk.StringVar(
            value="" if self.form.get("valid_to_year") is None
            else str(self.form.get("valid_to_year"))
        )
        self.context_code_var = tk.StringVar(
            value=self.form.get("default_context_code", "")
        )

        ttk.Label(meta, text="Aktart").grid(
            row=0, column=0, sticky="w", padx=8, pady=5
        )
        family = ttk.Combobox(
            meta, textvariable=self.family_var,
            values=["NAS", "MAT", "MOR", "MIG"],
            state="readonly", width=12
        )
        family.grid(row=0, column=1, sticky="w", padx=8, pady=5)
        family.bind(
            "<<ComboboxSelected>>",
            self.on_family_change
        )

        ttk.Label(meta, text="Formularcode").grid(
            row=0, column=2, sticky="w", padx=8, pady=5
        )
        ttk.Entry(meta, textvariable=self.code_var, width=36).grid(
            row=0, column=3, sticky="ew", padx=8, pady=5
        )

        ttk.Label(meta, text="Bezeichnung").grid(
            row=1, column=0, sticky="w", padx=8, pady=5
        )
        ttk.Entry(meta, textvariable=self.label_var, width=55).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=5
        )

        ttk.Label(meta, text="Gültig ab").grid(
            row=2, column=0, sticky="w", padx=8, pady=5
        )
        ttk.Entry(meta, textvariable=self.from_var, width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=5
        )

        ttk.Label(meta, text="Gültig bis").grid(
            row=2, column=2, sticky="w", padx=8, pady=5
        )
        ttk.Entry(meta, textvariable=self.to_var, width=12).grid(
            row=2, column=3, sticky="w", padx=8, pady=5
        )

        ttk.Label(meta, text="Kontextcode").grid(
            row=3, column=0, sticky="w", padx=8, pady=5
        )
        ttk.Label(
            meta,
            text="Wird aus dem Quellenkontext automatisch gebildet."
        ).grid(
            row=3, column=1, columnspan=3,
            sticky="w", padx=8, pady=5
        )

        meta.columnconfigure(3, weight=1)

        body = ttk.Panedwindow(self.steps[1], orient="horizontal")
        body.pack(fill="both", expand=True, padx=16, pady=8)

        left = ttk.Frame(body, width=350)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=3)

        # Components
        ttk.Label(
            left, text="Abschnitte", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        self.component_list = tk.Listbox(
            left, exportselection=False, height=20, selectmode=tk.BROWSE
        )
        self.component_list.pack(fill="both", expand=True)
        self.component_list.bind(
            "<<ListboxSelect>>", self.on_component_select
        )

        component_buttons = ttk.Frame(left)
        component_buttons.pack(fill="x", pady=6)

        ttk.Button(
            component_buttons, text="+ Person",
            command=lambda: self.add_component("PRI")
        ).grid(row=0, column=0, padx=2, pady=2)

        ttk.Button(
            component_buttons, text="+ Ereignis",
            command=lambda: self.add_component("EVENT")
        ).grid(row=0, column=1, padx=2, pady=2)

        ttk.Button(
            component_buttons, text="+ Dokument",
            command=lambda: self.add_component("SUPPORTING_DOCUMENT")
        ).grid(row=0, column=2, padx=2, pady=2)

        ttk.Button(
            component_buttons, text="Entfernen",
            command=self.delete_component
        ).grid(row=1, column=0, padx=2, pady=2)

        ttk.Button(
            component_buttons, text="↑",
            command=lambda: self.move_component(-1)
        ).grid(row=1, column=1, padx=2, pady=2)

        ttk.Button(
            component_buttons, text="↓",
            command=lambda: self.move_component(1)
        ).grid(row=1, column=2, padx=2, pady=2)

        # Right editor
        self.editor = ttk.Frame(right)
        self.editor.pack(fill="both", expand=True)

        self.bind("<Control-s>", self.save_form_shortcut)
        self.bind("<Control-S>", self.save_form_shortcut)

    # ---------- component list ----------

    def form_is_blank_core(self):
        components = self.form.get("components", [])
        return (
            len(components) == 2
            and {comp.get("id") for comp in components} == {"context", "record"}
            and all(not comp.get("fields") for comp in components)
        )

    def on_family_change(self, event=None):
        new_family = self.family_var.get().strip()
        old_family = self._active_family

        if new_family == old_family:
            return

        answer = messagebox.askyesnocancel(
            "Change source family?",
            (
                f"Switch from {old_family} to {new_family}?\n\n"
                f"Yes = reset to the {new_family} starter structure\n"
                "No = keep the current structure and only change the family\n"
                "Cancel = keep everything unchanged"
            ),
            parent=self,
        )

        if answer is None:
            self.family_var.set(old_family)
            return

        self.form["source_family"] = new_family
        self._active_family = new_family

        if answer:
            self.form["components"] = starter_components(new_family)
            old_default = FAMILY_DEFAULT_LABELS.get(old_family, "")
            current_label = self.label_var.get().strip()
            if not current_label or current_label == old_default:
                self.label_var.set(FAMILY_DEFAULT_LABELS[new_family])
            self.current_index = 0

        self.refresh_component_list(
            select_index=self.current_index if self.current_index is not None else 0
        )

    def save_form_shortcut(self, event=None):
        self.save_form()
        return "break"

    def component_display(self, comp):
        subtype = ""
        if comp["type"] == "PRI":
            subtype = f" · {comp.get('position_type', '?')}"
        elif comp["type"] == "EVENT":
            subtype = f" · {comp.get('event_type', '?')}"
        return component_label(comp)

    def refresh_component_list(self, select_index=None):
        self.component_list.delete(0, "end")
        for comp in self.form["components"]:
            self.component_list.insert("end", self.component_display(comp))

        if not self.form["components"]:
            self.current_index = None
            self.clear_editor()
            return

        if select_index is None:
            select_index = (
                self.current_index
                if self.current_index is not None
                else 0
            )

        select_index = max(
            0, min(select_index, len(self.form["components"]) - 1)
        )

        self.component_list.selection_clear(0, "end")
        self.component_list.selection_set(select_index)
        self.component_list.activate(select_index)
        self.current_index = select_index
        self.render_component_editor(select_index)

    def on_component_select(self, event=None):
        selected = self.component_list.curselection()
        if not selected:
            return

        new_index = selected[0]
        if new_index == self.current_index:
            return

        self.apply_component_settings(keep_selection=False)
        self.current_index = new_index
        self.component_list.selection_clear(0, "end")
        self.component_list.selection_set(new_index)
        self.component_list.activate(new_index)
        self.render_component_editor(new_index)

    def add_component(self, ctype):
        self.apply_component_settings()

        if ctype == "PRI":
            comp = {
                "id": self.unique_component_id("person"),
                "type": "PRI",
                "title": "Person",
                "position_type": "other_person",
                "fields": []
            }
        elif ctype == "EVENT":
            comp = {
                "id": self.unique_component_id("event"),
                "type": "EVENT",
                "title": "Event",
                "event_type": "birth",
                "fields": []
            }
        else:
            comp = {
                "id": self.unique_component_id("document"),
                "type": "SUPPORTING_DOCUMENT",
                "title": "Supporting document",
                "repeatable": True,
                "default_instances": 1,
                "fields": []
            }

        self.form["components"].append(comp)
        self.refresh_component_list(
            select_index=len(self.form["components"]) - 1
        )

    def unique_component_id(self, stem):
        existing = {c["id"] for c in self.form["components"]}
        i = 1
        while f"{stem}_{i}" in existing:
            i += 1
        return f"{stem}_{i}"

    def delete_component(self):
        if self.current_index is None:
            return
        comp = self.form["components"][self.current_index]
        if comp["id"] in ("context", "record"):
            messagebox.showinfo(
                "Fixed component",
                "Source context and record are core components and "
                "cannot be deleted in this alpha.",
                parent=self
            )
            return
        del self.form["components"][self.current_index]
        self.refresh_component_list(
            select_index=max(0, self.current_index - 1)
        )

    def move_component(self, delta):
        if self.current_index is None:
            return
        self.apply_component_settings()

        i = self.current_index
        j = i + delta

        if j < 0 or j >= len(self.form["components"]):
            return

        self.form["components"][i], self.form["components"][j] = (
            self.form["components"][j],
            self.form["components"][i]
        )
        self.current_index = j
        self.refresh_component_list(select_index=j)

    # ---------- component editor ----------

    def clear_editor(self):
        for child in self.editor.winfo_children():
            child.destroy()

    def render_component_editor(self, index):
        self.clear_editor()
        comp = self.form["components"][index]

        ttk.Label(
            self.editor,
            text="Abschnitt anpassen",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 6))

        settings = ttk.LabelFrame(self.editor, text=comp["type"])
        settings.pack(fill="x", pady=4)

        self.title_var = tk.StringVar(value=comp.get("title", ""))
        self.subtype_var = tk.StringVar(
            value=comp.get(
                "position_type",
                comp.get("event_type", "")
            )
        )
        self.repeatable_var = tk.BooleanVar(
            value=bool(comp.get("repeatable", False))
        )
        self.instances_var = tk.StringVar(
            value=str(comp.get("default_instances", 1))
        )

        ttk.Label(settings, text="Title").grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Entry(
            settings, textvariable=self.title_var, width=45
        ).grid(
            row=0, column=1, sticky="ew", padx=8, pady=4
        )

        row = 1

        if comp["type"] == "PRI":
            ttk.Label(settings, text="Position type").grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )
            with db.connect() as con:
                values = db.list_type_codes(con, "position_type")
            ttk.Combobox(
                settings,
                textvariable=self.subtype_var,
                values=values,
                state="readonly",
                width=30
            ).grid(
                row=row, column=1, sticky="w", padx=8, pady=4
            )
            row += 1

        elif comp["type"] == "EVENT":
            ttk.Label(settings, text="Event type").grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )
            with db.connect() as con:
                values = db.list_type_codes(con, "event_type")
            ttk.Combobox(
                settings,
                textvariable=self.subtype_var,
                values=values,
                state="readonly",
                width=30
            ).grid(
                row=row, column=1, sticky="w", padx=8, pady=4
            )
            row += 1

        if comp["type"] in ("PRI", "EVENT", "SUPPORTING_DOCUMENT"):
            ttk.Checkbutton(
                settings,
                text="Repeatable",
                variable=self.repeatable_var
            ).grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )

            ttk.Label(
                settings, text="Default instances"
            ).grid(
                row=row, column=1, sticky="w", padx=8, pady=4
            )
            ttk.Spinbox(
                settings,
                from_=1, to=20,
                textvariable=self.instances_var,
                width=7
            ).grid(
                row=row, column=1, sticky="e", padx=8, pady=4
            )
            row += 1

        ttk.Button(
            settings,
            text="Änderungen übernehmen",
            command=self.apply_component_settings
        ).grid(
            row=row, column=0, columnspan=2,
            sticky="e", padx=8, pady=6
        )

        settings.columnconfigure(1, weight=1)

        self.render_field_editor(comp)

    def apply_component_settings(self, keep_selection=True):
        if self.current_index is None:
            return

        comp = self.form["components"][self.current_index]

        if hasattr(self, "title_var"):
            comp["title"] = self.title_var.get().strip() or comp["type"].title()

        if comp["type"] == "PRI" and hasattr(self, "subtype_var"):
            comp["position_type"] = self.subtype_var.get().strip() or "other_person"

        if comp["type"] == "EVENT" and hasattr(self, "subtype_var"):
            comp["event_type"] = self.subtype_var.get().strip() or "birth"

        if comp["type"] in ("PRI", "EVENT", "SUPPORTING_DOCUMENT"):
            comp["repeatable"] = bool(self.repeatable_var.get())
            try:
                comp["default_instances"] = max(1, int(self.instances_var.get()))
            except ValueError:
                comp["default_instances"] = 1

        self.persist_selected_field_details()

        # Refresh the current label without leaving multiple rows highlighted.
        if self.current_index is not None:
            idx = self.current_index
            self.component_list.delete(idx)
            self.component_list.insert(idx, self.component_display(comp))
            if keep_selection:
                self.component_list.selection_clear(0, "end")
                self.component_list.selection_set(idx)
                self.component_list.activate(idx)

    # ---------- fields ----------

    def entity_for_component(self, comp):
        return comp["type"]

    def render_field_editor(self, comp):
        field_frame = ttk.LabelFrame(
            self.editor, text="Felder in diesem Abschnitt"
        )
        field_frame.pack(fill="both", expand=True, pady=8)

        lists = ttk.Frame(field_frame)
        lists.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(lists)
        middle = ttk.Frame(lists)
        right = ttk.Frame(lists)

        left.pack(side="left", fill="both", expand=True)
        middle.pack(side="left", fill="y", padx=8)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(
            left,
            text="Verfügbare Felder (Strg/Umschalt: Mehrfachauswahl)"
        ).pack(anchor="w")
        self.available_list = tk.Listbox(
            left,
            exportselection=False,
            selectmode=tk.EXTENDED
        )
        self.available_list.pack(fill="both", expand=True)
        self.available_list.bind(
            "<Control-a>",
            lambda e: self.select_all_in_list(self.available_list)
        )

        ttk.Label(
            right,
            text="Ausgewählte Felder / Reihenfolge"
        ).pack(anchor="w")
        self.selected_list = tk.Listbox(
            right,
            exportselection=False,
            selectmode=tk.EXTENDED
        )
        self.selected_list.pack(fill="both", expand=True)
        self.selected_list.bind(
            "<<ListboxSelect>>",
            lambda e: self.load_selected_field_details()
        )
        self.selected_list.bind(
            "<Control-a>",
            lambda e: self.select_all_in_list(self.selected_list)
        )

        ttk.Button(
            middle, text="Hinzufügen →", command=self.add_field
        ).pack(pady=(30, 4))
        ttk.Button(
            middle, text="← Entfernen", command=self.remove_field
        ).pack(pady=4)
        ttk.Separator(
            middle, orient="horizontal"
        ).pack(fill="x", pady=12)
        ttk.Button(
            middle, text="↑ Nach oben", command=lambda: self.move_field(-1)
        ).pack(pady=4)
        ttk.Button(
            middle, text="↓ Nach unten", command=lambda: self.move_field(1)
        ).pack(pady=4)

        self.advanced_visible = False
        self.advanced_toggle = ttk.Button(
            field_frame,
            text="Weitere Feldeinstellungen ▸",
            command=self.toggle_advanced_field_settings,
        )
        self.advanced_toggle.pack(anchor="w", padx=8, pady=(0, 6))

        self.advanced_details = ttk.Frame(field_frame)

        ttk.Label(
            self.advanced_details,
            text="Prefill / default",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.field_default_var = tk.StringVar()
        ttk.Entry(
            self.advanced_details,
            textvariable=self.field_default_var,
            width=24,
        ).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(
            self.advanced_details,
            text="Input control override",
        ).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.field_widget_var = tk.StringVar()
        ttk.Combobox(
            self.advanced_details,
            textvariable=self.field_widget_var,
            values=["", "Entry", "Combobox", "Checkbox", "Text"],
            state="readonly",
            width=16,
        ).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Button(
            self.advanced_details,
            text="Apply advanced settings",
            command=self.persist_selected_field_details,
        ).grid(row=0, column=4, padx=8, pady=4)

        self.advanced_help_var = tk.StringVar(
            value="Select exactly one field to edit advanced settings."
        )
        ttk.Label(
            self.advanced_details,
            textvariable=self.advanced_help_var,
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 4))

        self.refresh_field_lists()

    def toggle_advanced_field_settings(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_details.pack(fill="x", padx=8, pady=(0, 8))
            self.advanced_toggle.config(text="Weitere Feldeinstellungen ▾")
            self.load_selected_field_details()
        else:
            self.advanced_details.pack_forget()
            self.advanced_toggle.config(text="Weitere Feldeinstellungen ▸")

    def select_all_in_list(self, listbox):
        listbox.selection_set(0, "end")
        return "break"

    def catalog_rows_for_current(self):
        if self.current_index is None:
            return []
        comp = self.form["components"][self.current_index]
        entity = self.entity_for_component(comp)
        with db.connect() as con:
            return db.list_catalog_fields(
                con,
                entity,
                self.family_var.get(),
                selectable_only=True
            )

    def refresh_field_lists(self):
        if not hasattr(self, "available_list") or self.current_index is None:
            return

        comp = self.form["components"][self.current_index]
        selected_codes = [f["field_code"] for f in comp.get("fields", [])]

        catalog = self.catalog_rows_for_current()
        self.available_map = {}

        self.available_list.delete(0, "end")
        for row in catalog:
            code = row["field_code"]
            if code in selected_codes:
                continue
            display = field_label(code, row["label"])
            self.available_map[display] = code
            self.available_list.insert("end", display)

        self.selected_list.delete(0, "end")
        for spec in comp.get("fields", []):
            try:
                with db.connect() as con:
                    meta = db.field_meta(con, spec["field_code"])
                label = field_label(spec["field_code"], meta["label"])
            except Exception:
                label = spec["field_code"]

            self.selected_list.insert(
                "end",
                label
            )

    def add_field(self):
        selected = list(self.available_list.curselection())
        if not selected:
            return

        displays = [self.available_list.get(i) for i in selected]
        codes = [self.available_map[display] for display in displays]

        fields = self.form["components"][self.current_index].setdefault(
            "fields", []
        )
        existing = {spec["field_code"] for spec in fields}
        added_codes = []

        for code in codes:
            if code in existing:
                continue

            spec = {"field_code": code}

            if code in AUTO_CHOICES:
                spec["widget"] = "Combobox"
                spec["choices"] = AUTO_CHOICES[code]
                if code == "age_unit_raw":
                    spec["default"] = "anni"
                    spec["skip_tab"] = True

            fields.append(spec)
            existing.add(code)
            added_codes.append(code)

        self.refresh_field_lists()

        for i, spec in enumerate(fields):
            if spec["field_code"] in added_codes:
                self.selected_list.selection_set(i)

    def remove_field(self):
        selected = sorted(
            self.selected_list.curselection(),
            reverse=True
        )
        if not selected:
            return

        fields = self.form["components"][self.current_index]["fields"]
        for idx in selected:
            del fields[idx]

        self.refresh_field_lists()

    def move_field(self, delta):
        selected = sorted(self.selected_list.curselection())
        if not selected:
            return

        fields = self.form["components"][self.current_index]["fields"]
        selected_set = set(selected)

        if delta < 0:
            if selected[0] == 0:
                return
            for idx in selected:
                if idx - 1 not in selected_set:
                    fields[idx - 1], fields[idx] = fields[idx], fields[idx - 1]
            new_selected = [idx - 1 for idx in selected]
        else:
            if selected[-1] == len(fields) - 1:
                return
            for idx in reversed(selected):
                if idx + 1 not in selected_set:
                    fields[idx + 1], fields[idx] = fields[idx], fields[idx + 1]
            new_selected = [idx + 1 for idx in selected]

        self.refresh_field_lists()
        for idx in new_selected:
            self.selected_list.selection_set(idx)

    def selected_field_spec(self):
        selected = self.selected_list.curselection()
        if len(selected) != 1:
            return None
        return self.form["components"][self.current_index]["fields"][selected[0]]

    def load_selected_field_details(self):
        spec = self.selected_field_spec()
        if not spec:
            self.field_default_var.set("")
            self.field_widget_var.set("")
            if hasattr(self, "advanced_help_var"):
                self.advanced_help_var.set(
                    "Select exactly one field to edit advanced settings."
                )
            return

        self.field_default_var.set(str(spec.get("default", "")))
        self.field_widget_var.set(spec.get("widget", ""))
        if hasattr(self, "advanced_help_var"):
            self.advanced_help_var.set(
                "Advanced: normally leave these settings unchanged."
            )

    def persist_selected_field_details(self):
        if not hasattr(self, "selected_list"):
            return
        spec = self.selected_field_spec()
        if not spec:
            return

        default = self.field_default_var.get()
        widget = self.field_widget_var.get()

        if default != "":
            spec["default"] = default
        else:
            spec.pop("default", None)

        if widget:
            spec["widget"] = widget
        else:
            spec.pop("widget", None)

        if spec["field_code"] == "age_unit_raw":
            spec["widget"] = "Combobox"
            spec["choices"] = ["anni", "mesi", "giorni"]
            spec["skip_tab"] = True
            spec.setdefault("default", "anni")

        if spec["field_code"] == "sex_raw":
            spec["widget"] = "Combobox"
            spec["choices"] = ["", "maschio", "femmina"]

    # ---------- save ----------

    def save_form(self):
        self.apply_component_settings()

        code = self.code_var.get().strip()
        label = self.label_var.get().strip()
        family = self.family_var.get().strip()

        if not code or not label:
            messagebox.showerror(
                "Missing metadata",
                "Form code and label are required.",
                parent=self
            )
            return

        self.form["form_code"] = code
        self.form["label"] = label
        self.form["source_family"] = family
        # Context codes are source-instance identifiers and are generated
        # automatically on the Source/Form page, not stored as form defaults.
        self.form["default_context_code"] = ""

        try:
            valid_from_year = self.int_or_none(self.from_var.get())
            valid_to_year = self.int_or_none(self.to_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid year",
                (
                    "Valid from and Valid to must contain a whole-number year "
                    "(for example 1809) or be left blank."
                ),
                parent=self
            )
            return

        self.form["valid_from_year"] = valid_from_year
        self.form["valid_to_year"] = valid_to_year

        if (valid_from_year is not None and valid_to_year is not None
                and valid_from_year > valid_to_year):
            messagebox.showerror("Invalid year range", "Valid from must not exceed Valid to.", parent=self)
            return
        try:
            path = db.save_form_revision(self.form)
        except Exception as exc:
            messagebox.showerror("Form save failed", str(exc), parent=self)
            return

        # Close the modal builder first so a successful save can never leave
        # the user trapped behind its grab. Then let the caller refresh the
        # Source/Form or Capture page on the next Tk event-loop cycle.
        on_saved = self.on_saved
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

        if on_saved:
            self.master.after_idle(lambda: on_saved(path))

    @staticmethod
    def int_or_none(value):
        value = value.strip()
        return int(value) if value else None


class CtCApp(CaptureDefaults, ReferenceControls, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CtC – From Code to Code – v0.6")
        self.geometry("1400x860")
        self.minsize(960, 680)

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 6))
        style.configure("TNotebook.Tab", padding=(12, 6))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))

        db.init_db()

        self.session_id = None
        self.context_id = None
        self.form_version_id = None

        self.form_path = None
        self.form = None

        self.widgets = {}
        self.instances = {}
        self.inference_controls = {}
        self.source_context_snapshot = {}

        self.session_draft = {
            "transcriber": "",
            "transcription_date": date.today().isoformat(),
            "project_collection": "From Code to Code",
            "session_note": ""
        }
        self.scan_state = {}
        self.scan_reference = ""
        self.source_page_draft = None
        self.capture_draft = None

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.show_session_page()

    # ============================================================
    # Navigation / page helpers
    # ============================================================

    def clear_page(self):
        for sequence in ("<Return>", "<Control-Return>", "<Control-s>", "<Control-S>"):
            self.unbind(sequence)
        for child in self.container.winfo_children():
            child.destroy()

    def page_title(self, title, subtitle=None):
        ttk.Label(
            self.container,
            text=title,
            font=("Segoe UI", 20, "bold")
        ).pack(
            anchor="w", padx=24, pady=(22, 4)
        )

        if subtitle:
            ttk.Label(
                self.container,
                text=subtitle,
                font=("Segoe UI", 10)
            ).pack(
                anchor="w", padx=24, pady=(0, 16)
            )

    def show_birth_anchors(self):
        window = tk.Toplevel(self)
        window.title("Geburtsanker — GID und technische Kennung")
        window.geometry("1050x420")
        ttk.Label(window, text="GID bezeichnet einen Geburtsanker. Die UUID bleibt beim Kopieren dieser Datenbank erhalten.", wraplength=980).pack(anchor="w", padx=12, pady=12)
        table = ttk.Treeview(window, columns=("gid", "uuid", "record", "name"), show="headings")
        for key, label, width in [("gid", "GID", 120), ("uuid", "Dauerhafte UUID", 310), ("record", "Akt", 130), ("name", "Nome (RAW)", 220)]:
            table.heading(key, text=label)
            table.column(key, width=width)
        table.pack(fill="both", expand=True, padx=12)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=table.yview)
        scrollbar.pack(side="right", fill="y")
        table.configure(yscrollcommand=scrollbar.set)
        with db.connect() as con:
            rows = con.execute("""
                SELECT g.gid_code, g.identity_uuid, r.record_code,
                       COALESCE((SELECT raw_value FROM field_value v
                           WHERE v.owner_type='PRI' AND v.owner_id=g.anchor_pri_id
                             AND v.field_code='given_name_raw' LIMIT 1), '') AS name
                FROM gid g JOIN pri pr ON pr.pri_id=g.anchor_pri_id
                JOIN position_instance p ON p.position_id=pr.position_id
                JOIN source_record r ON r.record_id=p.record_id ORDER BY g.gid_id
            """).fetchall()
        for row in rows:
            table.insert("", "end", values=tuple(row))
        def copy_uuid():
            selection = table.selection()
            if selection:
                window.clipboard_clear()
                window.clipboard_append(table.item(selection[0], "values")[1])
        ttk.Button(window, text="UUID kopieren", command=copy_uuid).pack(side="left", padx=12, pady=12)
        ttk.Button(window, text="Schließen", command=window.destroy).pack(side="right", padx=12, pady=12)

    # ============================================================
    # PAGE 1 — session
    # ============================================================

    def show_session_page(self):
        self.current_page = "session"
        if hasattr(self, "context_widgets") and hasattr(self, "context_code_var"):
            self.source_page_draft = self.context_state()

        self.clear_page()

        self.page_title(
            "From Code to Code",
            "1 / 3 — Erfassungssitzung einrichten."
        )

        ttk.Button(self.container, text="Geburtsanker (GID) ansehen", command=self.show_birth_anchors).pack(anchor="e", padx=24)

        box = ttk.LabelFrame(
            self.container, text="Sitzung"
        )
        box.pack(fill="x", padx=24, pady=12)

        self.transcriber_var = tk.StringVar(
            value=self.session_draft.get("transcriber", "")
        )
        self.date_var = tk.StringVar(
            value=self.session_draft.get(
                "transcription_date",
                date.today().isoformat()
            )
        )
        self.project_var = tk.StringVar(
            value=self.session_draft.get(
                "project_collection",
                "From Code to Code"
            )
        )

        rows = [
            ("Bearbeiter", self.transcriber_var),
            ("Erfassungsdatum", self.date_var),
            ("Projekt / Sammlung", self.project_var),
        ]

        first_entry = None

        for r, (label, var) in enumerate(rows):
            ttk.Label(
                box, text=label
            ).grid(
                row=r, column=0,
                sticky="w", padx=10, pady=7
            )

            entry = ttk.Entry(
                box, textvariable=var, width=55
            )
            entry.grid(
                row=r, column=1,
                sticky="ew", padx=10, pady=7
            )

            if first_entry is None:
                first_entry = entry

            if label == "Erfassungsdatum":
                entry.state(["readonly"])

        ttk.Label(
            box, text="Sitzungsnotiz"
        ).grid(
            row=3, column=0,
            sticky="nw", padx=10, pady=7
        )

        self.session_note = tk.Text(
            box, height=4, width=60
        )
        self.session_note.grid(
            row=3, column=1,
            sticky="ew", padx=10, pady=7
        )
        self.session_note.insert(
            "1.0",
            self.session_draft.get("session_note", "")
        )

        box.columnconfigure(1, weight=1)

        nav = ttk.Frame(self.container)
        nav.pack(fill="x", padx=24, pady=18)

        ttk.Button(
            nav,
            text="Continue →  (Ctrl+Enter)",
            command=self.create_session_and_continue
        ).pack(side="right")

        self.session_note.bind("<Tab>", self.focus_next_widget)
        self.session_note.bind("<Shift-Tab>", self.focus_previous_widget)
        self.session_note.bind("<Control-Return>", self.continue_session_shortcut)
        self.bind("<Control-Return>", self.continue_session_shortcut)

        if first_entry:
            first_entry.focus_set()

    def create_session_and_continue(self):
        transcriber = self.transcriber_var.get().strip()

        if not transcriber:
            messagebox.showerror(
                "Missing transcriber",
                "Please enter the transcriber's name."
            )
            return

        self.session_draft = {
            "transcriber": transcriber,
            "transcription_date": self.date_var.get(),
            "project_collection": self.project_var.get().strip(),
            "session_note": self.session_note.get("1.0", "end").strip()
        }

        with db.connect() as con:
            if self.session_id is None:
                self.session_id = db.create_session(
                    con,
                    self.session_draft["transcriber"],
                    self.session_draft["transcription_date"],
                    self.session_draft["project_collection"],
                    self.session_draft["session_note"],
                )
            else:
                db.update_session(
                    con,
                    self.session_id,
                    self.session_draft["transcriber"],
                    self.session_draft["transcription_date"],
                    self.session_draft["project_collection"],
                    self.session_draft["session_note"],
                )
            con.commit()

        self.show_source_page(
            restore_context=self.source_page_draft
        )

    def show_source_page(self, restore_context=None):
        self.current_page = "source"
        self.clear_page()

        self.page_title(
            "Welche Quelle erfasst du?",
            "2 / 3 — Formular wählen und Quellenkontext festlegen."
        )

        top = ttk.Frame(self.container)
        top.pack(fill="x", padx=24, pady=(4, 10))

        ttk.Label(
            top, text="Formularversion"
        ).grid(
            row=0, column=0, sticky="w"
        )

        self.form_files = db.list_forms()
        labels = [
            f"{db.load_form(p)['label']} · {p.stem}"
            for p in self.form_files
        ]

        self.form_choice = ttk.Combobox(
            top,
            values=labels,
            state="readonly",
            width=55
        )
        self.form_choice.grid(
            row=0, column=1,
            sticky="ew", padx=8
        )

        selected_index = 0
        if self.form_path in self.form_files:
            selected_index = self.form_files.index(self.form_path)

        if labels:
            self.form_choice.current(selected_index)

        self.form_choice.bind(
            "<<ComboboxSelected>>",
            lambda e: self.load_selected_form()
        )

        ttk.Button(
            top,
            text="Neues Formular …",
            command=self.new_form_builder
        ).grid(
            row=0, column=2, padx=4
        )

        ttk.Button(
            top,
            text="Formular anpassen …",
            command=self.edit_form_builder_from_source_page
        ).grid(
            row=0, column=3, padx=4
        )

        top.columnconfigure(1, weight=1)

        self.source_scroll = ScrollFrame(self.container)
        self.source_scroll.pack(
            fill="both", expand=True,
            padx=24, pady=8
        )

        self.source_form_holder = ttk.Frame(
            self.source_scroll.inner
        )
        self.source_form_holder.pack(fill="x")

        nav = ttk.Frame(self.container)
        nav.pack(fill="x", padx=24, pady=12)

        ttk.Button(
            nav, text="← Zurück",
            command=self.show_session_page
        ).pack(side="left")

        ttk.Button(
            nav, text="Start capture →  (Ctrl+Enter)",
            command=self.prepare_capture
        ).pack(side="right")

        if restore_context is None:
            restore_context = self.source_page_draft

        self.load_selected_form(
            restore_context=restore_context
        )

        self.bind("<Control-Return>", self.start_capture_shortcut)

    def load_selected_form(self, restore_context=None):
        for child in self.source_form_holder.winfo_children():
            child.destroy()

        if not self.form_files:
            ttk.Label(
                self.source_form_holder,
                text="No form definitions found."
            ).pack()
            return

        idx = self.form_choice.current()
        if idx < 0:
            idx = 0

        self.form_path = self.form_files[idx]
        self.form = db.load_form(self.form_path)

        self.context_code_var = tk.StringVar(value="")

        hdr = ttk.LabelFrame(
            self.source_form_holder,
            text="Quellenkontext"
        )
        hdr.pack(fill="x", pady=6)

        ttk.Label(
            hdr, text="Kontextcode"
        ).grid(
            row=0, column=0,
            sticky="w", padx=8, pady=5
        )

        ttk.Entry(
            hdr,
            textvariable=self.context_code_var,
            width=35,
            state="readonly"
        ).grid(
            row=0, column=1,
            sticky="w", padx=8, pady=5
        )
        ttk.Label(
            hdr,
            text="CtC generates this code from the entered source context."
        ).grid(
            row=0, column=2,
            sticky="w", padx=8, pady=5
        )

        self.context_widgets = {}

        for comp in self.form["components"]:
            if comp["type"] == "SOURCE_CONTEXT":
                box = ttk.LabelFrame(
                    self.source_form_holder,
                    text=component_label(comp)
                )
                box.pack(fill="x", pady=6)

                self.context_widgets = self.render_fields(
                    box, comp["fields"],
                    allow_inheritance=False
                )
                break

        for info in self.context_widgets.values():
            if info.get("var") is not None:
                info["var"].trace_add(
                    "write",
                    lambda *_: self.update_auto_context_code()
                )
            else:
                info["widget"].bind(
                    "<KeyRelease>",
                    lambda _event: self.update_auto_context_code(),
                    add="+"
                )

        if restore_context:
            self.restore_fields(
                self.context_widgets,
                restore_context.get("fields", {})
            )

        self.update_auto_context_code()

    def update_auto_context_code(self):
        if not hasattr(self, "context_widgets") or not self.form:
            return
        values = self.collect_fields(self.context_widgets)
        self.context_code_var.set(
            derive_context_code(self.form, values)
        )

    def context_state(self):
        if not hasattr(self, "context_widgets"):
            return {}
        return {
            "context_code": self.context_code_var.get(),
            "fields": self.collect_fields(self.context_widgets)
        }

    def new_form_builder(self):
        context = self.context_state()

        def saved(path):
            self.reload_forms_and_select(
                path, restore_context=context
            )

        FormBuilder(
            self,
            source_form=None,
            on_saved=saved
        )

    def edit_form_builder_from_source_page(self):
        if not self.form:
            return

        context = self.context_state()

        def saved(path):
            self.reload_forms_and_select(
                path, restore_context=context
            )

        FormBuilder(
            self,
            source_form=self.form,
            on_saved=saved
        )

    def reload_forms_and_select(
        self,
        path,
        restore_context=None
    ):
        self.form_files = db.list_forms()

        labels = [
            f"{db.load_form(p)['label']} · {p.stem}"
            for p in self.form_files
        ]

        self.form_choice["values"] = labels

        for i, p in enumerate(self.form_files):
            if p == path:
                self.form_choice.current(i)
                break

        self.load_selected_form(
            restore_context=restore_context
        )

    def validate_form_structure(self):
        valid, reason = validate_birth_form(self.form)
        if not valid:
            return valid, reason
        components = self.form.get("components", [])

        capture_fields = sum(
            len(comp.get("fields", []))
            for comp in components
            if comp.get("type") != "SOURCE_CONTEXT"
        )

        if capture_fields == 0:
            return (
                False,
                "This form has no capture fields yet. "
                "Edit the form structure before starting capture."
            )

        if self.form.get("source_family") == "MIG":
            migrants = [
                comp for comp in components
                if comp.get("type") == "PRI"
                and comp.get("position_type") == "migrant"
            ]

            if not migrants:
                return (
                    False,
                    "This MIG form has no migrant/passenger component yet. "
                    "Add a Person with position type 'migrant' before starting capture."
                )

            if not any(comp.get("fields") for comp in migrants):
                return (
                    False,
                    "The migrant/passenger component has no fields yet. "
                    "Add at least one passenger field before starting capture."
                )

        return True, ""

    def back_to_source_page(self):
        if hasattr(self, "widgets") and self.widgets:
            self.capture_draft = self.capture_state()

        restore_context = {
            "context_code": self.context_code_var.get(),
            "fields": dict(self.source_context_snapshot)
        }
        self.source_page_draft = restore_context
        self.show_source_page(
            restore_context=restore_context
        )

    def prepare_capture(self):
        if not self.form:
            messagebox.showerror(
                "No form",
                "Choose or create a form version first."
            )
            return

        valid, reason = self.validate_form_structure()
        if not valid:
            messagebox.showwarning(
                "Form not ready for capture",
                reason
            )
            return

        self.update_auto_context_code()
        context_code = self.context_code_var.get().strip()

        if not context_code:
            messagebox.showerror(
                "Missing context code",
                "Please enter a context code."
            )
            return

        self.source_page_draft = self.context_state()

        self.source_context_snapshot = {
            code: self.value(info)
            for code, info
            in self.context_widgets.items()
        }

        with db.connect() as con:
            self.form_version_id = db.ensure_form_version(
                con, self.form
            )

            self.context_id = db.ensure_context(
                con,
                self.form["source_family"],
                context_code
            )

            self.save_fields(
                con,
                "SOURCE_CONTEXT",
                self.context_id,
                self.context_widgets
            )

            con.commit()

        draft = self.capture_draft
        if not hasattr(self, "capture_drafts"):
            self.capture_drafts = {}
        current_key = (self.context_id, self.form["form_code"])
        if draft:
            draft_key = (draft.get("context_id"), draft.get("form_code"))
            if draft_key != current_key:
                self.capture_drafts[draft_key] = draft
                draft = self.capture_drafts.pop(current_key, None)
        else:
            draft = self.capture_drafts.pop(current_key, None)
        self.capture_draft = None
        self.show_capture_page(
            restore_state=draft
        )

    def show_capture_page(self, restore_state=None):
        self.current_page = "capture"
        self.clear_page()

        self.page_title(
            self.form["label"],
            "3 / 3 — Scan lesen und Akt erfassen."
        )

        header = ttk.Frame(self.container)
        header.pack(
            fill="x", padx=24, pady=(0, 8)
        )

        ttk.Label(
            header,
            text=f"Context: {self.context_code_var.get()}"
        ).pack(side="left")

        ttk.Button(
            header,
            text="Quelle / Formular wechseln",
            command=self.back_to_source_page
        ).pack(side="right")

        edit_label = (
            "Formular anpassen …"
            if self.form.get("source_family") == "MIG"
            else "Formular anpassen …"
        )

        ttk.Button(
            header,
            text=edit_label,
            command=self.edit_atto_form_in_place
        ).pack(side="right", padx=8)

        meta = ttk.LabelFrame(
            self.container, text="Aktmetadaten"
        )
        meta.pack(
            fill="x", padx=24, pady=6
        )

        self.image_no_var = tk.StringVar()
        self.page_no_var = tk.StringVar()
        self.legibility_var = tk.StringVar(value="")

        meta_rows = [
            ("Numero immagine", self.image_no_var),
            ("Pagina / foglio", self.page_no_var),
        ]

        first_meta_entry = None

        for r, (label, var) in enumerate(meta_rows):
            ttk.Label(
                meta, text=label
            ).grid(
                row=r, column=0,
                sticky="w", padx=8, pady=5
            )

            entry = ttk.Entry(
                meta, textvariable=var, width=20
            )
            entry.grid(
                row=r, column=1,
                sticky="w", padx=8, pady=5
            )

            if first_meta_entry is None:
                first_meta_entry = entry

        ttk.Label(
            meta, text="Leggibilità"
        ).grid(
            row=2, column=0,
            sticky="w", padx=8, pady=5
        )

        legibility = ttk.Combobox(
            meta,
            textvariable=self.legibility_var,
            values=LEGIBILITY,
            state="readonly",
            width=34
        )
        legibility.grid(
            row=2, column=1,
            sticky="w", padx=8, pady=5
        )
        legibility.bind(
            "<MouseWheel>",
            lambda e: "break"
        )
        legibility.bind(
            "<KeyPress>",
            self.legibility_keypress
        )

        ttk.Label(
            meta,
            text="Die Akt-ID wird automatisch erzeugt."
        ).grid(
            row=0, column=2,
            rowspan=3,
            sticky="w",
            padx=18, pady=5
        )

        bottom = ttk.Frame(self.container)
        bottom.pack(side="bottom", fill="x", padx=16, pady=10)
        self.capture_split = ttk.Panedwindow(self.container, orient="horizontal")
        self.capture_split.pack(fill="both", expand=True, padx=16, pady=6)
        scan = ScanPane(self.capture_split, self.scan_state, self.accept_scan_reference)
        self.capture_split.add(scan, weight=1)
        self.capture_scroll = ScrollFrame(self.capture_split)
        self.capture_split.add(self.capture_scroll, weight=1)

        self.widgets = {}
        self.instances = {}
        self.inference_controls = {}

        for comp in self.form["components"]:
            if comp["type"] == "SOURCE_CONTEXT":
                continue

            if comp.get("repeatable"):
                self.render_repeatable_component(comp)
            else:
                box = ttk.LabelFrame(
                    self.capture_scroll.inner,
                    text=component_label(comp)
                )
                box.pack(
                    fill="x", pady=6
                )

                self.widgets[comp["id"]] = self.render_fields(
                    box,
                    comp.get("fields", []),
                    allow_inheritance=True
                )

                self.render_inference_controls(
                    box, comp
                )

        self.setup_reference_controls()
        self.setup_capture_defaults()

        ttk.Button(
            bottom,
            text="← Zurück",
            command=self.back_to_source_page
        ).pack(side="left")

        self.status = ttk.Label(
            bottom, text="Bereit"
        )
        self.status.pack(
            side="left", padx=12
        )

        if self.form.get("source_family") == "MIG":
            save_label = "Passagier speichern (Strg+S)"
            next_label = "Speichern und nächster Passagier"
        else:
            save_label = "Akt speichern (Strg+S)"
            next_label = "Speichern und nächster Akt"

        ttk.Button(
            bottom,
            text=next_label,
            command=lambda: self.save_record(True)
        ).pack(side="right")

        ttk.Button(
            bottom,
            text=save_label,
            command=lambda: self.save_record(False)
        ).pack(side="right", padx=8)

        self.setup_dynamic_inference_hints()

        self.bind("<Control-s>", self.save_record_shortcut)
        self.bind("<Control-S>", self.save_record_shortcut)

        if restore_state:
            self.restore_capture_state(restore_state)

        if first_meta_entry and not restore_state:
            first_meta_entry.focus_set()

    def accept_scan_reference(self, reference):
        self.scan_reference = reference
        self.status.config(text="Quellenverweis für diesen Akt übernommen" if reference else "Neuer Scan — Quellenverweis bei Bedarf übernehmen")

    def focus_next_widget(self, event):
        next_widget = event.widget.tk_focusNext()
        if next_widget:
            next_widget.focus_set()
        return "break"

    def focus_previous_widget(self, event):
        previous_widget = event.widget.tk_focusPrev()
        if previous_widget:
            previous_widget.focus_set()
        return "break"

    def continue_session_shortcut(self, event=None):
        self.create_session_and_continue()
        return "break"

    def start_capture_shortcut(self, event=None):
        self.prepare_capture()
        return "break"

    def save_record_shortcut(self, event=None):
        self.save_record(False)
        return "break"

    def legibility_keypress(self, event):
        if event.char in {"1", "2", "3", "4", "5"}:
            for label in LEGIBILITY:
                if label.startswith(event.char + " —"):
                    self.legibility_var.set(label)
                    return "break"
        return None

    def edit_atto_form_in_place(self):
        state = self.capture_state()

        def saved(path):
            self.form_path = path
            self.form = db.load_form(path)

            with db.connect() as con:
                self.form_version_id = db.ensure_form_version(
                    con, self.form
                )
                con.commit()

            self.show_capture_page(
                restore_state=state
            )

        FormBuilder(
            self,
            source_form=self.form,
            on_saved=saved,
            focus_atto=True
        )

    # ============================================================
    # Renderer
    # ============================================================

    def render_repeatable_component(self, comp):
        box = ttk.LabelFrame(
            self.capture_scroll.inner,
            text=component_label(comp)
        )
        box.pack(fill="x", pady=6)

        holder = ttk.Frame(box)
        holder.pack(
            fill="x", padx=6, pady=6
        )

        self.instances[comp["id"]] = []

        for _ in range(
            comp.get("default_instances", 1)
        ):
            self.add_repeatable_instance(
                comp, holder
            )

        ttk.Button(
            box,
            text=f"+ Add {comp['title'].lower()}",
            command=lambda c=comp, h=holder:
                self.add_repeatable_instance(c, h)
        ).pack(
            anchor="w", padx=6, pady=(0, 6)
        )

    def add_repeatable_instance(
        self, comp, holder
    ):
        seq = len(
            self.instances[comp["id"]]
        ) + 1

        frame = ttk.LabelFrame(
            holder,
            text=f"{comp['title']} {seq}"
        )
        frame.pack(
            fill="x", pady=4
        )

        fields = self.render_fields(
            frame,
            comp.get("fields", []),
            allow_inheritance=True
        )

        self.instances[comp["id"]].append(
            fields
        )

    def render_fields(
        self,
        parent,
        fields,
        allow_inheritance=True
    ):
        result = {}

        with db.connect() as con:
            for r, spec in enumerate(fields):
                code = spec["field_code"]
                meta = db.field_meta(con, code)

                label = spec.get(
                    "label",
                    field_label(code, meta["label"])
                )

                kind = (
                    spec.get("widget")
                    or meta["default_widget"]
                    or "Entry"
                )

                default = spec.get(
                    "default", ""
                )

                ttk.Label(
                    parent,
                    text=label
                ).grid(
                    row=r, column=0,
                    sticky="w",
                    padx=8, pady=4
                )

                if kind == "Checkbox":
                    var = tk.BooleanVar(
                        value=bool(default)
                    )
                    widget = ttk.Checkbutton(
                        parent,
                        variable=var
                    )

                elif kind == "Combobox":
                    var = tk.StringVar(
                        value=default
                    )
                    widget = ttk.Combobox(
                        parent,
                        textvariable=var,
                        values=spec.get(
                            "choices", []
                        ),
                        width=30,
                        state="readonly",
                        takefocus=(
                            False
                            if spec.get(
                                "skip_tab"
                            )
                            else True
                        )
                    )
                    widget.bind(
                        "<MouseWheel>",
                        lambda e: "break"
                    )

                elif kind == "Text":
                    var = None
                    widget = tk.Text(
                        parent,
                        width=70,
                        height=3
                    )
                    widget.bind("<Tab>", self.focus_next_widget)
                    widget.bind("<Shift-Tab>", self.focus_previous_widget)
                    if getattr(self, "current_page", None) == "source":
                        widget.bind("<Control-Return>", self.start_capture_shortcut)
                    if default:
                        widget.insert(
                            "1.0", default
                        )

                else:
                    var = tk.StringVar(
                        value=default
                    )
                    widget = ttk.Entry(
                        parent,
                        textvariable=var,
                        width=48
                    )

                widget.grid(
                    row=r, column=1,
                    sticky="ew",
                    padx=8, pady=4
                )

                hint_var = tk.StringVar()
                hint_label = None

                if (
                    allow_inheritance
                    and spec.get("inherit_from")
                ):
                    inherited = self.resolve_inheritance(
                        spec["inherit_from"]
                    )
                    if inherited:
                        hint_var.set(
                            f"Inherited: {inherited}"
                        )

                    hint_label = ttk.Label(
                        parent,
                        textvariable=hint_var
                    )
                    hint_label.grid(
                        row=r, column=2,
                        sticky="w",
                        padx=(2, 8), pady=4
                    )

                parent.columnconfigure(
                    1, weight=1
                )

                result[code] = {
                    "kind": kind,
                    "var": var,
                    "widget": widget,
                    "default": default,
                    "spec": spec,
                    "hint_var": hint_var,
                    "hint_label": hint_label
                }

        return result

    def render_inference_controls(
        self, parent, comp
    ):
        controls = comp.get(
            "inference_controls", []
        )

        if not controls:
            return

        row = len(
            comp.get("fields", [])
        )

        for control in controls:
            enabled = tk.BooleanVar(
                value=bool(
                    control.get(
                        "enabled_default", False
                    )
                )
            )

            hint = tk.StringVar(
                value=""
            )

            ttk.Checkbutton(
                parent,
                text=control["label"],
                variable=enabled
            ).grid(
                row=row,
                column=0,
                columnspan=2,
                sticky="w",
                padx=8, pady=(6, 2)
            )

            ttk.Label(
                parent,
                textvariable=hint
            ).grid(
                row=row,
                column=2,
                sticky="w",
                padx=(2, 8), pady=(6, 2)
            )

            self.inference_controls[
                control["id"]
            ] = {
                "config": control,
                "enabled": enabled,
                "hint": hint
            }

            row += 1

    def resolve_inheritance(
        self, inherit_from
    ):
        component_id = inherit_from.get(
            "component_id"
        )
        field_code = inherit_from.get(
            "field_code"
        )

        if component_id == "context":
            return self.source_context_snapshot.get(
                field_code, ""
            )

        return ""

    # ============================================================
    # Value collection / restore
    # ============================================================

    @staticmethod
    def value(info):
        kind = info["kind"]
        var = info["var"]
        widget = info["widget"]

        if kind == "Text":
            return widget.get(
                "1.0", "end"
            ).strip()

        return var.get()

    def collect_fields(self, fields):
        return {
            code: self.value(info)
            for code, info in fields.items()
        }

    def restore_fields(
        self,
        fields,
        values
    ):
        for code, value in values.items():
            if code not in fields:
                continue

            info = fields[code]

            if info["kind"] == "Text":
                info["widget"].delete(
                    "1.0", "end"
                )
                info["widget"].insert(
                    "1.0", value
                )

            elif info["kind"] == "Checkbox":
                info["var"].set(
                    bool(value)
                )

            else:
                info["var"].set(
                    value
                )

    def capture_state(self):
        return {
            "context_id": self.context_id,
            "form_code": self.form["form_code"],
            "keep_officer": self.keep_officer.get(),
            "officer_carry": {code: info.get("carry_default") for code, info in self.widgets.get("officer", {}).items()},
            "field_references": dict(self.field_references),
            "father_is_declarant": self.father_is_declarant.get(),
            "father_confirmed": self.father_confirmed.get(),
            "mother_confirmed": self.mother_confirmed.get(),
            "image_no": self.image_no_var.get(),
            "page_no": self.page_no_var.get(),
            "legibility": self.legibility_var.get(),
            "components": {
                comp_id: self.collect_fields(fields)
                for comp_id, fields
                in self.widgets.items()
            },
            "repeatables": {
                comp_id: [
                    self.collect_fields(fields)
                    for fields in instance_list
                ]
                for comp_id, instance_list
                in self.instances.items()
            },
            "inferences": {
                control_id: item["enabled"].get()
                for control_id, item
                in self.inference_controls.items()
            }
        }

    def restore_capture_state(
        self, state
    ):
        self.keep_officer.set(state.get("keep_officer", False))
        for code, carry in state.get("officer_carry", {}).items():
            if code in self.widgets.get("officer", {}):
                if carry is None:self.widgets["officer"][code].pop("carry_default", None)
                else:self.widgets["officer"][code]["carry_default"] = carry
        self.field_references = dict(state.get("field_references", {}))
        self.father_is_declarant.set(state.get("father_is_declarant", False))
        self.father_confirmed.set(state.get("father_confirmed", False))
        self.mother_confirmed.set(state.get("mother_confirmed", False))
        self.image_no_var.set(
            state.get("image_no", "")
        )
        self.page_no_var.set(
            state.get("page_no", "")
        )
        self.legibility_var.set(
            state.get("legibility", "")
        )

        for comp_id, values in state.get(
            "components", {}
        ).items():
            if comp_id in self.widgets:
                self.restore_fields(
                    self.widgets[comp_id],
                    values
                )

        for comp_id, old_instances in state.get(
            "repeatables", {}
        ).items():
            if comp_id not in self.instances:
                continue

            for i, values in enumerate(
                old_instances
            ):
                if i < len(
                    self.instances[comp_id]
                ):
                    self.restore_fields(
                        self.instances[comp_id][i],
                        values
                    )

        for control_id, enabled in state.get(
            "inferences", {}
        ).items():
            if control_id in self.inference_controls:
                self.inference_controls[
                    control_id
                ]["enabled"].set(
                    enabled
                )

        self.update_inference_hints()
        self.update_reference_hints()

    def setup_dynamic_inference_hints(self):
        for item in self.inference_controls.values():
            cfg = item["config"]
            source_comp = cfg.get(
                "source_component"
            )
            source_field = cfg.get(
                "source_field"
            )

            if (
                source_comp in self.widgets
                and source_field
                in self.widgets[source_comp]
            ):
                var = self.widgets[
                    source_comp
                ][source_field]["var"]

                if var is not None:
                    var.trace_add(
                        "write",
                        lambda *_:
                            self.update_inference_hints()
                    )

        self.update_inference_hints()

    def update_inference_hints(self):
        for item in self.inference_controls.values():
            cfg = item["config"]

            source_comp = cfg.get(
                "source_component"
            )
            source_field = cfg.get(
                "source_field"
            )

            value = ""

            if (
                source_comp in self.widgets
                and source_field
                in self.widgets[source_comp]
            ):
                value = self.value(
                    self.widgets[
                        source_comp
                    ][source_field]
                )

            if (
                item["enabled"].get()
                and value
            ):
                item["hint"].set(
                    f"Inferred value: {value}"
                )
            else:
                item["hint"].set("")

    # ============================================================
    # Saving values
    # ============================================================

    def save_fields(
        self,
        con,
        owner_type,
        owner_id,
        fields
    ):
        for code, info in fields.items():
            raw = self.value(info)
            spec = info["spec"]

            if (
                (raw == "" or (info.get("context_prefill") is not None and raw == info["context_prefill"]))
                and spec.get("inherit_from")
            ):
                inherited = self.resolve_inheritance(
                    spec["inherit_from"]
                )

                db.save_value(
                    con,
                    field_code=code,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    raw_value="",
                    norm_value=inherited,
                    value_origin="inherited",
                    origin_owner_type="SOURCE_CONTEXT",
                    origin_owner_id=self.context_id,
                    origin_field_code=spec[
                        "inherit_from"
                    ]["field_code"],
                    notes="Resolved from source context."
                )

            elif (info.get("carry_default") and raw != ""
                    and str(raw) == str(info["carry_default"]["value"])):
                db.save_value(con, code, owner_type, owner_id, raw_value=raw,
                    value_origin="default", origin_owner_type="PRI",
                    origin_owner_id=info["carry_default"]["owner_id"], origin_field_code=code,
                    notes="Transcriber enabled retention of repeated officer wording; field remains editable.")
            else:
                origin = (
                    "default"
                    if (
                        raw != ""
                        and str(
                            spec.get(
                                "default", ""
                            )
                        ) == str(raw)
                    )
                    else "explicit"
                )

                db.save_value(
                    con,
                    field_code=code,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    raw_value=raw,
                    value_origin=origin
                )

    # ============================================================
    # Record save
    # ============================================================

    def record_number(self):
        fields = self.widgets.get(
            "record", {}
        )

        info = fields.get(
            "record_number_raw"
        )

        return (
            str(self.value(info)).strip()
            if info
            else ""
        )

    def auto_record_code(self, con):
        return db.next_record_code(
            con,
            self.form["source_family"]
        )

    def save_record(self, next_record):
        valid, reason = self.validate_form_structure()
        if not valid:
            messagebox.showwarning(
                "Form not ready for capture",
                reason
            )
            return

        try:
            with db.connect() as con:
                if self.form.get("source_family") == "NAS":
                    number_info = self.widgets.get("record", {}).get("record_number_raw")
                    number = self.value(number_info) if number_info else ""
                    matches = db.matching_birth_records(con, self.context_id, number)
                    if matches and not messagebox.askyesno(
                        "Mögliche doppelte Geburt",
                        f"Aktnummer {number} ist in diesem Quellenkontext bereits gespeichert: "
                        + ", ".join(row["record_code"] for row in matches)
                        + "\n\nEin weiterer Akt erzeugt einen weiteren Geburtsanker. Nur fortfahren, wenn es tatsächlich ein anderer Akt ist. Trotzdem speichern?",
                        parent=self,
                    ):
                        return
                record_code = self.auto_record_code(con)

                record_id = db.create_record(
                    con,
                    self.session_id,
                    self.context_id,
                    self.form_version_id,
                    self.form["source_family"],
                    record_code
                )

                if self.scan_reference:
                    db.save_value(con, "scan_url_raw", "RECORD", record_id, raw_value=self.scan_reference)

                if self.image_no_var.get().strip():
                    db.save_value(
                        con,
                        "image_no_raw",
                        "RECORD",
                        record_id,
                        raw_value=self.image_no_var.get().strip()
                    )

                if self.page_no_var.get().strip():
                    db.save_value(
                        con,
                        "page_no_raw",
                        "RECORD",
                        record_id,
                        raw_value=self.page_no_var.get().strip()
                    )

                if self.legibility_var.get():
                    score = self.legibility_var.get().split(
                        " — ", 1
                    )[0]

                    db.save_value(
                        con,
                        "legibility_score",
                        "RECORD",
                        record_id,
                        raw_value=score
                    )

                child_pri = None
                birth_event = None
                owner_ids = {}
                self._owner_sequences = {}

                for comp in self.form["components"]:
                    if comp["type"] == "SOURCE_CONTEXT":
                        continue

                    if comp.get("repeatable"):
                        created_ids = []

                        for seq, fields in enumerate(
                            self.instances.get(
                                comp["id"], []
                            ),
                            start=1
                        ):
                            owner_id = self.create_owner(
                                con,
                                comp,
                                record_id,
                                seq
                            )

                            created_ids.append(
                                owner_id
                            )

                            self.save_fields(
                                con,
                                self.owner_type_for_component(comp),
                                owner_id,
                                fields
                            )

                            self.add_role_relation_if_needed(
                                con,
                                comp,
                                owner_id,
                                record_id
                            )

                        owner_ids[
                            comp["id"]
                        ] = created_ids
                        continue

                    owner_id = self.create_owner(
                        con,
                        comp,
                        record_id,
                        1
                    )

                    owner_ids[
                        comp["id"]
                    ] = owner_id

                    self.save_fields(
                        con,
                        self.owner_type_for_component(comp),
                        owner_id,
                        self.widgets[
                            comp["id"]
                        ]
                    )

                    self.add_role_relation_if_needed(
                        con,
                        comp,
                        owner_id,
                        record_id
                    )

                    if (
                        comp["type"] == "PRI"
                        and comp.get(
                            "position_type"
                        ) == "child"
                    ):
                        child_pri = owner_id

                    if (
                        comp["type"] == "EVENT"
                        and comp.get(
                            "event_type"
                        ) == "birth"
                    ):
                        birth_event = owner_id

                if self.form.get("source_family") == "NAS":
                    save_parent_relations(con, record_id, owner_ids,
                        self.father_is_declarant.get(), self.father_confirmed.get(), self.mother_confirmed.get())
                reference_owners = dict(owner_ids, context=self.context_id)
                reference_fields = {component: self.collect_fields(fields) for component, fields in self.widgets.items()}
                reference_fields["context"] = dict(self.source_context_snapshot)
                save_references(con, self.form["components"], reference_owners, reference_fields, self.effective_references())

                self.save_inferences(
                    con,
                    owner_ids
                )

                gid_code = "(no GID)"

                if (
                    child_pri
                    and birth_event
                ):
                    _, gid_code = db.create_gid_for_birth(
                        con,
                        child_pri,
                        birth_event
                    )

                con.commit()

            self.cache_officer_after_save(owner_ids)
            self.status.config(
                text=(
                    f"Gespeichert: {record_code} · "
                    f"{gid_code}"
                )
            )

            if next_record:
                self.clear_record()
                self.capture_scroll.canvas.yview_moveto(0)
                self.focus_first_record_field()
            else:
                messagebox.showinfo(
                    "Gespeichert",
                    f"{record_code}\n{gid_code}"
                )

        except Exception as exc:
            messagebox.showerror(
                "Speichern fehlgeschlagen",
                str(exc)
            )

    def create_owner(
        self,
        con,
        comp,
        record_id,
        sequence_no
    ):
        ctype = comp["type"]
        # Sequence is unique per record and role/event type, including distinct
        # components such as the two fathers in a marriage act.
        if ctype in {"PRI", "EVENT", "SUPPORTING_DOCUMENT"}:
            subtype = comp.get("position_type") if ctype == "PRI" else comp.get("event_type", ctype)
            key = (ctype, subtype)
            sequence_no = self._owner_sequences.get(key, 0) + 1
            self._owner_sequences[key] = sequence_no

        if ctype == "RECORD":
            return record_id

        if ctype == "PRI":
            return db.create_pri(
                con,
                record_id,
                comp["position_type"],
                sequence_no
            )

        if ctype == "EVENT":
            return db.create_event(
                con,
                record_id,
                comp["event_type"],
                sequence_no
            )

        if ctype == "SUPPORTING_DOCUMENT":
            return db.create_supporting_document(
                con,
                record_id,
                sequence_no
            )

        raise ValueError(
            f"Unsupported component type: {ctype}"
        )

    @staticmethod
    def owner_type_for_component(comp):
        return comp["type"]

    def add_role_relation_if_needed(
        self,
        con,
        comp,
        owner_id,
        record_id
    ):
        if comp["type"] != "PRI":
            return

        relation = ROLE_RELATIONS.get(
            comp.get("position_type")
        )

        if relation:
            db.add_record_relation(
                con,
                owner_id,
                relation,
                record_id
            )

    def save_inferences(
        self,
        con,
        owner_ids
    ):
        for item in self.inference_controls.values():
            cfg = item["config"]

            if not item["enabled"].get():
                continue
            if (self.form.get("source_family") == "NAS" and cfg.get("source_component") == "declarant"
                    and not self.father_is_declarant.get()):
                continue

            source_comp = cfg["source_component"]
            source_field = cfg["source_field"]
            target_comp = self.find_component_for_inference(
                cfg["id"]
            )

            if (
                source_comp not in self.widgets
                or target_comp is None
            ):
                continue

            source_value = self.value(
                self.widgets[
                    source_comp
                ][source_field]
            )

            target_fields = self.widgets.get(
                target_comp["id"], {}
            )

            target_raw_field = cfg[
                "target_raw_field"
            ]

            target_raw_value = ""

            if target_raw_field in target_fields:
                target_raw_value = self.value(
                    target_fields[
                        target_raw_field
                    ]
                )

            if (
                not source_value
                or target_raw_value
            ):
                continue

            target_owner_id = owner_ids.get(
                target_comp["id"]
            )

            if not isinstance(
                target_owner_id, int
            ):
                continue

            db.save_value(
                con,
                field_code=cfg[
                    "target_norm_field"
                ],
                owner_type=target_comp[
                    "type"
                ],
                owner_id=target_owner_id,
                raw_value="",
                norm_value=source_value,
                value_origin="inferred",
                notes=cfg.get(
                    "rule_code",
                    "inference"
                )
            )

    def find_component_for_inference(
        self, control_id
    ):
        for comp in self.form["components"]:
            for control in comp.get(
                "inference_controls", []
            ):
                if control["id"] == control_id:
                    return comp
        return None

    # ============================================================
    # Clear / next
    # ============================================================

    def clear_record(self):
        self.reset_reference_controls()
        self.image_no_var.set("")
        self.page_no_var.set("")
        self.legibility_var.set("")

        for fields in self.widgets.values():
            self.clear_fields(fields)

        for instance_list in self.instances.values():
            for fields in instance_list:
                self.clear_fields(fields)

        self.restore_capture_defaults_after_clear()

        self.status.config(
            text="Gespeichert. Bereit für den nächsten Akt."
        )

        self.update_inference_hints()

    @staticmethod
    def clear_fields(fields):
        for info in fields.values():
            kind = info["kind"]
            var = info["var"]
            widget = info["widget"]
            default = info["default"]

            if kind == "Text":
                widget.delete(
                    "1.0", "end"
                )
                if default:
                    widget.insert(
                        "1.0", default
                    )

            elif kind == "Checkbox":
                var.set(
                    bool(default)
                )

            else:
                var.set(
                    default
                )

    def focus_first_record_field(self):
        record_fields = self.widgets.get(
            "record", {}
        )

        preferred = [
            "record_number_raw",
            "record_day_raw",
            "record_month_raw"
        ]

        for code in preferred:
            if code in record_fields:
                record_fields[
                    code
                ]["widget"].focus_set()
                return

        for info in record_fields.values():
            info["widget"].focus_set()
            return


if __name__ == "__main__":
    CtCApp().mainloop()
