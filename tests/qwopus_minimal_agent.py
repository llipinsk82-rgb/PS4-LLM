"""Minimal PS4 coding agent: read-only Git checkout, isolated code proposal and tests.

No model-controlled shell, Git writes, SSH, network access other than PS4 chat.
Only a single, explicitly allowlisted pure-Python function may be proposed.
"""
import argparse,difflib,json,pathlib,re,subprocess,sys,time
from qwopus_capability_benchmark import api
from qwopus_repair_v2 import grade, TASKS

ROOT=pathlib.Path(__file__).resolve().parents[1]
ALLOW_PREFIXES=("tests/","docs/","pc/","chat/")
MAX_READ=12000
MAX_FILES=80
MAX_TURNS=3

def git_read(args):
    p=subprocess.run(["git","-C",str(ROOT),*args],capture_output=True,text=True,timeout=12)
    if p.returncode:raise RuntimeError("git read failed")
    return p.stdout

def repo_list(prefix="tests/"):
    if prefix not in ALLOW_PREFIXES:raise ValueError("prefix not allowed")
    return [p for p in git_read(["ls-files","--",prefix]).splitlines() if p.startswith(prefix)][:MAX_FILES]

def repo_read(path):
    if not isinstance(path,str) or not path.startswith(ALLOW_PREFIXES):raise ValueError("path not allowed")
    if path not in git_read(["ls-files","--",path]).splitlines():raise ValueError("not a tracked file")
    raw=git_read(["show","HEAD:"+path])
    if len(raw)>MAX_READ:raise ValueError("file too large")
    return raw

def repo_search(needle,prefix="tests/"):
    if not isinstance(needle,str) or not (2<=len(needle)<=80):raise ValueError("bad query")
    matches=[]
    for path in repo_list(prefix):
        try:body=repo_read(path)
        except (ValueError,RuntimeError):continue
        for n,line in enumerate(body.splitlines(),1):
            if needle.lower() in line.lower():
                matches.append({"path":path,"line":n,"text":line[:180]})
                if len(matches)>=15:return matches
    return matches

def model_reply(model,messages):
    response=api("192.168.1.120","/v1/chat/completions",
                 {"model":model,"messages":messages,"max_tokens":850,
                  "temperature":0.15,"stream":False})
    return response["choices"][0]["message"].get("content") or ""

def propose(task,retries=MAX_TURNS):
    if not (0<=retries<=MAX_TURNS):raise ValueError("retry limit")
    model=api("192.168.1.120","/v1/models")["data"][0]["id"]
    messages=[
      {"role":"system","content":"You are a constrained coding assistant. Output one complete Python function, no prose. Follow allowed calls and fix test failures. No shell commands."},
      {"role":"user","content":task[2]}
    ]
    attempts=[]
    for i in range(retries+1):
        start=time.monotonic()
        answer=model_reply(model,messages)
        ok,note,results=grade(answer,task)
        attempts.append({"attempt":i+1,"pass":ok,"feedback":note,"checks":results,
                         "answer":answer,"seconds":round(time.monotonic()-start,2)})
        print("ATTEMPT",i+1,"PASS" if ok else "FAIL",note,flush=True)
        if ok:break
        if len(attempts)>1 and answer.strip()==attempts[-2]["answer"].strip():break
        failures=[r for r in results if not r["pass"]]
        messages.extend([
          {"role":"assistant","content":answer},
          {"role":"user","content":"Tests failed. Actual and expected outputs: "+json.dumps(failures,ensure_ascii=False)[:2200]+
           ". "+note+". Return a corrected complete function, do not repeat the failing code."}
        ])
    return {"model":model,"pass":attempts[-1]["pass"],"attempts":attempts}

def prepare_diff(task,answer):
    from qwopus_repair_v2 import extract
    original=task[4].strip()+"\n"
    proposed=extract(answer).strip()+"\n"
    return "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                        proposed.splitlines(keepends=True),
                                        fromfile="a/fixtures/"+task[0]+".py",
                                        tofile="b/fixtures/"+task[0]+".py"))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--demo",action="store_true")
    p.add_argument("--task",choices=[t[0] for t in TASKS],default="discount")
    a=p.parse_args()
    if a.selftest:
        assert repo_list("tests/")
        assert "def " in repo_read("tests/qwopus_repair_v2.py")
        assert repo_search("def grade")
        try:repo_read(".git/config")
        except ValueError:pass
        else:raise AssertionError("path guard failed")
        try:repo_read("tests/../.git/config")
        except ValueError:pass
        else:raise AssertionError("path traversal guard failed")
        assert prepare_diff(TASKS[2],"def discount(price,pct):return price*(100-pct)/100")
        print("SELFTEST 6/6 PASS");return
    if not a.demo:p.error("choose --selftest or --demo")
    if api("192.168.1.120","/health").get("status")!="ok":raise RuntimeError("PS4 unavailable")
    task=next(t for t in TASKS if t[0]==a.task)
    print("REPO",git_read(["rev-parse","--short","HEAD"]).strip(),flush=True)
    print("READONLY_FILES",len(repo_list("tests/")),flush=True)
    print("SEARCH",json.dumps(repo_search("def grade")[:2]),flush=True)
    result=propose(task)
    result["task"]=task[0]
    result["repo_sha"]=git_read(["rev-parse","HEAD"]).strip()
    if result["pass"]:
        result["proposed_diff"]=prepare_diff(task,result["attempts"][-1]["answer"])
        from qwopus_repair_v2 import extract
        workspace=ROOT/"agent_workspace"
        workspace.mkdir(exist_ok=True)
        output=workspace/(task[0]+".py")
        if output.exists() or output.is_symlink():
            print("WORKSPACE EXISTS: preserving existing proposal",flush=True)
        else:
            output.write_text(extract(result["attempts"][-1]["answer"])+"\n",encoding="utf8")
            print("WORKSPACE PROPOSAL",output,flush=True)
    target=ROOT/"benchmark_results"/("qwopus_agent_demo_"+task[0]+".json")
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print("RESULT","PASS" if result["pass"] else "FAIL",target,flush=True)
    if not result["pass"]:sys.exit(2)
if __name__=="__main__":main()
