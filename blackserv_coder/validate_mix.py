"""Validate a Garlic mixed-intermediate model before q4s second-stage conversion.

No full model load: checks metadata, tensor bounds, offsets, sizes and aligned
GPU/embedding separation with constant RAM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_mix(path: str | Path) -> dict:
    path = Path(path)
    index = path.with_suffix(".json")
    if not path.is_file() or not index.is_file():
        raise FileNotFoundError("mix binary and metadata JSON are required")
    meta = json.loads(index.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or not isinstance(meta.get("tensors"), dict):
        raise ValueError("invalid mix metadata")
    actual = path.stat().st_size
    if actual <= 0 or meta.get("size") != actual:
        raise ValueError("mix size does not match metadata")
    gpu_size = meta.get("gpu_size")
    if not isinstance(gpu_size, int) or gpu_size <= 0 or gpu_size > actual or gpu_size % 4096:
        raise ValueError("invalid GPU region")
    records = meta["tensors"]
    if "lm_head" not in records or "embed" not in records or "final_norm" not in records:
        raise ValueError("missing required mix records")
    ordered = sorted(records.items(), key=lambda item: item[1].get("offset", -1))
    prior_end = 0
    for name, entry in ordered:
        offset, size = entry.get("offset"), entry.get("size")
        if not isinstance(offset, int) or not isinstance(size, int) or offset < prior_end or size <= 0:
            raise ValueError(f"invalid or overlapping record: {name}")
        if offset % 256 or offset + size > actual:
            raise ValueError(f"invalid aligned bounds: {name}")
        prior_end = offset + size
        if "n" in entry:
            if size != entry["n"] * 4:
                raise ValueError(f"incorrect float tensor size: {name}")
            continue
        fmt = entry.get("fmt")
        rows, cols = entry.get("rows"), entry.get("cols")
        if not isinstance(rows, int) or not isinstance(cols, int) or rows <= 0 or cols <= 0 or cols % 32:
            raise ValueError(f"incorrect matrix dimensions: {name}")
        if fmt not in ("q3i", "q4i", "q4row"):
            raise ValueError(f"unknown mixed quantization format: {name}")
        packed = rows * cols * (3 if fmt == "q3i" else 4) // 8
        expected = rows * cols * (7 if fmt == "q3i" else 9) // 16
        if size != expected:
            raise ValueError(f"invalid mixed tensor payload size: {name}")
        if fmt != "q4row" and entry.get("scales") != packed:
            raise ValueError(f"invalid scale boundary: {name}")
    e = records["embed"]
    head = records["lm_head"]
    if e["offset"] != gpu_size or head["offset"] + head["size"] > gpu_size:
        raise ValueError("GPU/embedding boundary mismatch")
    if prior_end != actual:
        raise ValueError("trailing data outside tensor index")
    if e.get("fmt") != "q4row" or e.get("rowbytes") != e["cols"] * 9 // 16:
        raise ValueError("invalid embedding row layout")
    return {"status":"pass","size_bytes":actual,"gpu_bytes":gpu_size,
            "tensors":len(records),"checkpoint":meta.get("checkpoint")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mix", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_mix(args.mix), indent=2))


if __name__ == "__main__":
    main()
