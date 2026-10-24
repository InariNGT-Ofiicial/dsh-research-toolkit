import json
import os
import re
import shutil
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_bridge.adapters.documents import compile_job
from research_bridge.core import run_process

class DocumentCompilerTests(unittest.TestCase):
    def setUp(self):
        self.parent=Path(os.environ.get("RB_TEST_TEMP",str(Path.cwd()/"work"))).resolve(); self.parent.mkdir(parents=True,exist_ok=True)
        self.root=self.parent/("doc-test-"+uuid.uuid4().hex); self.root.mkdir()
        self.source=self.root/"source"; self.source.mkdir()
        self.workspace=self.root/"job"; self.workspace.mkdir()
    def tearDown(self):
        if self.parent not in self.root.resolve().parents: raise AssertionError("cleanup escaped parent")
        shutil.rmtree(self.root)
    def test_word_cannot_disguise_pdf_as_recalculated_workbook(self):
        source=self.source/"test.docx"; source.write_text("fixture")
        with self.assertRaisesRegex(ValueError,"requires application=excel"):
            compile_job(dict(engine="office",operation="recalculate",inputs=dict(source=str(source)),parameters=dict(application="word")),self.workspace,{"office":"powershell.exe"})
    def test_git_rejects_copying_source_into_its_own_subdirectory(self):
        nested=self.source/"research-workspace/job"; nested.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,"outside the source"):
            compile_job(dict(engine="git",operation="snapshot",inputs=dict(source=str(self.source))),nested,{"git":"git"})
    def test_nested_document_resources_keep_relative_paths(self):
        source=self.source/"study.qmd"; source.write_text("data/observations.csv")
        data=self.source/"data/observations.csv"; data.parent.mkdir(); data.write_text("x,y\n1,2\n")
        compiled=compile_job(dict(engine="quarto",operation="render",inputs=dict(source=str(source),data=str(data)),parameters=dict(format="html")),self.workspace,{"quarto":"quarto"})
        self.assertEqual((self.workspace/"data/observations.csv").read_text(),data.read_text())
        self.assertEqual(compiled["input_map"][str(data)],str(self.workspace/"data/observations.csv"))
    def test_resource_map_cannot_escape_workspace(self):
        source=self.source/"study.qmd"; source.write_text("data")
        data=self.source/"observations.csv"; data.write_text("x,y\n1,2\n")
        with self.assertRaisesRegex(ValueError,"escapes"):
            compile_job(dict(engine="quarto",operation="render",inputs=dict(source=str(source),data=str(data)),parameters=dict(format="html",resource_map=dict(data="../../escaped.csv"))),self.workspace,{"quarto":"quarto"})
    def test_imagej_unicode_macro_survives_legacy_latin1_file_loader(self):
        home=self.root/"imagej"; (home/"jre/bin").mkdir(parents=True)
        java=home/"jre/bin/java.exe"; java.write_bytes(b"fixture")
        (home/"ij.jar").write_bytes(b"fixture")
        data=self.source/"图像 数据 $ literal.tif"; data.write_bytes(b"fixture")
        source=self.source/"analysis.ijm"; source.write_text('// 中文 comment and astral 🧪\nopen("{{INPUT_DATA}}");\nsaveAs("Results", "{{OUTPUT_DIR}}/measurements.csv");',encoding="utf-8")
        compiled=compile_job(dict(engine="imagej",operation="macro",inputs=dict(source=str(source),data=str(data))),self.workspace,{"imagej":str(home/"ImageJ.exe")})
        bootstrap=Path(compiled["source_path"]).read_bytes().decode("ascii")
        calls=re.findall(r'fromCharCode\(([0-9,]+)\)',bootstrap)
        self.assertGreater(len(calls),1)
        units=[]
        for call in calls:
            chunk=list(map(int,call.split(','))); self.assertLessEqual(len(chunk),96);units.extend(chunk)
        restored=b''.join(unit.to_bytes(2,"little") for unit in units).decode("utf-16-le")
        self.assertEqual(restored,(self.workspace/"analysis.utf8.ijm").read_text(encoding="utf-8"))
        self.assertIn(data.as_posix(),restored)
        self.assertIn("RB_IMAGEJ_COMPLETE",restored)
    def test_jupyter_relative_write_is_contained_in_copy_workspace(self):
        try: import nbconvert
        except ImportError: self.skipTest("nbconvert required for actual notebook regression")
        notebook={"nbformat":4,"nbformat_minor":5,"metadata":{"kernelspec":{"display_name":"DSH Research","language":"python","name":"dsh-research"}},"cells":[{"cell_type":"code","execution_count":None,"id":"relative-write","metadata":{},"outputs":[],"source":"from pathlib import Path\nPath('relative.txt').write_text('job-local')\nprint('done')"}]}
        source=self.source/"notebook.ipynb"; source.write_text(json.dumps(notebook),encoding="utf-8")
        compiled=compile_job(dict(engine="jupyter",operation="execute",inputs=dict(source=str(source)),timeout_s=30),self.workspace,{"jupyter":sys.executable})
        self.assertEqual(Path(compiled["source_path"]).parent,self.workspace)
        result=run_process(compiled["command"],compiled["cwd"],40,compiled["env"])
        self.assertEqual(result["status"],"passed",result)
        self.assertTrue((self.workspace/"relative.txt").is_file())
        self.assertFalse((self.source/"relative.txt").exists())

if __name__=="__main__": unittest.main()
