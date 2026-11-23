# QwopusFlash PS4 — isolated repair-loop experiment (2026-11-23)

## Scope
Host: Dell via SentinelX; model: PS4 Garlic API at 192.168.1.120:8080.
Project: llipinsk82-rgb/PS4-LLM, branch blackserv/qwopus-capability-benchmark.
No PS4 package installation, server SSH, production changes, or model-controlled file writes.

## Reproduction
Run from Windows Python:
```
python tests/qwopus_repair_loop.py --selftest
python tests/qwopus_repair_loop.py --run
```

The loop reuses the *actual previously failed* BS2 `parse_ports` response.
A restricted AST validator and isolated Python subprocess execute three deterministic
cases with a 3-second timeout and instruction budget. The model receives feedback,
and up to three further attempts are permitted. This is a narrow benchmark runner,
**not** a secure general-purpose untrusted Python sandbox or full connector.

## Observed results
- Selftests: 4/4 PASS.
- Original seed: FAIL, cases 1 and 3.
- Run A (failure indices): 3 attempts, all FAIL.
- Run B (failed inputs + expected outputs): 3 attempts, all FAIL.
- All three generated responses in run B were byte-for-byte identical to the seed,
  incorrectly interpreting `tcp/22 open` as two separate tokens `tcp` and `open`.
- No self-repair demonstrated. Whether the underlying API applies prior conversation
  messages as expected needs separate investigation. Do not infer the model is
  incapable of multi-turn correction from this one test.

## Evidence
`benchmark_results/qwopus_repair_20261123T213138Z.json`
`benchmark_results/qwopus_repair_20261123T213252Z.json`

## Next
Test API multi-turn memory with an unambiguous control question, then inspect
how Garlic 1.20 renders messages and system roles. Fix prompt serialization if
needed before concluding model-level failure. Keep tool executor read-only.

## Follow-up: history and diagnosis probes (2026-11-23 22:20 UTC)
Read-only source review of `chat/api_run.inc` and `chat/api_proto.c` confirms the API
iterates over all supplied conversation messages. Live probe results:
- Single-turn control BLUE: PASS.
- Multi-turn override BLUE -> GREEN: PASS.
- Multi-turn memory codeword ORCHID-729: PASS.
- Multi-turn explicit code correction: FAIL (still selected wrong token).
Thus history delivery is operational, but this does not establish robust code self-repair.

Two fresh prompt ablations for the real BS2 port parser also FAIL:
- Explicit root cause: generated `set()`, `seen.add()`, `list()` outside permitted calls, and retained wrong protocol comparison.
- Fresh restatement: generated `set()` outside permitted calls, compared port string against integer range, and failed to filter closed ports.
These are substantive model mistakes, not just formatting.
Evidence: `benchmark_results/qwopus_history_probe_20261123.json`,
`benchmark_results/qwopus_repair_prompt_probe_20261123.json`.

CTO conclusion: narrow deterministic coding is possible, but automatic self-repair
is not validated. Next: provide *actual vs expected* feedback, test additional
models/tasks, and avoid autonomous production changes.
