"""MCP mock end-to-end. No Sentinel_BS production endpoint or credentials."""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pc"))
from sentinel_connector_probe import SentinelMockClient, ConnectorError, PROTOCOL


class MCPStub(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n < 1 or n > 8192 or self.path != "/mcp":
            self.send_error(400)
            return
        req = json.loads(self.rfile.read(n))
        self.requests.append(req)
        method = req["method"]
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": {"name": "sentinel-mock", "version": "0"}}
        elif method == "tools/list":
            result = {"tools": [{"name": x} for x in ("hosts_list", "host_capabilities", "job_get", "host_exec")]}
        elif method == "tools/call":
            name = req["params"]["name"]
            if name == "hosts_list":
                result = {"structuredContent": [{"host_id": "mock-dev", "status": "online"}]}
            elif name == "host_capabilities":
                result = {"structuredContent": {"host_id": req["params"]["arguments"]["host_id"], "allowed_commands": []}}
            elif name == "job_get":
                result = {"structuredContent": {"found": True, "job_id": req["params"]["arguments"]["job_id"], "status": "completed", "stdout": "test result"}}
            elif name == "host_exec":
                result = {"structuredContent": {"job_id": "mock-job", "status": "queued"}}
            else:
                self.send_error(400)
                return
        else:
            self.send_error(404)
            return
        body = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def call(name, args=None, id="call-1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args or {})}}


class TestConnector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MCPStub)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/mcp"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=2)

    def setUp(self):
        MCPStub.requests.clear()
        self.client = SentinelMockClient(self.url)
        self.client.initialize()

    def test_handshake_and_discovery(self):
        self.assertEqual([r["method"] for r in MCPStub.requests], ["initialize", "notifications/initialized", "tools/list"])

    def test_hosts_list_tool_result_for_model(self):
        result = self.client.dispatch(call("sentinel_hosts_list"))
        self.assertEqual(result["role"], "tool")
        self.assertEqual(result["tool_call_id"], "call-1")
        self.assertIn("mock-dev", result["content"])
        self.assertEqual(MCPStub.requests[-1]["params"]["name"], "hosts_list")

    def test_read_capabilities_and_job_get(self):
        self.client.dispatch(call("sentinel_host_capabilities", {"host_id": "mock-dev"}))
        result = self.client.dispatch(call("sentinel_job_get", {"job_id": "mock-job"}))
        self.assertIn("test result", result["content"])

    def test_write_denied_before_network_call(self):
        previous = len(MCPStub.requests)
        with self.assertRaisesRegex(ConnectorError, "explicit approval"):
            self.client.dispatch(call("sentinel_host_exec", {"host_id": "mock-dev", "argv": ["echo", "test"]}))
        self.assertEqual(len(MCPStub.requests), previous)

    def test_approved_write_to_mock_only(self):
        result = self.client.dispatch(call("sentinel_host_exec", {"host_id": "mock-dev", "argv": ["echo", "test"]}), write_approved=True)
        self.assertIn("mock-job", result["content"])
        self.assertEqual(MCPStub.requests[-1]["params"]["name"], "host_exec")

    def test_unknown_tool_and_malformed_args_rejected(self):
        for item in (call("sentinel_read_all_secrets"), call("sentinel_hosts_list", {"override": 1}),
                     call("sentinel_host_capabilities", {"host_id": "../../wrong"}),
                     {"type": "function", "id": "x", "function": {"name": "sentinel_hosts_list", "arguments": "{"}}):
            with self.assertRaises(ConnectorError):
                self.client.dispatch(item)

    def test_not_initialised(self):
        with self.assertRaisesRegex(ConnectorError, "not initialized"):
            SentinelMockClient(self.url).dispatch(call("sentinel_hosts_list"))

    def test_refuses_nonlocal_endpoints_and_credentials(self):
        for url in ("https://mcp.blackserv.eu/mcp", "http://localhost:9999/mcp",
                    "http://192.168.1.200:8780/mcp", "http://127.0.0.1:8000/admin",
                    "http://user:pass@127.0.0.1:8000/mcp"):
            with self.subTest(url=url), self.assertRaises(ConnectorError):
                SentinelMockClient(url)


if __name__ == "__main__":
    unittest.main()