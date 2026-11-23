/* Fake, local-only transport. Does not contact any network host. */
#include "mcp_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks, failures;
#define CHECK(x) do { ++checks; if(!(x)) { ++failures; fprintf(stderr,"FAIL at %d: %s\n",__LINE__,#x); } } while(0)

typedef struct { int calls; int fail_step; int notifications; int bad_response_id; } Mock;
static int mock_post(void* opaque,const char* request,size_t req_len,char* out,size_t cap,size_t* n,int* status) {
    Mock* m = opaque;
    ++m->calls;
    if (m->calls == m->fail_step) return -1;
    const char* reply;
    char response_buf[256];
    JNode nodes[128];
    int root=json_parse(request,req_len,nodes,128);
    if(root<0) return -1;
    int method_node=json_get(nodes,root,"method");
    if(method_node<0) return -1;
    Sb method; sb_init(&method); json_str_sb(nodes,method_node,&method);
    if (!method.p) { sb_free(&method); return -1; }
    if (!strcmp(method.p,"notifications/initialized")) {
        m->notifications++;
        *n = 0; *status = 202; sb_free(&method); return 0;
    }
    if (!strcmp(method.p,"initialize")) {
        reply="{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"protocolVersion\":\"2025-06-18\"}}";
    } else if (!strcmp(method.p,"tools/list")) {
        reply="{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"tools\":[{\"name\":\"hosts_list\"},{\"name\":\"host_capabilities\"},{\"name\":\"job_get\"},{\"name\":\"host_exec\"}]}}";
    } else if (!strcmp(method.p,"tools/call")) {
        int idnode=json_get(nodes,root,"id");
        if(idnode<0||nodes[idnode].type!=J_NUM){ sb_free(&method); return -1; }
        int id=(int)nodes[idnode].num+(m->bad_response_id?100:0);
        snprintf(response_buf,sizeof response_buf,
            "{\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"structuredContent\":[{\"host_id\":\"mock\"}]}}",id);
        reply=response_buf;
    } else { sb_free(&method); return -1; }
    sb_free(&method);
    *n=strlen(reply);
    if (*n > cap || req_len == 0) return -1;
    memcpy(out,reply,*n); *status=200; return 0;
}

int main(void) {
    McpClient c; Mock mock={0};
    CHECK(mcp_client_open(&c,mock_post,&mock)==0);
    CHECK(mock.calls==3 && mock.notifications==1 && c.ready==1);
    ApiToolCall a={0}; strcpy(a.name,"sentinel_hosts_list");strcpy(a.id,"call_1_1");sb_init(&a.arguments);sb_str(&a.arguments,"{}");
    Sb result;
    int rc=mcp_client_call(&c,&a,&result);
    CHECK(rc==0);
    if(rc==0){CHECK(strstr(result.p,"mock")!=NULL); sb_free(&result);}
    CHECK(c.calls_this_turn==1 && mock.calls==4);
    /* Exactly 8 read-only calls per model turn; the 9th never reaches transport. */
    for (int i=1;i<MCP_CLIENT_MAX_CALLS_PER_TURN;++i) {
        CHECK(mcp_client_call(&c,&a,&result)==0);
        sb_free(&result);
    }
    CHECK(c.calls_this_turn==MCP_CLIENT_MAX_CALLS_PER_TURN);
    int before=mock.calls;
    CHECK(mcp_client_call(&c,&a,&result)!=0);
    CHECK(mock.calls==before);
    mcp_client_new_turn(&c);
    CHECK(c.calls_this_turn==0);
    CHECK(mcp_client_call(&c,&a,&result)==0); sb_free(&result);
    mock.bad_response_id=1;
    CHECK(mcp_client_call(&c,&a,&result)!=0);
    sb_free(&a.arguments);
    mcp_client_reset(&c);
    CHECK(mcp_client_call(&c,&a,&result)!=0);
    Mock bad={0};bad.fail_step=1;
    CHECK(mcp_client_open(&c,mock_post,&bad)!=0 && c.ready==0);
    bad=(Mock){0};bad.fail_step=2;
    CHECK(mcp_client_open(&c,mock_post,&bad)!=0 && c.ready==0);
    bad=(Mock){0};bad.fail_step=3;
    CHECK(mcp_client_open(&c,mock_post,&bad)!=0 && c.ready==0);
    printf("mcp_client: %u checks, %u failed\n",checks,failures);
    return failures ? 1:0;
}
