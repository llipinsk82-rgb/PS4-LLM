/* Test policy and cleanup with a fake SceHttp implementation, no network. */
#include "mcp_https.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#undef NDEBUG
#include <assert.h>
static int tls_fail,redirect_stuck,send_fail,read_fail,status_code,sends,deletes,auth_seen;
static size_t read_at;
static const char* payload;
static void reset(void) {
    tls_fail=redirect_stuck=send_fail=read_fail=sends=deletes=auth_seen=0;
    status_code=200;read_at=0;payload="{}";
}
int32_t sceHttpCreateTemplate(int32_t id,const char* ua,int32_t version,int32_t proxy) {
    assert(id==1 && ua && version==2 && !proxy);return 10;
}
int32_t sceHttpsEnableOption(int32_t id,uint32_t flags) {
    assert(id==10 && flags==0xbdu);return tls_fail?-1:0;
}
int32_t sceHttpSetAutoRedirect(int32_t id,int32_t enable){assert(id==10&&!enable);return 0;}
int32_t sceHttpGetAutoRedirect(int32_t id,int32_t* enable){assert(id==10);*enable=redirect_stuck;return 0;}
int32_t sceHttpSetResolveRetry(int32_t id,int32_t retry){assert(id==10&&!retry);return 0;}
int32_t sceHttpSetResolveTimeOut(int32_t id,uint32_t n){assert(id==10&&n==3000000);return 0;}
int32_t sceHttpSetConnectTimeOut(int32_t id,uint32_t n){return sceHttpSetResolveTimeOut(id,n);}
int32_t sceHttpSetSendTimeOut(int32_t id,uint32_t n){return sceHttpSetResolveTimeOut(id,n);}
int32_t sceHttpSetRecvTimeOut(int32_t id,uint32_t n){return sceHttpSetResolveTimeOut(id,n);}
int32_t sceHttpCreateConnection(int32_t id,const char* host,const char* scheme,uint16_t port,int32_t keep){
    assert(id==10&&!strcmp(host,"test.example")&&!strcmp(scheme,"https")&&port==443&&!keep);return 11;
}
int32_t sceHttpCreateRequest(int32_t id,int32_t method,const char* path,uint64_t len){
    assert(id==11&&method==1&&!strcmp(path,"/mcp")&&len==2);return 12;
}
int32_t sceHttpAddRequestHeader(int32_t id,const char* name,const char* value,int32_t mode) {
    assert(id==12&&name&&value&&!mode);
    if(!strcmp(name,"Authorization")){assert(!strcmp(value,"Bearer test-token"));auth_seen++;}
    return 0;
}
int32_t sceHttpSendRequest(int32_t id,const void* body,size_t len){
    assert(id==12&&len==2&&!memcmp(body,"{}",2));sends++;return send_fail?-1:0;
}
int32_t sceHttpGetStatusCode(int32_t id,int32_t* status){assert(id==12);*status=status_code;return 0;}
int32_t sceHttpReadData(int32_t id,void* dest,uint32_t cap){
    assert(id==12&&cap);if(read_fail)return -1;
    size_t n=strlen(payload)-read_at;if(n>cap)n=cap;
    memcpy(dest,payload+read_at,n);read_at+=n;return (int32_t)n;
}
int32_t sceHttpDeleteRequest(int32_t id){assert(id==12);deletes++;return 0;}
int32_t sceHttpDeleteConnection(int32_t id){assert(id==11);deletes++;return 0;}
int32_t sceHttpDeleteTemplate(int32_t id){assert(id==10);deletes++;return 0;}
int main(void){
    McpHttps cfg={1,"test.example","test-token"};
    char output[8];size_t n;int status;
    assert(mcp_https_config_valid(&cfg));
    const char* invalid[]={"http://test.example","test.example:443","test.example/mcp","test.example@evil.com","test..example","-test.example","test-.example","127.0.0.1","test.example\n"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(*invalid);i++){
        cfg.host=invalid[i];assert(!mcp_https_config_valid(&cfg));
    }
    cfg.host="test.example";cfg.bearer="token\r\nX-Fake: 1";assert(!mcp_https_config_valid(&cfg));cfg.bearer="test-token";
    reset();assert(!mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(n==2&&status==200&&auth_seen==1&&sends==1&&deletes==3);
    reset();tls_fail=1;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(!sends&&deletes==1&&!n&&!status);
    reset();redirect_stuck=1;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(!sends&&deletes==1);
    reset();status_code=302;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(sends==1&&deletes==3);
    reset();send_fail=1;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(deletes==3);
    reset();read_fail=1;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(deletes==3);
    reset();payload="123456789";assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(!n&&!status&&deletes==3);
    reset();payload="12345678";assert(!mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(n==8&&deletes==3);
    reset();status_code=202;payload="";assert(!mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(!n&&status==202&&deletes==3);
    reset();status_code=202;assert(mcp_https_post(&cfg,"{}",2,output,sizeof(output),&n,&status));assert(!n&&!status&&deletes==3);
    puts("MCP HTTPS policy and cleanup: PASS (mock SceHttp only)");return 0;
}
