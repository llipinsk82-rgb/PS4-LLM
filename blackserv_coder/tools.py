"""Restricted local tools for BlackServ Coder. Python standard library only."""
from __future__ import annotations
import json
import os
import re
import xml.etree.ElementTree as ET
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
        if self.root == self.root.anchor or len(self.root.parts) < 3:
            raise ToolError("workspace must be a project directory")
        if not self.root.is_dir():
            raise ToolError("workspace must exist")

    def path(self, name: str) -> Path:
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ToolError("path outside workspace")
        relative = path.relative_to(self.root)
        forbidden = {".git", ".ssh", ".env", ".aws", ".config", "credentials", "secrets"}
        if any(p.lower() in forbidden or p.lower().endswith((".pem", ".key", ".p12")) for p in relative.parts):
            raise ToolError("protected path")
        return path

    def execute(self, name: str, args: dict) -> str:
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        methods = {
            "list_files": self.list_files, "read_file": self.read_file,
            "write_file": self.write_file, "extract_zip": self.extract_zip,
            "git_status": self.git_status, "git_diff": self.git_diff,
            "web_fetch": self.web_fetch, "web_search": self.web_search,
            "github_repo_info": self.github_repo_info, "ssh_probe": self.ssh_probe,
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
                # Reject traversal, credential directories, Windows streams and Unix symlinks.
                if not target.is_relative_to(dest) or item.filename.startswith(("/", "\\")):
                    raise ToolError("ZIP traversal rejected")
                if ":" in item.filename or "\\" in item.filename:
                    raise ToolError("ZIP unsafe path")
                self.path(str(target.relative_to(self.root)))
                mode = (item.external_attr >> 16) & 0o170000
                if mode not in (0, 0o100000, 0o040000):
                    raise ToolError("ZIP special file rejected")
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

    def web_search(self, query: str) -> str:
        """Public search results; never send workspace content to a search engine."""
        if not isinstance(query, str) or not 2 <= len(query) <= 200:
            raise ToolError("search query must contain 2..200 characters")
        url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote_plus(query)
        req = urllib.request.Request(url, headers={"User-Agent":"BlackServCoder/0.1"})
        with urllib.request.urlopen(req, timeout=12) as response:
            if "xml" not in response.headers.get("Content-Type", "").lower():
                raise ToolError("search returned non-XML content")
            data = response.read(180000)
        root = ET.fromstring(data)
        entries = []
        for item in root.findall("./channel/item")[:8]:
            entries.append({
                "title": (item.findtext("title") or "")[:240],
                "url": (item.findtext("link") or "")[:800],
                "summary": (item.findtext("description") or "")[:600]
            })
        return json.dumps(entries, ensure_ascii=False)

    def github_repo_info(self, repository: str) -> str:
        """Public GitHub repo metadata without using the SYSTEM account token."""
        if (not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
                or any(part in (".", "..") for part in repository.split("/"))):
            raise ToolError("invalid GitHub owner/repository")
        req = urllib.request.Request("https://api.github.com/repos/" + repository,
            headers={"User-Agent":"BlackServCoder/0.1", "Accept":"application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.load(response)
        return json.dumps({k:data.get(k) for k in
            ("full_name", "description", "default_branch", "html_url",
             "stargazers_count", "archived", "disabled")})

    def ssh_probe(self, host: str, check: str = "uptime") -> str:
        """Allowlisted, read-only SSH checks. Never open an interactive shell."""
        allow = {x.strip() for x in os.environ.get("BLACKSERV_SSH_HOSTS", "").split(",") if x.strip()}
        checks = {"uptime":"uptime", "uname":"uname -a", "disk":"df -h"}
        if not allow or host not in allow or check not in checks:
            raise ToolError("SSH host/check not allowed")
        if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,200}", host):
            raise ToolError("invalid SSH host")
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=5", "-o", "NumberOfPasswordPrompts=0", host,
            checks[check]], capture_output=True, text=True, timeout=15, shell=False)
        if result.returncode:
            raise ToolError("SSH check failed: " + result.stderr[:500])
        return result.stdout[:12000]

TOOL_SCHEMAS = [
    {"name":"list_files","description":"List entries inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"}}}},
    {"name":"read_file","description":"Read UTF-8 file inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"write_file","description":"Write UTF-8 file inside workspace","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"extract_zip","description":"Extract bounded ZIP inside workspace","parameters":{"type":"object","properties":{"archive":{"type":"string"},"destination":{"type":"string"}},"required":["archive","destination"]}},
    {"name":"git_status","description":"Read git status","parameters":{"type":"object","properties":{}}},
    {"name":"git_diff","description":"Read unstaged git diff","parameters":{"type":"object","properties":{}}},
    {"name":"web_fetch","description":"Read HTTPS documentation from approved hosts","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
    {"name":"web_search","description":"Search public web pages via Bing RSS (no internal files or credentials)","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"name":"github_repo_info","description":"Get public GitHub repository metadata without token","parameters":{"type":"object","properties":{"repository":{"type":"string"}},"required":["repository"]}},
    {"name":"ssh_probe","description":"Run a predefined read-only SSH check on an approved host","parameters":{"type":"object","properties":{"host":{"type":"string"},"check":{"type":"string","enum":["uptime","uname","disk"]}},"required":["host"]}},
]
