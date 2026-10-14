"""Session-level keyboard savings for repeated source wording."""
import tkinter as tk
from tkinter import ttk

class CaptureDefaults:
    def setup_capture_defaults(self):
        if not hasattr(self,'officer_defaults'):self.officer_defaults={}
        setting=self.officer_defaults.get(self.context_id,{})
        self.keep_officer=tk.BooleanVar(value=setting.get('enabled',False))
        self.officer_saved_owner=None
        fields=self.widgets.get('officer',{})
        if fields:
            parent=next(iter(fields.values()))['widget'].master
            tools=ttk.Frame(parent)
            tools.grid(row=len(fields),column=0,columnspan=4,sticky='w',padx=8,pady=6)
            ttk.Checkbutton(tools,text='Sindaco für die nächsten Akte beibehalten',variable=self.keep_officer,command=self.remember_officer_setting).pack(anchor='w')
            ttk.Label(tools,text='Gleichbleibende Quellenangaben bleiben stehen. Änderungen direkt im Feld überschreiben.',wraplength=450).pack(anchor='w')
            if setting.get('enabled'):
                for code,stored in setting.get('fields',{}).items():
                    if code in fields and fields[code]['var'] is not None:
                        fields[code]['var'].set(stored['value'])
                        fields[code]['carry_default']=dict(stored)
        location=self.widgets.get('record',{}).get('record_place_raw')
        if location and location['var'] is not None and location['spec'].get('inherit_from'):
            value=self.resolve_inheritance(location['spec']['inherit_from'])
            if value:
                location['context_prefill']=value
                location['var'].set(value)
        self.update_reference_hints()

    def remember_officer_setting(self):
        setting=self.officer_defaults.setdefault(self.context_id,{})
        setting['enabled']=self.keep_officer.get()

    def cache_officer_after_save(self,owners):
        self.remember_officer_setting()
        if not self.keep_officer.get():return
        self.officer_defaults[self.context_id]['fields']={
            code:{'value':self.value(info),'owner_id':owners.get('officer')}
            for code,info in self.widgets.get('officer',{}).items()
            if info['var'] is not None
        }

    def restore_capture_defaults_after_clear(self):
        if self.keep_officer.get():
            for code,stored in self.officer_defaults.get(self.context_id,{}).get('fields',{}).items():
                if code in self.widgets.get('officer',{}):
                    info=self.widgets['officer'][code]
                    info['var'].set(stored['value']);info['carry_default']=dict(stored)
        else:
            for info in self.widgets.get('officer',{}).values():info.pop('carry_default',None)
        location=self.widgets.get('record',{}).get('record_place_raw')
        if location and location.get('context_prefill'):
            location['var'].set(location['context_prefill'])
        self.update_reference_hints()
