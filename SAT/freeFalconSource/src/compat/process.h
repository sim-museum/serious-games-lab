/*
 * FreeFalcon Linux Port - process.h compatibility
 *
 * Windows process functions replacement
 */

#ifndef FF_COMPAT_PROCESS_H
#define FF_COMPAT_PROCESS_H

#ifdef FF_LINUX

#include <pthread.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Process ID */
#define _getpid()       getpid()

/* Thread creation - _beginthread style */
typedef void (*_beginthread_proc_t)(void*);

static inline uintptr_t _beginthread(_beginthread_proc_t func, unsigned stack_size, void* arglist) {
    pthread_t thread;
    pthread_attr_t attr;

    (void)stack_size; /* Stack size hint ignored on Linux */

    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);

    if (pthread_create(&thread, &attr, (void*(*)(void*))func, arglist) != 0) {
        pthread_attr_destroy(&attr);
        return (uintptr_t)-1;
    }

    pthread_attr_destroy(&attr);
    return (uintptr_t)thread;
}

static inline void _endthread(void) {
    pthread_exit(NULL);
}

/* Thread creation - _beginthreadex style (more control) */
typedef unsigned (*_beginthreadex_proc_t)(void*);

/* Detached thread handle sentinel - CloseHandle recognizes this type and does nothing */
#define FF_HANDLE_TYPE_DETACHED_THREAD 0xDEAD0002

typedef struct {
    unsigned int type;  /* Set to FF_HANDLE_TYPE_DETACHED_THREAD */
    pthread_t thread;
} FF_DETACHED_THREAD_HANDLE;

static inline uintptr_t _beginthreadex(
    void* security,
    unsigned stack_size,
    _beginthreadex_proc_t start_address,
    void* arglist,
    unsigned initflag,
    unsigned* thrdaddr)
{
    (void)security;   /* Security not supported on Linux */
    (void)stack_size; /* Stack size hint ignored */
    (void)initflag;   /* Init flags not supported */

    /* Allocate handle so CloseHandle can properly identify and free it */
    FF_DETACHED_THREAD_HANDLE* h = (FF_DETACHED_THREAD_HANDLE*)malloc(sizeof(FF_DETACHED_THREAD_HANDLE));
    if (!h) return 0;

    h->type = FF_HANDLE_TYPE_DETACHED_THREAD;

    pthread_attr_t attr;
    pthread_attr_init(&attr);
    /* Detach the thread since caller will call CloseHandle to "close" it */
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);

    if (pthread_create(&h->thread, &attr, (void*(*)(void*))start_address, arglist) != 0) {
        pthread_attr_destroy(&attr);
        free(h);
        return 0;
    }

    pthread_attr_destroy(&attr);

    if (thrdaddr) {
        *thrdaddr = (unsigned)(uintptr_t)h->thread;
    }

    return (uintptr_t)h;
}

static inline void _endthreadex(unsigned retval) {
    (void)retval;
    pthread_exit(NULL);
}

/* Process spawning - stubs */
#define _P_WAIT     0
#define _P_NOWAIT   1
#define _P_OVERLAY  2
#define _P_NOWAITO  3
#define _P_DETACH   4

static inline intptr_t _spawnl(int mode, const char* cmdname, const char* arg0, ...) {
    (void)mode; (void)cmdname; (void)arg0;
    return -1; /* Not implemented */
}

static inline intptr_t _spawnlp(int mode, const char* cmdname, const char* arg0, ...) {
    (void)mode; (void)cmdname; (void)arg0;
    return -1; /* Not implemented */
}

/* Exec functions */
#define _execl      execl
#define _execle     execle
#define _execlp     execlp
#define _execlpe    execlpe
#define _execv      execv
#define _execve     execve
#define _execvp     execvp
#define _execvpe    execvpe

/* System */
#define _system     system

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_PROCESS_H */
