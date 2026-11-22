"""Small OpenAI-compatible Garlic tool-call loop; no cloud inference."""
from __future__ import annotations
import json
from urllib import request
from .tools import Tools, TOOL_SCHEMAS

class GarlicAgent:
    def __init__(self, api_url: str, tools: Tools, api_key: str | None = None, max_steps: int = 8):
        self.api_url = api_url.rstrip("/")
        self.tools = tools
        self.api_key = api_key
        self.max_steps = max_steps

    def run(self, prompt: str) -> dict:
        messages = [
            {"role": "system", "content": "You are BlackServ Coder. Use only available tools. Never claim a tool ran unless its result confirms it. Work inside the workspace."},
            {"role": "user", "content": prompt},
        ]
        schemas = [{"type":"function","function":x} for x in TOOL_SCHEMAS]
        for step in range(self.max_steps):
            body = json.dumps({"messages":messages, "tools":schemas,
                               "tool_choice":"auto", "parallel_tool_calls":False,
                               "max_tokens":1024}).encode("utf-8")
            headers = {"Content-Type":"application/json"}
            if self.api_key:
                headers["Authorization"] = "Bearer " + self.api_key
            req = request.Request(self.api_url + "/chat/completions", data=body, headers=headers)
            with request.urlopen(req, timeout=180) as response:
                payload = json.load(response)
            message = payload["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            messages.append({"role":"assistant", "content":message.get("content") or "", **({"tool_calls":calls} if calls else {})})
            if not calls:
                return {"status":"complete", "answer":message.get("content") or "", "steps":step+1}
            for call in calls:
                try:
                    f = call["function"]
                    output = self.tools.execute(f["name"], json.loads(f.get("arguments") or "{}"))
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    output = "TOOL_ERROR: " + str(exc)
                messages.append({"role":"tool", "tool_call_id":call["id"], "content":output})
        return {"status":"step_limit", "answer":"Agent stopped at configured step limit", "steps":self.max_steps}
