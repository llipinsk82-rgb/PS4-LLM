# Garlic LLM 1.21 CE-41839-5 — verified startup audit (2026-11-23)

## Scope
Read-only investigation of PS4 launch failure. No PS4 filesystem changes,
no reinstallation, no PS4 firmware operations and no model changes.

Target: PS4 / GoldHEN FTP 192.168.1.120:2121. Repository:
`llipinsk82-rgb/PS4-LLM`, experimental branch HEAD `6dafa66`;
upstream `leonardo-alegria/garlic-llm` latest HEAD observed:
`2214084b1fe9aab040434b9bb76bceca25b74515`.

## Verified results

1. Installed full base application found at `/user/app/PSAI00001/app.pkg`,
   size 6,022,889,472 bytes; `/user/patch/PSAI00001` not found by FTP.
   Package metadata from both local binaries: same
   `TITLE_ID=PSAI00001`, `CONTENT_ID=IV0000-PSAI00001_00-PS4LOCALAICHAT01`,
   `CATEGORY=gd`, `ATTRIBUTE=8388608`, `SYSTEM_VER=0`;
   version differs (1.20 vs 1.21). Installed full app header starts with
   expected `0x7f434e54`. A full cryptographic hash of the installed PS4
   `app.pkg` was NOT measured.
2. Locally downloaded 1.21 PKG size: 6,022,889,472 bytes.
   SHA256: `3e32b8c7cb48d0db99d8d42d2272a7a9b0b8e6124ead6ec503ccaf8a2b2b293b`
   (recomputed from the full Dell file).
3. Publisher's download page https://garlicllm.dev/download/ advertises
   the **same size** but a different SHA256:
   `35e3200a1d7a49c80bdaabd02e3e85227b082c1fc4db7eb92c7e1c331b73f7de`.
   This is a genuine published-checksum mismatch, so the downloaded
   file cannot be authenticated against the website.
4. HEAD request to the official current CDN URL
   https://download.garlicllm.dev/Garlic-LLM-1.21-experimental.pkg:
   HTTP 200, size 6,022,889,472; last-modified 2026-11-22 22:06:26 GMT.
   Seven 64-KiB HTTP Range checks at offsets 0, 131072, 41943040,
   536870912, 1073741824, 3221225472 and 6022823936 all matched
   exactly against our downloaded file. This strongly suggests a stale
   website checksum or mismatched publisher artifacts, but is NOT the
   same as a full remote SHA256 verification.
5. GitHub upstream issue #20:
   https://github.com/leonardo-alegria/garlic-llm/issues/20
   separately describes 1.21 launch CE-41839-5 and absent Garlic log;
   a standard PS4 user reports 1.19 and 1.20 worked, 1.21 fails.
   The issue's reporter used a 1.21 binary whose reported SHA256 is
   the **website** value, yet it also failed. Therefore the different
   checksum alone does NOT prove why our 1.21 fails.
6. Upstream main.c changed before its first log to write
   `__libc.threads_minus_1 = 1`; model chooser occurs after the first
   `say("starting")` and UI initialization. Neither is established
   as the root cause.
7. Comparable OpenOrbis issue:
   https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain/issues/283
   shows exactly CE-41839-5 with an observed
   `processSpawn() error: 0x80aa001a`; rolling back toolchain
   from v0.5.3 to v0.5.2 resolved that other app's launch problem.
   No PS4 processSpawn log from our Garlic has been decoded and the
   Garlic build's create-fself version is NOT established.
8. The local Dell worktree had no configured OpenOrbis/PS4Toolchain
   under the Garlic repo toolchain path; Zig alone exists separately.
   No isolated-title diagnostic PKG was built or installed.

## Assessment (evidence vs unproven hypothesis)

- FACT: Published SHA256 of 1.21 mismatches the binary currently on Dell.
- FACT: Independent 1.21 CE-41839-5 startup reports exist, including
  a report with the publisher-advertised SHA256.
- FACT: The installed image is in the base app directory and not a
  separate `/user/patch` package. An *update/previous-install state*
  conflict is still possible, but not demonstrated.
- UNPROVEN: malformed eboot/fSELF due to OpenOrbis create-fself; this
  is worth controlled testing because another project fixed identical
  error by rolling back its builder.
- UNPROVEN: a fault from the new `__libc` startup instruction. No
  application logs were observed; it is not valid to claim this line
  definitely executed or caused the failure.
- UNPROVEN: complete cryptographic identity of the official CDN file and
  installed PS4 app image.

## Safe next diagnostic sequence

1. Ask publisher to reconcile the official 1.21 SHA256 vs CDN artifact;
   do not blindly reinstall another PKG with an unverified hash.
2. Build minimal standalone 1.21 (no model files) in an isolated local
   toolchain, with a **different TITLE_ID and CONTENT_ID**, retaining
   existing Garlic 1.20 and user data. Use an audited working
   `create-fself` version and record it.
3. Only after validating the standalone package, perform the controlled
   PS4 launch test and collect real system loader logs. Test one variable
   at a time. If standalone starts, investigate upgrade/state conflict;
   if it fails with original 1.21 build and works with fixed FSELF tool,
   the packager is identified as the cause.
4. Keep existing rollback PKG and QwopusFlash directory intact.
   Do not update PS4 firmware, initialize, rebuild its database or delete
   installed applications to solve an unconfirmed homebrew error.

Final status: AUDIT PASS / CHECKSUM FAIL / EXACT BOOT ROOT CAUSE UNCONFIRMED.
