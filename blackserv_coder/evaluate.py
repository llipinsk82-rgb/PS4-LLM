"""Non-executing benchmark of Garlic's tool-choice accuracy.

All function definitions are passed to the local PS4 API; no tool is actually
executed by this evaluator. Run on the same task set for the baseline Qwen and
Qwopus Flash after selecting each model on the console.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib import request

from .tools import TOOL_SCHEMAS


TASKS = Path(__file__).resolve().parents[1] / "benchmarks" / "tool_choice.json"


def choose_tool(message: dict) -> str | None:
    calls = message.get("tool_calls") or []
    if not isinstance(calls, list) or not calls:
        return None
    function = calls[0].get("function") or {}
    return function.get("name")


def evaluate(base_url: str, tasks: list, api_key: str | None = None) -> list:
    url = base_url.rstrip("/") + "/chat/completions"
    schemas = [{"type":"function", "function":item} for item in TOOL_SCHEMAS]
    results = []
    for task in tasks:
        body = json.dumps({
            "messages":[{"role":"system","content":"Choose a relevant available tool before answering. Never invent unavailable tools."},
                        {"role":"user","content":task["prompt"]}],
            "tools":schemas, "tool_choice":"auto", "parallel_tool_calls":False,
            "max_tokens":192,
            "chat_template_kwargs":{"enable_thinking":False},
        }).encode("utf-8")
        headers={"Content-Type":"application/json"}
        if api_key:
            headers["Authorization"]="Bearer "+api_key
        started=time.perf_counter()
        with request.urlopen(request.Request(url,data=body,headers=headers),timeout=240) as res:
            response=json.load(res)
        elapsed=time.perf_counter()-started
        selected=choose_tool(response["choices"][0]["message"])
        results.append({"id":task["id"],"expected":task["tool"],"selected":selected,
                        "pass":selected==task["tool"],"seconds":round(elapsed,3),
                        "usage":response.get("usage")})
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--api",required=True)
    parser.add_argument("--label",required=True)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    tasks=json.loads(TASKS.read_text(encoding="utf-8"))
    result=evaluate(args.api,tasks,os.environ.get("GARLIC_API_KEY"))
    report={"model_label":args.label,
            "score":sum(int(x["pass"]) for x in result),
            "total":len(result),
            "tasks":result}
    if args.out.exists():
        parser.error("output exists; refusing overwrite")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"{report['score']}/{report['total']} tool-choice correct (model: {args.label})")


if __name__=="__main__":
    main()
