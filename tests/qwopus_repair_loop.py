"""Minimal PS4 coding repair loop: model proposes code, isolated tests return feedback.
No shell, SSH, filesystem write by model, Git mutation, or PS4 installation.
"""
import argparse,ast,datetime,json,pathlib,re,subprocess,sys,time
from qwopus_capability_benchmark import api
from qwopus_blackserv_coding import TASKS
from qwopus_hard_benchmark import SAFE,RUNNER

ALLOWED_METHODS={"split","splitlines","startswith","append"}
ALLOWED_FUNCTIONS={"len","range","int","sorted"}
MAX_OUTPUT=5000
ROOT=pathlib.Path(__file__).resolve().parents[1]

def extract(answer):
    m=re.search(r"```(?:python)?[ \t]*\r?\n(.*?)```",answer,re.S|re.I)
    return (m.group(1) if m else answer).strip()

def verify(answer,task):
    src=extract(answer)
    if not src or len(src)>MAX_OUTPUT:return False,"Code missing or too long",[]
    try:tree=ast.parse(src)
    except SyntaxError as e:return False,"SyntaxError at line "+str(e.lineno),[]
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!=task[1]:
        return False,"Expected exactly one function named "+task[1],[]
    if len(list(ast.walk(tree)))>350:return False,"AST too large",[]
    for n in ast.walk(tree):
        if not isinstance(n,SAFE+(ast.Is,ast.IsNot)):return False,"Disallowed syntax: "+type(n).__name__,[]
        if isinstance(n,ast.Name) and n.id.startswith("__"):return False,"Disallowed dunder name",[]
        if isinstance(n,ast.Attribute) and n.attr not in ALLOWED_METHODS:return False,"Disallowed method: "+n.attr,[]
        if isinstance(n,ast.Call):
            if n.keywords or not (
                isinstance(n.func,ast.Name) and n.func.id in ALLOWED_FUNCTIONS or
                isinstance(n.func,ast.Attribute) and n.func.attr in ALLOWED_METHODS
            ):return False,"Disallowed function call",[]
    runner=RUNNER.replace("actual==expected","json.loads(json.dumps(actual))==expected").replace("'range':range","'range':range,'int':int,'sorted':sorted")
    try:
        p=subprocess.run([sys.executable,"-I","-c",runner],input=json.dumps([src,task[1],task[3]]),
                         text=True,capture_output=True,timeout=3)
        if p.returncode:return False,"Isolated runner error: "+p.stderr[-220:],[]
        checks=json.loads(p.stdout)
        if not isinstance(checks,list) or len(checks)!=len(task[3]):return False,"Invalid test runner result",[]
        if all(checks):return True,"All "+str(len(checks))+" tests passed",checks
        failed=[i+1 for i,x in enumerate(checks) if not x]
        details=[{"case":i+1,"input":task[3][i][0],"expected":task[3][i][1]} for i,x in enumerate(checks) if not x]
        return False,"Failed cases with input and expected output: "+json.dumps(details,ensure_ascii=False),checks
    except subprocess.TimeoutExpired:return False,"Execution timeout",[]
    except Exception as e:return False,"Runner error: "+type(e).__name__,[]

def run(host,task,max_retries=2,seed=None):
    model=api(host,"/v1/models")["data"][0]["id"]
    msgs=[{"role":"system","content":"You are a coding assistant. Return only a single complete Python function, no prose. Observe all constraints. When tests fail, correct your previous solution."},
          {"role":"user","content":task[2]}]
    if seed is not None:
        msgs.append({"role":"assistant","content":seed})
        ok,note,checks=verify(seed,task)
        attempts=[{"attempt":0,"pass":ok,"feedback":note,"checks":checks,"code":extract(seed),"seconds":0,"seed":True}]
        if ok:return {"task":task[0],"pass":True,"attempts":attempts}
        msgs.append({"role":"user","content":"Your code failed isolated tests: "+note+". Fix the complete function. Return code only."})
    else:attempts=[]
    for index in range(1,max_retries+2):
        start=time.monotonic()
        resp=api(host,"/v1/chat/completions",{"model":model,"messages":msgs,"max_tokens":800,"temperature":0.1,"stream":False})
        choice=resp["choices"][0]
        answer=choice["message"].get("content") or ""
        ok,note,checks=verify(answer,task)
        attempts.append({"attempt":index,"pass":ok,"feedback":note,"checks":checks,
                         "code":extract(answer),"seconds":round(time.monotonic()-start,2),
                         "finish_reason":choice.get("finish_reason")})
        print("ATTEMPT",index,"PASS" if ok else "FAIL",note,flush=True)
        if ok:break
        msgs.append({"role":"assistant","content":answer})
        msgs.append({"role":"user","content":"Tests failed: "+note+". Repair your function. Follow the original requirements. Return complete code only."})
    return {"task":task[0],"pass":attempts[-1]["pass"],"attempts":attempts}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--run",action="store_true")
    args=p.parse_args()
    if args.selftest:
        task=TASKS[1]
        assert not verify("def parse_ports(lines): return []",task)[0]
        good="""def parse_ports(lines):
    out=[]
    for line in lines:
        parts=line.split()
        if len(parts)==2 and parts[1]=='open':
            p=parts[0].split('/')
            if len(p)==2 and p[0]=='tcp':
                n=int(p[1])
                if n not in out:out.append(n)
    return sorted(out)"""
        assert verify(good,task)[0]
        assert not verify("def parse_ports(lines): return __import__('os')",task)[0]
        assert not verify("def parse_ports(lines):\n while True:pass",task)[0]
        print("SELFTEST 4/4 PASS");return
    if not args.run:p.error("specify --run or --selftest")
    host="192.168.1.120"
    health=api(host,"/health")
    if health.get("status")!="ok" or health.get("busy"):raise RuntimeError("PS4 unavailable")
    prior=json.loads((ROOT/"benchmark_results"/"qwopus_blackserv_coding_20261123.json").read_text(encoding="utf8"))
    seed=next(x["answer"] for x in prior["results"] if x["id"]=="BS2")
    out={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"host":host,
         "task_source":"Actual BS2 parse_ports model output from previous PS4 benchmark",
         "mode":"read-only model, restricted subprocess test, no file writes except benchmark results",
         "result":run(host,TASKS[1],max_retries=2,seed=seed)}
    target=ROOT/"benchmark_results"/("qwopus_repair_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".json")
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
    print("FINAL","PASS" if out["result"]["pass"] else "FAIL","RESULT",target,flush=True)
if __name__=="__main__":main()
