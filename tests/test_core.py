import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_bridge.core import JobError, compile_job, run_compiled, run_process, save_json, validate_job
from research_bridge.verify import verify_directory

class CoreTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get("RB_TEST_TEMP",str(Path.cwd()/"work"))).resolve()
        parent.mkdir(parents=True,exist_ok=True)
        self.parent=parent
        self.root=parent/("core-test-"+uuid.uuid4().hex)
        self.root.mkdir()
    def tearDown(self):
        if self.parent not in self.root.resolve().parents:
            raise AssertionError("test cleanup escaped its parent")
        shutil.rmtree(self.root)
    def test_false_success_missing_marker_and_artifact(self):
        plan=dict(engine="python",operation="script",workspace=str(self.root),mode="native",ready=True,
                  command=[sys.executable,"-c","print('exited zero')"],expected_artifacts=[str(self.root/"required.txt")],required_markers=["ACTUAL_COMPLETE"])
        r=run_compiled(plan)
        self.assertEqual(r["status"],"failed")
        self.assertFalse(r["application_verified"])
        self.assertEqual(len(r["errors"]),2)
    def test_pdf_disguised_as_workbook_is_rejected(self):
        plan=dict(engine="office",operation="recalculate",workspace=str(self.root),mode="native",ready=True,
                  command=[sys.executable,"-c","from pathlib import Path; Path('book.xlsx').write_bytes(b'%PDF-1.7 fake'); print('DONE')"],expected_artifacts=[str(self.root/"book.xlsx")],required_markers=["DONE"])
        self.assertEqual(run_compiled(plan)["status"],"failed")
    def test_failed_scientific_oracle_cannot_pass_integrity_report(self):
        target=self.root/"answer.txt"
        plan=dict(engine="python",operation="script",workspace=str(self.root),mode="native",ready=True,
            command=[sys.executable,"-c","from pathlib import Path; Path('answer.txt').write_text('valid bytes'); print('DONE')"],required_markers=["DONE"],expected_artifacts=[str(target)])
        self.assertEqual(run_compiled(plan)["status"],"passed")
        save_json(self.root/"acceptance.json",dict(schema_version="research.acceptance.v1",status="failed",checks=[dict(status="failed",reason="numerical result differs from oracle")]))
        self.assertEqual(verify_directory(self.root)["status"],"failed")
    def test_timeout_is_not_success(self):
        r=run_process([sys.executable,"-c","import time; time.sleep(10)"],self.root,.2)
        self.assertEqual(r["status"],"failed")
        self.assertTrue(r["timed_out"])
    @unittest.skipUnless(os.name=="nt","Windows Job Object ownership")
    def test_detached_descendant_cannot_outlive_timeout(self):
        target=self.root/"orphan-wrote.txt"
        child="import time,pathlib; time.sleep(1.5); pathlib.Path("+repr(str(target))+").write_text('orphan')"
        parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"+repr(child)+"],creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(10)"
        result=run_process([sys.executable,"-c",parent],self.root,.3)
        self.assertTrue(result["timed_out"],result)
        time.sleep(1.7)
        self.assertFalse(target.exists(),"detached descendant survived cancellation")
    def test_fresh_artifact_and_integrity_recheck(self):
        target=self.root/"answer.txt"
        plan=dict(engine="python",operation="script",workspace=str(self.root),mode="native",ready=True,
            command=[sys.executable,"-c","from pathlib import Path; Path('answer.txt').write_text('verified'); print('DONE')"],required_markers=["DONE"],expected_artifacts=[str(target)])
        self.assertEqual(run_compiled(plan)["status"],"passed")
        self.assertEqual(verify_directory(self.root)["status"],"passed")
        target.write_text("tampered")
        self.assertEqual(verify_directory(self.root)["status"],"failed")
    def test_stale_artifacts_are_rejected_before_run(self):
        target=self.root/"old.txt"; target.write_text("old")
        with self.assertRaises(JobError):
            run_compiled(dict(engine="python",operation="script",workspace=str(self.root),mode="native",ready=True,command=[sys.executable,"-c","pass"],expected_artifacts=[str(target)]))
    def test_schema_rejects_unknown_operations(self):
        with self.assertRaises(JobError):
            validate_job(dict(schema_version="research.job.v1",engine="r",operation="erase"))
    def test_missing_runtime_generates_source_but_stays_blocked(self):
        data=self.root/"source.csv"; data.write_text("x,y\n1,3\n2,5\n3,7\n4,9\n")
        out=self.root/"job"
        p=compile_job(dict(schema_version="research.job.v1",engine="stata",operation="analysis",inputs=dict(data=str(data)),parameters=dict(outcome="y",predictors=["x"])),out,dict(executables=dict(stata=str(self.root/"missing.exe"))))
        # Existing installations can be discovered; the test only asserts when absent.
        if not p["ready"]:
            self.assertTrue(Path(p["source_path"]).is_file())
            self.assertEqual(run_compiled(p)["status"],"blocked")

if __name__=="__main__": unittest.main()
