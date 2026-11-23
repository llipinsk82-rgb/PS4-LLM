"""Host-only safety tests for the QwopusFlash external weight index rewrite."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pc"))
from prepare_qwopus120 import PATH_FIELD_LEN, rewrite_index


class TestIndexes(unittest.TestCase):
    def setUp(self):
        self.path = "qwen3.5-9b-q4s.bin"
        self.field = f"/data/{self.path}".encode().ljust(PATH_FIELD_LEN, b"\0")
        self.data = b"P" * 52 + self.field + b"METADATA"

    def test_preserves_index_metadata_and_size(self):
        patched = rewrite_index(self.data, 52, self.path, "/data/garlic/models/QwopusFlash")
        self.assertEqual(len(patched), len(self.data))
        self.assertEqual(patched[:52], self.data[:52])
        self.assertEqual(patched[-8:], b"METADATA")
        self.assertIn(b"/data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin", patched)
        self.assertNotEqual(patched, self.data)

    def test_rejects_nonzero_padding(self):
        bad = self.data[:52 + len(f"/data/{self.path}") + 1] + b"X" + self.data[52 + len(f"/data/{self.path}") + 2:]
        with self.assertRaises(ValueError):
            rewrite_index(bad, 52, self.path, "/data/garlic/models/QwopusFlash")

    def test_rejects_unsafe_paths(self):
        for path in ("/data/../etc", "/data/garlic//models", "/tmp/test", "/data/a/./b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                rewrite_index(self.data, 52, self.path, path)

    def test_rejects_long_paths_and_wrong_model(self):
        with self.assertRaises(ValueError):
            rewrite_index(self.data, 52, self.path, "/data/" + "a" * 120)
        with self.assertRaises(ValueError):
            rewrite_index(self.data, 52, "wrong.bin", "/data/garlic")

    def test_mtp_index_at_offset_8(self):
        name = "qwen3.5-9b-mtp.bin"
        data = b"\0" * 8 + f"/data/{name}".encode().ljust(PATH_FIELD_LEN, b"\0") + b"\x01\x04"
        patched = rewrite_index(data, 8, name, "/data/garlic/models/QwopusFlash")
        self.assertEqual(patched[-2:], b"\x01\x04")


if __name__ == "__main__":
    unittest.main()