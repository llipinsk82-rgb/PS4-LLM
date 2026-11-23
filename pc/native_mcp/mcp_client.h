/* MCP transport orchestration. No network implementation, URL, TLS or credentials.
 * The supplied callback MUST itself enforce verified TLS/auth and bound its IO.
 */
#ifndef GARLIC_MCP_CLIENT_H
#define GARLIC_MCP_CLIENT_H
#include "mcp_wire.h"

enum { MCP_CLIENT_MAX_CALLS_PER_TURN = 8 };
/* Result: 0 success, -1 transport error; HTTP status/body returned separately. */
typedef int (*McpPost)(void* opaque, const char* request, size_t request_len,
                       char* response, size_t response_capacity,
                       size_t* response_len, int* status_code);
typedef struct {
    McpWire wire;
    McpPost post;
    void* opaque;
    unsigned calls_this_turn;
    int ready;
} McpClient;

void mcp_client_reset(McpClient* client);
int mcp_client_open(McpClient* client, McpPost transport, void* opaque);
void mcp_client_new_turn(McpClient* client);
int mcp_client_call(McpClient* client, const ApiToolCall* call, Sb* tool_message);
#endif
