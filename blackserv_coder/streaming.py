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
