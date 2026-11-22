"""Tests for row-wise decoding and compatibility with Garlic's quantizers."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pc"))

from blackserv_coder.streaming import tensor_rows, iter_tensor_rows, estimated_peak_tensor_mib
from q3 import quantize_q3
from q4 import quantize_q4


class FakeCheckpoint:
    def __init__(self, matrix, dtype):
        self.name = "sample.weight"
        rows, cols = matrix.shape
        if dtype == "BF16":
            raw = (matrix.astype("<f4").view("<u4") >> 16).astype("<u2").tobytes()
        else:
            raw = matrix.astype({"F16": "<f2", "F32": "<f4"}[dtype]).tobytes()
        self.blob = b"HEADER" + raw
        self.weight_map = {self.name: "sample.safetensors"}
        self.meta = {self.name: {"dtype": dtype,
                     "shape": [rows, cols], "data_offsets": [0, len(raw)]}}
        self.calls = []

    def header(self, shard):
        return 6, self.meta

    def _get(self, shard, start, end):
        self.calls.append((start, end))
        return self.blob[start:end]


class StreamingTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.matrix = rng.normal(0, 0.15, size=(384, 128)).astype(np.float32)

    def test_exact_bf16_matching_garlic_decode(self):
        ck = FakeCheckpoint(self.matrix, "BF16")
        full = tensor_rows(ck, ck.name, 0, 384)
        chunks = list(iter_tensor_rows(ck, ck.name, 64))
        np.testing.assert_array_equal(np.concatenate([c.values for c in chunks]), full)
        self.assertTrue(all(end - start <= 64 * 128 * 2 for start, end in ck.calls[1:]))

    def test_fp16_and_fp32(self):
        for dtype in ("F16", "F32"):
            ck = FakeCheckpoint(self.matrix, dtype)
            actual = np.concatenate([ch.values for ch in iter_tensor_rows(ck, ck.name, 128)])
            np.testing.assert_array_equal(actual, self.matrix.astype({"F16": "<f2", "F32": "<f4"}[dtype]).astype(np.float32))

    def test_q4_chunk_equivalence(self):
        ck = FakeCheckpoint(self.matrix, "BF16")
        whole = tensor_rows(ck, ck.name, 0, 384)
        qwhole, dwhole = quantize_q4(whole)
        pieces = [quantize_q4(ch.values) for ch in iter_tensor_rows(ck, ck.name, 128)]
        np.testing.assert_array_equal(qwhole, np.concatenate([p[0] for p in pieces]))
        np.testing.assert_array_equal(dwhole, np.concatenate([p[1] for p in pieces]))

    def test_q3_chunk_equivalence(self):
        ck = FakeCheckpoint(self.matrix, "BF16")
        whole = tensor_rows(ck, ck.name, 0, 384)
        qwhole, dwhole = quantize_q3(whole)
        pieces = [quantize_q3(ch.values) for ch in iter_tensor_rows(ck, ck.name, 128)]
        np.testing.assert_array_equal(qwhole, np.concatenate([p[0] for p in pieces]))
        np.testing.assert_array_equal(dwhole, np.concatenate([p[1] for p in pieces]))

    def test_bounded_reads_and_rejection(self):
        ck = FakeCheckpoint(self.matrix, "BF16")
        list(iter_tensor_rows(ck, ck.name, 16))
        self.assertLessEqual(max(b - a for a,b in ck.calls), 16 * 128 * 2)
        with self.assertRaises(ValueError):
            tensor_rows(ck, ck.name, -1, 1)
        with self.assertRaises(ValueError):
            tensor_rows(ck, ck.name, 0, 1000)
        with self.assertRaises(ValueError):
            list(iter_tensor_rows(ck, ck.name, 0))
        self.assertGreater(estimated_peak_tensor_mib(24576, 4096, 256), 0)


if __name__ == "__main__":
    unittest.main()
