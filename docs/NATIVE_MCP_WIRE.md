# Native MCP wire layer — staged for PS4

Status: **experimental, not connected, no production access**. The protocol and transport-neutral session client compile independently of the PS4 application.

## Scope and boundaries

- Native C JSON-RPC MCP message codec AND bounded session client under pc/native_mcp/. The code reuses the
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

The `McpClient` callback handles `initialize` → notification (HTTP 202) → `tools/list` → `tools/call` and accepts at most **8 model tool requests per turn**, rejecting wrong response IDs and HTTP status codes. The callback is **not a network implementation**; a future PS4 adapter must enforce authenticated HTTPS, TLS certificate checks, bounded IO and timeouts.

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
    cc -std=gnu11 -O1 -Wall -Wextra -Werror \
      -Ichat -Ipc/native_mcp \
      pc/native_mcp/mcp_wire.c pc/native_mcp/mcp_client.c \
      tests/mcp_client_test.c chat/api_proto.c \
      -lm -o mcp_client_test
    ./mcp_client_test

An independent offline check used a json-c-based parser shim and
ran **52 checks, 0 failed**, including denied write tools, malformed ids,
wrong response ids, errors, and oversized responses. This is NOT a claim
that the real Garlic parser, PS4 binary, TLS, OAuth or live MCP service
has passed. GitHub Actions run 45206418434: native wire 30/30 and client 22/22 PASS against the actual Garlic JSON parser.

Dell SentinelX returned online on 2026-11-23; PS4-targeted compilation of both standalone modules PASS with installed OpenOrbis and Zig:
- mcp_wire.o: 34,376 bytes, x86-64 ELF (machine=62)
- mcp_client.o: 13,264 bytes, x86-64 ELF (machine=62)

Compiler settings for reproduction: zig cc -target x86_64-freebsd-none -march=btver2 -O2 -fPIC -fno-stack-protector -fshort-wchar -nostdinc -isystem <OpenOrbis/PS4Toolchain/include> -Wall -Wextra -Werror -c -Ichat -Ipc/native_mcp pc/native_mcp/<source>.c -o <object>.o.

Objects were produced in D:\BlackServ_Coder\tmp_mcp_native\ps4 (outside the source tree). Both passed ELF signature and target-machine checks.

No full PS4 app link, install, inference, HTTPS/TLS handshake or live MCP connection has been tested. Native codec remains outside chat/ to prevent accidental activation against production Sentinel_BS.

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

## Experimental native SceHttp adapter (2026-11-24)

`pc/native_mcp/mcp_https.c` implements the McpPost callback using PS4 SceHttp.
It requires a caller-owned initialized HTTP context, owner-selected DNS hostname,
port 443 and fixed /mcp route. It requests server, hostname, CA and certificate
validity verification plus SNI, explicitly disables redirects and checks that
setting, requests bounded DNS/connect/send/read timeouts and checks a monotonic
deadline between blocking operations. The deadline is not a hard asynchronous
cancellation guarantee. Only HTTP 200 and empty HTTP 202 are accepted. Responses
are capped at the wire size limit; request/connection/template objects are freed
on all paths. Optional bearer credentials must be supplied by the owner-side
caller, never by the model. No real token, endpoint, login, or production action
is included. Stateless JSON MCP only; SSE and session IDs are not supported.

OpenOrbis Http.h has incomplete declarations of the redirect, receive timeout,
and resolve retry functions. The adapter explicitly declares the signatures
cross-checked against shadPS4 network/http.h blob
82d692af981f5fa89a29fdd73c3512bae66182d6. Emulator declarations are supporting
evidence, not proof of actual PS4 firmware behavior.

Verified on Dell: PS4-targeted OpenOrbis/Zig compile with -Wall -Wextra -Werror
PASS (mcp_https.o 19,096 bytes); host mock-SceHttp policy and cleanup test PASS
(invalid endpoints/header injection, TLS configuration failure, redirect
configuration failure, 302, send/read failure, exact and oversized response,
202 notification). Mock checks do not verify real TLS or timing.

The adapter remains outside chat/ and is NOT enabled. Remaining acceptance gates:
actual PS4 SSL/HTTP context lifecycle, native inference/tool loop, physical PS4
positive and negative certificate/hostname tests with a dedicated test service,
server-enforced read-only client authorization, owner pairing, cancellation and
full app link/package. Do not use real Sentinel_BS credentials until these pass.
