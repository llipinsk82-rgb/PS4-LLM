/* PS4 Garlic -> MCP Streamable HTTP: transport-independent, read-only wire protocol.
 * Experimental. Requires chat/api_proto.h + api_proto.c. Not wired into the PS4 app.
 * Network, TLS, auth and approval are deliberately NOT implemented here.
 */
#ifndef GARLIC_MCP_WIRE_H
#define GARLIC_MCP_WIRE_H
#include "api_proto.h"
#include <stddef.h>

#define MCP_WIRE_MAX_RX (128u * 1024u)
#define MCP_WIRE_MAX_ARGUMENTS 4096u
#define MCP_WIRE_PROTOCOL "2025-06-18"

typedef struct {
    unsigned next_id;
    unsigned tools;        /* discovered allowlisted tool bitset */
    int initialized;
} McpWire;

enum {
    MCP_TOOL_HOSTS_LIST = 1,
    MCP_TOOL_HOST_CAPABILITIES = 2,
    MCP_TOOL_JOB_GET = 4,
};

void mcp_wire_reset(McpWire* m);
/* Every maker initialises out with sb_init. On success, id is the expected JSON-RPC id. */
int mcp_wire_make_initialize(McpWire* m, Sb* out, unsigned* id);
int mcp_wire_accept_initialize(McpWire* m, const char* response, size_t length, unsigned id);
/* MCP lifecycle notification: POST with no JSON-RPC id, HTTP 202 expected. */
int mcp_wire_make_initialized_notification(const McpWire* m, Sb* out);
int mcp_wire_make_list(McpWire* m, Sb* out, unsigned* id);
int mcp_wire_accept_list(McpWire* m, const char* response, size_t length, unsigned id);
/* Only read-only, explicit aliases. Write/exec never accepted in this layer. */
int mcp_wire_make_call(McpWire* m, const ApiToolCall* call, Sb* out, unsigned* id);
/* Produces one complete JSON message for Garlic's tool result, never executes a command. */
int mcp_wire_accept_call(const ApiToolCall* call, const char* response, size_t length,
                         unsigned id, Sb* tool_message);

#endif
