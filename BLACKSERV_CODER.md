# BlackServ Coder — local tool-agent prototype

This repository retains the upstream Garlic LLM engine. The `blackserv_coder/`
package is a small Dell-side tool executor for Garlic 1.21's OpenAI-compatible API.

## What works in the prototype
- Locally run model (Garlic API) selects a function and receives its result.
- Workspace-restricted file listing/read/write, bounded ZIP extraction.
- Read-only Git status/diff.
- Allowlisted HTTPS documentation fetching.
- Explicit maximum number of tool-call rounds.

## Not yet implemented
- Terminal command execution, SSH, GitHub writes, general search and live PS4 tests.
- Full Qwopus model weight conversion and PS4 inference.
These are deliberately not claimed as working. Do not point the executor at
sensitive directories or production repositories before policy review.

## Test on Dell
`C:\Users\lukas\AppData\Local\Programs\Python\Python313\python.exe -m unittest discover -s tests -p test_blackserv_coder.py -v`

## API
In Garlic 1.21 activate API (L3). The model must be accessible on the LAN,
for example at `http://PS4_IP:8080/v1`. Its server does not require an API
key by default; set `/data/garlic_api_key.txt` to restrict access before
using outside a trusted isolated network.

## Source and license
Garlic LLM upstream: https://github.com/leonardo-alegria/garlic-llm
The upstream GPL-3.0 license and attribution remain in this repository.
