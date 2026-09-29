from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parents[1]
FORM_PATH = ROOT / "forms" / "nas_1809_alpha.json"


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.window, width=e.width)
        )

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class CtCApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CtC – From Code to Code – alpha")
        self.geometry("1050x800")

        db.init_db()
        self.form = db.load_form(FORM_PATH)
        self.widgets = {}
        self.instances = {}

        self._build_header()
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._render_form()
        self._build_footer()

    def _build_header(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)

        ttk.Label(top, text=self.form["label"], font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        ttk.Label(top, text="Context code").grid(row=1, column=0, sticky="w")
        self.context_code = tk.StringVar(value=self.form.get("default_context_code", ""))
        ttk.Entry(top, textvariable=self.context_code, width=25).grid(
            row=1, column=1, sticky="w", padx=(6, 18)
        )

        ttk.Label(top, text="Record code (optional)").grid(row=1, column=2, sticky="w")
        self.record_code = tk.StringVar()
        ttk.Entry(top, textvariable=self.record_code, width=28).grid(
            row=1, column=3, sticky="w", padx=(6, 0)
        )

    def _build_footer(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(bar, text="Save record", command=self.save_record).pack(side="left")
        ttk.Button(bar, text="Clear record", command=self.clear_record).pack(
            side="left", padx=8
        )
        self.status = ttk.Label(bar, text="Ready")
        self.status.pack(side="left", padx=12)

    def _render_form(self):
        for comp in self.form["components"]:
            if comp.get("repeatable"):
                self.instances[comp["id"]] = []
                box = ttk.LabelFrame(self.scroll.inner, text=comp["title"])
                box.pack(fill="x", padx=4, pady=6)

                holder = ttk.Frame(box)
                holder.pack(fill="x", padx=6, pady=6)

                for _ in range(comp.get("default_instances", 1)):
                    self._add_repeatable_instance(comp, holder)

                ttk.Button(
                    box,
                    text=f"+ Add {comp['title'].lower()}",
                    command=lambda c=comp, h=holder: self._add_repeatable_instance(c, h),
                ).pack(anchor="w", padx=6, pady=(0, 6))
            else:
                self._render_single_component(comp)

    def _render_single_component(self, comp):
        box = ttk.LabelFrame(self.scroll.inner, text=comp["title"])
        box.pack(fill="x", padx=4, pady=6)
        self.widgets[comp["id"]] = self._render_fields(box, comp["fields"])

    def _add_repeatable_instance(self, comp, holder):
        seq = len(self.instances[comp["id"]]) + 1
        frame = ttk.LabelFrame(holder, text=f"{comp['title']} {seq}")
        frame.pack(fill="x", pady=4)
        fields = self._render_fields(frame, comp["fields"])
        self.instances[comp["id"]].append(fields)

    def _render_fields(self, parent, fields):
        field_widgets = {}
        with db.connect() as con:
            for row_idx, spec in enumerate(fields):
                code = spec["field_code"]
                meta = db.field_meta(con, code)
                label = spec.get("label", meta["label"])
                widget_kind = spec.get("widget") or meta["default_widget"] or "Entry"
                default = spec.get("default", "")

                ttk.Label(parent, text=label).grid(
                    row=row_idx, column=0, sticky="w", padx=6, pady=3
                )

                if widget_kind == "Checkbox":
                    var = tk.BooleanVar(value=bool(default))
                    widget = ttk.Checkbutton(parent, variable=var)
                elif widget_kind == "Combobox":
                    var = tk.StringVar(value=default)
                    choices = spec.get("choices", [])
                    widget = ttk.Combobox(
                        parent, textvariable=var, values=choices, width=28
                    )
                elif widget_kind == "Text":
                    var = None
                    widget = tk.Text(parent, width=70, height=3)
                    if default:
                        widget.insert("1.0", default)
                else:
                    var = tk.StringVar(value=default)
                    widget = ttk.Entry(parent, textvariable=var, width=42)

                widget.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=3)
                parent.columnconfigure(1, weight=1)
                field_widgets[code] = (widget_kind, var, widget)

        return field_widgets

    @staticmethod
    def _value(widget_info):
        kind, var, widget = widget_info
        if kind == "Text":
            return widget.get("1.0", "end").strip()
        return var.get()

    def _save_fields(self, con, owner_type, owner_id, field_widgets):
        for code, widget_info in field_widgets.items():
            db.save_value(
                con,
                field_code=code,
                owner_type=owner_type,
                owner_id=owner_id,
                raw_value=self._value(widget_info),
            )

    def _record_number(self):
        record_component = self.widgets.get("record", {})
        info = record_component.get("record_number_raw")
        if not info:
            return ""
        return str(self._value(info)).strip()

    def _auto_record_code(self):
        if self.record_code.get().strip():
            return self.record_code.get().strip()
        number = self._record_number() or "UNNUMBERED"
        return f"{self.form['source_family']}-{self.context_code.get().strip()}-{number}"

    def save_record(self):
        context_code = self.context_code.get().strip()
        if not context_code:
            messagebox.showerror("Missing context", "Please enter a context code.")
            return

        try:
            with db.connect() as con:
                form_version_id = db.ensure_form_version(con, self.form)
                context_id = db.ensure_context(
                    con, self.form["source_family"], context_code
                )
                record_code = self._auto_record_code()
                record_id = db.create_record(
                    con,
                    context_id=context_id,
                    form_version_id=form_version_id,
                    record_type=self.form["source_family"],
                    record_code=record_code,
                )

                child_pri_id = None
                birth_event_id = None

                for comp in self.form["components"]:
                    ctype = comp["type"]

                    if comp.get("repeatable"):
                        for seq, fields in enumerate(self.instances[comp["id"]], start=1):
                            pri_id = db.create_pri(
                                con, record_id, comp["position_type"], seq
                            )
                            self._save_fields(con, "PRI", pri_id, fields)
                            self._add_role_relation(
                                con, comp["position_type"], pri_id, record_id
                            )
                        continue

                    fields = self.widgets[comp["id"]]

                    if ctype == "SOURCE_CONTEXT":
                        self._save_fields(con, "SOURCE_CONTEXT", context_id, fields)

                    elif ctype == "RECORD":
                        self._save_fields(con, "RECORD", record_id, fields)

                    elif ctype == "PRI":
                        pri_id = db.create_pri(
                            con, record_id, comp["position_type"], 1
                        )
                        self._save_fields(con, "PRI", pri_id, fields)
                        self._add_role_relation(
                            con, comp["position_type"], pri_id, record_id
                        )
                        if comp["position_type"] == "child":
                            child_pri_id = pri_id

                    elif ctype == "EVENT":
                        event_id = db.create_event(
                            con, record_id, comp["event_type"], 1
                        )
                        self._save_fields(con, "EVENT", event_id, fields)
                        if comp["event_type"] == "birth":
                            birth_event_id = event_id

                if child_pri_id and birth_event_id:
                    _, gid_code = db.create_gid_for_birth(
                        con, child_pri_id, birth_event_id
                    )
                else:
                    gid_code = "(no GID created)"

                con.commit()

            self.status.config(text=f"Saved {record_code} · {gid_code}")
            messagebox.showinfo(
                "Saved",
                f"Record saved successfully.\n\n{record_code}\n{gid_code}",
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    @staticmethod
    def _add_role_relation(con, position_code, pri_id, record_id):
        mapping = {
            "officer": "officiates",
            "declarant": "declarant_of",
            "witness": "witness_of",
        }
        relation = mapping.get(position_code)
        if relation:
            db.add_record_relation(con, pri_id, relation, record_id)

    def clear_record(self):
        self.record_code.set("")
        for comp_id, fields in self.widgets.items():
            if comp_id == "context":
                continue
            self._clear_fields(fields)

        for comp_id, instance_list in self.instances.items():
            for fields in instance_list:
                self._clear_fields(fields)

        self.status.config(text="Record fields cleared; context retained")

    @staticmethod
    def _clear_fields(fields):
        for _, (kind, var, widget) in fields.items():
            if kind == "Text":
                widget.delete("1.0", "end")
            elif kind == "Checkbox":
                var.set(False)
            else:
                # Keep useful form defaults where obvious.
                current = var.get()
                if current in ("anni", "1809", "4"):
                    continue
                var.set("")


if __name__ == "__main__":
    CtCApp().mainloop()
