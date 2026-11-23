# BlackServ Garlic Coder — 1.20 engine + 1.21 tool-call API

## Scope
- Base: upstream Garlic LLM commit `49f08c6` (version 1.20).
- Protocol/API backport: files `chat/api.c`, `api.h`, `api_proto.c`, `api_proto.h`, `api_run.inc`, `assets/openapi.json` from upstream `ab4c5fe` (1.21).
- `chat/main.c` gets API integration for context length, busy reporting, and snapshot invalidation. `chat/engine.c` has a five-line path-priority guard so explicit `/data/garlic/models/` weights never silently fall back to old `/app0/models` weights. All GPU compute code, shaders, tokenizer and UI remain unchanged from 1.20.
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
- PS4 **native PKG build**: PASS on Dell with OpenOrbis v0.5.3, Zig 0.14.1, local .NET runtime 8.0.34. App-only PKG: 41,156,608 B, SHA-256 `D6361D3E000A99F76037B08E6F2A9F28B3C32D4B7244AA9AAC357CA548869FC8`.
- PS4 **FTP staging**: PASS. File `/data/pkg/GarlicCoder-120-Qwopus-toolcalls-33a43eb.pkg`, size matched; SHA-256 verified by **reading the staged package back** from PS4.
- PS4 **native install/launch/inference**: **NOT TESTED**. Installing the package is a separate step.
- The old, non-installed staging PKG was SHA-checked and removed after the corrected new PKG passed upload + read-back.
- After installation and app launch, check `/data/ps4ai_log.txt` for the exact QwopusFlash weights path. Enable the API with L3, then run `python tests/live_ps4_smoke.py` from the Dell. The script checks real coding inference, real `tool_calls` and a safe simulated tool-result round-trip; it never executes privileged tools.
- PS4 port 9295 (Remote Play) responded on 2026-11-23; remote package installer (12800) and Garlic API (8080) did not respond then. Do not probe BinLoader port 9090.
- Official chiaki-ng 1.10.1 portable for Windows was downloaded and SHA-256-verified at `D:\BlackServ_Coder\tools\chiaki-ng\chiaki-ng-Win\chiaki.exe`. No PS4 pairing, Remote Play streaming or console control verified yet.

## Safety and rollout
- No app installation or execution on PS4 before the native PKG is built and verified.
- GoldHEN FTP works on port 2121. Do **not** probe GoldHEN BinLoader port 9090, which is one-shot.
- Before first live tool-call test, enable the Garlic API via L3 and use its local IP and port 8080.
- If API is exposed on an untrusted LAN, configure `/data/garlic_api_key.txt` on PS4. Do not expose port 8080 to the internet.
- The new native package uses the existing Garlic title ID. Do not install without checking version, preserving the existing app's recovery package and having a tested installation path.
- Current PS4 remote package installer availability and UI/Remote Play pairing are not established by this branch.
## Live PS4 acceptance — 2026-11-23 (PASS)
- Device: real PS4; Garlic 1.20 + QwopusFlash + 1.21 tool-call backport, not a simulated model.
- FTP /data/ps4ai_log.txt confirmed external QwopusFlash weights and language model ready.
- API /health: HTTP 200. /v1/models exposed Qwen3.5-9B.
- Coding inference: HTTP 200, generated a valid Python add(a,b) function.
- Model requested named echo_test tool with arguments {"message":"QWOPUS_CHECK"}, finish_reason tool_calls: PASS.
- Test client supplied the simulated (not executed remotely) safe tool-result QWOPUS_TOOL_RESULT_OK.
- Model consumed tool result and replied with exact returned string: PASS.
- tests/live_ps4_smoke.py exited 0 on Dell via SentinelX.
- First attempt hit an incorrect /v1/health URL in the test script (HTTP 404); this was fixed in commit a6f3667.
- No real Sentinel_BS connection or PS4-native outbound HTTPS connector was tested.