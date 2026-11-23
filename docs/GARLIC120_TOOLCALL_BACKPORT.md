# BlackServ Garlic Coder — 1.20 engine + 1.21 tool-call API

## Scope
- Base: upstream Garlic LLM commit `49f08c6` (version 1.20).
- Protocol/API backport: files `chat/api.c`, `api.h`, `api_proto.c`, `api_proto.h`, `api_run.inc`, `assets/openapi.json` from upstream `ab4c5fe` (1.21).
- `chat/main.c` gets **only** the API integration for context length, busy reporting, and model-state snapshot invalidation. The version 1.20 GPU engine, shaders, tokenizer and UI are unchanged.
- No Sentinel_BS, SSH tools, remote executor or public cloud credentials.
- Function calling is OpenAI API tool-call *exchange*: the client receives a requested tool call and returns its result. This build does **not** execute privileged tools on the PS4.

## QwopusFlash (external weights; one PS4 app)
The app-only package loads **existing** PS4 files:
- `/data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin` — 4,641,752,088 B
- `/data/garlic/models/QwopusFlash/qwen3.5-9b-mtp.bin` — 212,420,608 B
- `model.idx` and `mtp.idx` in the app's `assets`, each containing a path to the external files.

The `pc/prepare_qwopus120.py` command regenerates those two app indexes from the QwopusFlash source index files without altering tensor metadata:

```powershell
python pc/prepare_qwopus120.py --source D:\BlackServ_Coder\garlic-llm\models\QwopusFlash
$env:GARLIC_TOOLCHAIN = "D:\BlackServ_Coder\toolchain"
python build_chat.py
```

**Never use `--full` for this experiment.** It would bundle the multi-gigabyte model into `/app0/models` and may override the external location.

The PS4 FTP `SIZE` command wraps at 2^32 bytes for weights larger than 4 GiB. The `LIST` response was checked and reports the full 4,641,752,088 B. A wrapped `SIZE` result of 346,784,792 B **does not indicate an incomplete file**.

## Evidence at preparation time
- Host API protocol: 153 checks, 0 failed.
- Host mocked API run: 319 checks, 0 failed.
- Host end-to-end HTTP API including tools, streaming and busy handling: 105 checks, 0 failed.
- External model index rewrite safety: 5 unit tests PASS.
- PS4 actual model inference: **NOT TESTED**.
- PS4 native build/install/launch: mark PASS only after actual result, separately.

## Safety and rollout
- No changes to PS4 until native PKG is built and verified.
- GoldHEN FTP works on port 2121. Do **not** probe GoldHEN BinLoader port 9090, which is one-shot.
- Before first live tool-call test, enable the Garlic API via L3 and use its local IP and port 8080.
- If API is exposed on an untrusted LAN, configure `/data/garlic_api_key.txt` on PS4. Do not expose port 8080 to the internet.
- The new native package uses the existing Garlic title ID. Do not install without checking version, preserving the existing app's recovery package and having a tested installation path.
- Current PS4 remote package installer availability and UI/Remote Play pairing are not established by this branch.