#ifndef GARLIC_MCP_AGENT_H
#define GARLIC_MCP_AGENT_H
#include "mcp_client.h"
#define MCP_AGENT_MAX_CONTEXT 32768u
#define MCP_AGENT_MAX_REPLY 32768u
/* Synchronous callback to the same on-console inference engine. Returns
 * one non-streamed OpenAI chat completion, not HTTP headers. Appends to an
 * initialized Sb. Failure or cancellation must return nonzero. */
typedef int (*McpGenerate)(void* ctx,const char* request,size_t request_len,Sb* completion);
typedef int (*McpCancelled)(void* ctx);
/* The client must be open. Exactly one tool call at a time, at most eight
 * per user question, with bounded history. No credentials in model context.
 * Initializes answer on entry; caller frees answer on every path. */
int mcp_agent_run(McpClient* client,const char* question,McpGenerate generate,
                  McpCancelled cancelled,void* ctx,Sb* answer);
#endif
