# PS4 Garlic Coder -> Sentinel_BS MCP connector (offline spike)

## Decision
Use the EXISTING Sentinel_BS Hub MCP as the tool executor. No new SSH agent,
issue runner, job backend, or extra public BlackServ API.

Goal after model validation:
  QwopusFlash (PS4) -> Garlic tool_calls -> *PS4-native MCP client*
    -> authenticated Sentinel_BS /mcp -> Hub -> existing agent -> result
    -> tool-role message -> QwopusFlash -> next action or answer.

**Important distinction:** The API tool_calls backported from Garlic 1.21
currently EMIT calls to the HTTP API client; Garlic does not execute them on
the PS4. For independent PS4 operation we still need a native tool loop and
HTTPS/OAuth transport in Garlic. The Dell-hosted Python code below is a
protocol spike and is NEVER the required runtime host.

## Actual Sentinel_BS source inspected
- Repo: llipinsk82-rgb/Sentinel_BS, main (GitHub, read-only inspection).
- Hub implements MCP Streamable HTTP at /mcp; stateless_http=True,
  json_response=True. The MCP toolset is fixed and includes hosts_list,
  host_capabilities, host_exec, host_read, host_git, job_get, etc.
- An executable task returns a job record; job_get returns status/output.
- Hub brokers work to existing authenticated agents with local policies.
- Public MCP endpoint is behind Cloudflare Access Managed OAuth. It is
  NOT a general unauthenticated REST endpoint.
- Current edge credentials and Cloudflare Access login were NOT used in this
  spike; no production host or auth flow was contacted.
- Source to revisit: hub/sentinel_bs_hub/mcp_server.py,
  public_auth.py, tests/test_mcp_transport.py and docs/HANDOFF.md.
- Cloudflare identity/authentication does not by itself guarantee a
  per-PS4 or read-only permission. That restriction must be independently
  enforced server-side before real operation.

## Prepared in branch blackserv/sentinel-connector-spike
- pc/sentinel_connector_probe.py: PC-only *mock-local* MCP client.
- tests/test_sentinel_connector_probe.py: offline real HTTP loopback stub;
  initialize -> notification -> tools/list -> tools/call -> tool-result.
- Exposes only a small hardcoded tool list to the model. All tool arguments
  are parsed and checked. Writes denied by default; deliberate approval
  in this mock-only client changes the test behavior but must NOT be
  considered an actual owner approval protocol.
- The Python client REFUSES non-loopback URLs, including real Sentinel_BS
  endpoints. No secrets, tokens, agent keys or real remote commands.
- Result is shaped as OpenAI {"role":"tool","tool_call_id":...,"content":...}
  for insertion into the Garlic model's context.
- This implementation deliberately does not support SSE, real OAuth, PS4
  libraries, background retry, sessions, tool-result streaming or live hosts.

Test on Dell:
  python -m unittest discover -s tests -p test_sentinel_connector_probe.py -v

## Acceptance gates before enabling the real connector
1. MODEL PASS on physical PS4 using the separate clean Garlic 1.20 package.
2. Tool-call request AND returned tool-result round-trip PASS on physical PS4.
3. PS4-native outbound HTTPS MCP transport (correct TLS verification,
   bounds/timeouts, no unrestricted redirects, session semantics) PASS.
   We must confirm available PS4 networking/crypto libraries before writing
   that port. Do not assume desktop Python sockets/subprocess exist on Orbis.
4. Owner-controlled one-time pairing and short-lived revocable credential.
   Restrict allowed hosts, tool names and actions **on the server**, not
   just in the model's prompt or console code. No hardcoded BlackServ keys,
   no direct privileged SSH, no Internet-facing unauthenticated PS4 API.
5. Replay/denial/timeout/job_get/result-loop/safe cancel tests on isolated
   test Hub + test agent, then controlled real read-only connection.
   Only after that consider read-write tools with per-action approval.

## Explicitly out of scope
- Production Sentinel_BS changes or direct access;
- PS4 deployment, installation, system update or model modifications;
- Enabling raw shell, SSH or hidden long-lived admin tokens for public users;
- Any assumption that the QwopusFlash model already generates valid tool calls.