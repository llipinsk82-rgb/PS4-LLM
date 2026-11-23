"""Read-only PS4 Garlic Coder acceptance test: boot path, coding reply, and OpenAI tool-call exchange.

Run from repo root after installing/launching the Coder PKG and enabling its API (L3):
  python tests/live_ps4_smoke.py
Optional: set GARLIC_API_KEY in the environment. No actual remote tools are executed.
"""
import argparse
import ftplib
import ipaddress
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

WEIGHTS_LOG = "weights: /data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin"
CHECK_PHRASE = "QWOPUS_TOOL_RESULT_OK"


def request(base, path, key, body=None, timeout=180):
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = Request(base + path, data=payload, headers=headers,
                  method="POST" if payload is not None else "GET")
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read(1024 * 1024).decode("utf-8"))


def check_boot_log(host):
    data = bytearray()
    with ftplib.FTP() as ftp:
        ftp.connect(host, 2121, timeout=15)
        ftp.login()

        def collect(chunk):
            if len(data) + len(chunk) > 4 * 1024 * 1024:
                raise RuntimeError("Garlic boot log larger than 4 MiB; inspect manually")
            data.extend(chunk)

        ftp.retrbinary("RETR /data/ps4ai_log.txt", collect, blocksize=32768)
    text = data.decode("utf-8", "replace")
    if WEIGHTS_LOG not in text:
        print("BOOT LOG LAST LINES:\n" + "\n".join(text.splitlines()[-18:]))
        raise RuntimeError("QwopusFlash path NOT found in current PS4 startup log")
    print("PASS PS4 boot log used QwopusFlash weights path")


def check_live(base, key):
    health = request(base, "/health", key, timeout=10)
    if health.get("status") != "ok":
        raise RuntimeError("Bad Garlic API health")
    print("PASS API health")

    models = request(base, "/v1/models", key, timeout=10)
    data = models.get("data", [])
    if not data or not isinstance(data[0].get("id"), str):
        raise RuntimeError("API returned no model")
    model = data[0]["id"]
    print("PASS API model declared:", model, "(not proof of which weights loaded)")

    basic = {
        "model": model,
        "messages": [{"role": "user", "content": "Write a Python function add(a, b) that returns a + b. Return only the code."}],
        "temperature": 0.2,
        "max_tokens": 120,
    }
    response = request(base, "/v1/chat/completions", key, basic)
    content = response.get("choices", [{}])[0].get("message", {}).get("content") or ""
    if not content.strip() or "def " not in content or "return" not in content:
        raise RuntimeError("Coding model did not generate a recognisable Python function: " + repr(content[:320]))
    print("PASS PS4 real coding inference:", repr(content[:160]))

    tool = {
        "type": "function",
        "function": {
            "name": "echo_test",
            "description": "Echo a diagnostic message; the client executes this test function.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    }
    messages = [{"role": "user", "content": "Call echo_test with message QWOPUS_CHECK. Do not answer before the function returns."}]
    tool_request = {
        "model": model,
        "messages": messages,
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": "echo_test"}},
        "parallel_tool_calls": False,
        "max_tokens": 160,
    }
    response = request(base, "/v1/chat/completions", key, tool_request)
    choice = response.get("choices", [{}])[0]
    calls = choice.get("message", {}).get("tool_calls") or []
    if choice.get("finish_reason") != "tool_calls" or not calls:
        raise RuntimeError("Model did not request tool_calls: " + repr(response)[:350])
    function = calls[0].get("function", {})
    if function.get("name") != "echo_test":
        raise RuntimeError("Unexpected tool name: " + repr(function.get("name")))
    try:
        args = json.loads(function["arguments"])
        if not isinstance(args, dict):
            raise ValueError("Expected JSON arguments object")
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Malformed model tool arguments") from exc
    print("PASS PS4 real model requested tool:", function["name"], "args:", args)

    tool_message = {"role": "tool", "tool_call_id": calls[0]["id"], "content": CHECK_PHRASE}
    continuation = {
        "model": model,
        "messages": [*messages, choice["message"], tool_message,
                     {"role": "user", "content": "What exact text did echo_test return?"}],
        "max_tokens": 120,
    }
    answer = request(base, "/v1/chat/completions", key, continuation)
    text = answer.get("choices", [{}])[0].get("message", {}).get("content") or ""
    if CHECK_PHRASE not in text:
        raise RuntimeError("Model did not use the tool result: " + repr(text[:300]))
    print("PASS PS4 real model consumed tool result:", repr(text[:160]))
    print("PROJECT MODEL+TOOLCALLS: LIVE PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://192.168.1.120:8080/v1")
    parser.add_argument("--skip-ftp-log", action="store_true",
                        help="Only for isolated host API tests; cannot validate actual model weights")
    args = parser.parse_args()
    url = urlsplit(args.api.rstrip("/"))
    if url.scheme != "http" or not url.hostname or not ipaddress.ip_address(url.hostname).is_private:
        parser.error("Use an HTTP API at a literal private LAN IP, never a public host")
    if url.path != "/v1":
        parser.error("API base must end with /v1")
    if not args.skip_ftp_log:
        check_boot_log(url.hostname)
    check_live(args.api.rstrip("/")[:-3], os.environ.get("GARLIC_API_KEY"))


if __name__ == "__main__":
    main()