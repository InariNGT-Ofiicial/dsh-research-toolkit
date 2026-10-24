"""Tests of real compiler behavior and the SPSS false-positive regression."""
import csv
import json
import os
import subprocess
import sys
import shutil
import uuid
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_bridge.adapters.stats import SUPPORTED_ENGINES, compile_job, normalize_spss_xml


class StatisticalCompilerTests(unittest.TestCase):
    def test_julia_analysis_treats_dollar_paths_as_literal_data(self):
        folder=self.root/'数据 $ literal'
        folder.mkdir()
        data=folder/'input $ value.csv'
        shutil.copy2(self.data,data)
        target=self.root/'输出 $ literal'
        item=self.job('julia','analysis')
        item['inputs']['data']=str(data)
        compiled=compile_job(item,target,{})
        source=Path(compiled['source_path']).read_text(encoding='utf-8')
        self.assertIn('数据 \\$ literal/input \\$ value.csv',source)
        self.assertIn('输出 \\$ literal',source)
        self.assertNotIn('数据 $ literal',source)
        # R does not interpolate dollar signs inside quoted strings.
        other=compile_job({**item,'engine':'r'},self.root/'r',{})
        self.assertIn('数据 $ literal',Path(other['source_path']).read_text(encoding='utf-8'))
    def setUp(self):
        temporary_parent=Path(os.environ.get("RB_TEST_TEMP",str(Path.cwd()/"work")))
        temporary_parent.mkdir(parents=True,exist_ok=True)
        self.temporary_parent=temporary_parent.resolve()
        self.root=self.temporary_parent/("stats-test-"+uuid.uuid4().hex)
        self.root.mkdir()
        self.data=self.root/"input with spaces.csv"
        with self.data.open("w",newline="",encoding="utf-8") as f:
            writer=csv.writer(f); writer.writerow(["score","time","treatment","time_treatment"])
            for i in range(20): writer.writerow([5+1.2*i+2*(i%2)+.4*i*(i%2)+(.1 if i%3 else -.2),i,i%2,i*(i%2)])
            writer.writerow(["",5,1,5])
    def tearDown(self):
        resolved=self.root.resolve()
        if not resolved.is_relative_to(self.temporary_parent) or resolved==self.temporary_parent:
            raise AssertionError("Refusing cleanup outside the test workspace")
        shutil.rmtree(resolved)
    def job(self,engine="python",operation="analysis"):
        return {"engine":engine,"operation":operation,"inputs":{"data":str(self.data)},"parameters":{}}
    def test_all_missing_runtimes_still_compile_native_source(self):
        for engine in SUPPORTED_ENGINES:
            with self.subTest(engine=engine):
                result=compile_job(self.job(engine),self.root/engine,{})
                self.assertFalse(result["ready"]); self.assertEqual(result["command"],[])
                self.assertTrue(Path(result["source_path"]).is_file())
    def test_real_python_analysis_audits_missing_and_writes_numeric_results(self):
        compiled=compile_job(self.job(),self.root/"analysis",{"python":sys.executable})
        env={**os.environ,**compiled["env"]}
        run=subprocess.run(compiled["command"],cwd=compiled["cwd"],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr); self.assertIn("RB_STATISTICS_COMPLETE",run.stdout)
        metrics=json.loads((self.root/"analysis/metrics.json").read_text())
        self.assertEqual((metrics["n_rows"],metrics["n_complete"],metrics["n_excluded"]),(21,20,1))
        self.assertGreater(metrics["r_squared"],.99)
    def test_rejects_native_identifier_injection(self):
        job=self.job(); job["parameters"]={"outcome":"score;system('x')"}
        with self.assertRaises(ValueError): compile_job(job,self.root/"bad",{})
    def test_rejects_expected_artifact_escape(self):
        source=self.root/"test.py"; source.write_text("print('hello')")
        job={"engine":"python","operation":"script","inputs":{"script":str(source)},"parameters":{"expected_artifacts":["../../escape"]}}
        with self.assertRaises(ValueError): compile_job(job,self.root/"job",{})
    def _fake_spss(self,fail=False):
        fake=self.root/"fake"; fake.mkdir(exist_ok=True)
        (fake/"spss.py").write_text("from pathlib import Path\nimport os\ndef StartSPSS():\n Path(os.environ['SPSS_CALL_LOG']).write_text('started')\n"+(" raise RuntimeError('not licensed')\n" if fail else "")+"def SetOutput(value): pass\ndef Submit(code):\n Path(os.environ['SPSS_CALL_LOG']).write_text('submitted:'+code)\ndef GetLastErrorLevel(): return 0\ndef GetCaseCount(): return 2\ndef GetVariableCount(): return 1\ndef GetDefaultPlugInVersion(): return 'test-double'\ndef StopSPSS(): pass\n")
        return fake
    def test_spss_probe_really_starts_and_submits_sentinel(self):
        fake=self._fake_spss(); compiled=compile_job(self.job("spss","probe"),self.root/"probe",{"spss":sys.executable})
        log=self.root/"calls.txt"
        run=subprocess.run(compiled["command"],env={**os.environ,**compiled["env"],"PYTHONPATH":str(fake),"SPSS_CALL_LOG":str(log)},capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr); self.assertIn("submitted:",log.read_text())
        self.assertIn("RB_SPSS_VERIFIED_COMPLETE",run.stdout)
        self.assertEqual(json.loads((self.root/"probe/spss_probe.json").read_text())["case_count"],2)
    def test_spss_license_failure_cannot_report_success(self):
        fake=self._fake_spss(fail=True); compiled=compile_job(self.job("spss","probe"),self.root/"denied",{"spss":sys.executable})
        run=subprocess.run(compiled["command"],env={**os.environ,**compiled["env"],"PYTHONPATH":str(fake),"SPSS_CALL_LOG":str(self.root/"calls.txt")},capture_output=True,text=True,timeout=10)
        self.assertNotEqual(run.returncode,0); self.assertNotIn("RB_SPSS_VERIFIED_COMPLETE",run.stdout)
        self.assertFalse((self.root/"denied/spss_probe.json").exists())
        self.assertIn("not licensed",(self.root/"denied/spss_error.json").read_text())
    def test_spss_xml_uses_precise_native_numbers_and_checks_model_terms(self):
        xml=self.root/"results.xml"
        xml.write_text('''<outputTree xmlns="http://www.ibm.com/software/analytics/spss/xml/oms">
<pivotTable subType="Coefficients"><dimension><category><dimension>
<category><cell number="50.1234567890123" text="50.123"/><cell number="0.1234567890123" text=".123"/></category>
<category varName="x"><cell number="1.9876543210987" text="1.988"/><cell number="0.2345678901234" text=".235"/></category>
</dimension></category></dimension></pivotTable>
<pivotTable subType="Model Summary"><cell number="0.9"/><cell number="0.81"/><cell number="0.8"/><cell number="1.2345678901234"/></pivotTable>
<pivotTable subType="Descriptive Statistics"><dimension>
<category varName="y"><cell number="20"/><cell number="0"/><cell number="2"/><cell number="1"/><cell number="0.5"/></category>
<category varName="x"><cell number="20"/><cell number="0"/><cell number="2"/><cell number="1"/><cell number="0.5"/></category>
</dimension></pivotTable></outputTree>''',encoding="utf-8")
        metrics=normalize_spss_xml(xml,self.root,["x"],{"n_rows":21,"n_complete":20,"n_excluded":1})
        self.assertEqual(metrics["r_squared"],.81)
        with (self.root/"coefficients.csv").open(newline="") as f: rows=list(csv.DictReader(f))
        self.assertEqual(float(rows[0]["estimate"]),50.1234567890123)
        self.assertEqual(float(rows[1]["std_error"]),.2345678901234)
        with self.assertRaises(ValueError): normalize_spss_xml(xml,self.root,["wrong"],{"n_complete":20})
    def test_spss_truncated_oms_cannot_be_success(self):
        xml=self.root/"truncated.xml"; xml.write_text("</outputTree>")
        with self.assertRaises(Exception): normalize_spss_xml(xml,self.root,["x"],{"n_complete":20})
        self.assertFalse((self.root/"coefficients.csv").exists())
    @unittest.skipUnless(os.name=="nt","SPSS job mutex uses the Windows local namespace")
    def test_spss_same_installation_is_serialized_and_busy_is_explicit(self):
        fake=self._fake_spss()
        source=fake/"spss.py"
        source.write_text(source.read_text().replace("import os\n","import os,time\n").replace("write_text('started')\n","write_text('started')\n time.sleep(1.0)\n"))
        job=self.job("spss","probe"); job["parameters"]={"lock_wait_s":0.1}
        first=compile_job(job,self.root/"first",{"spss":sys.executable})
        second=compile_job(job,self.root/"second",{"spss":sys.executable})
        env={**os.environ,"PYTHONPATH":str(fake),"SPSS_CALL_LOG":str(self.root/"calls.txt")}
        process=subprocess.Popen(first["command"],env={**env,**first["env"]},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertIn("RB_SPSS_STARTING_ENGINE",process.stdout.readline())
            busy=subprocess.run(second["command"],env={**env,**second["env"]},capture_output=True,text=True,timeout=5)
            self.assertEqual(busy.returncode,2,busy.stderr)
            self.assertIn("RB_BLOCKED:",busy.stdout)
            self.assertFalse((self.root/"second/spss_probe.json").exists())
            self.assertEqual(json.loads((self.root/"second/spss_busy.json").read_text())["status"],"blocked")
            stdout,stderr=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,stderr)
            self.assertIn("RB_SPSS_VERIFIED_COMPLETE",stdout)
        finally:
            if process.poll() is None: process.kill(); process.communicate(timeout=5)


if __name__=="__main__": unittest.main()
