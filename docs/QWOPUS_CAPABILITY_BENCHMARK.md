# QwopusFlash PS4 — capability benchmark (2026-11-23)

Environment: real PS4 Garlic 1.20 + tool_calls backport; API 192.168.1.120:8080.
Small functional smoke benchmark, not a validated industry benchmark.

## Observed
- Basic ability: 7/8 PASS. The strict-format failure returned correct JSON
  inside a Markdown code fence instead of bare JSON.
- Advanced coding: 4/5 PASS after correcting the Markdown-fence extractor
  and allowing narrowly defined safe list/dict methods in the scorer.
  Two Sum, bracket validation, binary search repair and word frequencies passed.
  Interval merging failed instruction compliance: used sort, lambda, max
  despite prompt restricting calls to len and range.
- Original interval-merge output truncated at max_tokens=240; rerun at 800 tokens.
  Other four advanced model responses were not regenerated.
- Code checks run in restricted Python subprocess with AST allowlist, no imports,
  3-second timeout, and line-step budget. Not a general-purpose secure sandbox.

## Source of truth
- benchmark_results/qwopus_20261123T185616Z.json — raw basic responses.
- benchmark_results/qwopus_hard_20261123T185943Z_corrected.json — corrected
  scoring and H1 rerun, with raw responses and explanation.
- tests/qwopus_capability_benchmark.py, tests/qwopus_hard_benchmark.py —
  clients; run --selftest before --run.

## Limitations
- Not proof of autonomous coding, long context, large codebases, SSH execution
  or agent safety.
- API model ID is not independent proof of loaded weights; PS4 FTP boot log
  check unavailable during this run.
- Too few cases to infer a general coding success rate.
- Original advanced benchmark scorer had an escaping bug; corrected result
  and corrected source are the canonical evidence.