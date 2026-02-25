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
