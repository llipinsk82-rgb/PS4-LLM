/* Exercise native loop against fake inference and fake MCP, using actual Garlic JSON. */
#include "mcp_agent.h"
#include <stdio.h>
#include <string.h>
#undef NDEBUG
#include <assert.h>

typedef struct { int posts,generations,mode,cancelled; } Mock;
static int post(void* opaque,const char* req,size_t req_len,char* out,size_t cap,size_t* n,int* status){
    Mock* m=opaque;m->posts++;
    JNode p[128];int root=json_parse(req,req_len,p,128);
    if(root<0)return -1;
    int idnode=json_get(p,root,"id");
    if(idnode<0){*n=0;*status=202;return 0;}
    int id=(int)p[idnode].num;
    char buf[256];
    if(id==1)snprintf(buf,sizeof(buf),"{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"protocolVersion\":\"2025-06-18\"}}");
    else if(id==2)snprintf(buf,sizeof(buf),"{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"tools\":[{\"name\":\"hosts_list\"},{\"name\":\"host_exec\"}]}}");
    else {
        assert(strstr(req,"hosts_list")!=NULL);
        snprintf(buf,sizeof(buf),"{\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"structuredContent\":{\"host_id\":\"mock\"}}}",id);
    }
    *n=strlen(buf);assert(*n<=cap);memcpy(out,buf,*n);*status=200;return 0;
}
static int generate(void* opaque,const char* req,size_t len,Sb* reply){
    Mock* m=opaque;int turn=++m->generations;
    JNode p[512];ChatRequest cr;const char* err=NULL;
    assert(api_chat_parse(req,len,p,512,&cr,&err)==0);
    assert(cr.n_tools==1&&cr.parallel_tool_calls==0&&!cr.stream);
    assert(!strstr(req,"host_exec"));
    if(m->mode==3){m->cancelled=1;return -1;}
    if(turn==1||m->mode==2){
        ApiToolCall call={0};
        strcpy(call.id,"call_1");
        strcpy(call.name,m->mode==1?"host_exec":"sentinel_hosts_list");
        sb_init(&call.arguments);sb_str(&call.arguments,"{}");
        api_json_completion(reply,"cmpl","Qwen",0,"",0,"",0,&call,1,
                            m->mode==4?"length":"tool_calls",10,10,0);
        sb_free(&call.arguments);
    }else{
        assert(strstr(req,"\"role\":\"tool\"")&&strstr(req,"mock"));
        api_json_completion(reply,"cmpl","Qwen",0,"",0,"Host mock",9,NULL,0,"stop",10,10,0);
    }
    return 0;
}
static int cancelled(void* opaque){return ((Mock*)opaque)->cancelled;}
static void run(int mode,int expected,int posts,int gens){
    Mock mock={0};mock.mode=mode;
    McpClient client;assert(!mcp_client_open(&client,post,&mock));
    Sb answer;int rc=mcp_agent_run(&client,"List allowed hosts",generate,cancelled,&mock,&answer);
    assert((rc==0)==expected);
    assert(mock.posts==posts&&mock.generations==gens);
    if(expected)assert(answer.p&&!strcmp(answer.p,"Host mock"));
    else assert(!answer.n);
    sb_free(&answer);
}
int main(void){
    run(0,1,4,2);  /* full model -> tool -> result -> model */
    run(1,0,3,1);  /* disallowed tool never sent */
    run(2,0,11,9); /* 8 calls then fail closed */
    run(3,0,3,1);  /* cancel before dispatch */
    run(4,0,3,1);  /* incomplete tool call not sent */
    puts("mcp_agent: 5/5 PASS (mock inference and MCP)");
    return 0;
}
