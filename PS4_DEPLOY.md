# PS4 deployment safety gate — BlackServ Coder

Controlled PS4 homebrew application/model update, NOT firmware flashing.
No installation or model upload is performed by Dell conversion scripts.

## Baseline (2026-11-23)

- PS4 Slim firmware 10.01, GoldHEN (previously reported).
- Garlic LLM 1.20 experimental, stock Qwen3.5-9B, API /health and /v1/models PASS.
- GoldHEN FTP port 2121 reachable; /data/garlic/models absent on 1.20.
- Application data/logs backed up on Dell:
  D:\BlackServ_Coder\backups\PS4_before_Garlic121_20261123
- Garlic inference runs in PS4 native OS, not Linux; Dell hosts the tool executor.

## Prerequisites and safeguards

1. Retain a verified copy of the publisher's Garlic 1.20 experimental PKG
   for a true rollback. Document size and SHA-256.
2. Verify publisher's Garlic 1.21 experimental package. Published SHA-256:
   3e32b8c7cb48d0db99d8d42d2272a7a9b0b8e6124ead6ec503ccaf8a2b2b293b.
3. Verify PS4 free storage for installed 1.21, staged package if applicable
   and separate Qwopus model (about 4.52 GiB including custom MTP head).
4. Record GoldHEN/installed app identity and do not overwrite Qwen weights.

## Controlled install and smoke test

1. On Dell finish local Qwopus conversion, then run:
   python pc/upload_model.py --model models/QwopusFlash --dry-run
2. Confirm PS4 storage and backup; install 1.21 using PS4 Package Installer,
   with a verified manual/UI process. No unsupported remote-install bypass.
3. Test built-in Qwen and native 1.21 API before adding model.
4. Upload separate Qwopus folder using GoldHEN FTP and the uploader, which
   checks transfer sizes; select the new model at app launch.
5. Verify /health, /v1/models, coding and tool-calling loop. Benchmark both
   models under identical Garlic 1.21 settings.

## Rollback

If 1.21 fails, reinstall verified Garlic 1.20 and restore relevant app files
if necessary. If Qwopus fails, select stock Qwen; do not delete known-good
models until stability is proven.

CRITICAL STOP: do not replace Garlic 1.20 without verified rollback package,
storage capacity, and a recoverable installation path.
