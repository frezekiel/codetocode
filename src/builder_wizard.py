"""Four-step form workflow with a footer outside the scrollable content."""
import tkinter as tk
from tkinter import ttk, messagebox
from ui_labels import component_label


class BuilderWizard:
    def wizard_start(self):
        self.geometry('1080x720'); self.minsize(780,520)
        footer=ttk.Frame(self,padding=(16,10))
        footer.pack(side='bottom',fill='x')
        ttk.Separator(self).pack(side='bottom',fill='x')
        ttk.Button(footer,text='Abbrechen',command=self.destroy).pack(side='left')
        self.previous_button=ttk.Button(footer,text='← Zurück',command=lambda:self.wizard_move(-1))
        self.previous_button.pack(side='left',padx=8)
        self.next_button=ttk.Button(footer,text='Weiter →',command=lambda:self.wizard_move(1))
        self.next_button.pack(side='right')
        ttk.Label(self,text='Formular einrichten',font=('Segoe UI',18,'bold')).pack(anchor='w',padx=16,pady=(14,4))
        ttk.Label(self,text='Vorlage wählen, anpassen und vor der Erfassung prüfen.').pack(anchor='w',padx=16,pady=(0,8))
        self.wizard=ttk.Notebook(self)
        self.wizard.pack(fill='both',expand=True,padx=16,pady=(0,8))
        self.steps=[]
        for title in ['1 · Vorlage','2 · Anpassen','3 · Vorschau','4 · Speichern']:
            step=ttk.Frame(self.wizard);self.wizard.add(step,text=title);self.steps.append(step)
        self.wizard.bind('<<NotebookTabChanged>>',self.wizard_changed)
        ttk.Label(self.steps[0],text='NAS · Nascite     MAT · Matrimoni     MOR · Morti     MIG · Passenger manifests',wraplength=850).pack(anchor='w',padx=8,pady=12)
        ttk.Label(self.steps[0],text='Die Auswahl legt die historische Feldstruktur fest. Fehlende Felder sind nicht dasselbe wie leere Felder.',wraplength=850).pack(anchor='w',padx=8,pady=8)
        self.preview_host=ttk.Frame(self.steps[2]);self.preview_host.pack(fill='both',expand=True)
        self.summary=ttk.Label(self.steps[3],text='',wraplength=700,justify='left',font=('Segoe UI',12))
        self.summary.pack(anchor='w',padx=24,pady=24)
        ttk.Label(self.steps[3],text='Bestehende Versionen bleiben erhalten. Nach dem Speichern öffnet sich die Quelleneinrichtung; dort prüfst du den Kontext und startest die Erfassung.',wraplength=700).pack(anchor='w',padx=24,pady=12)
        self.bind('<Control-Return>',lambda e:self.wizard_move(1))

    def wizard_move(self,delta):
        index=self.wizard.index(self.wizard.select())
        if delta>0 and index==0 and not self.code_var.get().strip():
            self.code_var.set(f'{self.family_var.get()}_{self.from_var.get().strip() or "FORM"}')
        if delta>0 and index==3:
            self.save_form();return
        self.wizard.select(max(0,min(3,index+delta)))

    def wizard_changed(self,event=None):
        if not hasattr(self,'code_var'):return
        index=self.wizard.index(self.wizard.select())
        self.previous_button.state(['disabled'] if index==0 else ['!disabled'])
        self.next_button.config(text='Speichern und erfassen' if index==3 else 'Weiter →')
        if getattr(self,'current_index',None) is not None:self.apply_component_settings(keep_selection=False)
        if index==2:
            for child in self.preview_host.winfo_children():child.destroy()
            from app import ScrollFrame
            scroll=ScrollFrame(self.preview_host);scroll.pack(fill='both',expand=True)
            ttk.Label(scroll.inner,text='Vorschau — Eingaben hier werden nicht gespeichert.',padding=8).pack(anchor='w')
            for comp in self.form['components']:
                box=ttk.LabelFrame(scroll.inner,text=component_label(comp));box.pack(fill='x',padx=8,pady=6)
                if comp.get('repeatable'):
                    ttk.Label(box,text=f'Wiederholbar · {comp.get("default_instances",1)} Instanz(en) zum Start').pack(anchor='w')
                    fields_host=ttk.Frame(box);fields_host.pack(fill='x')
                else:fields_host=box
                self.master.render_fields(fields_host,comp.get('fields',[]),allow_inheritance=False)
        if index==3:
            count=sum(len(c.get('fields',[])) for c in self.form['components'])
            self.summary.config(text=f'{self.label_var.get()}\n\nFormularcode: {self.code_var.get()}\nAktart: {self.family_var.get()}\nZeitraum: {self.from_var.get() or "offen"} – {self.to_var.get() or "offen"}\n\n{len(self.form["components"])} Abschnitte · {count} Felder')
