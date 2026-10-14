"""Capture controls for confirmed relations and resolved source references."""
import tkinter as tk
from tkinter import ttk, messagebox
from ui_labels import field_label, component_label
from capture_relations import resolve_references

class ReferenceControls:
    def setup_reference_controls(self):
        self.field_references = {}
        self.father_is_declarant = tk.BooleanVar(value=False)
        self.father_confirmed = tk.BooleanVar(value=False)
        self.mother_confirmed = tk.BooleanVar(value=False)
        self.reference_hints = {}
        if self.form.get('source_family')=='NAS':
            box=ttk.LabelFrame(self.capture_scroll.inner,text='Beziehungen laut Quelle')
            box.pack(fill='x',padx=2,pady=8)
            box.pack(before=self.capture_scroll.inner.winfo_children()[0])
            same=ttk.Checkbutton(box,text='Padre = Dichiarante — dieselbe Person',variable=self.father_is_declarant,command=self.update_reference_hints)
            same.pack(anchor='w',padx=8,pady=4)
            if not {'father','declarant','child'}.issubset(self.widgets):same.state(['disabled'])
            ttk.Checkbutton(box,text='Vater-Kind-Beziehung ausdrücklich bestätigt',variable=self.father_confirmed).pack(anchor='w',padx=8,pady=4)
            ttk.Checkbutton(box,text='Mutter-Kind-Beziehung ausdrücklich bestätigt',variable=self.mother_confirmed).pack(anchor='w',padx=8,pady=4)
            ttk.Label(box,text='Padre = Dichiarante bestätigt auch die Vater-Kind-Beziehung. Originaltext bleibt erhalten.',wraplength=500).pack(anchor='w',padx=8,pady=4)
        for component,entries in self.widgets.items():
            for code,info in entries.items():
                if info['kind']=='Checkbox':continue
                widget=info['widget'];row=int(widget.grid_info()['row'])
                ttk.Button(widget.master,text='↪',width=3,command=lambda key=(component,code):self.choose_reference(key)).grid(row=row,column=3,padx=2)
                hint=info.get('hint_label')
                if hint is None:
                    hint=ttk.Label(widget.master,text='',wraplength=150,foreground='#225e75')
                    hint.grid(row=row,column=2,sticky='w',padx=4)
                self.reference_hints[(component,code)]=hint
                if info['var'] is not None:
                    info['var'].trace_add('write',lambda *_:self.update_reference_hints())
                else:widget.bind('<FocusOut>',lambda e:self.update_reference_hints(),add='+')
        self.update_reference_hints()

    def reference_values(self):
        values={(component,code):self.value(info) for component,entries in self.widgets.items() for code,info in entries.items()}
        values.update({('context',code):value for code,value in self.source_context_snapshot.items()})
        return values

    def effective_references(self):
        refs=dict(self.field_references)
        if self.father_is_declarant.get():
            for code,info in self.widgets.get('father',{}).items():
                if code in self.widgets.get('declarant',{}) and self.value(info)=='' and (self.widgets['declarant'][code]['kind']!='Checkbox'):
                    source=('declarant',code)
                    if str(self.value(self.widgets['declarant'][code])).strip():
                        refs.setdefault(('father',code),source)
        return refs

    def update_reference_hints(self):
        if not hasattr(self,'reference_hints'):return
        refs=self.effective_references()
        try:resolved=resolve_references(self.reference_values(),refs)
        except ValueError:resolved={}
        for key,label in self.reference_hints.items():
            source=refs.get(key)
            if self.widgets[key[0]][key[1]].get('hint_label') is label:
                if source:self.widgets[key[0]][key[1]]['hint_var'].set(f'↪ {resolved.get(key,"Bezug prüfen")}')
                else:
                    inherited=self.resolve_inheritance(self.widgets[key[0]][key[1]]['spec']['inherit_from'])
                    self.widgets[key[0]][key[1]]['hint_var'].set(f'↪ {inherited}' if inherited else '')
            else:label.config(text=f'↪ {resolved.get(key,"Bezug prüfen")}' if source else '')
        if self.father_is_declarant.get():self.father_confirmed.set(True)

    def choose_reference(self,target):
        window=tk.Toplevel(self);window.title('Feldbezug festlegen');window.geometry('580x330');window.transient(self)
        ttk.Label(window,text='Originaltext bleibt erhalten. Wähle das Feld, auf das die Quelle verweist.',wraplength=540).pack(anchor='w',padx=12,pady=12)
        titles={comp['id']:component_label(comp) for comp in self.form['components']}
        keys=[key for key in self.reference_values() if key!=target and self.reference_values()[key] not in ('',False)]
        labels=[f'{titles.get(comp,comp)} · {field_label(code)}: {self.reference_values()[(comp,code)]}' for comp,code in keys]
        selection=tk.StringVar()
        combo=ttk.Combobox(window,textvariable=selection,values=labels,state='readonly');combo.pack(fill='x',padx=12)
        if labels:combo.current(0)
        ttk.Label(window,text='Für „come sopra“ den ursprünglichen Namen, Ort oder Beruf wählen; für „mese sudetto“ beispielsweise den Monat des Akts.',wraplength=540).pack(anchor='w',padx=12,pady=12)
        def apply():
            index=combo.current()
            if index<0:return
            refs=self.effective_references();refs[target]=keys[index]
            try:resolve_references(self.reference_values(),refs)
            except ValueError as exc:
                messagebox.showerror('Bezug nicht möglich',str(exc),parent=window);return
            self.field_references[target]=keys[index];self.update_reference_hints();window.destroy()
        def remove():
            self.field_references.pop(target,None);self.update_reference_hints();window.destroy()
        ttk.Button(window,text='Bezug übernehmen',command=apply).pack(side='right',padx=12,pady=12)
        ttk.Button(window,text='Bezug entfernen',command=remove).pack(side='left',padx=12,pady=12)

    def reset_reference_controls(self):
        self.field_references={}
        self.father_is_declarant.set(False);self.father_confirmed.set(False);self.mother_confirmed.set(False)
        self.update_reference_hints()
