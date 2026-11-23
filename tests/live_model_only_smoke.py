"""Live acceptance test for stock Garlic 1.20 using external QwopusFlash weights.

No tool-calling code and no remote command execution. Run after installing the
app-only PKG, launching Garlic and enabling its API using L3.
"""
import argparse
import ftplib
import ipaddress
import json
import os
from urllib.request import Request, urlopen

EXPECTED_WEIGHTS = "/data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin"


def ps4_log(host: str) -> str:
    data = bytearray()

    def collect(chunk: bytes) -> None:
        if len(data) + len(chunk) > 4 * 1024 * 1024:
            raise RuntimeError("Garlic log is larger than 4 MiB")
        data.extend(chunk)

    with ftplib.FTP() as ftp:
        ftp.connect(host, 2121, timeout=15)
        ftp.login()
        ftp.retrbinary("RETR /data/ps4ai_log.txt", collect)
    return data.decode("utf-8", "replace")


def api(host: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    key = os.getenv("GARLIC_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(
        f"http://{host}:8080{path}", data=data, headers=headers,
        method="POST" if data is not None else "GET"
    )
    with urlopen(request, timeout=150 if data is not None else 10) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise RuntimeError("API returned a non-object")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.1.120")
    parser.add_argument("--log-only", action="store_true")
    args = parser.parse_args()
    addr = ipaddress.ip_address(args.host)
    if not addr.is_private:
        parser.error("PS4 host must be a literal private IPv4 or IPv6 address")
    log = ps4_log(args.host)
    if f"weights: {EXPECTED_WEIGHTS}" not in log:
        print("\n".join(log.splitlines()[-18:]))
        raise RuntimeError("FAIL: app did not select external QwopusFlash weights")
    if "language model ready" not in log:
        print("\n".join(log.splitlines()[-18:]))
        raise RuntimeError("FAIL: model readiness not confirmed in current PS4 log")
    print("PASS: PS4 booted model with QwopusFlash external weights")
    if args.log_only:
        return

    health = api(args.host, "/health")
    if not health or "error" in health:
        raise RuntimeError(f"FAIL: API health: {health!r}")
    print("PASS: Garlic 1.20 API /health")

    models = api(args.host, "/v1/models").get("data", [])
    if not models or not isinstance(models[0].get("id"), str):
        raise RuntimeError("FAIL: API did not return a model id")
    mid = models[0]["id"]
    answer = api(args.host, "/v1/chat/completions", {
        "model": mid,
        "messages": [{
            "role": "user",
            "content": "Write a short Python function add(a, b) that returns their sum. Reply with code."
        }],
        "temperature": 0.1,
        "max_tokens": 180,
    })
    choices = answer.get("choices") or []
    content = choices[0].get("message", {}).get("content", "") if choices else ""
    if not isinstance(content, str) or "def " not in content or "return" not in content:
        raise RuntimeError("FAIL: no recognisable coding response: " + repr(content)[:400])
    print("PASS: QwopusFlash real coding response:")
    print(content[:400])
    print("MODEL PASS — native PS4 LLM inference confirmed. This does not test tool_calls.")


if __name__ == "__main__":
    main()