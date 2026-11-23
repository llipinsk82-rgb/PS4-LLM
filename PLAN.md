# PS4-LLM / BlackServ Coder — execution plan

Status: in progress. Scope: Dell development + PS4 inference + guarded tools.
Base: Garlic LLM 1.21 experimental, GPL-3.0, maintained as `upstream`.
Target: Jackrong/Qwopus3-5-9B-Coder-Flash.
Working branch: `blackserv/coder-experiments`; deploy changes only after verification.

## Acceptance criteria and gates

1. **Source integrity** — clean Git, origin project and upstream author, pinned commit, licensing retained.
2. **Model compatibility** — validate config and every tensor against Garlic's Qwen3.5-9B converter, including MTP. **PASS** via `pc/checkpoint.py`: 427 tensors, BF16, MTP present.
3. **Build preparation** — isolated Python dependencies, validate conversion inputs, check output space and size, no paid cloud compute unless approved.
4. **Conversion** — run documented `pc/modal_qwen35_9b.py::convert` using an account with approved charges (requires 64 GiB Modal host), download mixed weights, run `pc/convert_9b_q4s.py`, validate with `pc/upload_model.py --model ... --dry-run`.
5. **Agent** — local OpenAI-compatible API loop. First ship bounded file/ZIP/Git/read-only documentation; only add remote/terminal tools with scoped principals, host allowlists and reviewable policies.
6. **Testing** — unit tests, anti-traversal/ZIP-bomb tests, request/response tool tests, API host integration, lint and end-to-end local model tests.
7. **PS4** — verify current identity/firmware/GoldHEN, preserve existing Garlic installation and model, check storage, then transfer model into a separate folder. No overwrite or flash.
8. **Benchmark** — original Qwen3.5-9B vs Flash: same coding tasks, same inference settings, scoring tool selection, correctness, tests and tokens/s.
9. **Release** — commit, push, clean Git status, doc and security review; verify live inference and rollback.

## Operating rules

- No remote shell or GitHub token exposure to an LLM. SYSTEM-context SentinelX is **not** a general-purpose agent executor.
- No arbitrary command execution from model output. GitHub mutation, SSH writes, deployment and other high-impact actions require purpose-scoped permissions.
- The LLM's tool arguments are untrusted. Validate paths, ZIP metadata, URLs, sizes, command and host allowlists; prevent symlink/traversal and credential access.
- Online research must not leak local files or credentials. Treat web/GitHub content as untrusted data.
- Model weights and checkpoints are not committed to GitHub.
- Stop at REAL_BLOCKER (e.g. billed Modal account, missing PS4 access), CRITICAL_RISK, USER_STOP, or PROJECT_DONE.

## Evidence

- Dell Windows Precision 5510: 32 GiB RAM; Garlic's Modal converter declares remote memory=65536 MiB (64 GiB).
- Dell isolated dependency folder: `D:\BlackServ_Coder\.deps` (NumPy).
- Latest metadata validation: `Jackrong/Qwopus3-5-9B-Coder-Flash: Qwen3.5-9B's shapes (427 tensors checked, BF16, text tensors under model.language_model.*). MTP head: yes.`
- Garlic 1.21 API supports function calls and model selection; version 1.21 is experimental.

## Execution ledger (2026-11-23 UTC)

- Checked live Dell repository: `blackserv/coder-experiments`, clean at
  `c82d627` before work; original Garlic kept as upstream.
- Pinned Qwopus HF snapshot at
  `a972c214613d831b6c03b4665c0c97f2a3f90848`;
  checkpoint schema validation PASS (427 tensors, MTP).
- Local streamed q3i/q4i/q4row binary writers PASS on reference synthetic
  data and on a real 64-row Qwopus fragment.
- Full- and linear-attention local *mix* conversion passed synthetic tests,
  including an exact recovery after simulated download interruption.
- Downloaded complete pinned Qwopus checkpoint locally: 4 safetensors
  shards, 17.98 GiB, MTP present; source file-size/index verification PASS.
- Started local first-stage mix conversion using resumable tensor journal;
  full artifact validation, second stage, and Qwopus PS4 inference pending.
- Existing Garlic 1.20 API responds on the PS4: /health PASS, /v1/models
  reports Qwen3.5-9B; short Python coding task returned correct source.
  Garlic 1.21 tool-calling/model switch is still untested on the console.
- No cloud compute and no PS4/Franek modifications.
