import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from blackserv_coder.tools import Tools, ToolError
from blackserv_coder.agent import GarlicAgent

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tools = Tools(self.root)

    def test_read_write_and_list(self):
        self.assertIn("written", self.tools.write_file("a.txt", "hello"))
        self.assertEqual(self.tools.read_file("a.txt"), "hello")
        self.assertIn("a.txt", self.tools.list_files())

    def test_traversal_rejected(self):
        with self.assertRaises(ToolError):
            self.tools.read_file("../secret.txt")
        with self.assertRaises(ToolError):
            self.tools.write_file("../escape.txt", "no")

    def test_zip_safe(self):
        p = self.root / "a.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("folder/file.txt", "hello")
        self.tools.extract_zip("a.zip", ".")
        self.assertEqual((self.root / "folder/file.txt").read_text(), "hello")

    def test_zip_traversal_rejected(self):
        p = self.root / "bad.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("../escape.txt", "unsafe")
        with self.assertRaises(ToolError):
            self.tools.extract_zip("bad.zip", ".")

    def test_web_denied(self):
        for url in ("http://github.com", "https://127.0.0.1/", "https://evil.org/"):
            with self.assertRaises(ToolError):
                self.tools.web_fetch(url)

    def test_unknown_tool_denied(self):
        with self.assertRaises(ToolError):
            self.tools.execute("ssh", {})

    def test_agent_tool_loop(self):
        responses = iter([
            {"choices":[{"message":{"content":"","tool_calls":[{"id":"call1","type":"function","function":{"name":"write_file","arguments":json.dumps({"path":"result.txt","content":"OK"})}}]}}]},
            {"choices":[{"message":{"content":"File written"}}]},
        ])
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        def fake_open(req, timeout):
            item = next(responses)
            class Resp(FakeResponse):
                pass
            resp = Resp()
            resp.read = lambda: json.dumps(item).encode()
            return resp
        with patch("blackserv_coder.agent.request.urlopen", fake_open):
            result = GarlicAgent("http://localhost:8080/v1", self.tools).run("Write result")
        self.assertEqual(result["status"], "complete")
        self.assertEqual((self.root / "result.txt").read_text(), "OK")

    def test_protected_paths(self):
        for name in (".git/config", ".ssh/id_rsa", ".env", "keys/private.pem"):
            with self.assertRaises(ToolError):
                self.tools.write_file(name, "blocked")

    def test_zip_protected_path(self):
        p = self.root / "unsafe.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr(".git/config", "no")
        with self.assertRaises(ToolError):
            self.tools.extract_zip("unsafe.zip", ".")

    def test_zip_symlink(self):
        p = self.root / "link.zip"
        with zipfile.ZipFile(p, "w") as z:
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "outside")
        with self.assertRaises(ToolError):
            self.tools.extract_zip("link.zip", ".")

    def test_github_repo_name_validation(self):
        for name in ("../evil", "evil", "a/b/../../"):
            with self.assertRaises(ToolError):
                self.tools.github_repo_info(name)

    def test_ssh_default_denied(self):
        with patch.dict("os.environ", {"BLACKSERV_SSH_HOSTS":""}):
            with self.assertRaises(ToolError):
                self.tools.ssh_probe("example.org")

if __name__ == "__main__":
    unittest.main()
