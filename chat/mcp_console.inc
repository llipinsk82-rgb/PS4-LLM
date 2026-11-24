/* Experimental on-console diagnostic, no network or external credentials.
 * Included only in the separate --mcp-experimental package.
 * Uses the same GPU engine through a local ApiJob, not the LAN HTTP server.
 */
#include "mcp_agent.h"

static int mcp_console_generate(void* ctx,const char* request,size_t len,Sb* result) {
    (void)ctx;
    ApiJob local={0};
    local.fd=-1;
    local.body=(char*)request;
    local.body_len=len;
    api_job_impl(&local,result);
    return result->oom||!result->n ? -1 : 0;
}
static int mcp_console_cancel(void* ctx) {
    (void)ctx;
    return (read_buttons()&ORBIS_PAD_BUTTON_CIRCLE)!=0;
}
static int mcp_console_mock(void* ctx,const char* request,size_t len,
                            char* response,size_t cap,size_t* out_len,int* status) {
    (void)ctx;
    JNode nodes[128];
    int root=json_parse(request,len,nodes,128);
    if(root<0)return -1;
    int method=json_get(nodes,root,"method");
    int idnode=json_get(nodes,root,"id");
    if(method<0||nodes[method].type!=J_STR)return -1;
    Sb m;sb_init(&m);json_str_sb(nodes,method,&m);
    if(!m.p||m.oom){sb_free(&m);return -1;}
    int rc=-1;
    char out[256];
    int n=-1;
    *out_len=0;*status=0;
    if(!strcmp(m.p,"notifications/initialized")&&idnode<0){
        *status=202;rc=0;goto done;
    }
    if(idnode<0||nodes[idnode].type!=J_NUM||nodes[idnode].num<1||nodes[idnode].num>100)goto done;
    int id=(int)nodes[idnode].num;
    if(!strcmp(m.p,"initialize")){
        n=snprintf(out,sizeof(out),"{\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"protocolVersion\":\"2025-06-18\"}}",id);
    }else if(!strcmp(m.p,"tools/list")){
        n=snprintf(out,sizeof(out),"{\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"tools\":[{\"name\":\"hosts_list\"}]}}",id);
    }else if(!strcmp(m.p,"tools/call")){
        int params=json_get(nodes,root,"params");
        if(params<0||nodes[params].type!=J_OBJ)goto done;
        int name=json_get(nodes,params,"name"),args=json_get(nodes,params,"arguments");
        if(name<0||nodes[name].type!=J_STR||nodes[name].slen!=10||memcmp(nodes[name].s,"hosts_list",10)||
           args<0||nodes[args].type!=J_OBJ||nodes[args].count)goto done;
        n=snprintf(out,sizeof(out),"{\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"structuredContent\":{\"host_id\":\"mock-ps4\"}}}",id);
    }
    if(n<0||(size_t)n>=sizeof(out)||(size_t)n>cap)goto done;
    memcpy(response,out,(size_t)n);*out_len=(size_t)n;*status=200;rc=0;
done:
    sb_free(&m);return rc;
}
static void mcp_console_test(void) {
    McpClient client;
    Sb answer;sb_init(&answer);
    int opened=mcp_client_open(&client,mcp_console_mock,NULL)==0;
    int ok=opened && mcp_agent_run(&client,
        "Use sentinel_hosts_list to list allowed hosts. Reply with the returned host_id only.",
        mcp_console_generate,mcp_console_cancel,NULL,&answer)==0 &&
        client.calls_this_turn==1 && answer.p && strstr(answer.p,"mock-ps4");
    msgs_clear();
    const char* label=ok?"MCP diagnostic PASS (local mock, no network)":"MCP diagnostic FAIL or cancelled";
    Msg* note=msg_new(MSG_NOTE);
    msg_append(note,label,strlen(label));
    if(ok){
        Msg* result=msg_new(MSG_NOTE);
        msg_append(result,answer.p,answer.n);
    }
    say("mcp diagnostic %s; tool calls=%u",ok?"PASS":"FAIL",opened?client.calls_this_turn:0);
    sb_free(&answer);
    mcp_client_reset(&client);
    pos=0;need_close=0;hist_n=hist_done=0;api_snap_n=0;
}
