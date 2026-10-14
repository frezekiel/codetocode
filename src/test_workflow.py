import sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path('src').resolve()))
import db
from app import CtCApp,FormBuilder,starter_components

original_connect=db.connect;original_init=db.init_db
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);(root/'forms').mkdir();path=root/'ui.sqlite'
 for family in ['NAS','MAT','MOR','MIG']:
  form={'form_code':family+'_TEST','source_family':family,'label':family,'components':starter_components(family)}
  (root/'forms'/f'{family}.json').write_text(json.dumps(form),encoding='utf-8')
 with patch.object(db,'ROOT',root),patch.object(db,'connect',lambda db_path=path:original_connect(db_path)),patch.object(db,'init_db',lambda:original_init(path)):
  app=CtCApp();app.update()
  app.transcriber_var.set('UI test');app.create_session_and_continue();app.update()
  errors=[]
  import app as app_module
  app_module.messagebox.showerror=lambda *args,**kwargs: errors.append(('dialog',args))
  app_module.messagebox.showwarning=lambda *args,**kwargs: errors.append(('warning',args))
  app.report_callback_exception=lambda *args:errors.append(args)
  builder=FormBuilder(app,source_form=db.load_form(root/'forms/NAS.json'))
  builder.geometry('900x600');app.update()
  for index in range(4):
   builder.wizard.select(index);app.update()
   button=builder.next_button
   assert button.winfo_ismapped()
   assert button.winfo_rooty()+button.winfo_height()<=builder.winfo_rooty()+builder.winfo_height()
  builder.wizard.select(2);app.update()
  builder.wizard.select(3);app.update();builder.save_form();app.update()
  assert not builder.winfo_exists()
  app.withdraw()
  for family in ['NAS','MAT','MOR','MIG']:
   app.form_path=root/'forms'/f'{family}.json'
   app.show_source_page();app.update()
   if family=='NAS':
    app.context_widgets['comune_universita_raw']['var'].set('Cortale')
    app.context_widgets['register_year_raw']['var'].set('1818')
   app.prepare_capture();app.update()
   assert app.current_page=='capture',family
   if family=='NAS':
    assert app.widgets['record']['record_place_raw']['var'].get()=='Cortale'
    app.keep_officer.set(True)
    app.widgets['officer']['given_name_raw']['var'].set('G.')
    app.widgets['officer']['surname_raw']['var'].set('Cefali')
    app.widgets['record']['record_number_raw']['var'].set('8')
    app.widgets['declarant']['given_name_raw']['var'].set('Nicola')
    app.widgets['declarant']['surname_raw']['var'].set('Pellegrino')
    app.widgets['declarant']['domicile_raw']['var'].set('Cortale')
    app.widgets['father']['domicile_raw']['var'].set('come sopra')
    app.widgets['record']['record_month_raw']['var'].set('Gennaio')
    app.widgets['birth']['event_month_raw']['var'].set('mese sudetto')
    app.father_is_declarant.set(True)
    app.field_references={('father','domicile_raw'):('declarant','domicile_raw'),('birth','event_month_raw'):('record','record_month_raw')}
    app.update_reference_hints()
    app.back_to_source_page();app.update();app.prepare_capture();app.update()
    assert app.father_is_declarant.get()
    assert app.field_references[('father','domicile_raw')]==('declarant','domicile_raw')
   app.accept_scan_reference('https://example.org/'+family+'.jpg')
   app.save_record(True);app.update()
   if family=='NAS':
    assert not app.father_is_declarant.get() and not app.field_references
    app.widgets['record']['record_number_raw']['var'].set('8')
    with patch.object(app_module.messagebox,'askyesno',return_value=False) as confirmation:
     app.save_record(True)
     assert confirmation.called
     assert app.widgets['record']['record_number_raw']['var'].get()=='8'
    assert app.widgets['officer']['given_name_raw']['var'].get()=='G.'
    assert app.widgets['officer']['surname_raw']['var'].get()=='Cefali'
    assert app.widgets['record']['record_place_raw']['var'].get()=='Cortale'
    app.widgets['record']['record_number_raw']['var'].set('9')
    app.save_record(True)
    app.widgets['record']['record_number_raw']['var'].set('10')
    app.widgets['officer']['surname_raw']['var'].set('Altro')
    app.save_record(True)
    assert app.widgets['officer']['surname_raw']['var'].get()=='Altro'


   app.back_to_source_page();app.update()
  with db.connect() as con:
   print('Records',con.execute('SELECT COUNT(*) FROM source_record').fetchone()[0], 'Errors',errors)
   assert not errors,errors
   assert con.execute('SELECT COUNT(*) FROM source_record').fetchone()[0]==6
   assert con.execute("SELECT COUNT(*) FROM field_value WHERE field_code='scan_url_raw'").fetchone()[0]==6
   assert con.execute("SELECT COUNT(*) FROM pri_relation r JOIN relation_type t ON t.relation_type_id=r.relation_type_id WHERE t.code='father_of'").fetchone()[0]==1
   assert con.execute("SELECT COUNT(*) FROM pri_relation r JOIN relation_type t ON t.relation_type_id=r.relation_type_id WHERE t.code='same_person_in_record'").fetchone()[0]==1
   row=con.execute("SELECT raw_value,norm_value,value_origin FROM field_value WHERE field_code='event_month_raw' AND raw_value='mese sudetto'").fetchone()
   assert tuple(row)==('mese sudetto','Gennaio','inherited')
   row=con.execute("SELECT raw_value,norm_value FROM field_value WHERE field_code='domicile_raw' AND raw_value='come sopra'").fetchone()
   assert tuple(row)==('come sopra','Cortale')
   assert con.execute("SELECT COUNT(*) FROM field_value WHERE field_code='given_name_raw' AND raw_value='' AND norm_value='Nicola'").fetchone()[0]==1
   rows=con.execute("SELECT raw_value,value_origin,origin_owner_id FROM field_value WHERE field_code='surname_raw' AND raw_value IN ('Cefali','Altro') ORDER BY value_id").fetchall()
   assert [(r[0],r[1]) for r in rows]==[('Cefali','explicit'),('Cefali','default'),('Altro','explicit')],rows
   rows=con.execute("SELECT v.raw_value,v.norm_value,v.value_origin FROM field_value v JOIN source_record r ON r.record_id=v.owner_id AND v.owner_type='RECORD' WHERE v.field_code='record_place_raw' AND v.norm_value='Cortale' AND r.record_type='NAS'").fetchall()
   assert len(rows)==3 and all(tuple(row)==('','Cortale','inherited') for row in rows)
  assert not errors,errors
  app.show_birth_anchors();app.update()
  app.destroy()
print('Four-step wizard visible at 900x600; NAS/MAT/MOR/MIG capture and URL persistence: OK')


