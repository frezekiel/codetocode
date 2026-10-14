from pathlib import Path
import tempfile
import unittest

import db
from capture_relations import resolve_references, save_parent_relations, save_references


class RelationTests(unittest.TestCase):
    def test_pointer_chain_and_cycles(self):
        values = {('record','month'):'Gennaio', ('birth','month'):'mese sudetto', ('later','month'):'come sopra'}
        refs = {('birth','month'):('record','month'), ('later','month'):('birth','month')}
        self.assertEqual('Gennaio', resolve_references(values,refs)[('later','month')])
        refs[('record','month')]=('later','month')
        with self.assertRaises(ValueError):resolve_references(values,refs)
        with self.assertRaises(ValueError):resolve_references({('a','name'):'',('b','name'):'come sopra'},{('b','name'):('a','name')})

    def test_identity_parent_and_raw_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.sqlite';db.init_db(path)
            form=db.load_form(db.ROOT/'forms/nas_1809_alpha_v3.json')
            with db.connect(path) as con:
                form_id=db.ensure_form_version(con,form)
                session=db.create_session(con,'test','2026-10-06')
                context=db.ensure_context(con,'NAS','TEST')
                record=db.create_record(con,session,context,form_id,'NAS','NAS-TEST')
                owners={role:db.create_pri(con,record,role) for role in ['declarant','father','mother','child']}
                save_parent_relations(con,record,owners,True,False,True)
                relations=[tuple(r) for r in con.execute('SELECT subject_pri_id,t.code,object_pri_id FROM pri_relation r JOIN relation_type t ON t.relation_type_id=r.relation_type_id')]
                self.assertIn((owners['father'],'same_person_in_record',owners['declarant']),relations)
                self.assertIn((owners['father'],'father_of',owners['child']),relations)
                self.assertIn((owners['mother'],'mother_of',owners['child']),relations)
                fields={'declarant':{'domicile_raw':'Cortale'},'father':{'domicile_raw':'come sopra'}}
                save_references(con,form['components'],owners,fields,{('father','domicile_raw'):('declarant','domicile_raw')})
                row=con.execute("SELECT * FROM field_value WHERE owner_id=? AND owner_type='PRI'",(owners['father'],)).fetchone()
                self.assertEqual('come sopra',row['raw_value'])
                self.assertEqual('Cortale',row['norm_value'])
                self.assertEqual(('inherited','PRI',owners['declarant'],'domicile_raw'),tuple(row[k] for k in ['value_origin','origin_owner_type','origin_owner_id','origin_field_code']))
                self.assertEqual(0,con.execute('SELECT COUNT(*) FROM mid').fetchone()[0])

    def test_no_relationship_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.sqlite';db.init_db(path)
            with db.connect(path) as con:
                save_parent_relations(con,1,{},False,False,False)
                self.assertEqual(0,con.execute('SELECT COUNT(*) FROM pri_relation').fetchone()[0])


if __name__=='__main__':unittest.main()
