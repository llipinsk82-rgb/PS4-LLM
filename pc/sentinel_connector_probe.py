"""PC-only proof of concept: OpenAI tool_calls -> Sentinel_BS MCP.

NO PS4 runtime here. NO public/private Sentinel access: transport permits
127.0.0.1 loopback only and never accepts authentication material.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PROTOCOL = "2025-06-18"
MAX_RESPONSE = 128 * 1024
MAX_ARGS = 4096
TOOLS = {
    "sentinel_hosts_list": ("hosts_list", False),
    "sentinel_host_capabilities": ("host_capabilities", False),
    "sentinel_job_get": ("job_get", False),
    "sentinel_host_exec": ("host_exec", True),
}


class ConnectorError(RuntimeError):
    pass


class SentinelMockClient:
    """Deliberately restrict this first spike to a loopback-only mock MCP server."""

    def __init__(self, url: str):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != "/mcp" or parsed.query or parsed.fragment:
            raise ConnectorError("mock-only: endpoint must be http://127.0.0.1:<port>/mcp")
        if not parsed.port or not 1 <= parsed.port <= 65535:
            raise ConnectorError("mock-only: explicit TCP port is required")
        if parsed.username or parsed.password:
            raise ConnectorError("mock-only: credentials are forbidden")
        self.url = url
        self.seq = 0
        self.available = set()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _exchange(self, method: str, params: dict | None = None, *, notify: bool = False) -> dict:
        self.seq += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            msg["id"] = self.seq
        raw = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(self.url, raw, {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL,
        }, method="POST")
        try:
            with self.opener.open(req, timeout=5) as resp:
                if notify:
                    return {}
                if resp.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    raise ConnectorError("unexpected content type; SSE transport not supported in this spike")
                body = resp.read(MAX_RESPONSE + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ConnectorError(f"MCP transport failure: {type(e).__name__}") from e
        if len(body) > MAX_RESPONSE:
            raise ConnectorError("MCP response too large")
        try:
            obj = json.loads(body)
        except (ValueError, UnicodeDecodeError) as e:
            raise ConnectorError("malformed MCP response") from e
        if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0" or obj.get("id") != self.seq:
            raise ConnectorError("invalid JSON-RPC envelope or request id")
        if "error" in obj:
            raise ConnectorError("MCP remote error")
        result = obj.get("result")
        if not isinstance(result, dict):
            raise ConnectorError("MCP result is not an object")
        return result

    def initialize(self) -> None:
        result = self._exchange("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "garlic-sentinel-spike", "version": "0.1.0"},
        })
        if result.get("protocolVersion") != PROTOCOL:
            raise ConnectorError("MCP protocol version mismatch")
        self._exchange("notifications/initialized", notify=True)
        listed = self._exchange("tools/list")
        tools = listed.get("tools")
        if not isinstance(tools, list):
            raise ConnectorError("MCP tools/list missing tools")
        self.available = {item["name"] for item in tools if isinstance(item, dict) and isinstance(item.get("name"), str)}
        if not {"hosts_list", "host_capabilities", "job_get"}.issubset(self.available):
            raise ConnectorError("Sentinel mock lacks required tools")

    def dispatch(self, tool_call: dict, *, write_approved: bool = False) -> dict:
        if not self.available:
            raise ConnectorError("MCP session not initialized")
        if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
            raise ConnectorError("invalid OpenAI tool_call")
        fn = tool_call.get("function")
        if not isinstance(fn, dict):
            raise ConnectorError("missing function")
        call_id = tool_call.get("id")
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", call_id):
            raise ConnectorError("invalid tool_call id")
        name, arguments = fn.get("name"), fn.get("arguments")
        if name not in TOOLS:
            raise ConnectorError("unknown/unapproved function")
        remote, is_write = TOOLS[name]
        if remote not in self.available:
            raise ConnectorError("tool not advertised by Hub")
        if is_write and not write_approved:
            raise ConnectorError("write operation requires explicit approval")
        if not isinstance(arguments, str) or len(arguments) > MAX_ARGS:
            raise ConnectorError("arguments too large or not a JSON string")
        try:
            args = json.loads(arguments)
        except ValueError as exc:
            raise ConnectorError("tool arguments are not JSON") from exc
        if not isinstance(args, dict):
            raise ConnectorError("arguments must be a JSON object")
        if name == "sentinel_hosts_list" and args:
            raise ConnectorError("hosts_list accepts no arguments")
        if name in {"sentinel_host_capabilities", "sentinel_job_get"}:
            required = "host_id" if name.endswith("capabilities") else "job_id"
            if (set(args) != {required} or not isinstance(args[required], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", args[required])
                    or ".." in args[required]):
                raise ConnectorError(f"invalid {required}")
        if name == "sentinel_host_exec":
            if set(args) != {"host_id", "argv"} or not isinstance(args["host_id"], str) or not isinstance(args["argv"], list):
                raise ConnectorError("invalid host_exec arguments")
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", args["host_id"])
                    or ".." in args["host_id"] or not 1 <= len(args["argv"]) <= 16
                    or any(not isinstance(a, str) or not a or len(a) > 256 for a in args["argv"])):
                raise ConnectorError("invalid host_exec target/argv")
        payload = self._exchange("tools/call", {"name": remote, "arguments": args})
        if payload.get("isError"):
            raise ConnectorError("MCP tool execution returned an error")
        content = payload.get("structuredContent", payload.get("content"))
        if content is None:
            raise ConnectorError("MCP tool returned no content")
        # Return a bounded tool-role message for the Garlic model's conversation.
        encoded = json.dumps(content, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_RESPONSE:
            raise ConnectorError("MCP tool result too large")
        return {"role": "tool", "tool_call_id": call_id, "content": encoded}