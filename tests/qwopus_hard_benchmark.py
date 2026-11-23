"""Advanced PS4 coding benchmark; execute only AST-restricted pure Python in subprocess."""
import ast,json,os,pathlib,re,subprocess,sys,time,datetime
from qwopus_capability_benchmark import api,chat
CASES=[
("H1","merge_intervals","Write Python function merge_intervals(intervals) merging sorted overlapping inclusive intervals [start,end]. Return list of merged lists. No imports. Only len and range calls permitted.",[(([[1,3],[2,6],[8,10]],),[[1,6],[8,10]]),(([],),[]),(([[1,4],[4,5]],),[[1,5]]),(([[1,10],[2,3]],),[[1,10]])]),
("H2","two_sum","Write Python function two_sum(nums,target) returning lexicographically first pair of indices [i,j] where i<j and nums[i]+nums[j]==target; [] if none. No imports. Only len and range calls permitted.",[(([2,7,11],9),[0,1]),(([3,3],6),[0,1]),(([1,2,3],8),[]),(([-2,4,8,0],2),[0,1])]),
("H3","is_valid_brackets","Write Python function is_valid_brackets(s) to check properly nested (), [], {}. Input only brackets. No imports. Only len and range calls permitted.",[(("",),True),(("([{}])",),True),(("([)]",),False),(("(((",),False),(("](",),False)]),
("H4","binary_search","Fix binary_search and return full corrected Python function. Use len, no imports. Original buggy code: def binary_search(nums,target):\n left=0\n right=len(nums)\n while left<right:\n  mid=(left+right)//2\n  if nums[mid]==target:return mid\n  if nums[mid]<target:left=mid\n  else:right=mid\n return -1",[(([],2),-1),(([1],1),0),(([1],2),-1),(([1,3,5,7],7),3),(([1,3,5,7],6),-1)]),
("H5","group_counts","Write Python function group_counts(words) returning dict of word frequencies. No imports. Only len and range calls permitted.",[(([],),{}),((["a","b","a"],),{"a":2,"b":1}),((["x","x"],),{"x":2})])
]
SAFE=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.If,ast.IfExp,ast.For,ast.While,ast.Break,ast.Continue,ast.Assign,ast.AugAssign,ast.Expr,ast.Pass,ast.Name,ast.Load,ast.Store,ast.Constant,ast.List,ast.Tuple,ast.Dict,ast.Subscript,ast.Slice,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,ast.Mod,ast.USub,ast.Not,ast.And,ast.Or,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.In,ast.NotIn,ast.Call,ast.Attribute,ast.ListComp,ast.comprehension)
RUNNER="""import ast,json,sys
src,fn,cases=json.loads(sys.stdin.read())
env={'__builtins__':{'len':len,'range':range}}
exec(compile(ast.parse(src),'<restricted>','exec'),env,env)
f=env[fn]
steps=[0]
def trace(frame,event,arg):
 if event=='line':
  steps[0]+=1
  if steps[0]>50000:raise RuntimeError('instruction budget')
 return trace
sys.settrace(trace)
out=[]
for args,expected in cases:
 try:
  actual=f(*args)
  out.append(actual==expected and (type(actual) is bool if type(expected) is bool else True))
 except Exception:out.append(False)
sys.settrace(None)
print(json.dumps(out))
"""
def grade(answer,task):
 fence=chr(96)*3
 m=re.search(re.escape(fence)+r"(?:python)?[ \t]*\r?\n(.*?)"+re.escape(fence),answer,re.S|re.I)
 src=(m.group(1) if m else answer).strip()
 if len(src)>5000:return False,"oversized"
 try:tree=ast.parse(src)
 except SyntaxError:return False,"syntax"
 if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!=task[1]:return False,"function signature"
 if len(list(ast.walk(tree)))>350:return False,"AST too large"
 for node in ast.walk(tree):
  if not isinstance(node,SAFE):return False,"disallowed "+type(node).__name__
  if isinstance(node,ast.Name) and node.id.startswith("__"):return False,"dunder"
  if isinstance(node,ast.Attribute) and node.attr not in ("append","pop","values"):return False,"unsafe attribute"
  if isinstance(node,ast.Call) and (node.keywords or not (isinstance(node.func,ast.Name) and node.func.id in ("len","range") or isinstance(node.func,ast.Attribute) and node.func.attr in ("append","pop","values"))):return False,"unsafe call"
 try:
  p=subprocess.run([sys.executable,"-I","-c",RUNNER],input=json.dumps([src,task[1],task[3]]),text=True,capture_output=True,timeout=3)
  if p.returncode:return False,"subprocess failed "+p.stderr[:100]
  checks=json.loads(p.stdout)
  return all(checks),str(sum(checks))+"/"+str(len(checks))+" cases"
 except subprocess.TimeoutExpired:return False,"timeout"
 except Exception as e:return False,"grader "+type(e).__name__
def main():
 import argparse
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 g.add_argument("--selftest",action="store_true");g.add_argument("--run",action="store_true")
 a=p.parse_args()
 if a.selftest:
  good="def two_sum(nums,target):\\n for i in range(len(nums)):\\n  for j in range(i+1,len(nums)):\\n   if nums[i]+nums[j]==target:return [i,j]\\n return []".replace("\\n","\n")
  assert grade(good,CASES[1])[0]
  assert not grade("def two_sum(nums,target):return []",CASES[1])[0]
  assert not grade("def two_sum(nums,target):return __import__('os')",CASES[1])[0]
  assert not grade("def two_sum(nums,target):\\n while True:pass".replace("\\n","\n"),CASES[1])[0]
  print("HARD SELFTEST 4/4 PASS");return
 host="192.168.1.120"
 health=api(host,"/health")
 if health.get("status")!="ok" or health.get("busy"):raise RuntimeError("model not ready")
 model=api(host,"/v1/models")["data"][0]["id"]
 out={"host":host,"model":model,"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"tests":[]}
 for t in CASES:
  print("RUN",t[0],t[1],flush=True)
  try:
   c,s=chat(host,model,[{"role":"user","content":t[2]}])
   ans=c.get("message",{}).get("content") or ""
   ok,note=grade(ans,t)
   item={"id":t[0],"name":t[1],"pass":ok,"detail":note,"seconds":s,"answer":ans[:3500]}
  except Exception as e:
   item={"id":t[0],"name":t[1],"pass":False,"error":type(e).__name__+": "+str(e)[:180]}
   out["tests"].append(item);print("STOP API ERROR",item["error"],flush=True);break
  out["tests"].append(item);print("PASS" if ok else "FAIL",note,"seconds",s,flush=True)
 out["summary"]={"passed":sum(bool(x["pass"]) for x in out["tests"]),"attempted":len(out["tests"]),"planned":len(CASES)}
 d=pathlib.Path(__file__).resolve().parents[1]/"benchmark_results";d.mkdir(exist_ok=True)
 f=d/("qwopus_hard_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".json")
 f.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
 print("SCORE",out["summary"],"FILE",f,flush=True)
if __name__=="__main__":main()
