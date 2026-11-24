"""PS4 Remote PKG Installer NextGen v0.0.10 LAN client.

Status queries are read-only. Installation is EXPLICIT, from a local PKG
verified against a specified SHA-256 digest. No GUI/Remote Play support.
Never run an installation while console storage capacity is unknown.
"""
import argparse
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LIMIT = 1_000_000_000
HOST = "192.168.1.120"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        raise RuntimeError("Unexpected redirect")


def private_ip(value):
    ip = ipaddress.ip_address(value)
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local:
        raise ValueError("Expected private LAN IPv4")
    return str(ip)


def api(ip, path, payload=None):
    if not re.fullmatch(r"/api/[a-zA-Z0-9_/-]+", path):
        raise ValueError("Unexpected API path")
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        "http://%s:12800%s" % (private_ip(ip), path),
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=12) as res:
        if res.status != 200:
            raise RuntimeError("Installer HTTP %s" % res.status)
        raw = res.read(65537)
    if len(raw) > 65536:
        raise RuntimeError("Oversized response")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("status") != "success":
        raise RuntimeError("Installer reported error")
    return data


def status(ip):
    system = api(ip, "/api/v2/system").get("data", {})
    if system.get("title_id") != "RPIN00001":
        raise RuntimeError("Unexpected service at :12800")
    jobs = api(ip, "/api/v2/jobs").get("data", {}).get("jobs")
    if not isinstance(jobs, list):
        raise RuntimeError("Malformed installer jobs")
    storage = system.get("storage", {})
    reliable = (isinstance(storage, dict) and isinstance(storage.get("free"), int)
                and isinstance(storage.get("total"), int)
                and 0 <= storage["free"] <= storage["total"] and storage["total"] > 0)
    return system, jobs, reliable


def check_file(file, expected):
    p = Path(file).resolve(strict=True)
    if not p.is_file() or p.suffix.lower() != ".pkg" or not re.fullmatch(r"[a-zA-Z0-9._-]+", p.name):
        raise ValueError("PKG name must be simple and ASCII")
    if not (1024 <= p.stat().st_size <= LIMIT):
        raise ValueError("Only small app-only PKGs up to 1 GB")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
        raise ValueError("Explicit 64-char SHA-256 required")
    digest = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest().lower() != expected.lower():
        raise ValueError("PKG SHA-256 mismatch")
    return p


def parse_range(text, size):
    if text is None:
        return 0, size - 1, False
    m = re.fullmatch(r"bytes=(\d+)-(\d*)", text)
    if not m:
        raise ValueError("Unsupported HTTP range")
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else size - 1
    if start >= size or end >= size or end < start:
        raise ValueError("Invalid HTTP range bounds")
    return start, end, True


def server_class(file, allowed_ip):
    class PkgServer(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, fmt, *args):
            pass
        def do_HEAD(self):
            self.send_file(False)
        def do_GET(self):
            self.send_file(True)
        def send_file(self, body):
            if self.client_address[0] != allowed_ip or self.path != "/garlic.pkg":
                self.send_error(403)
                self.close_connection = True
                return
            size = file.stat().st_size
            try:
                first, last, partial = parse_range(self.headers.get("Range"), size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                self.close_connection = True
                return
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(last - first + 1))
            if partial:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (first, last, size))
            self.send_header("Connection", "close")
            self.end_headers()
            if body:
                with file.open("rb") as f:
                    f.seek(first)
                    remaining = last - first + 1
                    try:
                        while remaining:
                            b = f.read(min(remaining, 65536))
                            if not b:
                                raise RuntimeError("PKG unexpectedly truncated")
                            self.wfile.write(b)
                            remaining -= len(b)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
            self.close_connection = True
    return PkgServer


def dell_ip(ps4):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((ps4, 9))
        return private_ip(s.getsockname()[0])


def verified_capacity(system, reliable, size, confirmed_free_gb=None):
    if reliable:
        free = system["storage"]["free"]
    else:
        if type(confirmed_free_gb) is not int or not 1 <= confirmed_free_gb <= 16000:
            raise RuntimeError("Storage API invalid; verify free disk space on PS4 before installing")
        free = confirmed_free_gb * 1_000_000_000
    if free < max(1_000_000_000, size * 2):
        raise RuntimeError("Insufficient verified free space")
    return free


def check_jobs(jobs, retry_failed_id=None):
    if not jobs and retry_failed_id is None:
        return
    # Only an explicitly identified, failed header fetch with no BGFT task
    # or transferred data can be ignored. All other entries block.
    if (type(retry_failed_id) is int and retry_failed_id > 0 and len(jobs) == 1
            and isinstance(jobs[0], dict)):
        j = jobs[0]
        if (j.get("id") == retry_failed_id and j.get("state") == "failed"
                and j.get("bgft_task_id") == -1 and j.get("transferred") == 0
                and j.get("package_size") == 0 and j.get("content_id") == ""):
            return
    raise RuntimeError("Installer already has jobs; refusing overlap")


def install(ip, file, port, confirmed_free_gb=None, retry_failed_id=None):
    system, jobs, reliable = status(ip)
    free = verified_capacity(system, reliable, file.stat().st_size, confirmed_free_gb)
    print("CAPACITY_VERIFIED", free, "API" if reliable else "OWNER_SCREEN", flush=True)
    check_jobs(jobs, retry_failed_id)
    local = dell_ip(ip)
    srv = ThreadingHTTPServer((local, port), server_class(file, ip))
    srv.daemon_threads = True
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        url = "http://%s:%d/garlic.pkg" % (local, srv.server_port)
        response = api(ip, "/api/v2/install", {"url": url})
        job_id = response.get("data", {}).get("job_id")
        if not isinstance(job_id, int):
            raise RuntimeError("No job ID; inspect PS4")
        print("INSTALL_ACCEPTED", job_id, flush=True)
        until = time.monotonic() + 240
        last_state = None
        while time.monotonic() < until:
            time.sleep(3)
            job = api(ip, "/api/v2/jobs/%d" % job_id).get("data", {})
            state = job.get("state")
            if state != last_state:
                print("JOB", job_id, state, job.get("percent"), flush=True)
                last_state = state
            if state in ("completed", "already_installed"):
                print("INSTALL_PASS", state)
                return
            if state in ("failed", "stopped"):
                raise RuntimeError("INSTALL_FAIL %s, error %s" % (state, job.get("error")))
        raise TimeoutError("Install timed out; check job state before retry")
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(timeout=5)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ps4", default=HOST, type=private_ip)
    cmd = p.add_subparsers(dest="command", required=True)
    cmd.add_parser("status", help="Read-only status and storage warning")
    op = cmd.add_parser("install", help="Send one small verified PKG over LAN")
    op.add_argument("--pkg", required=True)
    op.add_argument("--sha256", required=True)
    op.add_argument("--execute", action="store_true")
    op.add_argument("--port", type=int, default=18080)
    op.add_argument("--retry-failed-id", type=int, help="Explicit retry of a single failed header fetch with no BGFT task or bytes transferred")
    op.add_argument("--confirmed-free-gb", type=int, help="Whole GB rounded DOWN from current owner-verified PS4 Storage screen; only used if API is invalid")
    a = p.parse_args()
    if a.command == "status":
        info, jobs, reliable = status(a.ps4)
        print(json.dumps({"name": info.get("name"), "version": info.get("version"),
                          "storage": info.get("storage"), "storage_reliable": reliable,
                          "jobs": jobs}, indent=2))
    else:
        file = check_file(a.pkg, a.sha256)
        print("PACKAGE_VERIFIED", file.name, file.stat().st_size)
        if not a.execute:
            print("DRY_RUN_ONLY; no request sent")
            return
        if not 1024 <= a.port <= 65535:
            raise ValueError("Invalid local port")
        install(a.ps4, file, a.port, a.confirmed_free_gb, a.retry_failed_id)


if __name__ == "__main__":
    main()