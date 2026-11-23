import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ps4remote", HERE / "pc" / "ps4_remote_install.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RemotePkgSafety(unittest.TestCase):
    def test_private_network(self):
        self.assertEqual(m.private_ip("192.168.1.120"), "192.168.1.120")
        for ip in ("8.8.8.8", "127.0.0.1", "169.254.1.1", "bad.test"):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                m.private_ip(ip)

    def test_byte_ranges(self):
        self.assertEqual(m.parse_range(None, 100), (0, 99, False))
        self.assertEqual(m.parse_range("bytes=5-9", 100), (5, 9, True))
        self.assertEqual(m.parse_range("bytes=50-", 100), (50, 99, True))
        for value in ("bytes=0-100", "bytes=10-1", "bytes=-5", "bytes=1-2,3-4", "bytes=100-"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.parse_range(value, 100)

    def test_sha_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "test.pkg"
            data = b"P" * 1024
            file.write_bytes(data)
            good = hashlib.sha256(data).hexdigest()
            self.assertEqual(m.check_file(str(file), good), file)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                m.check_file(str(file), "f" * 64)
            with self.assertRaisesRegex(ValueError, "64-char"):
                m.check_file(str(file), "bad")

    def test_wrong_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "not-a-package.txt"
            file.write_bytes(b"P" * 1024)
            with self.assertRaises(ValueError):
                m.check_file(str(file), hashlib.sha256(b"P" * 1024).hexdigest())

    def test_no_redirect(self):
        with self.assertRaises(RuntimeError):
            m.NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://example.com")

    def test_reject_unverified_capacity(self):
        original = m.status
        try:
            m.status = lambda _: ({"storage": {"free": 2**63, "total": 0}}, [], False)
            with tempfile.TemporaryDirectory() as folder:
                file = Path(folder) / "fake.pkg"
                file.write_bytes(b"P" * 1024)
                with self.assertRaisesRegex(RuntimeError, "Storage API invalid"):
                    m.install("192.168.1.120", file, 18080)
        finally:
            m.status = original


if __name__ == "__main__":
    unittest.main()