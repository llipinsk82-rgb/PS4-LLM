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
