/* Minimal host-test stub, not a PS4 SDK replacement. */
#ifndef MCP_TEST_HTTP_H
#define MCP_TEST_HTTP_H
#include <stdint.h>
#include <stddef.h>
enum { ORBIS_HTTP_VERSION_1_1=2, ORBIS_METHOD_POST=1 };
int32_t sceHttpCreateTemplate(int32_t,const char*,int32_t,int32_t);
int32_t sceHttpsEnableOption(int32_t,uint32_t);
void sceHttpSetAutoRedirect(void);
void sceHttpSetRecvTimeOut(void);
void sceHttpSetResolveRetry(void);
int32_t sceHttpGetAutoRedirect(int32_t,int32_t*);
int32_t sceHttpSetResolveTimeOut(int32_t,uint32_t);
int32_t sceHttpSetConnectTimeOut(int32_t,uint32_t);
int32_t sceHttpSetSendTimeOut(int32_t,uint32_t);
int32_t sceHttpCreateConnection(int32_t,const char*,const char*,uint16_t,int32_t);
int32_t sceHttpCreateRequest(int32_t,int32_t,const char*,uint64_t);
int32_t sceHttpAddRequestHeader(int32_t,const char*,const char*,int32_t);
int32_t sceHttpSendRequest(int32_t,const void*,size_t);
int32_t sceHttpGetStatusCode(int32_t,int32_t*);
int32_t sceHttpReadData(int32_t,void*,uint32_t);
int32_t sceHttpDeleteRequest(int32_t);
int32_t sceHttpDeleteConnection(int32_t);
int32_t sceHttpDeleteTemplate(int32_t);
#endif
