"""Read-only BlackServ search_engine source case study; no source repo mutation."""
import ast,datetime,difflib,json,pathlib,re,subprocess,sys,time
from qwopus_capability_benchmark import api
from qwopus_repair_v2 import extract
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE="""def contains_all_terms(value: str, terms: list[str]) -> bool:
    return set(terms).issubset(set(query_tokens(value)))"""
TASK="""Improve this existing BlackServ search_engine helper without changing its signature.
It should match terms case-insensitively even when caller supplies uppercase terms,
and preserve current behavior for already-normalized terms. Return only a single
Python function. You may call set(), query_tokens(), and str.lower().
Existing source:
"""+SOURCE
CASES=[
 (["Hello World",["hello","world"]],True),
 (["Hello World",["HELLO","WORLD"]],True),
 (["Hello World",["hello","missing"]],False),
 (["",[]],True),
 (["Zażółć gęślą",["ZAŻÓŁĆ"]],True)
]
SAFE=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.Name,ast.Load,ast.Store,ast.Constant,ast.Call,ast.Attribute,ast.ListComp,ast.GeneratorExp,ast.comprehension,ast.For,ast.If,ast.Assign,ast.Compare,ast.Eq,ast.BoolOp,ast.And,ast.Or,ast.UnaryOp,ast.Not,ast.Subscript,ast.List,ast.Set,ast.Tuple,ast.Is,ast.IsNot,ast.In,ast.NotIn)
RUNNER=r"""import json,re,sys
src,cases=json.loads(sys.stdin.read())
def query_tokens(value):return re.findall(r'\w+',value.lower(),re.UNICODE)
env={'__builtins__':{'set':set,'str':str,'list':list,'bool':bool},'query_tokens':query_tokens}
exec(compile(src,'<restricted>','exec'),env,env)
fn=env['contains_all_terms']
print(json.dumps([fn(*args)==expected for args,expected in cases]))
"""
def grade(answer):
 src=extract(answer)
 if not src or len(src)>1500:return False,"missing/oversized",[]
 try:tree=ast.parse(src)
 except SyntaxError:return False,"syntax",[]
 if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!="contains_all_terms":return False,"wrong signature",[]
 if len(list(ast.walk(tree)))>100:return False,"oversized AST",[]
 for n in ast.walk(tree):
  if not isinstance(n,SAFE):return False,"disallowed "+type(n).__name__,[]
  if isinstance(n,ast.Name) and n.id.startswith("__"):return False,"dunder",[]
  if isinstance(n,ast.Attribute) and n.attr not in ("lower","issubset"):return False,"attribute",[]
  if isinstance(n,ast.Call) and (n.keywords or not (isinstance(n.func,ast.Name) and n.func.id in ("set","query_tokens") or isinstance(n.func,ast.Attribute) and n.func.attr in ("lower","issubset"))):return False,"call",[]
 try:
  p=subprocess.run([sys.executable,"-I","-c",RUNNER],input=json.dumps([src,CASES]),capture_output=True,text=True,timeout=3)
  if p.returncode:return False,"runner "+p.stderr[-90:],[]
  checks=json.loads(p.stdout)
  return all(checks),str(sum(checks))+"/"+str(len(checks)),checks
 except subprocess.TimeoutExpired:return False,"timeout",[]
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--selftest",action="store_true");p.add_argument("--run",action="store_true");args=p.parse_args()
 if args.selftest:
  assert not grade(SOURCE)[0]
  assert grade("def contains_all_terms(value: str, terms: list[str]) -> bool:\n return set(t.lower() for t in terms).issubset(set(query_tokens(value)))")[0]
  assert not grade("def contains_all_terms(value,terms):return __import__('os')")[0]
  print("SELFTEST 3/3 PASS");return
 if not args.run:p.error("--selftest or --run")
 model=api("192.168.1.120","/v1/models")["data"][0]["id"]
 messages=[{"role":"user","content":TASK}]
 attempts=[]
 for i in range(3):
  t=time.monotonic()
  response=api("192.168.1.120","/v1/chat/completions",{"model":model,"messages":messages,"max_tokens":500,"temperature":0.1,"stream":False})
  answer=response["choices"][0]["message"].get("content") or ""
  ok,note,checks=grade(answer)
  attempts.append({"pass":ok,"note":note,"checks":checks,"answer":answer,"seconds":round(time.monotonic()-t,2)})
  print("ATTEMPT",i+1,"PASS" if ok else "FAIL",note,flush=True)
  if ok:break
  messages.extend([{"role":"assistant","content":answer},{"role":"user","content":"Tests failed: "+note+"; failed indices: "+str([j for j,x in enumerate(checks) if not x])+". Correct function; code only."}])
 result={"source":"llipinsk82-rgb/search_engine backend/query.py, default main, GitHub read-only","model":model,"attempts":attempts,"pass":attempts[-1]["pass"]}
 if result["pass"]:
  proposed=extract(attempts[-1]["answer"])
  result["diff"]="".join(difflib.unified_diff((SOURCE+"\n").splitlines(True),(proposed+"\n").splitlines(True),fromfile="a/backend/query.py:contains_all_terms",tofile="b/backend/query.py:contains_all_terms"))
 target=ROOT/"benchmark_results"/"qwopus_blackserv_query_case_study.json"
 target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
 print("RESULT","PASS" if result["pass"] else "FAIL",target,flush=True)
if __name__=="__main__":main()
