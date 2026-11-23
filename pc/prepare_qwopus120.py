"""Prepare Garlic 1.20 app-only model indexes for an already-uploaded QwopusFlash.

Run: python pc/prepare_qwopus120.py --source /path/to/QwopusFlash
No model weights are copied into the application package.
"""
import argparse
from pathlib import Path
import re

FIELDS = {
    "model.idx": (52, "qwen3.5-9b-q4s.bin", 4641752088),
    "mtp.idx": (8, "qwen3.5-9b-mtp.bin", 212420608),
}
PATH_FIELD_LEN = 128
DEFAULT_REMOTE_DIR = "/data/garlic/models/QwopusFlash"


def rewrite_index(data: bytes, offset: int, expected_file: str, remote_dir: str) -> bytes:
    """Change only the NUL-padded 128-byte model path, keeping all tensor metadata intact."""
    if not re.fullmatch(r"/data/[A-Za-z0-9_./-]+", remote_dir) or "//" in remote_dir:
        raise ValueError("remote directory must be a safe absolute /data path")
    if any(segment in {".", ".."} for segment in remote_dir.split("/")):
        raise ValueError("remote directory cannot include dot components")
    if len(data) < offset + PATH_FIELD_LEN:
        raise ValueError("index too short to contain model path")
    field = data[offset:offset + PATH_FIELD_LEN]
    head, sep, tail = field.partition(b"\0")
    if not sep or any(tail):
        raise ValueError("index path field is not NUL-padded")
    if head != f"/data/{expected_file}".encode("ascii"):
        raise ValueError(f"unexpected original index model path: {head!r}")
    replacement = f"{remote_dir}/{expected_file}".encode("ascii")
    if len(replacement) >= PATH_FIELD_LEN:
        raise ValueError("remote path does not fit model index")
    patched = data[:offset] + replacement.ljust(PATH_FIELD_LEN, b"\0") + data[offset + PATH_FIELD_LEN:]
    if len(patched) != len(data):
        raise AssertionError("model index changed size")
    return patched


def prepare(source: Path, target: Path, remote_dir: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for index, (offset, weights, expected_size) in FIELDS.items():
        model = source / weights
        actual_size = model.stat().st_size
        if actual_size != expected_size:
            raise ValueError(f"{weights}: {actual_size} bytes, expected {expected_size}")
        original = (source / index).read_bytes()
        patched = rewrite_index(original, offset, weights, remote_dir)
        (target / index).write_bytes(patched)
        print(f"PASS {index}: {len(patched)} bytes -> {remote_dir}/{weights}")
    print("Weights remain external; build_chat.py without --full is required.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Local QwopusFlash weight+index directory")
    parser.add_argument("--target", type=Path, default=Path(__file__).resolve().parents[1] / "chat" / "assets_9b")
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    args = parser.parse_args()
    prepare(args.source, args.target, args.remote_dir)


if __name__ == "__main__":
    main()