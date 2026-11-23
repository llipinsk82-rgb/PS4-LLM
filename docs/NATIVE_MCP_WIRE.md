# Native MCP wire layer — staged for PS4

Status: **experimental, not connected, no production access**.

## Scope and boundaries

- Native C JSON-RPC MCP message codec under pc/native_mcp/. It reuses the
  existing Garlic 1.21-backported chat/api_proto.h and api_proto.c.
- The app's existing GPU engine and QwopusFlash model files are unchanged.
- Nothing has been deployed or installed on PS4. This code is deliberately
  NOT in chat/, so build_chat.py does not compile or activate it yet.
- No network client, SSL connection, OAuth token, direct SSH, Sentinel_BS
  credential, privileged action or background daemon is present.
- The separate MODEL-ONLY baseline is not modified.

## Supported MCP operations

The wire layer builds and validates:
1. initialize (MCP protocol 2025-06-18)
2. notifications/initialized (transport should expect HTTP 202)
3. tools/list
4. tools/call for three explicit aliases:
   - sentinel_hosts_list -> hosts_list
   - sentinel_host_capabilities -> host_capabilities
   - sentinel_job_get -> job_get
5. A bounded JSON tool-role message to feed back to QwopusFlash.

It will **reject** host_exec, host_edit, host_git, host_script_run and any
other undeclared function, including if the remote server advertises it.
This is a client-side safety guard, NOT a substitute for server-side
authorization. For real access, Sentinel_BS Hub must independently enforce
allowed client identity, hosts, tools, and arguments.

Input limits: 4 KiB arguments, 128 KiB MCP reply, bounded identifiers,
no duplicate/extra tool arguments, tool names allowlisted, JSON-RPC id
and protocol version checked, JSON-RPC errors denied.

## Local tests

This is native C intended to be compiled with the actual Garlic JSON
parser; from the repository root:

    cc -std=gnu11 -O1 -Wall -Wextra -Werror \
      -Ichat -Ipc/native_mcp \
      pc/native_mcp/mcp_wire.c tests/mcp_wire_test.c chat/api_proto.c \
      -lm -o mcp_wire_test
    ./mcp_wire_test

An independent developer-box check used a json-c-based parser shim and
ran **30 checks, 0 failed**, including denied write tools, malformed ids,
wrong response ids, errors, and oversized responses. This is NOT a claim
that the real Garlic parser, PS4 binary, TLS, OAuth or live MCP service
has passed. Repeat with the real api_proto.c when build access is available.

## Next native integration work

1. MODEL PASS on physical PS4: clean Garlic 1.20 + existing QwopusFlash.
2. tool_calls generated and tool results consumed on physical PS4.
3. Choose PS4 system HTTP/SSL APIs after verifying transport and TLS
   certificate validation in the actual OpenOrbis build; do NOT bypass
   certificate verification or hardcode a shared master credential.
4. Native connector configurable by the owner, OFF by default, with
   revocable device-specific authorization and server-enforced read-only
   scopes. Begin with a TEST MCP Hub/agent, not production Sentinel_BS.
5. Implement bounded executor loop (max tool calls/turn, timeout/retry,
   cancellation, job_get polling), preserve clear audit and owner approval
   before any write operation. Then demonstrate an end-to-end result on PS4.

There is **no requirement for an always-on Dell** in the final
architecture: the native transport and tool loop must run on PS4.

## Relevant branches

- blackserv/garlic120-model-only: isolated model baseline for PS4 acceptance.
- blackserv/garlic120-toolcalls: 1.20 + 1.21 OpenAI tool call protocol.
- blackserv/sentinel-connector-spike: this experimental, isolated work.

Changes to Sentinel_BS production, Cloudflare Access settings, VM101/VM102,
Della system configuration and the PS4 were not performed.
