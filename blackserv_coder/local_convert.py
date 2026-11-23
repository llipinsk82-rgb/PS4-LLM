"""Local, bounded-memory first-stage Garlic Qwen3.5-9B converter.

Writes the same *mix* layout as pc/modal_qwen35_9b.py, without requiring
Modal/PyTorch or materializing entire BF16 matrices. The stock Garlic second
stage (pc/convert_9b_q4s.py) then produces the PS4 model folder.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

from .streaming import write_quantized_parts

PC = Path(__file__).resolve().parents[1] / "pc"
if str(PC) not in sys.path:
    sys.path.insert(0, str(PC))
from checkpoint import Checkpoint, check  # noqa: E402


def convert_mix(ck: Checkpoint, outfile: Path) -> dict:
    """Write and index the original Garlic mix representation.

    Caller must validate the original checkpoint first. Existing successful
    output is left intact; incomplete runs use <outfile>.part.
    """
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    part = outfile.with_name(outfile.name + ".part")
    journal = outfile.with_name(outfile.name + ".progress.json")
    if outfile.exists() or outfile.with_suffix(".json").exists():
        raise FileExistsError("refusing to overwrite an existing model")
    if part.exists() != journal.exists():
        raise FileExistsError("partial output and progress journal must exist together")
    cfg = ck.text_config
    prefix = ck.prefix
    saved = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else None
    if saved and saved.get("source") != ck.src:
        raise ValueError("checkpoint source changed since partial conversion")
    index = saved["tensors"] if saved else {}
    offset = int(saved["offset"]) if saved else 0
    if saved and (offset < 0 or offset > part.stat().st_size):
        raise ValueError("invalid conversion progress offset")
    completed = False
    try:
        with part.open("r+b" if saved else "xb") as out:
            if saved:
                out.truncate(offset)
                out.seek(offset)
                print(f"resuming at {offset / 2**20:.0f} MiB, {len(index)} tensors", flush=True)
            def put(name: str, write, **metadata):
                nonlocal offset
                if name in index:
                    return
                padding = (-offset) % 256
                if padding:
                    out.write(bytes(padding))
                    offset += padding
                start = offset
                result = write(out)
                length = out.tell() - start
                record = {"offset":start, "size":length}
                record.update(result or metadata)
                index[name] = record
                offset = out.tell()
                out.flush()
                os.fsync(out.fileno())
                temp_journal = journal.with_name(journal.name + ".tmp")
                temp_journal.write_text(json.dumps({"source":ck.src, "offset":offset,
                                                    "tensors":index}), encoding="utf-8")
                os.replace(temp_journal, journal)

            def put_f32(name: str, src: np.ndarray):
                data = np.ascontiguousarray(src, dtype=np.float32).tobytes()
                put(name, lambda f: f.write(data) and {"n":int(src.size)})

            def put_matrix(name: str, fragments, fmt="q4i"):
                put(name, lambda f: write_quantized_parts(ck, fragments, f, fmt))

            def whole(name: str):
                _, h = ck.header(ck.weight_map[name])
                shape = h[name]["shape"]
                if len(shape) != 2:
                    raise ValueError(f"{name}: expected matrix")
                return (name, 0, shape[0])

            def small(name: str):
                _, h = ck.header(ck.weight_map[name])
                dimensions = h[name]["shape"]
                if int(np.prod(dimensions)) > 200000:
                    raise ValueError(f"{name}: too large for small tensor path")
                return ck.tensor(name)

            put_f32("final_norm", 1.0 + small(prefix + "norm.weight"))
            nh, hd = cfg["num_attention_heads"], cfg["head_dim"]
            for i, kind in enumerate(cfg["layer_types"]):
                p = f"{prefix}layers.{i}."
                put_f32(f"{i}.attn_norm", 1.0 + small(p+"input_layernorm.weight"))
                put_f32(f"{i}.mlp_norm", 1.0 + small(p+"post_attention_layernorm.weight"))
                if kind == "full_attention":
                    a = p+"self_attn."
                    put_f32(f"{i}.q_norm", 1.0 + small(a+"q_norm.weight"))
                    put_f32(f"{i}.k_norm", 1.0 + small(a+"k_norm.weight"))
                    qname = a + "q_proj.weight"
                    query = [(qname, h*2*hd, h*2*hd+hd) for h in range(nh)]
                    gates = [(qname, h*2*hd+hd, (h+1)*2*hd) for h in range(nh)]
                    put_matrix(f"{i}.wqkv", query + [whole(a+"k_proj.weight"),
                              whole(a+"v_proj.weight")] + gates)
                    put_matrix(f"{i}.wo", [whole(a+"o_proj.weight")])
                elif kind == "linear_attention":
                    a = p+"linear_attn."
                    put_matrix(f"{i}.w_in", [whole(a+k+".weight") for k in (
                        "in_proj_qkv","in_proj_z","in_proj_b","in_proj_a")])
                    put_f32(f"{i}.conv", small(a+"conv1d.weight").reshape(
                        -1, cfg["linear_conv_kernel_dim"]))
                    put_f32(f"{i}.A", -np.exp(small(a+"A_log")))
                    put_f32(f"{i}.dt_bias", small(a+"dt_bias"))
                    put_f32(f"{i}.gnorm", small(a+"norm.weight"))
                    put_matrix(f"{i}.wout", [whole(a+"out_proj.weight")])
                else:
                    raise ValueError(f"unsupported layer type: {kind}")
                put_matrix(f"{i}.wgu", [whole(p+"mlp.gate_proj.weight"),
                                       whole(p+"mlp.up_proj.weight")], "q3i")
                put_matrix(f"{i}.wdown", [whole(p+"mlp.down_proj.weight")])
                print(f"layer {i} ({kind}) complete, {out.tell() / 2**20:.0f} MiB", flush=True)
            put_matrix("lm_head", [whole("lm_head.weight")])
            gpu_end = index["lm_head"]["offset"] + index["lm_head"]["size"]
            gpu_size = (gpu_end + 4095) // 4096 * 4096
            if "embed" not in index:
                out.write(bytes(gpu_size - out.tell()))
                offset = out.tell()
            emb = prefix+"embed_tokens.weight"
            _, headers = ck.header(ck.weight_map[emb])
            rows, cols = headers[emb]["shape"]
            def put_embeddings(f):
                meta = write_quantized_parts(ck, [whole(emb)], f, "q4row")
                return {"offset":offset, "size":meta["size"], "rows":rows, "cols":cols,
                        "scales":cols//2, "rowbytes":cols//2+cols//32*2, "fmt":"q4row"}
            put("embed", put_embeddings)
            out.flush()
            os.fsync(out.fileno())
        metadata = {"config":cfg, "size":part.stat().st_size, "gpu_size":gpu_size,
                    "tensors":index, "checkpoint":ck.src}
        json_path = outfile.with_suffix(".json")
        temporary_json = json_path.with_name(json_path.name + ".part")
        temporary_json.write_text(json.dumps(metadata, indent=1), encoding="utf-8")
        os.replace(part, outfile)
        os.replace(temporary_json, json_path)
        journal.unlink(missing_ok=True)
        completed = True
        return metadata
    finally:
        if not completed and part.exists():
            print(f"conversion incomplete; inspect partial file: {part}", file=sys.stderr)


def main():
    cli = argparse.ArgumentParser(description="Convert Qwen3.5-9B fine-tunes locally to Garlic mix format")
    cli.add_argument("--src", required=True, help="Hugging Face owner/model or local safetensors directory")
    cli.add_argument("--out", required=True, type=Path, help="Output -mix.bin path")
    args = cli.parse_args()
    ck = Checkpoint(args.src)
    check(ck)
    print(f"checkpoint verified: {args.src}; writing {args.out}")
    convert_mix(ck, args.out)


if __name__ == "__main__":
    main()
