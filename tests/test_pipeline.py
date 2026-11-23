"""Deterministic dry-run tests of the local converter orchestration."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from blackserv_coder.pipeline import run_pipeline
from test_local_convert import FakeModel


class PipelineTests(unittest.TestCase):
    def test_pipeline_validates_then_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"source"
            src.mkdir()
            out=root/"output"
            invocations=[]
            def pretend_second_stage(cmd, cwd, check):
                invocations.append(cmd)
                if "convert_9b_q4s.py" in str(cmd[1]):
                    target=next(arg.split("=",1)[1] for arg in cmd if arg.startswith("--out="))
                    Path(target).mkdir()
                    (Path(target)/"sample.dat").write_bytes(b"fixture")
                return None
            with patch("blackserv_coder.pipeline.verify_local_checkpoint",return_value=FakeModel()), \
                 patch("blackserv_coder.pipeline.subprocess.run", side_effect=pretend_second_stage):
                result=run_pipeline(src,out,name="TestModel")
            self.assertEqual(result["status"],"validated")
            self.assertFalse(result["ps4_uploaded"])
            self.assertTrue((out/"TestModel").is_dir())
            self.assertTrue((out/"TestModel-mix.bin").is_file())
            self.assertEqual(len(invocations),2)
            with patch("blackserv_coder.pipeline.verify_local_checkpoint",return_value=FakeModel()):
                with self.assertRaises(FileExistsError):
                    run_pipeline(src,out,name="TestModel")

    def test_pipeline_rejects_unsafe_names_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ("../../etc", "bad:name", ".foo", "x"*33):
                with self.assertRaises(ValueError):
                    run_pipeline(root, root/"models", name=name)
            with patch("blackserv_coder.pipeline.verify_local_checkpoint",return_value=FakeModel()):
                with self.assertRaises(ValueError):
                    run_pipeline(root, root/"nested", name="Safe")


if __name__ == "__main__":
    unittest.main()
