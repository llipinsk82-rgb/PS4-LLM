/* Minimal MCP JSON-RPC codec for Garlic's existing JSON reader/string builder.
 * Strict, read-only, fail-closed; NO HTTP transport or production credentials.
 */
#include "mcp_wire.h"
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int string_is(const JNode* p, int i, const char* s) {
    return i >= 0 && p[i].type == J_STR && p[i].slen == strlen(s)
        && !memcmp(p[i].s, s, p[i].slen);
}

static size_t bounded_len(const char* s, size_t limit) {
    const char* end = s ? memchr(s, 0, limit) : NULL;
    return end ? (size_t)(end - s) : 0;
}

static int safe_id(const char* s, size_t limit) {
    size_t length = bounded_len(s, limit);
    if (!length || length > 127) return 0;
    if (!((s[0] >= 'A' && s[0] <= 'Z') || (s[0] >= 'a' && s[0] <= 'z')
        || (s[0] >= '0' && s[0] <= '9'))) return 0;
    for (const char* p = s; *p; ++p) {
        char c = *p;
        if (!( (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
             || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.' || c == ':')) return 0;
        if (c == '.' && p[1] == '.') return 0;
    }
    return 1;
}

static int read_arg_id(const JNode* p, int obj, const char* key) {
    if (obj < 0 || p[obj].type != J_OBJ || p[obj].count != 1) return 0;
    int i = json_get(p, obj, key);
    if (i < 0 || p[i].type != J_STR || !p[i].slen || p[i].slen > 127) return 0;
    Sb decoded; sb_init(&decoded); json_str_sb(p, i, &decoded);
    int good = !decoded.oom && decoded.p && decoded.n == bounded_len(decoded.p, decoded.n + 1)
        && safe_id(decoded.p, decoded.n + 1);
    sb_free(&decoded);
    return good;
}

/* A response envelope is checked against its one outstanding request.
 * The JSON-RPC error field is never interpreted as success. */
static JNode* parse_response(const char* s, size_t len, unsigned id,
                             int* result, int* root) {
    *result = -1; *root = -1;
    if (!s || len == 0 || len > MCP_WIRE_MAX_RX || id == 0) return NULL;
    JNode* p = json_parse_grow(s, len, 128, root);
    if (!p || *root < 0 || p[*root].type != J_OBJ) { free(p); return NULL; }
    int version = json_get(p, *root, "jsonrpc");
    int rid = json_get(p, *root, "id");
    int err = json_get(p, *root, "error");
    int res = json_get(p, *root, "result");
    if (!string_is(p, version, "2.0") || rid < 0 || p[rid].type != J_NUM
        || p[rid].num != (double)id || err >= 0 || res < 0 || p[res].type != J_OBJ) {
        free(p); return NULL;
    }
    *result = res;
    return p;
}

static int begin_request(McpWire* m, const char* method, Sb* out, unsigned* id) {
    if (!m || !out || !id || !method || m->next_id == UINT32_MAX) return -1;
    *id = ++m->next_id;
    sb_init(out);
    sb_str(out, "{\"jsonrpc\":\"2.0\",\"id\":");
    sb_int(out, *id);
    sb_str(out, ",\"method\":");
    sb_json_str(out, method, strlen(method));
    return out->oom ? -1 : 0;
}

void mcp_wire_reset(McpWire* m) {
    if (m) memset(m, 0, sizeof(*m));
}

int mcp_wire_make_initialize(McpWire* m, Sb* out, unsigned* id) {
    if (!m || m->initialized || begin_request(m, "initialize", out, id)) return -1;
    sb_str(out, ",\"params\":{\"protocolVersion\":\"" MCP_WIRE_PROTOCOL
                "\",\"capabilities\":{},\"clientInfo\":{\"name\":\"garlic-ps4-mcp\",\"version\":\"0.1\"}}}");
    return out->oom ? -1 : 0;
}

int mcp_wire_accept_initialize(McpWire* m, const char* response, size_t length, unsigned id) {
    if (!m || m->initialized) return -1;
    int result, root;
    JNode* p = parse_response(response, length, id, &result, &root);
    if (!p) return -1;
    int version = json_get(p, result, "protocolVersion");
    int ok = string_is(p, version, MCP_WIRE_PROTOCOL);
    free(p);
    if (!ok) return -1;
    m->initialized = 1;
    return 0;
}

int mcp_wire_make_initialized_notification(const McpWire* m, Sb* out) {
    if (!m || !out || !m->initialized) return -1;
    sb_init(out);
    sb_str(out, "{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}");
    return out->oom ? -1 : 0;
}

int mcp_wire_make_list(McpWire* m, Sb* out, unsigned* id) {
    if (!m || !m->initialized || begin_request(m, "tools/list", out, id)) return -1;
    sb_str(out, ",\"params\":{}}");
    return out->oom ? -1 : 0;
}

int mcp_wire_accept_list(McpWire* m, const char* response, size_t length, unsigned id) {
    if (!m || !m->initialized) return -1;
    int result, root;
    JNode* p = parse_response(response, length, id, &result, &root);
    if (!p) return -1;
    int arr = json_get(p, result, "tools");
    if (arr < 0 || p[arr].type != J_ARR) { free(p); return -1; }
    unsigned flags = 0;
    for (int i = p[arr].first; i >= 0; i = p[i].next) {
        if (p[i].type != J_OBJ) { free(p); return -1; }
        int n = json_get(p, i, "name");
        if (string_is(p, n, "hosts_list")) flags |= MCP_TOOL_HOSTS_LIST;
        else if (string_is(p, n, "host_capabilities")) flags |= MCP_TOOL_HOST_CAPABILITIES;
        else if (string_is(p, n, "job_get")) flags |= MCP_TOOL_JOB_GET;
    }
    free(p);
    if (!(flags & MCP_TOOL_HOSTS_LIST)) return -1;
    m->tools = flags;
    return 0;
}

static int get_tool(const char* name, const char** remote, unsigned* flag, const char** id_key) {
    if (!strcmp(name, "sentinel_hosts_list")) {
        *remote = "hosts_list"; *flag = MCP_TOOL_HOSTS_LIST; *id_key = NULL;
    } else if (!strcmp(name, "sentinel_host_capabilities")) {
        *remote = "host_capabilities"; *flag = MCP_TOOL_HOST_CAPABILITIES; *id_key = "host_id";
    } else if (!strcmp(name, "sentinel_job_get")) {
        *remote = "job_get"; *flag = MCP_TOOL_JOB_GET; *id_key = "job_id";
    } else return -1;
    return 0;
}

int mcp_wire_make_call(McpWire* m, const ApiToolCall* call, Sb* out, unsigned* id) {
    if (!m || !call || !m->initialized || !m->tools || !call->arguments.p
        || call->arguments.n > MCP_WIRE_MAX_ARGUMENTS || !call->arguments.n
        || !safe_id(call->id, sizeof(call->id))) return -1;
    const char* name; const char* key; unsigned flag;
    if (!bounded_len(call->name, sizeof(call->name))
        || get_tool(call->name, &name, &flag, &key) || !(m->tools & flag)) return -1;
    JNode nodes[128];
    int root = json_parse(call->arguments.p, call->arguments.n, nodes, 128);
    if (root < 0 || nodes[root].type != J_OBJ) return -1;
    if (key ? !read_arg_id(nodes, root, key) : nodes[root].count != 0) return -1;
    if (begin_request(m, "tools/call", out, id)) return -1;
    sb_str(out, ",\"params\":{\"name\":");
    sb_json_str(out, name, strlen(name));
    sb_str(out, ",\"arguments\":");
    sb_add(out, call->arguments.p, call->arguments.n);
    sb_str(out, "}}");
    return out->oom ? -1 : 0;
}

int mcp_wire_accept_call(const ApiToolCall* call, const char* response, size_t length,
                         unsigned id, Sb* tool_message) {
    if (!call || !tool_message || !safe_id(call->id, sizeof(call->id))) return -1;
    int result, root;
    JNode* p = parse_response(response, length, id, &result, &root);
    if (!p) return -1;
    int err = json_get(p, result, "isError");
    int payload = json_get(p, result, "structuredContent");
    if (payload < 0) payload = json_get(p, result, "content");
    if ((err >= 0 && (p[err].type != J_BOOL || p[err].b)) || payload < 0) {
        free(p); return -1;
    }
    Sb content; sb_init(&content);
    json_write(p, payload, &content);
    free(p);
    if (content.oom || content.n > MCP_WIRE_MAX_RX) { sb_free(&content); return -1; }
    sb_init(tool_message);
    sb_str(tool_message, "{\"role\":\"tool\",\"tool_call_id\":");
    sb_json_str(tool_message, call->id, strlen(call->id));
    sb_str(tool_message, ",\"content\":");
    sb_json_str(tool_message, content.p ? content.p : "", content.n);
    sb_str(tool_message, "}");
    sb_free(&content);
    return tool_message->oom ? -1 : 0;
}
