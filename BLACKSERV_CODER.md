# BlackServ Coder — local PS4 coding agent (in development)

This project uses the Garlic LLM engine and its experimental 1.21 model switch
and OpenAI-compatible API. The intended inference model is
`Jackrong/Qwopus3-5-9B-Coder-Flash`; the model is not yet converted or running
on the console. Our own code lives in `blackserv_coder/`.

## Currently implemented and tested

- Tool-call loop with a per-task step limit, using Garlic 1.21's API protocol.
- Workspace-scoped read/write/list, bounded ZIP extraction, read-only Git.
- Public Bing RSS web search, restricted HTTPS documentation fetching.
- GitHub **public repository metadata** without any SYSTEM account token.
- Read-only SSH checks (`uptime`, `uname`, `disk`) **only** for
  `BLACKSERV_SSH_HOSTS`-allowlisted targets; empty allowlist by default.
- Explicit rejection of protected `.git`, `.ssh`, `.env` and private-key paths.
- Tests use an API response stub; they do not establish model performance.

**Not implemented:** arbitrary shell/terminal commands, GitHub write operations,
full file search/edit patches, unattended execution of tests, PS4 inference.
These must be scoped to a non-privileged runner; the current SentinelX agent
runs as Windows SYSTEM and cannot safely execute arbitrary model-produced code.

## Run on Dell after PS4 API is configured

```powershell
$py = 'C:\Users\lukas\AppData\Local\Programs\Python\Python313\python.exe'
& $py -m unittest discover -s tests -p test_blackserv_coder.py -v
& $py -m blackserv_coder --workspace D:\BlackServ_Coder\workspace --api http://PS4_IP:8080/v1 "Inspect the source files"
```

Create a dedicated `workspace` folder before launching. Never use `C:\`,
`D:\`, the user's home folder, or a sensitive production repository as
workspace. The API is local to the LAN and not encrypted by default.
Garlic API can be protected by `/data/garlic_api_key.txt`; set
`GARLIC_API_KEY` in the executor environment, without putting it in Git.

## Model conversion (not yet run)

```powershell
$env:PYTHONPATH = 'D:\BlackServ_Coder\.deps'
$py = 'C:\Users\lukas\AppData\Local\Programs\Python\Python313\python.exe'
& $py pc/checkpoint.py Jackrong/Qwopus3-5-9B-Coder-Flash
# Following line uses PAID Modal 64-GiB cloud compute: requires separate approval/account.
# & $py -m modal run pc/modal_qwen35_9b.py::convert --src Jackrong/Qwopus3-5-9B-Coder-Flash
```

The first validation **passed** on Dell: 427 tensors, BF16, MTP.
No conversion, upload or PS4 benchmark has happened.

See `PLAN.md` for gates. Garlic upstream remains tracked separately and the
project preserves GPL-3.0 copyright and license information.
