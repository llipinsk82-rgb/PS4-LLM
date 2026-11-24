/* Experimental PS4 HTTPS transport for stateless MCP. Not activated in Garlic.
 * Caller owns an initialized SceHttp context and the owner-approved endpoint.
 * No secrets embedded; do not expose endpoint or credentials to model tools.
 */
#include "mcp_https.h"
#include "mcp_wire.h"
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
/* OpenOrbis Http.h has incomplete declarations for these three functions.
 * Signatures and SSL flags cross-checked against shadPS4 network/http.h
 * blob 82d692af981f5fa89a29fdd73c3512bae66182d6.
 */
#define sceHttpSetAutoRedirect oo_incomplete_redirect
#define sceHttpSetRecvTimeOut oo_incomplete_recv
#define sceHttpSetResolveRetry oo_incomplete_retry
#include <orbis/Http.h>
#undef sceHttpSetAutoRedirect
#undef sceHttpSetRecvTimeOut
#undef sceHttpSetResolveRetry
extern int32_t sceHttpSetAutoRedirect(int32_t, int32_t);
extern int32_t sceHttpSetRecvTimeOut(int32_t, uint32_t);
extern int32_t sceHttpSetResolveRetry(int32_t, int32_t);

#define TLS_REQUIRED (0x01u|0x04u|0x08u|0x10u|0x20u|0x80u)
#define IO_TIMEOUT_US 3000000u
#define TOTAL_TIMEOUT_S 15

int mcp_https_config_valid(const McpHttps* cfg) {
    if (!cfg || cfg->http_id < 0 || !cfg->host) return 0;
    size_t n = strnlen(cfg->host, 254);
    if (!n || n > 253 || cfg->host[0] == '.' || cfg->host[n-1] == '.') return 0;
    size_t label = 0;
    int dots = 0, alpha = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = cfg->host[i];
        if (c == '.') {
            if (!label || cfg->host[i-1] == '-') return 0;
            label = 0; dots++; continue;
        }
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) alpha = 1;
        else if (!(c >= '0' && c <= '9') && c != '-') return 0;
        if (!label && c == '-') return 0;
        if (++label > 63) return 0;
    }
    if (!dots || !alpha || cfg->host[n-1] == '-') return 0;
    if (cfg->bearer) {
        n = strnlen(cfg->bearer, 4097);
        if (!n || n > 4096) return 0;
        for (size_t i = 0; i < n; i++) {
            unsigned char c = cfg->bearer[i];
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || strchr("-._~+/=", c))) return 0;
        }
    }
    return 1;
}

static int within(const struct timespec* start) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return 0;
    return now.tv_sec - start->tv_sec < TOTAL_TIMEOUT_S;
}
static void wipe(char* p, size_t n) {
    volatile char* v = p;
    while (n--) *v++ = 0;
}

int mcp_https_post(void* opaque, const char* body, size_t len,
                   char* response, size_t cap, size_t* out_len, int* status) {
    const McpHttps* cfg = opaque;
    if (!out_len || !status) return -1;
    *out_len = 0; *status = 0;
    if (!mcp_https_config_valid(cfg) || !body || !len ||
        len > MCP_WIRE_MAX_ARGUMENTS + 1024u || !response || !cap ||
        cap > MCP_WIRE_MAX_RX) return -1;
    struct timespec start;
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return -1;
    int tmpl = -1, conn = -1, req = -1, rc = -1, redirect = -1;
    int32_t code = 0;
    char auth[4104];
    size_t n = 0;
    tmpl = sceHttpCreateTemplate(cfg->http_id, "BlackServCoder/0.1", ORBIS_HTTP_VERSION_1_1, 0);
    if (tmpl < 0) goto done;
    if (sceHttpsEnableOption(tmpl, TLS_REQUIRED) < 0 ||
        sceHttpSetAutoRedirect(tmpl, 0) < 0 ||
        sceHttpGetAutoRedirect(tmpl, &redirect) < 0 || redirect != 0 ||
        sceHttpSetResolveRetry(tmpl, 0) < 0 ||
        sceHttpSetResolveTimeOut(tmpl, IO_TIMEOUT_US) < 0 ||
        sceHttpSetConnectTimeOut(tmpl, IO_TIMEOUT_US) < 0 ||
        sceHttpSetSendTimeOut(tmpl, IO_TIMEOUT_US) < 0 ||
        sceHttpSetRecvTimeOut(tmpl, IO_TIMEOUT_US) < 0) goto done;
    conn = sceHttpCreateConnection(tmpl, cfg->host, "https", 443, 0);
    if (conn < 0 || !within(&start)) goto done;
    req = sceHttpCreateRequest(conn, ORBIS_METHOD_POST, "/mcp", len);
    if (req < 0) goto done;
    if (sceHttpAddRequestHeader(req, "Content-Type", "application/json", 0) < 0 ||
        sceHttpAddRequestHeader(req, "Accept", "application/json, text/event-stream", 0) < 0 ||
        sceHttpAddRequestHeader(req, "MCP-Protocol-Version", MCP_WIRE_PROTOCOL, 0) < 0) goto done;
    if (cfg->bearer) {
        int k = snprintf(auth, sizeof(auth), "Bearer %s", cfg->bearer);
        if (k < 0 || (size_t)k >= sizeof(auth) ||
            sceHttpAddRequestHeader(req, "Authorization", auth, 0) < 0) goto done;
    }
    if (!within(&start) || sceHttpSendRequest(req, body, len) < 0 ||
        sceHttpGetStatusCode(req, &code) < 0 || !within(&start)) goto done;
    /* No redirects, auth challenges, or other statuses are followed. */
    if (code != 200 && code != 202) goto done;
    for (;;) {
        if (!within(&start)) goto done;
        char extra;
        uint32_t room = n == cap ? 1u : (uint32_t)(cap - n);
        int got = sceHttpReadData(req, n == cap ? &extra : response+n, room);
        if (got < 0 || (uint32_t)got > room || (n == cap && got)) goto done;
        if (!got) break;
        n += (size_t)got;
    }
    if (!within(&start) || (code == 202 && n)) goto done;
    *out_len = n; *status = code; rc = 0;
done:
    if (req >= 0) sceHttpDeleteRequest(req);
    if (conn >= 0) sceHttpDeleteConnection(conn);
    if (tmpl >= 0) sceHttpDeleteTemplate(tmpl);
    wipe(auth, sizeof(auth));
    return rc;
}
