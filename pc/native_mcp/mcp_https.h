#ifndef GARLIC_MCP_HTTPS_H
#define GARLIC_MCP_HTTPS_H
#include <stddef.h>
typedef struct {
    int http_id;         /* caller-owned initialized SceHttp context */
    const char* host;    /* owner-configured DNS name, port 443, /mcp only */
    const char* bearer;  /* optional caller-owned short-lived credential */
} McpHttps;
int mcp_https_config_valid(const McpHttps* cfg);
int mcp_https_post(void* opaque, const char* request, size_t request_len,
                   char* response, size_t response_capacity,
                   size_t* response_len, int* status_code);
#endif
