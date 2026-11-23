# Garlic 1.20 + QwopusFlash — isolated baseline

## What this is
- **Unmodified native Garlic 1.20 app code** from upstream commit `49f08c6`.
- **No Garlic 1.21 tool_calls**, Sentinel_BS, SSH, GitHub integration or new executable logic.
- Only `chat/assets_9b/model.idx` and `mtp.idx` differ from upstream, pointing at externally stored QwopusFlash weights.
- `pc/prepare_qwopus120.py` and `tests/test_qwopus_index.py` are host-only maintenance and safety test scripts; not compiled into the PS4 app.
- Original PS4 title ID `PSAI00001`; app version `1.20`, same application as the installed Garlic. This package replaces the app on installation, it is **not** a parallel install.

## Separate application and model
Weights are already present on PS4 and are **not** part of this PKG:
- `/data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin` (4,641,752,088 bytes)
- `/data/garlic/models/QwopusFlash/qwen3.5-9b-mtp.bin` (212,420,608 bytes)

Package assets include indices pointing to the above. **Do not build with `--full`**:
```powershell
$env:GARLIC_TOOLCHAIN="D:\BlackServ_Coder\toolchain"
python pc/prepare_qwopus120.py --source D:\BlackServ_Coder\garlic-llm\models\QwopusFlash
python build_chat.py
```

The engine retains upstream 1.20 behavior: if the PKG contains `/app0/models/<basename>`, that file could override the index's external path. The package intentionally has **no models directory**. Verify after installing that the runtime log includes the exact external weights path.

## Test order
1. Installation on PS4 (do not remove existing working Garlic in advance). Keep the known-good original 1.20 PKG on Dell. If the package manager rejects same-version replacement, diagnose before taking any destructive action.
2. Launch Garlic and use FTP to inspect `/data/ps4ai_log.txt`; ensure `weights: /data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin` and `language model ready` appear in the new log.
3. Toggle API with L3 and run `python tests/live_model_only_smoke.py` on Dell. The script only reads log and sends an ordinary coding prompt. It does **not** modify the console or call tools.
4. Mark MODEL PASS only on real PS4 startup + nontrivial model-generated response. If FAIL, diagnose index/path, application launch, GPU loading, and conversion separately; never infer automatically that the model weights are corrupted.
5. Only after MODEL PASS test separate branch `blackserv/garlic120-toolcalls`.

## Verified on Dell
- Base upstream Garlic 1.20 API host tests: 57 + 103 checks, 0 failed.
- Qwopus index rewrite safety tests: 5 PASS.
- Native build from original 1.20 sources: PASS, app-only package 41,091,072 bytes.
- Package SHA-256: `D477F1B5E3E34E73D7BD4B0D7ECCD07D806D14B81A96241A4FD930C9AF3F1FEC`.
- PS4 FTP staging: PASS, `/data/pkg/Garlic120-QwopusFlash-MODEL-ONLY-4dec5c6.pkg`. Verified size and read-back SHA-256 against the original Dell package.
- Installed Garlic app on the PS4 was not modified. No launch or inference yet.
- Physical PS4 model inference and package installation: NOT TESTED YET.

## Safety
Do not upload or activate the tool-call package instead of this clean model-only baseline. PS4 app API is not accessible until enabled; never expose it publicly or add production Sentinel credentials. GoldHEN port 9090 is a one-shot BinLoader; do not probe it. Updating the app does not require re-uploading 6 GB if weights remain external and the app supports their existing format.