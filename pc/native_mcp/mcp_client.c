/* Transport-neutral bounded MCP request/notification/call orchestration. */
#include "mcp_client.h"
#include <stdlib.h>
#include <string.h>

static int post(McpClient* c, const Sb* req, char* rx, size_t* n, int* status) {
    *n = 0; *status = 0;
    if (!c->post || !req || req->oom || !req->p || req->n > MCP_WIRE_MAX_ARGUMENTS + 1024u)
        return -1;
    if (c->post(c->opaque, req->p, req->n, rx, MCP_WIRE_MAX_RX, n, status) != 0)
        return -1;
    return *n <= MCP_WIRE_MAX_RX ? 0 : -1;
}

void mcp_client_reset(McpClient* c) {
    if (c) memset(c, 0, sizeof(*c));
}

int mcp_client_open(McpClient* c, McpPost transport, void* opaque) {
    if (!c || !transport) return -1;
    mcp_client_reset(c);
    c->post = transport;
    c->opaque = opaque;
    char* rx = malloc(MCP_WIRE_MAX_RX + 1);
    if (!rx) return -1;
    Sb req;
    unsigned id;
    size_t n;
    int status, rc = -1;
    if (mcp_wire_make_initialize(&c->wire, &req, &id)) goto done;
    int ok = !post(c, &req, rx, &n, &status) && status == 200
        && !mcp_wire_accept_initialize(&c->wire, rx, n, id);
    sb_free(&req);
    if (!ok) goto done;
    if (mcp_wire_make_initialized_notification(&c->wire, &req)) goto done;
    ok = !post(c, &req, rx, &n, &status) && status == 202 && n == 0;
    sb_free(&req);
    if (!ok) goto done;
    if (mcp_wire_make_list(&c->wire, &req, &id)) goto done;
    ok = !post(c, &req, rx, &n, &status) && status == 200
        && !mcp_wire_accept_list(&c->wire, rx, n, id);
    sb_free(&req);
    if (!ok) goto done;
    c->ready = 1;
    rc = 0;
done:
    free(rx);
    if (rc) mcp_client_reset(c);
    return rc;
}

void mcp_client_new_turn(McpClient* c) {
    if (c) c->calls_this_turn = 0;
}

int mcp_client_call(McpClient* c, const ApiToolCall* call, Sb* tool_message) {
    if (!c || !c->ready || !call || !tool_message || c->calls_this_turn >= MCP_CLIENT_MAX_CALLS_PER_TURN)
        return -1;
    Sb req;
    unsigned id;
    if (mcp_wire_make_call(&c->wire, call, &req, &id)) return -1;
    char* rx = malloc(MCP_WIRE_MAX_RX + 1);
    if (!rx) { sb_free(&req); return -1; }
    size_t n;
    int status;
    c->calls_this_turn++;
    int ok = !post(c, &req, rx, &n, &status) && status == 200
        && !mcp_wire_accept_call(call, rx, n, id, tool_message);
    sb_free(&req);
    free(rx);
    return ok ? 0 : -1;
}
