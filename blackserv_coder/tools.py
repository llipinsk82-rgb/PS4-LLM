"""Restricted local tools for BlackServ Coder. Python standard library only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
import zipfile

class ToolError(ValueError):
    pass

class Tools:
    def __init__(self, workspace: str | Path):
        self.root = Path(workspace).resolve()
        if not self.root.is_dir():
            raise ToolError("workspace must exist")

    def path(self, name: str) -> Path:
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ToolError("path outside workspace")
        return path

    def execute(self, name: str, args: dict) -> str:
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        methods = {
            "list_files": self.list_files, "read_file": self.read_file,
            "write_file": self.write_file, "extract_zip": self.extract_zip,
            "git_status": self.git_status, "git_diff": self.git_diff,
            "web_fetch": self.web_fetch,
        }
        if name not in methods:
            raise ToolError("unknown or unapproved tool")
        try:
            return str(methods[name](**args))[:24000]
        except TypeError as exc:
            raise ToolError("invalid tool arguments") from exc

    def list_files(self, path: str = ".") -> str:
        p = self.path(path)
        if not p.is_dir():
            raise ToolError("not a directory")
        return json.dumps([{"name": x.name, "dir": x.is_dir()} for x in sorted(p.iterdir())[:150]])

    def read_file(self, path: str) -> str:
        p = self.path(path)
        if not p.is_file() or p.stat().st_size > 1_000_000:
            raise ToolError("missing or oversized file")
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        if not isinstance(content, str) or len(content.encode("utf-8")) > 1_000_000:
            raise ToolError("oversized content")
        p = self.path(path)
        if p.exists() and not p.is_file():
            raise ToolError("not a file")
        if not p.parent.is_dir():
            raise ToolError("parent directory does not exist")
        p.write_text(content, encoding="utf-8")
        return "written: " + str(p.relative_to(self.root))

    def extract_zip(self, archive: str, destination: str) -> str:
        source, dest = self.path(archive), self.path(destination)
        if not source.is_file() or not zipfile.is_zipfile(source):
            raise ToolError("invalid ZIP")
        if not dest.is_dir():
            raise ToolError("destination must exist")
        with zipfile.ZipFile(source) as z:
            items = z.infolist()
            if len(items) > 1000 or sum(x.file_size for x in items) > 100_000_000:
                raise ToolError("ZIP limits exceeded")
            for item in items:
                target = (dest / item.filename).resolve()
                if not target.is_relative_to(dest) or item.filename.startswith(("/", "\\")):
                    raise ToolError("ZIP traversal rejected")
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ToolError("ZIP symbolic link rejected")
            z.extractall(dest)
        return "extracted " + str(len(items)) + " entries"

    def _git(self, arguments: list[str]) -> str:
        result = subprocess.run(["git", "-C", str(self.root), *arguments],
                                capture_output=True, text=True, timeout=20, shell=False)
        if result.returncode:
            raise ToolError((result.stderr or result.stdout)[:1500])
        return result.stdout[:24000]

    def git_status(self) -> str:
        return self._git(["status", "--short", "--branch"])

    def git_diff(self) -> str:
        return self._git(["diff", "--", "."])

    def web_fetch(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        allowed = {"docs.python.org", "github.com", "raw.githubusercontent.com",
                   "learn.microsoft.com", "huggingface.co"}
        if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.password or parsed.port:
            raise ToolError("web host not approved")
        req = urllib.request.Request(url, headers={"User-Agent": "BlackServCoder/0.1"})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise ToolError("redirect not allowed")
        with urllib.request.build_opener(NoRedirect).open(req, timeout=10) as res:
            if "text" not in res.headers.get("Content-Type", "").lower() and "json" not in res.headers.get("Content-Type", "").lower():
                raise ToolError("only text/json content supported")
            return res.read(24000).decode("utf-8", errors="replace")

TOOL_SCHEMAS = [
    {"name":"list_files","description":"List entries inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"}}}},
    {"name":"read_file","description":"Read UTF-8 file inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"write_file","description":"Write UTF-8 file inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"extract_zip","description":"Extract bounded ZIP inside workspace","parameters":{"type":"object","properties":{"archive":{"type":"string"},"destination":{"type":"string"}},"required":["archive","destination"]}},
    {"name":"git_status","description":"Read git status","parameters":{"type":"object","properties":{}}},
    {"name":"git_diff","description":"Read unstaged git diff","parameters":{"type":"object","properties":{}}},
    {"name":"web_fetch","description":"Read HTTPS documentation from approved hosts","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
]
