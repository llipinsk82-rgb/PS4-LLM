# PS4 QwopusFlash minimal coding agent — stage 1

## Status
**Working prototype, not an autonomous BlackServ engineer.** Runs on Dell,
queries PS4 Garlic over the LAN, and reads the current Git checkout of
llipinsk82-rgb/PS4-LLM. No new PS4 installation or production deployment.

## Commands
From the repo on Dell (Python 3):
- `python tests/qwopus_minimal_agent.py --selftest`
- `python tests/qwopus_minimal_agent.py --demo --task discount`
- `python tests/qwopus_minimal_agent.py --demo --task binary_search`
- `python tests/qwopus_minimal_agent.py --demo --task parse_ports`

## Implemented
1. Read-only Git checkout tools: tracked-file listing, tracked-file read
   (`git show HEAD:path`), bounded case-insensitive search. This is a local
   clone of the GitHub repository, not a live GitHub REST connector.
2. Fixed allowlist of three pure Python function tasks; model cannot choose
   arbitrary paths, commands, or tests. Deterministic AST checks and a
   restricted subprocess with timeout and instruction budget.
3. Bounded model→test→failure feedback→retry loop. Stops on repeated
   identical answers. Real vs expected results are returned.
4. PASS-only code proposals written once to ignored `agent_workspace/`,
   never overwritten. Unified diff and results in `benchmark_results/`.
   The model never receives filesystem write or shell access.
5. Git changes remain under human/CTO control. No autonomous commit,
   push, SSH, or production access.

## Evidence
- `--selftest`: 6/6 PASS.
- `--demo --task discount`: PASS 3/3; workspace proposal produced.
- `--demo --task binary_search`: PASS 4/4; workspace proposal produced.
- `parse_ports`: known recurring model failure in prior repair benchmarks.
- An experiment that blindly prepended unrelated repo source code to the
  prompt failed: model copied the unrelated `parse_ports` function instead
  of implementing `discount`. Removed this approach. Repository context
  must be *relevant and bounded*, not indiscriminately pasted.

## Limitations / safety
The local Git checkout can be stale relative to GitHub unless fetched.
The AST validator and subprocess are **not a hardened sandbox** against
malicious Python; only allowlisted, limited benchmark tasks are supported.
PASS means those explicit cases passed, not general correctness or security.
No general arbitrary repository edit workflow is implemented. Expanding to
real BlackServ repo modifications requires a separately isolated executor,
reviewable diff, stronger sandbox and more model reliability evidence.

## Next development gate
Choose a small, real tracked source bug with existing deterministic tests.
Supply *only relevant* source to the model, stage changes in a disposable
worktree, run project tests and independent regression checks, then present
a diff for approval. Do not grant SSH/production privileges.

## BlackServ source case study (read-only, 2026-11-23)
Source: GitHub llipinsk82-rgb/search_engine, backend/query.py on main,
retrieved read-only. The existing contains_all_terms helper lowercases the
haystack through query_tokens but assumes caller terms are already lowercase.
A case-insensitive input robustness improvement was proposed and tested.
PS4 model produced a one-line correction on its first attempt:
set(term.lower() for term in terms).issubset(set(query_tokens(value)))
Independent restricted test harness: 3/3 selftests PASS, 5/5 model
proposal cases PASS. Evidence in tests/qwopus_blackserv_query_case_study.py
and benchmark_results/qwopus_blackserv_query_case_study.json.
This is a candidate hardening change, NOT a confirmed production defect:
current callers may already normalize terms. No search_engine branch, source,
Git history or deployment was changed. The case study uses a frozen copy of
the fetched source and must be refreshed before any real integration.

## Read-only model-selected repository tools
Implemented tests/qwopus_repo_tool_agent.py with three function tools:
repo_list, repo_read, repo_search. Tool dispatch is host-side allowlisted,
with path, size and step limits; no shell, write, Git mutation, SSH or deploy.
Live PS4 tool demo: model called repo_search with needle 'def grade',
received the tool result and returned a matching tracked path in two turns.
Selftest 5/5 PASS. Evidence: benchmark_results/qwopus_repo_tool_demo.json.
Fixed a Windows cp1250 Git subprocess decoding failure by explicitly
requesting UTF-8 with replacement for malformed bytes.
This establishes a narrow, working model->read-only tool->answer cycle.
