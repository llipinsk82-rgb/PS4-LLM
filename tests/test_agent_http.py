"""Real localhost HTTP round-trip for Garlic-compatible function calls."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from blackserv_coder.agent import GarlicAgent
from blackserv_coder.tools import Tools


class FakeGarlicHandler(BaseHTTPRequestHandler):
    calls = []
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        data = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(data)
        self.calls.append(body)
        if len(body["messages"]) == 2:
            reply = {"choices":[{"message":{
                "role":"assistant","content":None,"tool_calls":[{
                    "id":"example", "type":"function",
                    "function":{"name":"write_file","arguments":json.dumps(
                        {"path":"hello.txt","content":"from mock Garlic"})}
                }]}}]}
        else:
            reply = {"choices":[{"message":{"role":"assistant","content":"Done"}}]}
        encoded = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
    def log_message(self, *args):
        pass


class HttpAgentTests(unittest.TestCase):
    def setUp(self):
        FakeGarlicHandler.calls = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeGarlicHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_real_http_two_round_tool_exchange(self):
        base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        agent = GarlicAgent(base, Tools(self.temp.name), max_steps=4)
        result = agent.run("Create a file")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["answer"], "Done")
        self.assertEqual((Path(self.temp.name)/"hello.txt").read_text(), "from mock Garlic")
        self.assertEqual(len(FakeGarlicHandler.calls), 2)
        initial, followup = FakeGarlicHandler.calls
        self.assertEqual(initial["tool_choice"], "auto")
        self.assertEqual(initial["parallel_tool_calls"], False)
        self.assertEqual(followup["messages"][-1]["role"], "tool")
        self.assertEqual(followup["messages"][-1]["tool_call_id"], "example")

    def test_loop_has_hard_limit(self):
        base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        result = GarlicAgent(base, Tools(self.temp.name), max_steps=1).run("Write")
        self.assertEqual(result["status"], "step_limit")


if __name__ == "__main__":
    unittest.main()
