"""Chunked safetensors reader for a local Garlic converter.

A feasibility component, NOT the complete PS4 model converter. Reads selected
contiguous rows by byte-range, with a bounded memory footprint. Uses Garlic's
existing Checkpoint index, file layout, and dtype semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class TensorChunk:
    start: int
    end: int
    values: np.ndarray


def tensor_rows(checkpoint, name: str, start: int, end: int) -> np.ndarray:
    """Return float32 values of 2-D rows [start:end) without fetching all rows.

    Safetensors is row-major contiguous for the layout supported by Garlic.
    This keeps the existing BF16/F16/F32 decode behavior; large downloads are
    bounded by row_count * row_width * dtype_bytes, not by tensor size.
    """
    shard = checkpoint.weight_map[name]
    base, headers = checkpoint.header(shard)
    entry = headers[name]
    shape = entry["shape"]
    if len(shape) != 2:
        raise ValueError("tensor_rows only supports matrices")
    rows, columns = shape
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= rows:
        raise ValueError("invalid tensor row interval")
    dtype = entry["dtype"]
    types = {"BF16": ("<u2", 2), "F16": ("<f2", 2), "F32": ("<f4", 4)}
    if dtype not in types:
        raise ValueError("unsupported safetensors dtype")
    np_dtype, itemsize = types[dtype]
    begin, finish = entry["data_offsets"]
    required_size = rows * columns * itemsize
    if finish - begin != required_size:
        raise ValueError("invalid tensor size in index")
    a = base + begin + start * columns * itemsize
    b = base + begin + end * columns * itemsize
    raw = checkpoint._get(shard, a, b)
    if len(raw) != b - a:
        raise ValueError("incomplete tensor chunk")
    if dtype == "BF16":
        values = (np.frombuffer(raw, dtype="<u2").astype("<u4") << 16).view("<f4")
    elif dtype == "F16":
        values = np.frombuffer(raw, dtype="<f2").astype("<f4")
    else:
        values = np.frombuffer(raw, dtype="<f4").copy()
    return values.reshape(end - start, columns)


def iter_tensor_rows(checkpoint, name: str, rows_per_chunk: int = 256) -> Iterator[TensorChunk]:
    if not isinstance(rows_per_chunk, int) or rows_per_chunk <= 0:
        raise ValueError("rows_per_chunk must be positive")
    shard = checkpoint.weight_map[name]
    _, headers = checkpoint.header(shard)
    shape = headers[name]["shape"]
    if len(shape) != 2:
        raise ValueError("only 2-D matrix tensors")
    for start in range(0, shape[0], rows_per_chunk):
        end = min(shape[0], start + rows_per_chunk)
        yield TensorChunk(start, end, tensor_rows(checkpoint, name, start, end))


def estimated_peak_tensor_mib(rows: int, columns: int, rows_per_chunk: int = 256) -> float:
    """Input + float32 + q3 scratch estimate, not a measured process peak."""
    if min(rows, columns, rows_per_chunk) <= 0:
        raise ValueError("positive dimensions required")
    return min(rows, rows_per_chunk) * columns * 32 / (1024 * 1024)


def write_quantized_tensor(checkpoint, name: str, out, fmt: str,
                           rows_per_chunk: int = 64) -> dict:
    """Stream Garlic-compatible q4i/q3i/q4row tensor into a binary file.

    q4i/q3i have separate packed-weight and scale regions, so scales are
    spooled to a temporary file before appending. Peak RAM is limited by
    a row tile, not the full matrix. No intermediate full-size NumPy arrays.
    This function does not handle QKV/gate-up concatenation, MTP or model.idx.
    """
    import tempfile
    import shutil
    import sys
    from pathlib import Path

    pc = Path(__file__).resolve().parents[1] / "pc"
    if str(pc) not in sys.path:
        sys.path.insert(0, str(pc))
    from q3 import quantize_q3, interleave_q3
    from q4 import quantize_q4, interleave_q4

    if fmt not in ("q4i", "q3i", "q4row"):
        raise ValueError("unsupported format")
    if rows_per_chunk <= 0 or rows_per_chunk % 64 != 0:
        raise ValueError("rows_per_chunk must be a multiple of 64")
    _, headers = checkpoint.header(checkpoint.weight_map[name])
    shape = headers[name]["shape"]
    if len(shape) != 2 or shape[0] % 64 or shape[1] % 32:
        raise ValueError("incompatible source dimensions")
    rows, cols = shape
    packed_size = 0
    scale_size = 0
    with tempfile.TemporaryFile() as scale_spool:
        for chunk in iter_tensor_rows(checkpoint, name, rows_per_chunk):
            w = chunk.values
            if fmt == "q3i":
                q, scales = quantize_q3(w)
                packed, sc = interleave_q3(q, scales)
            else:
                q, scales = quantize_q4(w)
                if fmt == "q4i":
                    packed, sc = interleave_q4(q, scales)
                else:
                    rowwise = np.concatenate((q, scales.view(np.uint8)), axis=1)
                    packed, sc = rowwise.tobytes(), b""
            out.write(packed)
            packed_size += len(packed)
            if sc:
                scale_spool.write(sc)
                scale_size += len(sc)
        if scale_size:
            scale_spool.seek(0)
            shutil.copyfileobj(scale_spool, out, 1 << 20)
    return {"rows": rows, "cols": cols, "fmt": fmt,
            "size": packed_size + scale_size, "scales": packed_size}
