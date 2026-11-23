/* Offline native-wire tests; compile with Garlic's actual api_proto.c and mcp_wire.c. */
#include "mcp_wire.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; fprintf(stderr, "FAIL line %d: %s\n",__LINE__,#x); } } while(0)

static ApiToolCall call(const char* name, const char* args) {
    ApiToolCall c; memset(&c, 0, sizeof(c));
    strcpy(c.id, "call_1_1");
    strncpy(c.name, name, sizeof(c.name) - 1);
    sb_init(&c.arguments);
    sb_str(&c.arguments, args);
    return c;
}

int main(void) {
    McpWire m; mcp_wire_reset(&m);
    Sb req, out; unsigned id;
    const char* init = "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"protocolVersion\":\"2025-06-18\"}}";
    CHECK(mcp_wire_make_list(&m,&req,&id) != 0);
    CHECK(mcp_wire_make_initialize(&m,&req,&id) == 0);
    CHECK(id == 1 && strstr(req.p,"\"initialize\"") != NULL);
    CHECK(strstr(req.p,"2025-06-18") != NULL); sb_free(&req);
    CHECK(mcp_wire_accept_initialize(&m,init,strlen(init),1)==0);
    CHECK(m.initialized == 1);
    CHECK(mcp_wire_accept_initialize(&m,init,strlen(init),1)!=0);
    CHECK(mcp_wire_make_initialized_notification(&m,&req)==0);
    CHECK(strstr(req.p,"notifications")!=NULL); sb_free(&req);
    CHECK(mcp_wire_make_list(&m,&req,&id)==0);
    CHECK(id == 2 && strstr(req.p,"tools") != NULL); sb_free(&req);
    const char* list = "{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"tools\":["
      "{\"name\":\"hosts_list\"},{\"name\":\"host_capabilities\"},"
      "{\"name\":\"job_get\"},{\"name\":\"host_exec\"}]}}";
    CHECK(mcp_wire_accept_list(&m,list,strlen(list),2)==0);
    CHECK(m.tools == 7);
    ApiToolCall c=call("sentinel_hosts_list","{}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)==0);
    CHECK(id == 3 && strstr(req.p,"\"name\":\"hosts_list\"") != NULL); sb_free(&req);
    const char* tool_result="{\"jsonrpc\":\"2.0\",\"id\":3,\"result\":{\"structuredContent\":[{\"host_id\":\"mock\"}]}}";
    CHECK(mcp_wire_accept_call(&c,tool_result,strlen(tool_result),3,&out)==0);
    CHECK(strstr(out.p,"\"role\":\"tool\"") != NULL);
    CHECK(strstr(out.p,"call_1_1") != NULL);
    CHECK(strstr(out.p,"mock") != NULL); sb_free(&out);
    CHECK(mcp_wire_accept_call(&c,tool_result,strlen(tool_result),999,&out)!=0);
    const char* err="{\"jsonrpc\":\"2.0\",\"id\":3,\"error\":{\"code\":-32000}}";
    CHECK(mcp_wire_accept_call(&c,err,strlen(err),3,&out)!=0);
    const char* iserr="{\"jsonrpc\":\"2.0\",\"id\":3,\"result\":{\"isError\":true,\"content\":[]}}";
    CHECK(mcp_wire_accept_call(&c,iserr,strlen(iserr),3,&out)!=0);
    sb_free(&c.arguments);
    c=call("sentinel_host_exec","{\"host_id\":\"mock\",\"argv\":[\"ls\"]}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0);
    sb_free(&c.arguments);
    c=call("sentinel_host_capabilities","{\"host_id\":\"mock\"}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)==0); sb_free(&req);
    sb_free(&c.arguments);
    c=call("sentinel_host_capabilities","{\"host_id\":\"../../etc\"}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0); sb_free(&c.arguments);
    c=call("sentinel_job_get","{\"job_id\":\"bad\\u0000good\"}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0); sb_free(&c.arguments);
    c=call("sentinel_job_get","{\"job_id\":\"mock-1\",\"override\":true}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0); sb_free(&c.arguments);
    c=call("sentinel_hosts_list","{\"other\":true}");
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0); sb_free(&c.arguments);
    c=call("sentinel_hosts_list","{}");
    memset(c.id,'A',sizeof(c.id));
    CHECK(mcp_wire_make_call(&m,&c,&req,&id)!=0); sb_free(&c.arguments);
    char *huge=malloc(MCP_WIRE_MAX_RX+1); memset(huge,'x',MCP_WIRE_MAX_RX+1);
    CHECK(mcp_wire_accept_initialize(&m,huge,MCP_WIRE_MAX_RX+1,42)!=0);
    free(huge);
    printf("mcp_wire: %u checks, %u failed\n",checks,failures);
    return failures ? 1 : 0;
}
