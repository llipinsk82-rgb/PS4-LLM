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
