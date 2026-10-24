"""Independent interchange checks: external XSD and real Pandoc citeproc."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from lxml import etree

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from research_bridge.adapters import exchange, exchange_worker as worker

VALIDATION = Path(os.environ.get('RB_EXCHANGE_VALIDATION',str(SOURCE.parent/'exchange-validation'))).resolve()
SCHEMA_PATH = Path(os.environ.get('REFI_CODEBOOK_XSD',str(SOURCE/'tests/fixtures/Codebook.xsd')))
PANDOC = os.environ.get('PANDOC') or shutil.which('pandoc') or r'E:\ResearchTools\Typesetting\Pandoc\pandoc.exe'
GUIDS = ['aabbccdd-0000-4000-8000-000000000001','aabbccdd-0000-4000-8000-000000000002','aabbccdd-0000-4000-8000-000000000003','aabbccdd-0000-4000-8000-000000000004']

class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.parent=VALIDATION/'cases'
        self.parent.mkdir(parents=True,exist_ok=True)
        self.root=self.parent/(self._testMethodName+'-'+uuid.uuid4().hex)
        self.root.mkdir()
        self.sample={'origin':'DSH 独立验收', 'codes':[
            {'guid':GUIDS[0],'name':'结构性支持 & Policy','isCodable':False,'color':'#2563eb',
             'description':'理论 <机制> 与证据\n保留中英文与 XML 字符。',
             'children':[{'guid':GUIDS[1],'name':'公共服务 / Access','isCodable':True,'color':'#a0F',
                          'description':'', 'children':[{'guid':GUIDS[2],'name':'Nested: β','isCodable':True}]}]}],
            'sets':[{'guid':GUIDS[3],'name':'机制集合','description':'Cross-cutting links','member_guids':[GUIDS[0],GUIDS[2]]}]}
    def tearDown(self):
        if os.environ.get('RB_KEEP_EXCHANGE_ARTIFACTS')!='1':
            if self.parent not in self.root.resolve().parents:
                raise AssertionError('cleanup escaped test parent')
            shutil.rmtree(self.root)
    def json_input(self,data,name='input.json'):
        path=self.root/name
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        return path
    def export(self,data=None):
        src=self.json_input(self.sample if data is None else data)
        return worker.codebook({'inputs':{'source':str(src)}},self.root)
    def schema_validate(self,path):
        parser=etree.XMLParser(resolve_entities=False,no_network=True)
        schema=etree.XMLSchema(etree.parse(str(SCHEMA_PATH),parser))
        doc=etree.parse(str(path),parser)
        self.assertTrue(schema.validate(doc),str(schema.error_log))
    def import_file(self,path=None):
        return worker.import_codebook({'inputs':{'source':str(path or self.root/'codebook.qdc')}},self.root)
    def test_nested_bilingual_codebook_passes_external_xsd(self):
        result=self.export()
        self.schema_validate(self.root/'codebook.qdc')
        self.assertEqual(result['codes'],3)
        self.assertEqual(result['sets'],1)
        self.assertFalse(result['application_verified'])
    def test_external_schema_rejects_tampered_color_and_missing_required_flag(self):
        self.export()
        original=(self.root/'codebook.qdc').read_text(encoding='utf-8')
        parser=etree.XMLParser(resolve_entities=False,no_network=True)
        schema=etree.XMLSchema(etree.parse(str(SCHEMA_PATH),parser))
        for xml in [original.replace('#2563eb','orange'),original.replace(' isCodable="false"','',1)]:
            self.assertFalse(schema.validate(etree.fromstring(xml.encode('utf-8'),parser)))
    def test_codebook_roundtrip_preserves_hierarchy_flags_sets_and_text(self):
        self.export()
        self.import_file()
        imported=json.loads((self.root/'codebook.json').read_text(encoding='utf-8'))
        self.assertEqual(imported,self.sample)
        self.export(imported)
        self.schema_validate(self.root/'codebook.qdc')
    def test_guid_case_or_brace_variants_are_duplicates(self):
        for duplicate in [GUIDS[0],GUIDS[0].upper(),'{'+GUIDS[0].upper()+'}']:
            data=copy.deepcopy(self.sample)
            data['codes'][0]['children'][0]['guid']=duplicate
            with self.assertRaisesRegex(ValueError,'duplicate'):
                self.export(data)
    def test_illegal_colors_fail_export(self):
        for color in ['blue','#12','#abcd','#gggggg','#1234567','123456',None]:
            with self.subTest(color=color):
                data=copy.deepcopy(self.sample)
                data['codes'][0]['color']=color
                with self.assertRaisesRegex(ValueError,'color'):
                    self.export(data)
    def test_invalid_guid_or_xml_control_character_is_rejected(self):
        data=copy.deepcopy(self.sample)
        data['codes'][0]['guid']='not-a-uuid'
        with self.assertRaisesRegex(ValueError,'GUID'):
            self.export(data)
        data=copy.deepcopy(self.sample)
        data['codes'][0]['name']='control\x01char'
        with self.assertRaisesRegex(ValueError,'XML'):
            self.export(data)
    def test_unresolved_set_member_is_rejected(self):
        data=copy.deepcopy(self.sample)
        data['sets'][0]['member_guids']=[str(uuid.uuid4())]
        with self.assertRaisesRegex(ValueError,'unknown code'):
            self.export(data)
    def test_import_rejects_namespace_missing_flag_duplicate_guid_bad_color(self):
        self.export()
        original=(self.root/'codebook.qdc').read_text(encoding='utf-8')
        bad=[original.replace(worker.NS,'urn:not-refi'),
             original.replace(' isCodable="false"','',1),
             original.replace(GUIDS[1],GUIDS[0].upper()),
             original.replace('#2563eb','red')]
        for i,xml in enumerate(bad):
            with self.subTest(index=i):
                path=self.root/f'invalid-{i}.qdc'
                path.write_text(xml,encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.import_file(path)
    def test_import_rejects_unknown_elements_and_dtd(self):
        self.export()
        original=(self.root/'codebook.qdc').read_text(encoding='utf-8')
        invalid=self.root/'invalid.qdc'
        invalid.write_text(original.replace('</CodeBook>','<Unsupported /></CodeBook>'),encoding='utf-8')
        with self.assertRaises(ValueError):
            self.import_file(invalid)
        invalid.write_text('<!DOCTYPE CodeBook [<!ENTITY x "expanded">]>'+original.split('?>',1)[1],encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'DTD'):
            self.import_file(invalid)
    def test_import_operation_compiles_and_runs_worker_without_application_claim(self):
        self.export()
        out=self.root/'import-run';out.mkdir()
        plan=exchange.compile_job({'engine':'nvivo','operation':'import_codebook','inputs':{'source':str(self.root/'codebook.qdc')}},out,{})
        process=subprocess.run(plan['command'],cwd=plan['cwd'],capture_output=True,text=True,timeout=30)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn('RB_EXCHANGE_COMPLETE',process.stdout)
        audit=json.loads((out/'exchange-audit.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['scope'],'file_interchange')
        self.assertFalse(audit['application_verified'])
        self.assertEqual(json.loads((out/'codebook.json').read_text(encoding='utf-8')),self.sample)
    def test_import_independent_schema_fixture_with_prefix_braced_guid_boolean_tokens(self):
        xml='''<?xml version="1.0" encoding="UTF-8"?>
<qda:CodeBook xmlns:qda="urn:QDA-XML:codebook:1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="urn:QDA-XML:codebook:1.0 http://schema.qdasoftware.org/versions/Codebook/v1.0/Codebook.xsd" origin="External fixture">
 <qda:Codes><qda:Code guid="{AABBCCDD-0000-4000-8000-000000000001}" name="外部研究" isCodable=" 0 " color=" #abc ">
  <qda:Code guid="aabbccdd-0000-4000-8000-000000000002" name="Evidence" isCodable="1" />
 </qda:Code></qda:Codes></qda:CodeBook>'''
        path=self.root/'independent-standard-fixture.qdc'
        path.write_text(xml,encoding='utf-8')
        self.schema_validate(path)
        self.import_file(path)
        parsed=json.loads((self.root/'codebook.json').read_text(encoding='utf-8'))
        self.assertEqual(parsed['codes'][0]['guid'],GUIDS[0])
        self.assertFalse(parsed['codes'][0]['isCodable'])
        self.assertEqual(parsed['codes'][0]['color'],'#abc')
        self.assertTrue(parsed['codes'][0]['children'][0]['isCodable'])
    def bibliography_and_pandoc(self,engine,format):
        data=[{'id':'refAlpha','title':'Survey {A} & α_2: 50% cost #1 $5 ~ x^2 \\ path',
               'author':[{'family':'García','given':'Ana'},{'family':'Smith','given':'John'}],
               'year':2024,'container-title':'Research & Methods','DOI':'https://doi.org/10.1234/test.2024'},
              {'id':'refChina','title':'公共服务与科研桥接：复杂调用的可复现验证',
               'author':[{'family':'张','given':'晓明'}], 'year':2025,'container-title':'方法研究','DOI':'10.5678/中文'}]
        src=self.json_input(data,'references.json')
        audit=worker.bibliography({'engine':engine,'inputs':{'source':str(src)}},self.root)
        self.assertFalse(audit['application_verified'])
        refs=self.root/('references.bib' if format=='bibtex' else 'references.ris')
        parsed=subprocess.run([PANDOC,str(refs),'--from',format,'--to','csljson'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(parsed.returncode,0,parsed.stderr)
        parsed_json=json.loads(parsed.stdout)
        (self.root/'pandoc-parsed.json').write_text(parsed.stdout,encoding='utf-8')
        self.assertEqual(len(parsed_json),2)
        byid={r['id']:r for r in parsed_json}
        self.assertEqual(set(byid),{'refAlpha','refChina'})
        self.assertEqual(byid['refAlpha']['DOI'],'10.1234/test.2024')
        self.assertEqual(byid['refAlpha']['issued']['date-parts'][0][0],2024)
        self.assertEqual(byid['refAlpha']['author'][0]['family'],'García')
        self.assertIn('公共服务',byid['refChina']['title'])
        self.assertIn('50%',byid['refAlpha']['title'])
        self.assertIn('\\ path',byid['refAlpha']['title'])
        markdown=self.root/'citations.md'
        markdown.write_text('Prior work [@refAlpha; @refChina].\n\n# References\n',encoding='utf-8')
        rendered=self.root/'citeproc.html'
        run=subprocess.run([PANDOC,str(markdown),'--citeproc','--bibliography',str(refs),'--to','html','--output',str(rendered)],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertNotIn('not found',run.stderr.lower())
        html=rendered.read_text(encoding='utf-8')
        self.assertIn('ref-refAlpha',html)
        self.assertIn('ref-refChina',html)
        self.assertIn('García',html)
        self.assertIn('公共服务',html)
    def test_bibtex_is_read_by_real_pandoc_and_citeproc(self):
        self.bibliography_and_pandoc('jabref','bibtex')
    def test_ris_is_read_by_real_pandoc_and_citeproc(self):
        self.bibliography_and_pandoc('endnote','ris')
    def test_corporate_bib_authors_survive_real_pandoc(self):
        data=[{'id':'explicit','title':'R Language','author':[{'literal':'R Core Team'}],'year':2025},
              {'id':'fallback','title':'R Methods','author':[{'family':'R Core Team'}],'year':2024}]
        source=self.json_input(data)
        worker.bibliography({'engine':'jabref','inputs':{'source':str(source)}},self.root)
        result=subprocess.run([PANDOC,str(self.root/'references.bib'),'--from','bibtex','--to','csljson'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        parsed=json.loads(result.stdout)
        (self.root/'pandoc-parsed.json').write_text(result.stdout,encoding='utf-8')
        self.assertEqual([r['author'][0] for r in parsed],[{'literal':'R Core Team'},{'literal':'R Core Team'}])
    def test_ris_keeps_institution_name_instead_of_dropping_it(self):
        source=self.json_input([{'id':'institution','title':'Institutional reference','author':[{'literal':'R Core Team'}],'year':2025}])
        worker.bibliography({'engine':'endnote','inputs':{'source':str(source)}},self.root)
        result=subprocess.run([PANDOC,str(self.root/'references.ris'),'--from','ris','--to','csljson'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        parsed=json.loads(result.stdout)
        # RIS has no unambiguous CSL literal flag. Preserve the full institution
        # as the family field with no fabricated given-name initials.
        self.assertEqual(parsed[0]['author'][0],{'family':'R Core Team'})
    def test_singleword_family_without_given_remains_a_personal_name(self):
        source=self.json_input([{'id':'personal','title':'A reference','author':[{'family':'Smith'}],'year':2025}])
        worker.bibliography({'engine':'jabref','inputs':{'source':str(source)}},self.root)
        result=subprocess.run([PANDOC,str(self.root/'references.bib'),'--from','bibtex','--to','csljson'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['author'][0],{'family':'Smith'})
    def test_prism_and_jasp_csv_remain_file_interchange(self):
        source=self.root/'source.csv';source.write_text('分组,value\ncontrol,1\ntreated,2\n',encoding='utf-8')
        for engine in ['prism','jasp']:
            out=self.root/engine;out.mkdir()
            plan=exchange.compile_job({'engine':engine,'operation':'table','inputs':{'source':str(source)}},out,{})
            result=subprocess.run(plan['command'],cwd=plan['cwd'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            audit=json.loads((out/'exchange-audit.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['scope'],'file_interchange')
            self.assertFalse(audit['application_verified'])

if __name__=='__main__':
    unittest.main()
