"""Read-only PS4 Garlic multi-turn history probe."""
import datetime,json,pathlib,time
from qwopus_capability_benchmark import api
host="192.168.1.120"
model=api(host,"/v1/models")["data"][0]["id"]
cases=[
 ("single_control",[{"role":"user","content":"Return only the word BLUE."}]),
 ("multi_override",[{"role":"user","content":"Return only the word BLUE."},{"role":"assistant","content":"BLUE"},{"role":"user","content":"Correction: return only the word GREEN, not BLUE."}]),
 ("multi_fact",[{"role":"user","content":"Remember the codeword: ORCHID-729."},{"role":"assistant","content":"I will remember ORCHID-729."},{"role":"user","content":"What is the exact codeword? Return only the codeword."}]),
 ("repair_explicit",[{"role":"user","content":"Return only Python function def port_value(text): returning int of TCP port from 'tcp/22 open'. Do not use imports."},{"role":"assistant","content":"def port_value(text):\n    return int(text.split()[1])"},{"role":"user","content":"Your previous code is WRONG: text.split()[1] equals 'open'. Correct by using text.split()[0].split('/')[1]. Return full corrected function only."}])
]
out={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"model":model,"cases":[]}
for name,msgs in cases:
 print("RUN",name,flush=True)
 try:
  t=time.monotonic()
  r=api(host,"/v1/chat/completions",{"model":model,"messages":msgs,"max_tokens":240,"temperature":0.1,"stream":False})
  c=r["choices"][0]
  x={"name":name,"seconds":round(time.monotonic()-t,2),"answer":c["message"].get("content"),"finish_reason":c.get("finish_reason")}
  print("ANSWER",name,repr(x["answer"])[:550],flush=True)
 except Exception as e:
  x={"name":name,"error":type(e).__name__+": "+str(e)[:200]}
  print("ERROR",x["error"],flush=True)
 out["cases"].append(x)
 target=pathlib.Path(__file__).resolve().parents[1]/"benchmark_results"/"qwopus_history_probe_20261123.json"
 target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
print("DONE",target,flush=True)
