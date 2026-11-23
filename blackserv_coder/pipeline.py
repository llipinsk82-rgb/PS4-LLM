"""Safe local Garlic conversion pipeline: full model checkpoint -> PS4 folder.

No PS4 network access, flash or model upload. Requires local source shards.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .local_convert import Checkpoint, check, convert_mix
from .validate_mix import validate_mix


ROOT = Path(__file__).resolve().parents[1]


def verify_local_checkpoint(src: Path) -> Checkpoint:
    if not src.is_dir():
        raise FileNotFoundError("local checkpoint directory is missing")
    ck = Checkpoint(str(src.resolve()))
    check(ck, mtp=ck.has_mtp)
    for shard in set(ck.weight_map.values()):
        base, header = ck.header(shard)
        end = max((entry["data_offsets"][1] for entry in header.values()
                   if isinstance(entry, dict) and "data_offsets" in entry), default=0)
        expected = base + end
        actual = (src / shard).stat().st_size
        if actual != expected:
            raise ValueError(f"{shard}: size {actual} does not match safetensors index {expected}")
    return ck


def run_pipeline(src: Path, models_dir: Path, name: str = "QwopusFlash") -> dict:
    """Do not overwrite existing models; temp outputs are verified before publish."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        raise ValueError("model folder name must be ASCII letters/digits/_/- (up to 32 bytes)")
    src = src.resolve()
    models_dir = models_dir.resolve()
    if src == models_dir or models_dir.is_relative_to(src):
        raise ValueError("output directory cannot be inside the source snapshot")
    ck = verify_local_checkpoint(src)
    models_dir.mkdir(parents=True, exist_ok=True)
    available = shutil.disk_usage(models_dir).free
    if available < (15 << 30):
        raise RuntimeError("at least 15 GiB free disk is required before conversion")
    mix = models_dir / f"{name}-mix.bin"
    if mix.is_file():
        first = validate_mix(mix)
    else:
        convert_mix(ck, mix)
        first = validate_mix(mix)
    finished = models_dir / name
    if finished.exists():
        raise FileExistsError("final PS4 model folder already exists; no overwrite")
    building = models_dir / (name + ".building")
    if building.exists():
        raise FileExistsError("incomplete second-stage folder exists; inspect it before retrying")
    cmd = [sys.executable, str(ROOT / "pc" / "convert_9b_q4s.py"),
           f"--mix={mix}", f"--out={building}"]
    subprocess.run(cmd, cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "pc" / "upload_model.py"),
                    "--model", str(building), "--dry-run"], cwd=ROOT, check=True)
    os.replace(building, finished)
    return {"status":"validated", "mix":first, "model_folder":str(finished),
            "ps4_uploaded":False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True, help="Complete local Hugging Face safetensors snapshot")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--name", default="QwopusFlash")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.src, args.models_dir, args.name), indent=2))


if __name__ == "__main__":
    main()
