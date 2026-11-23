"""PS4 repair prompt ablation; read-only API and restricted isolated grading."""
import datetime,json,pathlib,time
from qwopus_capability_benchmark import api
from qwopus_blackserv_coding import TASKS
from qwopus_repair_loop import verify
host="192.168.1.120";model=api(host,"/v1/models")["data"][0]["id"];task=TASKS[1]
seed=json.loads((pathlib.Path(__file__).resolve().parents[1]/"benchmark_results"/"qwopus_blackserv_coding_20261123.json").read_text(encoding="utf8"))["results"][1]["answer"]
prompts=[
 ("explicit_root_cause","Original request: "+task[2]+"\nHere is your previous WRONG function:\n"+seed+"\nThe input is 'tcp/22 open'. line.split() gives ['tcp/22','open']. The port is the substring after '/' in the FIRST token, not int('open'). The code also must deduplicate repeated ports. Rewrite the complete function from scratch. Return only Python."),
 ("fresh_reformulation","Write a fresh function parse_ports(lines) that parses strings like 'tcp/22 open' and 'tcp/443 open', ignores UDP and closed ports, returns sorted unique integers. First split each line into two whitespace-separated fields; first field is 'tcp/22', split it by '/' to get protocol and numeric port. Only allowed functions len,range,int,sorted and methods split,append. Return only code.")
]
out={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"model":model,"tests":[]}
for name,prompt in prompts:
 print("RUN",name,flush=True)
 t=time.monotonic()
 try:
  r=api(host,"/v1/chat/completions",{"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":850,"temperature":0.2,"stream":False})
  answer=r["choices"][0]["message"].get("content") or ""
  ok,note,checks=verify(answer,task)
  item={"name":name,"pass":ok,"note":note,"checks":checks,"answer":answer,"seconds":round(time.monotonic()-t,2)}
  print("RESULT",name,"PASS" if ok else "FAIL",note,flush=True)
 except Exception as e:
  item={"name":name,"pass":False,"error":type(e).__name__+": "+str(e)[:160]}
  print("ERROR",item["error"],flush=True)
 out["tests"].append(item)
 target=pathlib.Path(__file__).resolve().parents[1]/"benchmark_results"/"qwopus_repair_prompt_probe_20261123.json"
 target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
print("DONE",target,flush=True)
