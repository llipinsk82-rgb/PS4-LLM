"""Bounded read-only repository tool loop for PS4 Garlic function calling."""
import argparse,json,pathlib,time
from qwopus_capability_benchmark import api
from qwopus_minimal_agent import repo_list,repo_read,repo_search
ROOT=pathlib.Path(__file__).resolve().parents[1]
TOOLS=[
 {"type":"function","function":{"name":"repo_list","description":"List tracked files under tests/ or docs/ only","parameters":{"type":"object","properties":{"prefix":{"type":"string"}},"required":["prefix"]}}},
 {"type":"function","function":{"name":"repo_read","description":"Read one tracked source file from allowed directory, max 12K chars","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
 {"type":"function","function":{"name":"repo_search","description":"Find text in tracked tests files","parameters":{"type":"object","properties":{"needle":{"type":"string"}},"required":["needle"]}}}
]
def dispatch(name,args):
 if name=="repo_list":return repo_list(args.get("prefix","tests/"))
 if name=="repo_read":return repo_read(args["path"])
 if name=="repo_search":return repo_search(args["needle"])
 raise ValueError("unknown tool")
def loop(question,host="192.168.1.120",max_steps=4):
 if max_steps>4:raise ValueError("too many steps")
 model=api(host,"/v1/models")["data"][0]["id"]
 messages=[{"role":"system","content":"Use read-only repository tools to answer the user's question. Never request edits or shell commands. Keep answer short."},{"role":"user","content":question}]
 events=[]
 for i in range(max_steps):
  response=api(host,"/v1/chat/completions",{"model":model,"messages":messages,"tools":TOOLS,"tool_choice":"auto","parallel_tool_calls":False,"max_tokens":320,"temperature":0.1,"stream":False})
  choice=response["choices"][0]
  msg=choice["message"]
  calls=msg.get("tool_calls") or []
  if not calls:
   return {"answer":msg.get("content") or "","events":events,"steps":i+1}
  messages.append(msg)
  for call in calls[:2]:
   fn=call.get("function") or {}
   name=fn.get("name","")
   try:
    args=json.loads(fn.get("arguments","{}"))
    if not isinstance(args,dict):raise ValueError("invalid arguments")
    result=dispatch(name,args)
    content=json.dumps({"ok":True,"result":result},ensure_ascii=False)[:5000]
    events.append({"name":name,"args":args,"ok":True})
   except (ValueError,KeyError,TypeError,RuntimeError) as e:
    content=json.dumps({"ok":False,"error":type(e).__name__})
    events.append({"name":name,"ok":False,"error":type(e).__name__})
   messages.append({"role":"tool","tool_call_id":call["id"],"content":content})
 return {"answer":"","events":events,"steps":max_steps,"stopped":"step budget"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--selftest",action="store_true");p.add_argument("--demo",action="store_true");args=p.parse_args()
 if args.selftest:
  assert dispatch("repo_list",{"prefix":"tests/"})
  assert "def grade" in dispatch("repo_read",{"path":"tests/qwopus_hard_benchmark.py"})
  assert dispatch("repo_search",{"needle":"def grade"})
  try:dispatch("repo_read",{"path":".git/config"})
  except ValueError:pass
  else:raise AssertionError("blocked path")
  try:dispatch("shell",{"cmd":"whoami"})
  except ValueError:pass
  else:raise AssertionError("blocked tool")
  print("SELFTEST 5/5 PASS");return
 if not args.demo:p.error("--selftest or --demo")
 result=loop("Use repo_search to find where the Python function 'grade' is defined in the tests. Then answer with one matching file path.")
 target=ROOT/"benchmark_results"/"qwopus_repo_tool_demo.json"
 target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
 print("RESULT",json.dumps(result,ensure_ascii=False)[:2500],flush=True)
if __name__=="__main__":main()
