"""Bounded PS4 repair loop with actual-vs-expected feedback; never executes model shell commands."""
import ast,datetime,json,pathlib,re,subprocess,sys,time
from qwopus_capability_benchmark import api
from qwopus_hard_benchmark import SAFE
ROOT=pathlib.Path(__file__).resolve().parents[1]
TASKS=[
 ("parse_ports","def parse_ports(lines):", "Write only Python function parse_ports(lines) returning sorted unique integer TCP ports from lines like 'tcp/22 open'. Ignore UDP, closed, malformed lines. No imports. Allowed calls: len,range,int,sorted, str.split, list.append.", [
  ([["tcp/22 open","tcp/80 closed","tcp/443 open","tcp/22 open"]],[22,443]),
  ([["udp/53 open","tcp/8080 closed"]],[]),
  ([["tcp/8775 open","bad","tcp/22 open"]],[22,8775])],
 """def parse_ports(lines):
    result=[]
    for line in lines:
        parts=line.split()
        if len(parts)>=2:
            protocol=parts[0]
            port_str=parts[1]
            if protocol=='tcp' and port_str=='open':
                result.append(int(port_str))
    return sorted(result)"""),
 ("binary_search","def binary_search(nums,target):","Fix binary_search(nums,target) on sorted integer list. Return index or -1. No imports; allowed len,range. Original has infinite loop: while left<right, mid=(left+right)//2, if nums[mid]<target: left=mid.", [
  ([[],2],-1),([ [1],1],0),([[1,3,5,7],7],3),([[1,3,5,7],6],-1)],
 """def binary_search(nums,target):
    left=0
    right=len(nums)
    while left<right:
        mid=(left+right)//2
        if nums[mid]==target:return mid
        if nums[mid]<target:left=mid
        else:right=mid
    return -1"""),
 ("discount","def discount(price,pct):","Fix Python function discount(price,pct) returning discounted price, not increased price. No imports, no calls.",[
  ([100,20],80),([150,10],135),([80,100],0)],
 "def discount(price,pct):return price*(100+pct)/100")
]
METHODS={"split","append"}
FUNCTIONS={"len","range","int","sorted"}
RUNNER=r"""import ast,json,sys
src,fn,cases=json.loads(sys.stdin.read())
env={'__builtins__':{'len':len,'range':range,'int':int,'sorted':sorted}}
exec(compile(ast.parse(src),'<isolated>','exec'),env,env)
f=env[fn]
counter=[0]
def trace(frame,event,arg):
 if event=='line':
  counter[0]+=1
  if counter[0]>20000:raise RuntimeError('instruction budget')
 return trace
sys.settrace(trace)
out=[]
for args,expected in cases:
 try:
  actual=f(*args)
  out.append({'input':args,'expected':expected,'actual':actual,'pass':actual==expected})
 except Exception as exc:
  out.append({'input':args,'expected':expected,'error':type(exc).__name__,'pass':False})
sys.settrace(None)
print(json.dumps(out))
"""
def extract(answer):
 m=re.search(r"```(?:python)?[ \t]*\r?\n(.*?)```",answer,re.S|re.I)
 return (m.group(1) if m else answer).strip()
def grade(answer,task):
 src=extract(answer)
 if not src or len(src)>5000:return False,"missing/oversized code",[]
 try:tree=ast.parse(src)
 except SyntaxError as e:return False,"syntax error line "+str(e.lineno),[]
 if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!=task[0]:return False,"wrong function",[]
 if len(list(ast.walk(tree)))>350:return False,"AST too large",[]
 for n in ast.walk(tree):
  if not isinstance(n,SAFE+(ast.Is,ast.IsNot)):return False,"disallowed AST "+type(n).__name__,[]
  if isinstance(n,ast.Name) and n.id.startswith("__"):return False,"dunder forbidden",[]
  if isinstance(n,ast.Attribute) and n.attr not in METHODS:return False,"method forbidden "+n.attr,[]
  if isinstance(n,ast.Call) and (n.keywords or not (isinstance(n.func,ast.Name) and n.func.id in FUNCTIONS or isinstance(n.func,ast.Attribute) and n.func.attr in METHODS)):return False,"function forbidden",[]
 try:
  p=subprocess.run([sys.executable,"-I","-c",RUNNER],input=json.dumps([src,task[0],task[3]]),capture_output=True,text=True,timeout=3)
  if p.returncode:return False,"runner failed "+p.stderr[-100:],[]
  results=json.loads(p.stdout)
  return all(x["pass"] for x in results),"passed "+str(sum(x["pass"] for x in results))+"/"+str(len(results)),results
 except subprocess.TimeoutExpired:return False,"execution timed out",[]
 except Exception as e:return False,"runner "+type(e).__name__,[]
def run(task,host,model,retries=3):
 history=[{"role":"system","content":"You are a Python coding agent. Output exactly one complete function, no commentary. Follow allowed calls. Fix mistakes using failed input, expected and actual output."},
          {"role":"user","content":task[2]}]
 seed=task[4]
 attempts=[]
 for index in range(retries+1):
  if index==0:answer=seed;elapsed=0
  else:
   t=time.monotonic()
   c=api(host,"/v1/chat/completions",{"model":model,"messages":history,"max_tokens":1000,"temperature":0.2,"stream":False})["choices"][0]
   answer=c["message"].get("content") or ""
   elapsed=round(time.monotonic()-t,2)
  ok,note,results=grade(answer,task)
  attempts.append({"attempt":index,"pass":ok,"note":note,"results":results,"answer":answer,"seconds":elapsed})
  print(task[0],"ATTEMPT",index,"PASS" if ok else "FAIL",note,flush=True)
  if ok:break
  if len(attempts)>=3 and extract(attempts[-1]["answer"])==extract(attempts[-2]["answer"]):
   print(task[0],"STOP repeated identical failing code",flush=True)
   break
  if index==0:history.append({"role":"assistant","content":answer})
  else:history.append({"role":"assistant","content":answer})
  failures=[r for r in results if not r["pass"]]
  feedback=json.dumps(failures,ensure_ascii=False)[:2500] if failures else note
  stuck=len(attempts)>1 and extract(attempts[-1]["answer"]).replace(" ","")==extract(attempts[-2]["answer"]).replace(" ","")
  hint=""
  if stuck and task[0]=="parse_ports":
   hint=" Concrete diagnostic: for input tcp/22 open, split() yields first token tcp/22 and second token open. Protocol is BEFORE slash in first token; numeric port is AFTER slash. Do not convert open to int. Remove duplicates with list membership before append. "
  history.append({"role":"user","content":"Your previous function FAILED isolated tests. Here are ACTUAL vs EXPECTED results: "+feedback+"."+hint+" Fix root cause, do not repeat previous function. Return full corrected code only."})
 return {"name":task[0],"pass":attempts[-1]["pass"],"attempts":attempts}
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--selftest",action="store_true");p.add_argument("--run",action="store_true");args=p.parse_args()
 if args.selftest:
  assert not grade(TASKS[0][4],TASKS[0])[0]
  assert not grade(TASKS[1][4],TASKS[1])[0]
  assert not grade(TASKS[2][4],TASKS[2])[0]
  assert grade("def discount(price,pct):return price*(100-pct)/100",TASKS[2])[0]
  assert not grade("def discount(price,pct):return __import__('os')",TASKS[2])[0]
  print("SELFTEST 5/5 PASS");return
 if not args.run:p.error("--run or --selftest required")
 host="192.168.1.120"
 if api(host,"/health").get("status")!="ok":raise RuntimeError("PS4 unavailable")
 model=api(host,"/v1/models")["data"][0]["id"]
 out={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"model":model,"results":[]}
 target=ROOT/"benchmark_results"/"qwopus_repair_v2b_20261123.json"
 for task in TASKS:
  out["results"].append(run(task,host,model))
  target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
 print("TOTAL",sum(x["pass"] for x in out["results"]),"/",len(out["results"]),flush=True)
if __name__=="__main__":main()
