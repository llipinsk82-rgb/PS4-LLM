// OpenAI-compatible HTTP API, server part on the console (see api.h). One thread accepts the connections and
// reads their requests; the chat requests go to the main loop one at a time (api_run.inc), which owns the model.
// The sockets are the console's sceNet calls, declared here as the OpenOrbis headers do not have them all.
// Nothing here runs until api_enable(1): no network library, no socket, no thread.
//
// A client may go away in the middle of a reply (a stopped generation, a closed tab). The next send to that
// connection would then raise SIGPIPE, which ends the whole app by default. The signal is ignored (no_sigpipe) and
// the sockets are marked SO_NOSIGPIPE, so the send fails instead and only that reply ends.
#include "api.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <orbis/Net.h>
#include <orbis/Sysmodule.h>
#include <orbis/libkernel.h>

#include "api_proto.h"
#include "ui.h"

#define API_ASSETS "/app0/assets"
#define API_KEY_FILE "/data/garlic_api_key.txt"   // optional: if it holds a key, requests need "Authorization: Bearer <key>"
#define API_DRAIN (16 << 20)      // the most of a refused body that is read and dropped (see drain)

// Socket constants that the SDK's headers do not name (the BSD values the console's libSceNet uses)
#define API_SOL_SOCKET 0xffff
#define API_SO_REUSEADDR 0x0004
#define API_SO_NOSIGPIPE 0x0800
#define API_SO_RCVTIMEO 0x1006
#define API_SO_SNDTIMEO 0x1005
#define API_IPPROTO_TCP 6
#define API_IPPROTO_UDP 17
#define API_SIGPIPE 13

int _sigaction(int sig, const void* act, void* old);   // (libkernel: FreeBSD's sigaction; the headers leave it out)

typedef struct {                // the BSD sockaddr_in: 16 bytes, the same size as OrbisNetSockaddr
    uint8_t len, family;
    uint16_t port;              // network byte order
    uint32_t addr;
    char zero[8];
} ApiSockaddrIn;
_Static_assert(sizeof(ApiSockaddrIn) == sizeof(OrbisNetSockaddr), "sockaddr size");

#define API_QUEUE 8               // chat requests that may wait for the model, the one being answered included

static OrbisPthreadMutex api_mu;
static ApiJob *queue_head, *queue_tail;   // waiting for the main loop, oldest first
static int jobs;                // chat jobs queued or being answered (api_done counts one off)
static int answering;           // the main loop is answering one of them (api_take to api_done)
static volatile int console_busy;   // the console itself is using the model (api_console_busy)
static char model_name[64] = "Garlic";
static int context_length = 16384;
static char* key;               // the API key, or NULL
static OrbisPthread api_th;
static int ready, have_thread;  // the network library, the mutex and the key are set up (once); the thread exists
static volatile int on;         // the API is on: connections are served
static OrbisNetId listen_fd = -1;   // the listening socket (changes under api_mu)
static volatile int accepting;  // the server thread is waiting for a connection on it (in sceNetAccept)
static char address[32];        // api_address()

void api_set_model(const char* name) {
    snprintf(model_name, sizeof(model_name), "%s", name);
}

const char* api_model(void) { return model_name; }

void api_set_context(int tokens) { context_length = tokens; }

int api_send(int fd, const char* p, size_t n) {
    while (n) {
        int w = sceNetSend(fd, p, n, 0);
        if (w <= 0) return -1;
        p += w;
        n -= (size_t)w;
    }
    return 0;
}

int api_client_gone(int fd) {
    char c;   // (MSG_PEEK | MSG_DONTWAIT: 0 means the client closed the connection; nothing is taken from it)
    return sceNetRecv(fd, &c, 1, 0x02 | 0x80) == 0;
}

static void reply(int fd, int status, const char* reason, const char* ctype, const char* body, size_t n) {
    char head[512];
    int h = snprintf(head, sizeof(head),
                     "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %zu\r\n"
                     "Access-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n",
                     status, reason, ctype, n);
    if (api_send(fd, head, h) == 0) api_send(fd, body, n);
}

static void reply_json_error(int fd, int status, const char* reason, const char* message, const char* type,
                             const char* code) {
    Sb s;
    sb_init(&s);
    api_json_error(&s, message, type, code);
    reply(fd, status, reason, "application/json", s.p, s.n);
    sb_free(&s);
}

ApiJob* api_take(void) {
    if (!ready) return NULL;   // (the API was never turned on)
    scePthreadMutexLock(&api_mu);
    ApiJob* j = queue_head;
    if (j) {
        queue_head = j->next;
        if (!queue_head) queue_tail = NULL;
        j->next = NULL;
        answering = 1;
    }
    scePthreadMutexUnlock(&api_mu);
    return j;
}

void api_done(ApiJob* job) {
    sceNetSocketClose(job->fd);
    free(job->body);
    free(job);
    scePthreadMutexLock(&api_mu);
    jobs--;
    answering = 0;
    scePthreadMutexUnlock(&api_mu);
}

void api_console_busy(int busy) { console_busy = busy; }

// GET /health: up, and whether a request sent now would wait (the model is answering one, or the console uses it).
static void reply_health(int fd) {
    int waiting = 0, busy = console_busy;
    if (ready) {
        scePthreadMutexLock(&api_mu);
        waiting = jobs - answering;
        busy |= answering || waiting > 0;
        scePthreadMutexUnlock(&api_mu);
    }
    Sb s;
    sb_init(&s);
    api_json_health(&s, busy, waiting);
    reply(fd, 200, "OK", "application/json", s.p, s.n);
    sb_free(&s);
}

// the header value of Authorization must be "Bearer <key>"
static int authorized(const HttpRequest* r) {
    if (!key) return 1;
    size_t k = strlen(key);
    return strncmp(r->auth, "Bearer ", 7) == 0 && strlen(r->auth + 7) == k && !memcmp(r->auth + 7, key, k);
}

// Reads one request. Returns 1 when it is whole (its body points into *buf_out, to free once the reply is written),
// 0 if the client stopped sending before its end, -1 if it is malformed, or -2 if its body is over API_MAX_BODY.
// *len_out: the bytes read.
static int read_request(int fd, char** buf_out, size_t* len_out, HttpRequest* req) {
    size_t cap = 16384, len = 0;
    char* buf = malloc(cap);
    *len_out = 0;
    if (!buf) return -1;
    int r = 0;
    for (;;) {
        if (len == cap) {   // twice the room, or once the head is whole the request's own size (not twice 1 MiB)
            size_t want = cap * 2, whole = req->head_len + (size_t)req->content_length;
            if (req->head_len && whole > cap && whole < want) want = whole;
            if (cap >= API_MAX_BODY + 16384) break;
            char* nb = realloc(buf, want);
            if (!nb) break;
            buf = nb;
            cap = want;
        }
        int n = sceNetRecv(fd, buf + len, cap - len, 0);
        if (n <= 0) break;
        len += (size_t)n;
        r = api_http_parse(buf, len, req);
        if (r != 0) break;
    }
    *len_out = len;
    if (r == 1) {   // the body points into buf: keep the buffer until the reply is written
        *buf_out = buf;
        return 1;
    }
    free(buf);
    return r;
}

// Reads and drops the rest of a refused body (up to API_DRAIN bytes), so that the client reads the answer: a socket
// closed with bytes it has not read is reset, and the answer may be lost with it.
static void drain(int fd, long left) {
    char tmp[4096];
    if (left > API_DRAIN) left = API_DRAIN;
    while (left > 0) {
        int n = sceNetRecv(fd, tmp, left < (long)sizeof(tmp) ? (size_t)left : sizeof(tmp), 0);
        if (n <= 0) break;
        left -= n;
    }
}

// Queues a chat request for the main loop. Returns 1 if the main loop now owns fd (api_done closes it), or 0 if the
// request was answered here (malformed, out of memory, or another one is being answered) and fd is still ours.
static int serve_chat(int fd, HttpRequest* req) {
    ChatRequest cr;
    const char* err = NULL;
    JNode* pool = api_chat_parse_pool(req->body, req->body_len, &cr, &err);   // (read only to check it)
    if (!pool) {
        say("api: request refused (%zu bytes): %s", req->body_len, err ? err : "out of memory");
        if (err) reply_json_error(fd, 400, "Bad Request", err, "invalid_request_error", "invalid_body");
        else reply_json_error(fd, 500, "Internal Server Error", "Out of memory.", "server_error", NULL);
        return 0;
    }
    free(pool);
    ApiJob* job = calloc(1, sizeof(ApiJob));
    char* body = malloc(req->body_len + 1);
    if (!job || !body) {
        free(job);
        free(body);
        reply_json_error(fd, 500, "Internal Server Error", "Out of memory.", "server_error", NULL);
        return 0;
    }
    memcpy(body, req->body, req->body_len);
    body[req->body_len] = 0;
    job->fd = fd;
    job->body = body;
    job->body_len = req->body_len;
    scePthreadMutexLock(&api_mu);
    int ahead = jobs, full = jobs >= API_QUEUE;
    if (!full) {   // (at the end of the line: the requests are answered in the order they came)
        jobs++;
        if (queue_tail) queue_tail->next = job;
        else queue_head = job;
        queue_tail = job;
    }
    scePthreadMutexUnlock(&api_mu);
    if (full) {
        free(body);
        free(job);
        reply_json_error(fd, 503, "Service Unavailable", "Too many requests are waiting for the model.",
                         "server_error", "busy");
        return 0;
    }
    say("api: chat request, %zu bytes, %s, %d ahead of it", req->body_len, cr.stream ? "streamed" : "whole reply", ahead);
    return 1;   // (the main loop writes the reply to fd and closes it)
}

// Answers one connection. Returns 1 if fd went to the main loop with a chat job, 0 if the caller closes it.
static int handle(int fd) {
    struct {
        long sec, usec;
    } tmo = {20, 0};
    sceNetSetsockopt(fd, API_SOL_SOCKET, API_SO_RCVTIMEO, &tmo, sizeof(tmo));
    sceNetSetsockopt(fd, API_SOL_SOCKET, API_SO_SNDTIMEO, &tmo, sizeof(tmo));
    int one = 1;   // (accepted sockets inherit it from the listening one; set again in case they do not)
    sceNetSetsockopt(fd, API_SOL_SOCKET, API_SO_NOSIGPIPE, &one, sizeof(one));
    char* buf = NULL;
    size_t len = 0;
    HttpRequest req;
    int r = read_request(fd, &buf, &len, &req);
    if (r == -2) {
        say("api: request refused: a body of %ld bytes, over %d", req.content_length, API_MAX_BODY);
        reply_json_error(fd, 413, "Payload Too Large", "The request body is larger than 1 MiB, the most the API reads.",
                         "invalid_request_error", "request_too_large");
        drain(fd, req.content_length - (long)(len - req.head_len));
        return 0;
    }
    if (r == 0 && len == 0) return 0;   // (a connection that sent nothing: a browser's spare one, a port check)
    if (r != 1) {   // malformed, or cut off before the end
        say("api: %s request (%zu bytes read)", r ? "malformed" : "incomplete", len);
        reply_json_error(fd, 400, "Bad Request", "Malformed or incomplete request.", "invalid_request_error", NULL);
        return 0;
    }
    if (!strcmp(req.method, "OPTIONS")) {
        // A browser asks first. "*" lets it send any header an OpenAI client library adds; Authorization must be named
        // (the wildcard does not cover it). Private-Network: a page on the internet may reach the console's address.
        const char* h = "HTTP/1.1 204 No Content\r\nAccess-Control-Allow-Origin: *\r\n"
                        "Access-Control-Allow-Headers: Authorization, Content-Type, *\r\n"
                        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                        "Access-Control-Allow-Private-Network: true\r\nAccess-Control-Max-Age: 86400\r\n"
                        "Content-Length: 0\r\nConnection: close\r\n\r\n";
        api_send(fd, h, strlen(h));
    } else if (!strcmp(req.method, "GET") && !strcmp(req.path, "/health")) {   // (no key needed, as documented)
        reply_health(fd);
    } else if (!strcmp(req.method, "GET") && (!strcmp(req.path, "/openapi.json") || !strcmp(req.path, "/"))) {
        size_t n = 0;   // (no key needed either: the description is the same on every console)
        uint8_t* spec = read_all(API_ASSETS "/openapi.json", &n);
        if (spec) reply(fd, 200, "OK", "application/json", (const char*)spec, n);
        else reply_json_error(fd, 404, "Not Found", "The API description is missing.", "invalid_request_error", NULL);
        free(spec);
    } else if (!authorized(&req)) {
        say("api: request refused: %s API key (%s %s)", req.auth[0] ? "wrong" : "no", req.method, req.path);
        reply_json_error(fd, 401, "Unauthorized", "Missing or wrong API key.", "invalid_request_error",
                         "invalid_api_key");
    } else if (!strcmp(req.method, "GET") && (!strcmp(req.path, "/v1/models") || !strcmp(req.path, "/models"))) {
        Sb s;
        sb_init(&s);
        api_json_models(&s, model_name, 0, context_length);
        reply(fd, 200, "OK", "application/json", s.p, s.n);
        sb_free(&s);
    } else if (!strcmp(req.method, "GET") && !strncmp(req.path, "/v1/models/", 11)) {   // (one model, by its id)
        Sb s;
        sb_init(&s);
        if (!strcmp(req.path + 11, model_name)) {
            api_json_model(&s, model_name, 0, context_length);
            reply(fd, 200, "OK", "application/json", s.p, s.n);
        } else {
            api_json_error(&s, "The console runs one model; see GET /v1/models.", "invalid_request_error",
                           "model_not_found");
            reply(fd, 404, "Not Found", "application/json", s.p, s.n);
        }
        sb_free(&s);
    } else if (!strcmp(req.method, "POST") && !strcmp(req.path, "/v1/chat/completions")) {
        int queued_it = serve_chat(fd, &req);   // (the job has its own copy of the body)
        free(buf);
        return queued_it;
    } else {
        say("api: no such endpoint: %s %s", req.method, req.path);
        reply_json_error(fd, 404, "Not Found", "No such endpoint.", "invalid_request_error", NULL);
    }
    free(buf);
    return 0;
}

// The API is off: its port is closed, unless the server thread is waiting on the socket (then the thread closes it
// when its wait ends). The socket is never closed under a thread that is using it.
static void close_if_off(void) {
    scePthreadMutexLock(&api_mu);
    if (!on && !accepting && listen_fd >= 0) {
        sceNetSocketClose(listen_fd);
        listen_fd = -1;
    }
    scePthreadMutexUnlock(&api_mu);
}

static void* api_main(void* arg) {
    (void)arg;
    for (;;) {
        scePthreadMutexLock(&api_mu);
        OrbisNetId l = on ? listen_fd : -1;
        accepting = l >= 0;
        scePthreadMutexUnlock(&api_mu);
        if (l < 0) {   // the API is off: nothing to wait for
            sceKernelUsleep(100000);
            continue;
        }
        ApiSockaddrIn peer;
        OrbisNetSocklen_t plen = sizeof(peer);
        int fd = sceNetAccept(l, (OrbisNetSockaddr*)&peer, &plen);
        accepting = 0;
        // (a connection that came in after the API was turned off gets no answer; one with a chat job now belongs
        // to the main loop, which closes it in api_done)
        if (fd >= 0 && !(on && handle(fd))) sceNetSocketClose(fd);
        close_if_off();
        if (fd < 0) sceKernelUsleep(100000);   // (an error, or api_enable ended the wait to turn the API off)
    }
    return NULL;
}

// SIGPIPE ignored for the whole app (see the top of this file). FreeBSD's struct sigaction: the handler (SIG_IGN
// is 1), no flags, an empty mask; the zeros after it cover a longer layout too.
static void no_sigpipe(void) {
    uint64_t act[20] = {1};
    int r = _sigaction(API_SIGPIPE, act, NULL);
    say("api: SIGPIPE %s (%d)", r ? "not ignored" : "ignored", r);
}

// The network library (as the SDK's net_http sample starts it), the mutex and the optional key: once, the first
// time the API is turned on.
static int api_setup(void) {
    if (ready) return 0;
    int r = sceSysmoduleLoadModuleInternal(ORBIS_SYSMODULE_INTERNAL_NET);
    if (r < 0) {
        say("api: network module 0x%08X; the API stays off", r);
        return -1;
    }
    r = sceNetInit();
    if (r < 0) {
        say("api: sceNetInit 0x%08X; the API stays off", r);
        return -1;
    }
    no_sigpipe();
    scePthreadMutexInit(&api_mu, NULL, "garlic_api");
    size_t n = 0;
    uint8_t* kd = read_all(API_KEY_FILE, &n);
    if (kd) {
        while (n && (kd[n - 1] == '\n' || kd[n - 1] == '\r' || kd[n - 1] == ' ')) n--;
        if (n) {
            key = malloc(n + 1);
            if (key) {
                memcpy(key, kd, n);
                key[n] = 0;
            }
        }
        free(kd);
    }
    ready = 1;
    return 0;
}

// A socket listening on API_PORT, on any of the console's addresses; -1 if it cannot (logged).
static OrbisNetId api_listen(void) {
    OrbisNetId s = sceNetSocket("garlic_api", ORBIS_NET_AF_INET, ORBIS_NET_SOCK_STREAM, API_IPPROTO_TCP);
    if (s < 0) {
        say("api: no socket (%d); the API stays off", s);
        return -1;
    }
    int one = 1;
    sceNetSetsockopt(s, API_SOL_SOCKET, API_SO_REUSEADDR, &one, sizeof(one));
    int r = sceNetSetsockopt(s, API_SOL_SOCKET, API_SO_NOSIGPIPE, &one, sizeof(one));
    if (r < 0) say("api: SO_NOSIGPIPE refused (0x%08X)", (unsigned)r);
    ApiSockaddrIn a;
    memset(&a, 0, sizeof(a));
    a.len = sizeof(a);
    a.family = ORBIS_NET_AF_INET;
    a.port = sceNetHtons(API_PORT);
    a.addr = 0;   // any address
    if (sceNetBind(s, (const OrbisNetSockaddr*)&a, sizeof(a)) || sceNetListen(s, 4)) {
        say("api: cannot listen on port %d; the API stays off", API_PORT);
        sceNetSocketClose(s);
        return -1;
    }
    return s;
}

// The console's address on the network, for the screen: the one the system would send from to reach another
// network. Connecting a UDP socket only makes the system choose that address; nothing is sent. Without a network
// the address stays ":8080".
static void find_address(void) {
    snprintf(address, sizeof(address), ":%d", API_PORT);
    OrbisNetId s = sceNetSocket("garlic_api_addr", ORBIS_NET_AF_INET, ORBIS_NET_SOCK_DGRAM, API_IPPROTO_UDP);
    if (s < 0) return;
    static const uint8_t far[4] = {192, 0, 2, 1};   // (an address reserved for documentation: never a real host)
    ApiSockaddrIn a;
    memset(&a, 0, sizeof(a));
    a.len = sizeof(a);
    a.family = ORBIS_NET_AF_INET;
    a.port = sceNetHtons(9);
    memcpy(&a.addr, far, 4);
    OrbisNetSocklen_t len = sizeof(a);
    if (sceNetConnect(s, (const OrbisNetSockaddr*)&a, sizeof(a)) == 0 &&
        sceNetGetsockname(s, (OrbisNetSockaddr*)&a, &len) == 0 && a.addr) {
        const uint8_t* b = (const uint8_t*)&a.addr;   // (network byte order: the bytes as they are written)
        snprintf(address, sizeof(address), "%u.%u.%u.%u:%d", b[0], b[1], b[2], b[3], API_PORT);
    }
    sceNetSocketClose(s);
}

int api_enabled(void) { return on; }

const char* api_address(void) { return address; }

int api_enable(int want) {
    if (!want) {
        if (!on) return 0;
        scePthreadMutexLock(&api_mu);
        OrbisNetId l = listen_fd;
        on = 0;
        scePthreadMutexUnlock(&api_mu);
        // the server thread leaves its wait for a connection, and the port is closed (close_if_off)
        if (l >= 0) sceNetSocketAbort(l, 0);
        for (int i = 0; i < 40 && accepting; i++) sceKernelUsleep(5000);
        close_if_off();
        say("api: off");
        return 0;
    }
    if (on) return 0;
    if (api_setup()) return -1;
    scePthreadMutexLock(&api_mu);
    int l = listen_fd;   // (still open only if the server thread has been waiting on it since the API went off)
    if (l < 0) l = listen_fd = api_listen();
    if (l >= 0) on = 1;
    scePthreadMutexUnlock(&api_mu);
    if (l < 0) return -1;
    if (!have_thread) {
        OrbisPthreadAttr attr;
        scePthreadAttrInit(&attr);
        scePthreadAttrSetstacksize(&attr, 256 << 10);
        if (scePthreadCreate(&api_th, &attr, api_main, NULL, "garlic_api")) {
            say("api: no thread; the API stays off");
            on = 0;
            close_if_off();
            return -1;
        }
        have_thread = 1;
    }
    find_address();
    say("api: OpenAI-compatible API on %s%s", address, key ? " (API key required)" : "");
    return 0;
}
