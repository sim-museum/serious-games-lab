/*
 * FreeFalcon Linux Port - winbase.h compatibility
 *
 * Windows kernel function stubs and implementations.
 */

#ifndef FF_COMPAT_WINBASE_H
#define FF_COMPAT_WINBASE_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <pthread.h>
#include <time.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <dlfcn.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declaration for case-insensitive file lookup (defined in linux_stubs.cpp) */
int open_nocase(const char* filepath, int flags, int mode);

/* ============================================================
 * Error Handling
 * ============================================================ */

/* Thread-local error code */
static __thread DWORD ff_last_error = 0;

static inline void SetLastError(DWORD dwErrCode) {
    ff_last_error = dwErrCode;
}

static inline DWORD GetLastError(void) {
    return ff_last_error;
}

/* Error codes */
#define ERROR_SUCCESS           0
#define ERROR_INVALID_FUNCTION  1
#define ERROR_FILE_NOT_FOUND    2
#define ERROR_PATH_NOT_FOUND    3
#define ERROR_ACCESS_DENIED     5
#define ERROR_INVALID_HANDLE    6
#define ERROR_NOT_ENOUGH_MEMORY 8
#define ERROR_INVALID_DATA      13
#define ERROR_OUTOFMEMORY       14
#define ERROR_INVALID_PARAMETER 87
#define ERROR_INSUFFICIENT_BUFFER 122
#define ERROR_ALREADY_EXISTS    183
#define ERROR_MORE_DATA         234
#define ERROR_NO_MORE_ITEMS     259
#define ERROR_TIMEOUT           1460

/* Language IDs for FormatMessage */
#define LANG_NEUTRAL            0x00
#define SUBLANG_DEFAULT         0x01
#define MAKELANGID(p, s)        ((((WORD)(s)) << 10) | (WORD)(p))

/* FormatMessage flags */
#define FORMAT_MESSAGE_ALLOCATE_BUFFER  0x00000100
#define FORMAT_MESSAGE_ARGUMENT_ARRAY   0x00002000
#define FORMAT_MESSAGE_FROM_HMODULE     0x00000800
#define FORMAT_MESSAGE_FROM_STRING      0x00000400
#define FORMAT_MESSAGE_FROM_SYSTEM      0x00001000
#define FORMAT_MESSAGE_IGNORE_INSERTS   0x00000200

/* FormatMessage - stub implementation */
static inline DWORD FormatMessageA(DWORD dwFlags, LPCVOID lpSource, DWORD dwMessageId,
                                   DWORD dwLanguageId, LPSTR lpBuffer, DWORD nSize, void* Arguments) {
    (void)dwFlags; (void)lpSource; (void)dwMessageId; (void)dwLanguageId; (void)Arguments;
    if (lpBuffer && nSize > 0) {
        snprintf(lpBuffer, nSize, "Error code: 0x%08X", dwMessageId);
        return (DWORD)strlen(lpBuffer);
    }
    return 0;
}
#define FormatMessage FormatMessageA

#define WAIT_FAILED             ((DWORD)0xFFFFFFFF)
#define WAIT_OBJECT_0           ((DWORD)0x00000000)
#define WAIT_ABANDONED          ((DWORD)0x00000080)
#define WAIT_TIMEOUT            ((DWORD)0x00000102)
#define INFINITE                ((DWORD)0xFFFFFFFF)

/* Drive types */
#define DRIVE_UNKNOWN           0
#define DRIVE_NO_ROOT_DIR       1
#define DRIVE_REMOVABLE         2
#define DRIVE_FIXED             3
#define DRIVE_REMOTE            4
#define DRIVE_CDROM             5
#define DRIVE_RAMDISK           6

/* Volume/Drive functions - stubs */
static inline DWORD GetLogicalDrives(void) {
    return 0x4; /* Only C: drive (bit 2) on Linux */
}

static inline UINT GetDriveType(LPCSTR lpRootPathName) {
    (void)lpRootPathName;
    return DRIVE_FIXED; /* Everything is a fixed drive on Linux */
}

static inline BOOL GetVolumeInformation(
    LPCSTR lpRootPathName,
    LPSTR lpVolumeNameBuffer,
    DWORD nVolumeNameSize,
    LPDWORD lpVolumeSerialNumber,
    LPDWORD lpMaximumComponentLength,
    LPDWORD lpFileSystemFlags,
    LPSTR lpFileSystemNameBuffer,
    DWORD nFileSystemNameSize
) {
    (void)lpRootPathName;
    if (lpVolumeNameBuffer && nVolumeNameSize > 0) {
        strncpy(lpVolumeNameBuffer, "Linux", nVolumeNameSize - 1);
        lpVolumeNameBuffer[nVolumeNameSize - 1] = '\0';
    }
    if (lpVolumeSerialNumber) *lpVolumeSerialNumber = 0x12345678;
    if (lpMaximumComponentLength) *lpMaximumComponentLength = 255;
    if (lpFileSystemFlags) *lpFileSystemFlags = 0;
    if (lpFileSystemNameBuffer && nFileSystemNameSize > 0) {
        strncpy(lpFileSystemNameBuffer, "ext4", nFileSystemNameSize - 1);
        lpFileSystemNameBuffer[nFileSystemNameSize - 1] = '\0';
    }
    return TRUE;
}

static inline DWORD GetTempPath(DWORD nBufferLength, LPSTR lpBuffer) {
    const char* tmp = getenv("TMPDIR");
    if (!tmp) tmp = "/tmp";
    size_t len = strlen(tmp);
    if (lpBuffer && nBufferLength > len) {
        strcpy(lpBuffer, tmp);
        if (lpBuffer[len-1] != '/') {
            strcat(lpBuffer, "/");
            len++;
        }
    }
    return (DWORD)len;
}

/* File commit - sync to disk */
#define _commit(fd)     fsync(fd)

/* ============================================================
 * Time Functions
 * ============================================================ */

static inline DWORD GetTickCount(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (DWORD)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

static inline ULONGLONG GetTickCount64(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (ULONGLONG)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

static inline BOOL QueryPerformanceCounter(LARGE_INTEGER* lpPerformanceCount) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    lpPerformanceCount->QuadPart = (LONGLONG)ts.tv_sec * 1000000000LL + ts.tv_nsec;
    return TRUE;
}

static inline BOOL QueryPerformanceFrequency(LARGE_INTEGER* lpFrequency) {
    lpFrequency->QuadPart = 1000000000LL; /* nanoseconds */
    return TRUE;
}

static inline void GetSystemTime(LPSYSTEMTIME lpSystemTime) {
    time_t t = time(NULL);
    struct tm* tm = gmtime(&t);
    lpSystemTime->wYear = tm->tm_year + 1900;
    lpSystemTime->wMonth = tm->tm_mon + 1;
    lpSystemTime->wDayOfWeek = tm->tm_wday;
    lpSystemTime->wDay = tm->tm_mday;
    lpSystemTime->wHour = tm->tm_hour;
    lpSystemTime->wMinute = tm->tm_min;
    lpSystemTime->wSecond = tm->tm_sec;
    lpSystemTime->wMilliseconds = 0;
}

static inline void GetLocalTime(LPSYSTEMTIME lpSystemTime) {
    time_t t = time(NULL);
    struct tm* tm = localtime(&t);
    lpSystemTime->wYear = tm->tm_year + 1900;
    lpSystemTime->wMonth = tm->tm_mon + 1;
    lpSystemTime->wDayOfWeek = tm->tm_wday;
    lpSystemTime->wDay = tm->tm_mday;
    lpSystemTime->wHour = tm->tm_hour;
    lpSystemTime->wMinute = tm->tm_min;
    lpSystemTime->wSecond = tm->tm_sec;
    lpSystemTime->wMilliseconds = 0;
}

/* FILETIME epoch: January 1, 1601. Unix epoch: January 1, 1970.
 * Difference in 100-nanosecond intervals: 116444736000000000ULL */
#define FILETIME_UNIX_DIFF 116444736000000000ULL

static inline void GetSystemTimeAsFileTime(LPFILETIME lpSystemTimeAsFileTime) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    ULONGLONG result = ((ULONGLONG)tv.tv_sec * 10000000ULL) +
                       ((ULONGLONG)tv.tv_usec * 10ULL) +
                       FILETIME_UNIX_DIFF;
    lpSystemTimeAsFileTime->dwLowDateTime = (DWORD)(result & 0xFFFFFFFF);
    lpSystemTimeAsFileTime->dwHighDateTime = (DWORD)(result >> 32);
}

static inline BOOL FileTimeToLocalFileTime(const FILETIME* lpFileTime, LPFILETIME lpLocalFileTime) {
    if (!lpFileTime || !lpLocalFileTime) return FALSE;
    /* On Linux, we adjust for timezone offset */
    time_t now = time(NULL);
    struct tm* local_tm = localtime(&now);
    long tz_offset = local_tm->tm_gmtoff; /* seconds east of UTC */

    ULONGLONG ft = ((ULONGLONG)lpFileTime->dwHighDateTime << 32) | lpFileTime->dwLowDateTime;
    ft += (LONGLONG)tz_offset * 10000000LL; /* Convert seconds to 100-ns intervals */

    lpLocalFileTime->dwLowDateTime = (DWORD)(ft & 0xFFFFFFFF);
    lpLocalFileTime->dwHighDateTime = (DWORD)(ft >> 32);
    return TRUE;
}

static inline BOOL FileTimeToDosDateTime(
    const FILETIME* lpFileTime,
    LPWORD lpFatDate,
    LPWORD lpFatTime)
{
    if (!lpFileTime || !lpFatDate || !lpFatTime) return FALSE;

    /* Convert FILETIME to Unix time */
    ULONGLONG ft = ((ULONGLONG)lpFileTime->dwHighDateTime << 32) | lpFileTime->dwLowDateTime;
    time_t unix_time = (time_t)((ft - FILETIME_UNIX_DIFF) / 10000000ULL);

    struct tm* tm = localtime(&unix_time);
    if (!tm) return FALSE;

    /* DOS date: bits 0-4 = day, bits 5-8 = month, bits 9-15 = year since 1980 */
    *lpFatDate = (WORD)(tm->tm_mday | ((tm->tm_mon + 1) << 5) | ((tm->tm_year - 80) << 9));

    /* DOS time: bits 0-4 = seconds/2, bits 5-10 = minutes, bits 11-15 = hours */
    *lpFatTime = (WORD)((tm->tm_sec / 2) | (tm->tm_min << 5) | (tm->tm_hour << 11));

    return TRUE;
}

static inline BOOL SystemTimeToFileTime(const SYSTEMTIME* lpSystemTime, LPFILETIME lpFileTime) {
    if (!lpSystemTime || !lpFileTime) return FALSE;

    struct tm tm;
    tm.tm_year = lpSystemTime->wYear - 1900;
    tm.tm_mon = lpSystemTime->wMonth - 1;
    tm.tm_mday = lpSystemTime->wDay;
    tm.tm_hour = lpSystemTime->wHour;
    tm.tm_min = lpSystemTime->wMinute;
    tm.tm_sec = lpSystemTime->wSecond;
    tm.tm_isdst = -1;

    time_t t = mktime(&tm);
    if (t == (time_t)-1) return FALSE;

    ULONGLONG ft = ((ULONGLONG)t * 10000000ULL) + FILETIME_UNIX_DIFF +
                   ((ULONGLONG)lpSystemTime->wMilliseconds * 10000ULL);

    lpFileTime->dwLowDateTime = (DWORD)(ft & 0xFFFFFFFF);
    lpFileTime->dwHighDateTime = (DWORD)(ft >> 32);
    return TRUE;
}

static inline BOOL FileTimeToSystemTime(const FILETIME* lpFileTime, LPSYSTEMTIME lpSystemTime) {
    if (!lpFileTime || !lpSystemTime) return FALSE;

    ULONGLONG ft = ((ULONGLONG)lpFileTime->dwHighDateTime << 32) | lpFileTime->dwLowDateTime;
    time_t unix_time = (time_t)((ft - FILETIME_UNIX_DIFF) / 10000000ULL);
    DWORD ms = (DWORD)((ft - FILETIME_UNIX_DIFF) % 10000000ULL) / 10000;

    struct tm* tm = gmtime(&unix_time);
    if (!tm) return FALSE;

    lpSystemTime->wYear = tm->tm_year + 1900;
    lpSystemTime->wMonth = tm->tm_mon + 1;
    lpSystemTime->wDayOfWeek = tm->tm_wday;
    lpSystemTime->wDay = tm->tm_mday;
    lpSystemTime->wHour = tm->tm_hour;
    lpSystemTime->wMinute = tm->tm_min;
    lpSystemTime->wSecond = tm->tm_sec;
    lpSystemTime->wMilliseconds = ms;
    return TRUE;
}

/* ============================================================
 * Critical Section Functions
 * ============================================================ */

/* We store a pthread_mutex_t* in the LockSemaphore field */
static inline void InitializeCriticalSection(LPCRITICAL_SECTION lpCriticalSection) {
    pthread_mutex_t* mutex = (pthread_mutex_t*)malloc(sizeof(pthread_mutex_t));
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(mutex, &attr);
    pthread_mutexattr_destroy(&attr);
    lpCriticalSection->LockSemaphore = (HANDLE)mutex;
    lpCriticalSection->LockCount = -1;
    lpCriticalSection->RecursionCount = 0;
    lpCriticalSection->OwningThread = NULL;
}

static inline BOOL InitializeCriticalSectionAndSpinCount(LPCRITICAL_SECTION lpCriticalSection, DWORD dwSpinCount) {
    InitializeCriticalSection(lpCriticalSection);
    lpCriticalSection->SpinCount = dwSpinCount;
    return TRUE;
}

static inline void DeleteCriticalSection(LPCRITICAL_SECTION lpCriticalSection) {
    if (lpCriticalSection->LockSemaphore) {
        pthread_mutex_destroy((pthread_mutex_t*)lpCriticalSection->LockSemaphore);
        free(lpCriticalSection->LockSemaphore);
        lpCriticalSection->LockSemaphore = NULL;
    }
}

static inline void EnterCriticalSection(LPCRITICAL_SECTION lpCriticalSection) {
    pthread_mutex_lock((pthread_mutex_t*)lpCriticalSection->LockSemaphore);
}

static inline BOOL TryEnterCriticalSection(LPCRITICAL_SECTION lpCriticalSection) {
    return pthread_mutex_trylock((pthread_mutex_t*)lpCriticalSection->LockSemaphore) == 0;
}

static inline void LeaveCriticalSection(LPCRITICAL_SECTION lpCriticalSection) {
    pthread_mutex_unlock((pthread_mutex_t*)lpCriticalSection->LockSemaphore);
}

/* ============================================================
 * Handle Type System
 * ============================================================ */

/* Handle type identifiers for WaitForSingleObject */
typedef enum {
    FF_HANDLE_TYPE_UNKNOWN = 0,
    FF_HANDLE_TYPE_THREAD = 0x54485244,   /* 'THRD' */
    FF_HANDLE_TYPE_EVENT = 0x45564E54,    /* 'EVNT' */
    FF_HANDLE_TYPE_MUTEX = 0x4D555458     /* 'MUTX' */
} FF_HANDLE_TYPE;

/* Base handle structure - all handle types start with this */
typedef struct {
    FF_HANDLE_TYPE type;
} FF_HANDLE_BASE;

/* Thread handle structure */
typedef struct {
    FF_HANDLE_TYPE type;
    pthread_t thread;
    volatile int finished;
    pthread_mutex_t finish_mutex;
    pthread_cond_t finish_cond;
} FF_THREAD_HANDLE;

/* Event handle structure - forward declaration for WaitForSingleObject */
typedef struct {
    FF_HANDLE_TYPE type;
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    BOOL signaled;
    BOOL manualReset;
} FF_EVENT;

/* Mutex handle structure - forward declaration for WaitForSingleObject */
typedef struct {
    FF_HANDLE_TYPE type;
    pthread_mutex_t mutex;
} FF_MUTEX;

/* ============================================================
 * Thread Functions
 * ============================================================ */

/* Thread start routine type - must be before CreateThread */
typedef DWORD (WINAPI *LPTHREAD_START_ROUTINE)(LPVOID);
typedef LPTHREAD_START_ROUTINE PTHREAD_START_ROUTINE;

/* Thread creation data */
typedef struct {
    LPTHREAD_START_ROUTINE lpStartAddress;
    LPVOID lpParameter;
    FF_THREAD_HANDLE* thread_handle;
} FF_THREAD_START_DATA;

static inline void* ff_thread_start_routine(void* arg) {
    FF_THREAD_START_DATA* data = (FF_THREAD_START_DATA*)arg;
    DWORD (*startAddr)(LPVOID) = (DWORD (*)(LPVOID))data->lpStartAddress;
    LPVOID param = data->lpParameter;
    FF_THREAD_HANDLE* th = data->thread_handle;
    free(data);
    DWORD result = startAddr(param);

    /* Signal thread completion */
    if (th) {
        pthread_mutex_lock(&th->finish_mutex);
        th->finished = 1;
        pthread_cond_broadcast(&th->finish_cond);
        pthread_mutex_unlock(&th->finish_mutex);
    }

    return (void*)(intptr_t)result;
}

static inline HANDLE CreateThread(
    LPSECURITY_ATTRIBUTES lpThreadAttributes,
    SIZE_T dwStackSize,
    LPTHREAD_START_ROUTINE lpStartAddress,
    LPVOID lpParameter,
    DWORD dwCreationFlags,
    LPDWORD lpThreadId)
{
    (void)lpThreadAttributes;
    (void)dwStackSize;
    (void)dwCreationFlags; /* TODO: Handle CREATE_SUSPENDED */

    FF_THREAD_HANDLE* th = (FF_THREAD_HANDLE*)malloc(sizeof(FF_THREAD_HANDLE));
    if (!th) return NULL;

    th->type = FF_HANDLE_TYPE_THREAD;
    th->finished = 0;
    pthread_mutex_init(&th->finish_mutex, NULL);
    pthread_cond_init(&th->finish_cond, NULL);

    FF_THREAD_START_DATA* data = (FF_THREAD_START_DATA*)malloc(sizeof(FF_THREAD_START_DATA));
    if (!data) {
        pthread_mutex_destroy(&th->finish_mutex);
        pthread_cond_destroy(&th->finish_cond);
        free(th);
        return NULL;
    }
    data->lpStartAddress = lpStartAddress;
    data->lpParameter = lpParameter;
    data->thread_handle = th;

    if (pthread_create(&th->thread, NULL, ff_thread_start_routine, data) != 0) {
        pthread_mutex_destroy(&th->finish_mutex);
        pthread_cond_destroy(&th->finish_cond);
        free(th);
        free(data);
        return NULL;
    }

    if (lpThreadId) {
        *lpThreadId = (DWORD)(intptr_t)th->thread;
    }

    return (HANDLE)th;
}

/* String comparison - Windows uses stricmp, Linux uses strcasecmp */
#include <strings.h>
#define stricmp strcasecmp
#define strnicmp strncasecmp
#define _stricmp strcasecmp
#define _strnicmp strncasecmp

static inline DWORD GetCurrentThreadId(void) {
    return (DWORD)pthread_self();
}

/* Thread affinity - stub on Linux (would need sched_setaffinity for real impl) */
static inline DWORD_PTR SetThreadAffinityMask(HANDLE hThread, DWORD_PTR dwThreadAffinityMask) {
    (void)hThread;
    (void)dwThreadAffinityMask;
    /* Return non-zero to indicate success (previous affinity mask) */
    return 1;
}

static inline HANDLE GetCurrentThread(void) {
    return (HANDLE)(intptr_t)pthread_self();
}

/* Maximum number of objects for WaitForMultipleObjects */
#define MAXIMUM_WAIT_OBJECTS 64

static inline DWORD WaitForSingleObject(HANDLE hHandle, DWORD dwMilliseconds) {
    if (!hHandle || hHandle == INVALID_HANDLE_VALUE) {
        return WAIT_FAILED;
    }

    /* Check handle type via magic number */
    FF_HANDLE_BASE* base = (FF_HANDLE_BASE*)hHandle;

    switch (base->type) {
        case FF_HANDLE_TYPE_THREAD: {
            FF_THREAD_HANDLE* th = (FF_THREAD_HANDLE*)hHandle;
            if (dwMilliseconds == INFINITE) {
                /* Wait indefinitely for thread to finish */
                pthread_mutex_lock(&th->finish_mutex);
                while (!th->finished) {
                    pthread_cond_wait(&th->finish_cond, &th->finish_mutex);
                }
                pthread_mutex_unlock(&th->finish_mutex);
                pthread_join(th->thread, NULL);
                return WAIT_OBJECT_0;
            } else if (dwMilliseconds == 0) {
                /* Non-blocking check */
                pthread_mutex_lock(&th->finish_mutex);
                int done = th->finished;
                pthread_mutex_unlock(&th->finish_mutex);
                if (done) {
                    pthread_join(th->thread, NULL);
                    return WAIT_OBJECT_0;
                }
                return WAIT_TIMEOUT;
            } else {
                /* Timed wait */
                struct timespec ts;
                clock_gettime(CLOCK_REALTIME, &ts);
                ts.tv_sec += dwMilliseconds / 1000;
                ts.tv_nsec += (dwMilliseconds % 1000) * 1000000;
                if (ts.tv_nsec >= 1000000000) {
                    ts.tv_sec++;
                    ts.tv_nsec -= 1000000000;
                }
                pthread_mutex_lock(&th->finish_mutex);
                int rc = 0;
                while (!th->finished && rc == 0) {
                    rc = pthread_cond_timedwait(&th->finish_cond, &th->finish_mutex, &ts);
                }
                int done = th->finished;
                pthread_mutex_unlock(&th->finish_mutex);
                if (done) {
                    pthread_join(th->thread, NULL);
                    return WAIT_OBJECT_0;
                }
                return WAIT_TIMEOUT;
            }
        }

        case FF_HANDLE_TYPE_EVENT: {
            FF_EVENT* event = (FF_EVENT*)hHandle;
            if (dwMilliseconds == INFINITE) {
                pthread_mutex_lock(&event->mutex);
                while (!event->signaled) {
                    pthread_cond_wait(&event->cond, &event->mutex);
                }
                if (!event->manualReset) {
                    event->signaled = FALSE;
                }
                pthread_mutex_unlock(&event->mutex);
                return WAIT_OBJECT_0;
            } else if (dwMilliseconds == 0) {
                pthread_mutex_lock(&event->mutex);
                BOOL was_signaled = event->signaled;
                if (was_signaled && !event->manualReset) {
                    event->signaled = FALSE;
                }
                pthread_mutex_unlock(&event->mutex);
                return was_signaled ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
            } else {
                struct timespec ts;
                clock_gettime(CLOCK_REALTIME, &ts);
                ts.tv_sec += dwMilliseconds / 1000;
                ts.tv_nsec += (dwMilliseconds % 1000) * 1000000;
                if (ts.tv_nsec >= 1000000000) {
                    ts.tv_sec++;
                    ts.tv_nsec -= 1000000000;
                }
                pthread_mutex_lock(&event->mutex);
                int rc = 0;
                while (!event->signaled && rc == 0) {
                    rc = pthread_cond_timedwait(&event->cond, &event->mutex, &ts);
                }
                BOOL was_signaled = event->signaled;
                if (was_signaled && !event->manualReset) {
                    event->signaled = FALSE;
                }
                pthread_mutex_unlock(&event->mutex);
                return was_signaled ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
            }
        }

        case FF_HANDLE_TYPE_MUTEX: {
            FF_MUTEX* m = (FF_MUTEX*)hHandle;
            if (dwMilliseconds == INFINITE) {
                pthread_mutex_lock(&m->mutex);
                return WAIT_OBJECT_0;
            } else if (dwMilliseconds == 0) {
                if (pthread_mutex_trylock(&m->mutex) == 0) {
                    return WAIT_OBJECT_0;
                }
                return WAIT_TIMEOUT;
            } else {
                /* pthreads doesn't have timed mutex lock, so use trylock + sleep */
                struct timespec start, now;
                clock_gettime(CLOCK_MONOTONIC, &start);
                while (1) {
                    if (pthread_mutex_trylock(&m->mutex) == 0) {
                        return WAIT_OBJECT_0;
                    }
                    clock_gettime(CLOCK_MONOTONIC, &now);
                    long elapsed_ms = (now.tv_sec - start.tv_sec) * 1000 +
                                      (now.tv_nsec - start.tv_nsec) / 1000000;
                    if (elapsed_ms >= (long)dwMilliseconds) {
                        return WAIT_TIMEOUT;
                    }
                    usleep(1000); /* Sleep 1ms between retries */
                }
            }
        }

        default:
            /* Unknown handle type - could be a file descriptor or other handle */
            /* For now, just sleep and return timeout for non-zero waits */
            if (dwMilliseconds > 0 && dwMilliseconds != INFINITE) {
                usleep(dwMilliseconds * 1000);
            }
            return WAIT_TIMEOUT;
    }
}

static inline DWORD WaitForMultipleObjects(DWORD nCount, const HANDLE* lpHandles, BOOL bWaitAll, DWORD dwMilliseconds) {
    /* Simplified stub - returns timeout to indicate no events signaled */
    (void)nCount;
    (void)lpHandles;
    (void)bWaitAll;
    (void)dwMilliseconds;
    /* Sleep a bit and return timeout */
    if (dwMilliseconds > 0 && dwMilliseconds != INFINITE) {
        usleep(dwMilliseconds * 1000);
    }
    return WAIT_TIMEOUT;
}

static inline BOOL CloseHandle(HANDLE hObject) {
    if (!hObject || hObject == INVALID_HANDLE_VALUE) {
        return FALSE;
    }

    /* Check if this is a raw file descriptor (from CreateFile)
     * Raw fds are small positive integers, while FF_HANDLE structures
     * are pointers to heap memory (large addresses on 64-bit systems)
     */
    intptr_t val = (intptr_t)hObject;
    if (val > 0 && val < 65536) {
        /* This appears to be a raw file descriptor */
        return (close((int)val) == 0) ? TRUE : FALSE;
    }

    FF_HANDLE_BASE* base = (FF_HANDLE_BASE*)hObject;

    switch (base->type) {
        case FF_HANDLE_TYPE_THREAD: {
            FF_THREAD_HANDLE* th = (FF_THREAD_HANDLE*)hObject;
            pthread_mutex_destroy(&th->finish_mutex);
            pthread_cond_destroy(&th->finish_cond);
            free(th);
            return TRUE;
        }
        case 0xDEAD0002: /* FF_HANDLE_TYPE_DETACHED_THREAD from _beginthreadex */
            /* Detached thread - just free the handle struct, thread continues running */
            free(hObject);
            return TRUE;
        case FF_HANDLE_TYPE_EVENT: {
            FF_EVENT* event = (FF_EVENT*)hObject;
            pthread_mutex_destroy(&event->mutex);
            pthread_cond_destroy(&event->cond);
            free(event);
            return TRUE;
        }
        case FF_HANDLE_TYPE_MUTEX: {
            FF_MUTEX* m = (FF_MUTEX*)hObject;
            pthread_mutex_destroy(&m->mutex);
            free(m);
            return TRUE;
        }
        default:
            /* Unknown handle type - just free it */
            free(hObject);
            return TRUE;
    }
}

static inline BOOL TerminateThread(HANDLE hThread, DWORD dwExitCode) {
    (void)dwExitCode;
    if (hThread) {
        FF_THREAD_HANDLE* th = (FF_THREAD_HANDLE*)hThread;
        if (th->type == FF_HANDLE_TYPE_THREAD) {
            pthread_cancel(th->thread);
            /* Mark as finished so WaitForSingleObject doesn't block */
            pthread_mutex_lock(&th->finish_mutex);
            th->finished = 1;
            pthread_cond_broadcast(&th->finish_cond);
            pthread_mutex_unlock(&th->finish_mutex);
            return TRUE;
        }
    }
    return FALSE;
}

static inline BOOL SetThreadPriority(HANDLE hThread, int nPriority) {
    (void)hThread;
    (void)nPriority;
    /* TODO: Map Windows priorities to Linux nice values / scheduling policies */
    return TRUE;
}

#define THREAD_PRIORITY_LOWEST          (-2)
#define THREAD_PRIORITY_BELOW_NORMAL    (-1)
#define THREAD_PRIORITY_NORMAL          0
#define THREAD_PRIORITY_ABOVE_NORMAL    1
#define THREAD_PRIORITY_HIGHEST         2
#define THREAD_PRIORITY_TIME_CRITICAL   15
#define THREAD_PRIORITY_IDLE            (-15)

/* ============================================================
 * Event Functions
 * ============================================================ */

/* FF_EVENT is defined in Handle Type System section above */

static inline HANDLE CreateEventA(
    LPSECURITY_ATTRIBUTES lpEventAttributes,
    BOOL bManualReset,
    BOOL bInitialState,
    LPCSTR lpName)
{
    (void)lpEventAttributes;
    (void)lpName;

    FF_EVENT* event = (FF_EVENT*)malloc(sizeof(FF_EVENT));
    if (!event) return NULL;
    event->type = FF_HANDLE_TYPE_EVENT;
    pthread_mutex_init(&event->mutex, NULL);
    pthread_cond_init(&event->cond, NULL);
    event->signaled = bInitialState;
    event->manualReset = bManualReset;
    return (HANDLE)event;
}

#define CreateEvent CreateEventA

static inline BOOL SetEvent(HANDLE hEvent) {
    FF_EVENT* event = (FF_EVENT*)hEvent;
    pthread_mutex_lock(&event->mutex);
    event->signaled = TRUE;
    if (event->manualReset) {
        pthread_cond_broadcast(&event->cond);
    } else {
        pthread_cond_signal(&event->cond);
    }
    pthread_mutex_unlock(&event->mutex);
    return TRUE;
}

static inline BOOL ResetEvent(HANDLE hEvent) {
    FF_EVENT* event = (FF_EVENT*)hEvent;
    pthread_mutex_lock(&event->mutex);
    event->signaled = FALSE;
    pthread_mutex_unlock(&event->mutex);
    return TRUE;
}

static inline BOOL PulseEvent(HANDLE hEvent) {
    SetEvent(hEvent);
    ResetEvent(hEvent);
    return TRUE;
}

/* ============================================================
 * Mutex Functions
 * ============================================================ */

/* FF_MUTEX is defined in Handle Type System section above */

static inline HANDLE CreateMutexA(
    LPSECURITY_ATTRIBUTES lpMutexAttributes,
    BOOL bInitialOwner,
    LPCSTR lpName)
{
    (void)lpMutexAttributes;
    (void)lpName;

    FF_MUTEX* m = (FF_MUTEX*)malloc(sizeof(FF_MUTEX));
    if (!m) return NULL;
    m->type = FF_HANDLE_TYPE_MUTEX;

    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&m->mutex, &attr);
    pthread_mutexattr_destroy(&attr);

    if (bInitialOwner) {
        pthread_mutex_lock(&m->mutex);
    }

    return (HANDLE)m;
}

#define CreateMutex CreateMutexA

static inline BOOL ReleaseMutex(HANDLE hMutex) {
    FF_MUTEX* m = (FF_MUTEX*)hMutex;
    return pthread_mutex_unlock(&m->mutex) == 0;
}

/* ============================================================
 * Dynamic Library Functions
 * ============================================================ */

static inline HMODULE LoadLibraryA(LPCSTR lpLibFileName) {
    return (HMODULE)dlopen(lpLibFileName, RTLD_NOW);
}

static inline HMODULE LoadLibraryExA(LPCSTR lpLibFileName, HANDLE hFile, DWORD dwFlags) {
    (void)hFile;
    (void)dwFlags;
    return LoadLibraryA(lpLibFileName);
}

#define LoadLibrary LoadLibraryA
#define LoadLibraryEx LoadLibraryExA

static inline BOOL FreeLibrary(HMODULE hLibModule) {
    return dlclose(hLibModule) == 0;
}

static inline FARPROC GetProcAddress(HMODULE hModule, LPCSTR lpProcName) {
    return (FARPROC)dlsym(hModule, lpProcName);
}

static inline DWORD GetModuleFileNameA(HMODULE hModule, LPSTR lpFilename, DWORD nSize) {
    (void)hModule;
    ssize_t len = readlink("/proc/self/exe", lpFilename, nSize - 1);
    if (len != -1) {
        lpFilename[len] = '\0';
        return (DWORD)len;
    }
    return 0;
}

#define GetModuleFileName GetModuleFileNameA

static inline HMODULE GetModuleHandleA(LPCSTR lpModuleName) {
    (void)lpModuleName;
    return (HMODULE)dlopen(NULL, RTLD_NOW);
}

#define GetModuleHandle GetModuleHandleA

/* ============================================================
 * Memory Functions
 * ============================================================ */

#define GMEM_FIXED          0x0000
#define GMEM_MOVEABLE       0x0002
#define GMEM_ZEROINIT       0x0040
#define GHND                (GMEM_MOVEABLE | GMEM_ZEROINIT)
#define GPTR                (GMEM_FIXED | GMEM_ZEROINIT)

static inline HGLOBAL GlobalAlloc(UINT uFlags, SIZE_T dwBytes) {
    void* ptr;
    if (uFlags & GMEM_ZEROINIT) {
        ptr = calloc(1, dwBytes);
    } else {
        ptr = malloc(dwBytes);
    }
    return (HGLOBAL)ptr;
}

static inline HGLOBAL GlobalFree(HGLOBAL hMem) {
    free(hMem);
    return NULL;
}

static inline LPVOID GlobalLock(HGLOBAL hMem) {
    return (LPVOID)hMem;
}

static inline BOOL GlobalUnlock(HGLOBAL hMem) {
    (void)hMem;
    return TRUE;
}

static inline SIZE_T GlobalSize(HGLOBAL hMem) {
    (void)hMem;
    return 0; /* Can't determine on Linux without tracking */
}

#define LocalAlloc      GlobalAlloc
#define LocalFree       GlobalFree
#define LocalLock       GlobalLock
#define LocalUnlock     GlobalUnlock

/* Heap functions */
static inline HANDLE GetProcessHeap(void) {
    return (HANDLE)1; /* Dummy handle */
}

static inline HANDLE HeapCreate(DWORD flOptions, SIZE_T dwInitialSize, SIZE_T dwMaximumSize) {
    (void)flOptions;
    (void)dwInitialSize;
    (void)dwMaximumSize;
    return (HANDLE)2; /* Dummy handle for custom heap - use standard malloc */
}

static inline BOOL HeapDestroy(HANDLE hHeap) {
    (void)hHeap;
    return TRUE; /* No-op - we use standard malloc which doesn't need heap destruction */
}

static inline LPVOID HeapAlloc(HANDLE hHeap, DWORD dwFlags, SIZE_T dwBytes) {
    (void)hHeap;
    if (dwFlags & 0x08) { /* HEAP_ZERO_MEMORY */
        return calloc(1, dwBytes);
    }
    return malloc(dwBytes);
}

static inline BOOL HeapFree(HANDLE hHeap, DWORD dwFlags, LPVOID lpMem) {
    (void)hHeap;
    (void)dwFlags;
    free(lpMem);
    return TRUE;
}

static inline LPVOID HeapReAlloc(HANDLE hHeap, DWORD dwFlags, LPVOID lpMem, SIZE_T dwBytes) {
    (void)hHeap;
    (void)dwFlags;
    return realloc(lpMem, dwBytes);
}

/* Virtual memory */
#define MEM_COMMIT          0x00001000
#define MEM_RESERVE         0x00002000
#define MEM_RELEASE         0x00008000
#define PAGE_READWRITE      0x04
#define PAGE_EXECUTE_READWRITE 0x40

static inline LPVOID VirtualAlloc(LPVOID lpAddress, SIZE_T dwSize, DWORD flAllocationType, DWORD flProtect) {
    (void)lpAddress;
    (void)flAllocationType;
    (void)flProtect;
    return calloc(1, dwSize);
}

static inline BOOL VirtualFree(LPVOID lpAddress, SIZE_T dwSize, DWORD dwFreeType) {
    (void)dwSize;
    (void)dwFreeType;
    free(lpAddress);
    return TRUE;
}

/* ============================================================
 * Process Functions
 * ============================================================ */

static inline HANDLE GetCurrentProcess(void) {
    return (HANDLE)(intptr_t)getpid();
}

static inline DWORD GetCurrentProcessId(void) {
    return (DWORD)getpid();
}

static inline void ExitProcess(UINT uExitCode) {
    exit(uExitCode);
}

/* ============================================================
 * INI File Functions
 * ============================================================ */

/* These need real implementations - stub for now */
static inline DWORD GetPrivateProfileStringA(
    LPCSTR lpAppName,
    LPCSTR lpKeyName,
    LPCSTR lpDefault,
    LPSTR lpReturnedString,
    DWORD nSize,
    LPCSTR lpFileName)
{
    (void)lpAppName;
    (void)lpKeyName;
    (void)lpFileName;
    if (lpDefault && lpReturnedString && nSize > 0) {
        strncpy(lpReturnedString, lpDefault, nSize - 1);
        lpReturnedString[nSize - 1] = '\0';
        return (DWORD)strlen(lpReturnedString);
    }
    return 0;
}

static inline UINT GetPrivateProfileIntA(
    LPCSTR lpAppName,
    LPCSTR lpKeyName,
    INT nDefault,
    LPCSTR lpFileName)
{
    (void)lpAppName;
    (void)lpKeyName;
    (void)lpFileName;
    return nDefault;
}

static inline BOOL WritePrivateProfileStringA(
    LPCSTR lpAppName,
    LPCSTR lpKeyName,
    LPCSTR lpString,
    LPCSTR lpFileName)
{
    (void)lpAppName;
    (void)lpKeyName;
    (void)lpString;
    (void)lpFileName;
    return FALSE; /* Stub */
}

#define GetPrivateProfileString GetPrivateProfileStringA
#define GetPrivateProfileInt GetPrivateProfileIntA
#define WritePrivateProfileString WritePrivateProfileStringA

/* ============================================================
 * System Information Functions
 * ============================================================ */

static inline BOOL GetComputerNameA(LPSTR lpBuffer, LPDWORD nSize) {
    if (!lpBuffer || !nSize || *nSize == 0) return FALSE;
    if (gethostname(lpBuffer, *nSize) == 0) {
        *nSize = (DWORD)strlen(lpBuffer);
        return TRUE;
    }
    /* Fallback */
    strncpy(lpBuffer, "localhost", *nSize - 1);
    lpBuffer[*nSize - 1] = '\0';
    *nSize = (DWORD)strlen(lpBuffer);
    return TRUE;
}
#define GetComputerName GetComputerNameA

/* ============================================================
 * File I/O Functions (CreateFile, etc.)
 * ============================================================ */

/* Access flags */
#define GENERIC_READ            0x80000000
#define GENERIC_WRITE           0x40000000
#define GENERIC_EXECUTE         0x20000000
#define GENERIC_ALL             0x10000000

/* Share mode */
#define FILE_SHARE_READ         0x00000001
#define FILE_SHARE_WRITE        0x00000002
#define FILE_SHARE_DELETE       0x00000004

/* Creation disposition */
#define CREATE_NEW              1
#define CREATE_ALWAYS           2
#define OPEN_EXISTING           3
#define OPEN_ALWAYS             4
#define TRUNCATE_EXISTING       5

/* File attributes */
#define FILE_ATTRIBUTE_READONLY     0x00000001
#define FILE_ATTRIBUTE_HIDDEN       0x00000002
#define FILE_ATTRIBUTE_SYSTEM       0x00000004
#define FILE_ATTRIBUTE_DIRECTORY    0x00000010
#define FILE_ATTRIBUTE_ARCHIVE      0x00000020
#define FILE_ATTRIBUTE_NORMAL       0x00000080
#define FILE_ATTRIBUTE_TEMPORARY    0x00000100

/* File flags */
#define FILE_FLAG_WRITE_THROUGH     0x80000000
#define FILE_FLAG_NO_BUFFERING      0x20000000
#define FILE_FLAG_RANDOM_ACCESS     0x10000000
#define FILE_FLAG_SEQUENTIAL_SCAN   0x08000000
#define FILE_FLAG_DELETE_ON_CLOSE   0x04000000

/* CreateFile - opens or creates a file */
static inline HANDLE CreateFile(
    LPCSTR lpFileName,
    DWORD dwDesiredAccess,
    DWORD dwShareMode,
    void* lpSecurityAttributes,
    DWORD dwCreationDisposition,
    DWORD dwFlagsAndAttributes,
    HANDLE hTemplateFile)
{
    (void)dwShareMode;
    (void)lpSecurityAttributes;
    (void)dwFlagsAndAttributes;
    (void)hTemplateFile;

    int flags = 0;

    /* Determine access mode */
    if ((dwDesiredAccess & GENERIC_READ) && (dwDesiredAccess & GENERIC_WRITE)) {
        flags = O_RDWR;
    } else if (dwDesiredAccess & GENERIC_WRITE) {
        flags = O_WRONLY;
    } else {
        flags = O_RDONLY;
    }

    /* Creation disposition */
    switch (dwCreationDisposition) {
        case CREATE_NEW:
            flags |= O_CREAT | O_EXCL;
            break;
        case CREATE_ALWAYS:
            flags |= O_CREAT | O_TRUNC;
            break;
        case OPEN_EXISTING:
            /* No extra flags */
            break;
        case OPEN_ALWAYS:
            flags |= O_CREAT;
            break;
        case TRUNCATE_EXISTING:
            flags |= O_TRUNC;
            break;
    }

    /* Try case-insensitive file lookup on Linux */
    int fd = open_nocase(lpFileName, flags, 0644);
    if (fd == -1) {
        return INVALID_HANDLE_VALUE;
    }
    return (HANDLE)(intptr_t)fd;
}
#define CreateFileA CreateFile

/* GetFileSize - get file size */
static inline DWORD GetFileSize(HANDLE hFile, LPDWORD lpFileSizeHigh) {
    int fd = (int)(intptr_t)hFile;
    struct stat st;
    if (fstat(fd, &st) == -1) {
        if (lpFileSizeHigh) *lpFileSizeHigh = 0;
        return INVALID_FILE_SIZE;
    }
    if (lpFileSizeHigh) *lpFileSizeHigh = (DWORD)(st.st_size >> 32);
    return (DWORD)(st.st_size & 0xFFFFFFFF);
}

/* File position constants */
#define FILE_BEGIN      0
#define FILE_CURRENT    1
#define FILE_END        2

#define INVALID_SET_FILE_POINTER ((DWORD)-1)
#define INVALID_FILE_SIZE       ((DWORD)0xFFFFFFFF)

/* SetFilePointer - seek in file */
static inline DWORD SetFilePointer(
    HANDLE hFile,
    LONG lDistanceToMove,
    PLONG lpDistanceToMoveHigh,
    DWORD dwMoveMethod)
{
    int fd = (int)(intptr_t)hFile;
    int whence;

    switch (dwMoveMethod) {
        case FILE_BEGIN:   whence = SEEK_SET; break;
        case FILE_CURRENT: whence = SEEK_CUR; break;
        case FILE_END:     whence = SEEK_END; break;
        default:           return INVALID_SET_FILE_POINTER;
    }

    off_t offset = lDistanceToMove;
    if (lpDistanceToMoveHigh) {
        offset |= ((off_t)*lpDistanceToMoveHigh << 32);
    }

    off_t result = lseek(fd, offset, whence);
    if (result == -1) return INVALID_SET_FILE_POINTER;

    if (lpDistanceToMoveHigh) {
        *lpDistanceToMoveHigh = (LONG)(result >> 32);
    }
    return (DWORD)(result & 0xFFFFFFFF);
}

/* ReadFile - read from file */
static inline BOOL ReadFile(
    HANDLE hFile,
    LPVOID lpBuffer,
    DWORD nNumberOfBytesToRead,
    LPDWORD lpNumberOfBytesRead,
    void* lpOverlapped)
{
    (void)lpOverlapped;  /* Async I/O not supported */

    int fd = (int)(intptr_t)hFile;
    ssize_t result = read(fd, lpBuffer, nNumberOfBytesToRead);

    if (result == -1) {
        if (lpNumberOfBytesRead) *lpNumberOfBytesRead = 0;
        return FALSE;
    }

    if (lpNumberOfBytesRead) *lpNumberOfBytesRead = (DWORD)result;
    return TRUE;
}

/* WriteFile - write to file */
static inline BOOL WriteFile(
    HANDLE hFile,
    LPCVOID lpBuffer,
    DWORD nNumberOfBytesToWrite,
    LPDWORD lpNumberOfBytesWritten,
    void* lpOverlapped)
{
    (void)lpOverlapped;  /* Async I/O not supported */

    int fd = (int)(intptr_t)hFile;
    ssize_t result = write(fd, lpBuffer, nNumberOfBytesToWrite);

    if (result == -1) {
        if (lpNumberOfBytesWritten) *lpNumberOfBytesWritten = 0;
        return FALSE;
    }

    if (lpNumberOfBytesWritten) *lpNumberOfBytesWritten = (DWORD)result;
    return TRUE;
}

/* FlushFileBuffers - sync file to disk */
static inline BOOL FlushFileBuffers(HANDLE hFile) {
    int fd = (int)(intptr_t)hFile;
    return fsync(fd) == 0;
}

/* SetEndOfFile - truncate/extend file at current position */
static inline BOOL SetEndOfFile(HANDLE hFile) {
    int fd = (int)(intptr_t)hFile;
    off_t pos = lseek(fd, 0, SEEK_CUR);
    if (pos == -1) return FALSE;
    return ftruncate(fd, pos) == 0;
}

/* CreateDirectory - create a directory */
static inline BOOL CreateDirectoryA(LPCSTR lpPathName, LPSECURITY_ATTRIBUTES lpSecurityAttributes) {
    (void)lpSecurityAttributes;
    if (!lpPathName) return FALSE;
    /* mkdir returns 0 on success, -1 on error */
    if (mkdir(lpPathName, 0755) == 0) return TRUE;
    /* If directory already exists, that's OK */
    if (errno == EEXIST) {
        struct stat st;
        if (stat(lpPathName, &st) == 0 && S_ISDIR(st.st_mode)) {
            return TRUE;
        }
    }
    return FALSE;
}
#define CreateDirectory CreateDirectoryA

/* RemoveDirectory - remove a directory */
static inline BOOL RemoveDirectoryA(LPCSTR lpPathName) {
    if (!lpPathName) return FALSE;
    return rmdir(lpPathName) == 0;
}
#define RemoveDirectory RemoveDirectoryA

/* DeleteFile - delete a file */
static inline BOOL DeleteFileA(LPCSTR lpFileName) {
    if (!lpFileName) return FALSE;
    return unlink(lpFileName) == 0;
}
#define DeleteFile DeleteFileA

/* CopyFile - copy a file */
static inline BOOL CopyFileA(LPCSTR lpExistingFileName, LPCSTR lpNewFileName, BOOL bFailIfExists) {
    if (!lpExistingFileName || !lpNewFileName) return FALSE;

    /* Check if destination exists */
    if (bFailIfExists && access(lpNewFileName, F_OK) == 0) {
        return FALSE;
    }

    int src_fd = open(lpExistingFileName, O_RDONLY);
    if (src_fd == -1) return FALSE;

    int dst_fd = open(lpNewFileName, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (dst_fd == -1) {
        close(src_fd);
        return FALSE;
    }

    char buffer[8192];
    ssize_t bytes_read;
    BOOL success = TRUE;

    while ((bytes_read = read(src_fd, buffer, sizeof(buffer))) > 0) {
        if (write(dst_fd, buffer, bytes_read) != bytes_read) {
            success = FALSE;
            break;
        }
    }

    if (bytes_read < 0) success = FALSE;

    close(src_fd);
    close(dst_fd);
    return success;
}
#define CopyFile CopyFileA

/* MoveFile - move/rename a file */
static inline BOOL MoveFileA(LPCSTR lpExistingFileName, LPCSTR lpNewFileName) {
    if (!lpExistingFileName || !lpNewFileName) return FALSE;
    return rename(lpExistingFileName, lpNewFileName) == 0;
}
#define MoveFile MoveFileA

/* GetFileAttributes - get file attributes */
static inline DWORD GetFileAttributesA(LPCSTR lpFileName) {
    if (!lpFileName) return INVALID_FILE_ATTRIBUTES;

    struct stat st;
    if (stat(lpFileName, &st) != 0) {
        return INVALID_FILE_ATTRIBUTES;
    }

    DWORD attrs = 0;
    if (S_ISDIR(st.st_mode)) {
        attrs |= FILE_ATTRIBUTE_DIRECTORY;
    } else {
        attrs |= FILE_ATTRIBUTE_NORMAL;
    }
    if (!(st.st_mode & S_IWUSR)) {
        attrs |= FILE_ATTRIBUTE_READONLY;
    }
    return attrs;
}
#define GetFileAttributes GetFileAttributesA

#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)

/* SetFileAttributes - set file attributes (limited support on Linux) */
static inline BOOL SetFileAttributesA(LPCSTR lpFileName, DWORD dwFileAttributes) {
    if (!lpFileName) return FALSE;

    struct stat st;
    if (stat(lpFileName, &st) != 0) return FALSE;

    mode_t mode = st.st_mode;
    if (dwFileAttributes & FILE_ATTRIBUTE_READONLY) {
        mode &= ~(S_IWUSR | S_IWGRP | S_IWOTH);
    } else {
        mode |= S_IWUSR;
    }

    return chmod(lpFileName, mode) == 0;
}
#define SetFileAttributes SetFileAttributesA

/* ============================================================
 * File Mapping Functions
 * ============================================================ */
#include <sys/mman.h>

/* Page protection flags */
#define PAGE_READONLY           0x02
#define PAGE_READWRITE          0x04
#define PAGE_WRITECOPY          0x08
#define PAGE_EXECUTE_READ       0x20
#define PAGE_EXECUTE_READWRITE  0x40

/* Section flags */
#define SEC_COMMIT              0x8000000
#define SEC_IMAGE               0x1000000
#define SEC_NOCACHE             0x10000000
#define SEC_RESERVE             0x4000000

/* File map access */
#define FILE_MAP_COPY           0x0001
#define FILE_MAP_WRITE          0x0002
#define FILE_MAP_READ           0x0004
#define FILE_MAP_ALL_ACCESS     0x001F

/* CreateFileMapping stub - on Linux we use mmap directly */
static inline HANDLE CreateFileMapping(
    HANDLE hFile,
    void* lpFileMappingAttributes,
    DWORD flProtect,
    DWORD dwMaximumSizeHigh,
    DWORD dwMaximumSizeLow,
    LPCSTR lpName)
{
    (void)lpFileMappingAttributes;
    (void)flProtect;
    (void)dwMaximumSizeHigh;
    (void)dwMaximumSizeLow;
    (void)lpName;

    /* Just return the file handle - actual mapping done in MapViewOfFileEx */
    return hFile;
}
#define CreateFileMappingA CreateFileMapping

/* ============================================================
 * Pointer Validation Functions (IsBad* family)
 * These are deprecated on Windows but still used in legacy code.
 * On Linux we provide simple stubs.
 * ============================================================ */

/* IsBadReadPtr - checks if pointer can be read (always FALSE unless NULL) */
static inline BOOL IsBadReadPtr(const void* lp, UINT_PTR ucb) {
    (void)ucb;
    return (lp == NULL) ? TRUE : FALSE;
}

/* IsBadWritePtr - checks if pointer can be written (always FALSE unless NULL) */
static inline BOOL IsBadWritePtr(LPVOID lp, UINT_PTR ucb) {
    (void)ucb;
    return (lp == NULL) ? TRUE : FALSE;
}

/* IsBadStringPtr - checks if string pointer is valid */
static inline BOOL IsBadStringPtrA(LPCSTR lpsz, UINT_PTR ucchMax) {
    (void)ucchMax;
    return (lpsz == NULL) ? TRUE : FALSE;
}
#define IsBadStringPtr IsBadStringPtrA
#define IsBadStringPtrW IsBadStringPtrA

/* IsBadCodePtr - checks if code pointer is valid */
static inline BOOL IsBadCodePtr(FARPROC lpfn) {
    return (lpfn == NULL) ? TRUE : FALSE;
}

/* MapViewOfFileEx - maps file to memory */
static inline LPVOID MapViewOfFileEx(
    HANDLE hFileMappingObject,
    DWORD dwDesiredAccess,
    DWORD dwFileOffsetHigh,
    DWORD dwFileOffsetLow,
    SIZE_T dwNumberOfBytesToMap,
    LPVOID lpBaseAddress)
{
    (void)lpBaseAddress;  /* Linux mmap doesn't guarantee address */

    int fd = (int)(intptr_t)hFileMappingObject;
    int prot = PROT_NONE;
    int flags = MAP_PRIVATE;

    if (dwDesiredAccess & FILE_MAP_WRITE) {
        prot = PROT_READ | PROT_WRITE;
        flags = MAP_SHARED;
    } else if (dwDesiredAccess & FILE_MAP_READ) {
        prot = PROT_READ;
    } else if (dwDesiredAccess & FILE_MAP_COPY) {
        prot = PROT_READ | PROT_WRITE;
        flags = MAP_PRIVATE;
    }

    off_t offset = ((off_t)dwFileOffsetHigh << 32) | dwFileOffsetLow;

    /* If dwNumberOfBytesToMap is 0, map entire file */
    if (dwNumberOfBytesToMap == 0) {
        struct stat st;
        if (fstat(fd, &st) == -1) return NULL;
        dwNumberOfBytesToMap = st.st_size - offset;
    }

    void* result = mmap(NULL, dwNumberOfBytesToMap, prot, flags, fd, offset);
    if (result == MAP_FAILED) return NULL;
    return result;
}

static inline LPVOID MapViewOfFile(
    HANDLE hFileMappingObject,
    DWORD dwDesiredAccess,
    DWORD dwFileOffsetHigh,
    DWORD dwFileOffsetLow,
    SIZE_T dwNumberOfBytesToMap)
{
    return MapViewOfFileEx(hFileMappingObject, dwDesiredAccess,
                          dwFileOffsetHigh, dwFileOffsetLow,
                          dwNumberOfBytesToMap, NULL);
}

static inline BOOL UnmapViewOfFile(LPCVOID lpBaseAddress) {
    /* Note: We don't track size, so this is a best-effort stub */
    /* Real applications should track mapped region sizes */
    (void)lpBaseAddress;
    return TRUE;
}

/* ============================================================
 * Thread Suspend/Resume (Stubs - not fully supported on Linux)
 * ============================================================ */

/* Note: pthreads doesn't have direct suspend/resume.
 * These are stubs that return success but don't actually suspend. */
static inline DWORD SuspendThread(HANDLE hThread) {
    (void)hThread;
    /* Return previous suspend count - we fake it as 0 (was running) */
    return 0;
}

static inline DWORD ResumeThread(HANDLE hThread) {
    (void)hThread;
    /* Return previous suspend count - we fake it as 1 (was suspended) */
    return 1;
}

/* ============================================================
 * Time Functions
 * ============================================================ */

/* GetDoubleClickTime - Returns mouse double-click time in milliseconds */
static inline UINT GetDoubleClickTime(void) {
    return 500; /* Default Windows value */
}

/* GetCurrentTime - Deprecated, same as GetTickCount */
static inline DWORD GetCurrentTime(void) {
    return GetTickCount();
}

/* GetMessageTime - Returns tick count when message was posted */
static inline LONG GetMessageTime(void) {
    return (LONG)GetTickCount();
}

/* ============================================================
 * Version Info Functions (Stubs)
 * ============================================================ */

static inline DWORD GetFileVersionInfoSizeA(LPCSTR lptstrFilename, LPDWORD lpdwHandle) {
    (void)lptstrFilename;
    if (lpdwHandle) *lpdwHandle = 0;
    return 0; /* Return 0 to indicate no version info available */
}

#define GetFileVersionInfoSize GetFileVersionInfoSizeA

static inline BOOL GetFileVersionInfoA(LPCSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData) {
    (void)lptstrFilename;
    (void)dwHandle;
    (void)dwLen;
    (void)lpData;
    return FALSE; /* No version info available on Linux */
}

#define GetFileVersionInfo GetFileVersionInfoA

static inline BOOL VerQueryValueA(LPCVOID pBlock, LPCSTR lpSubBlock, LPVOID* lplpBuffer, PUINT puLen) {
    (void)pBlock;
    (void)lpSubBlock;
    *lplpBuffer = NULL;
    *puLen = 0;
    return FALSE;
}

#define VerQueryValue VerQueryValueA

/* ============================================================
 * File Enumeration (FindFirstFile/FindNextFile)
 * ============================================================ */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dirent.h>
#include <fnmatch.h>
#include <sys/stat.h>

/* FNM_CASEFOLD is a GNU extension, provide fallback */
#ifndef FNM_CASEFOLD
#define FNM_CASEFOLD 0
#endif

#ifndef MAX_PATH
#define MAX_PATH 260
#endif

/* File attribute flags */
#ifndef FILE_ATTRIBUTE_DIRECTORY
#define FILE_ATTRIBUTE_DIRECTORY    0x00000010
#endif
#ifndef FILE_ATTRIBUTE_NORMAL
#define FILE_ATTRIBUTE_NORMAL       0x00000080
#endif
#ifndef FILE_ATTRIBUTE_READONLY
#define FILE_ATTRIBUTE_READONLY     0x00000001
#endif
#ifndef FILE_ATTRIBUTE_HIDDEN
#define FILE_ATTRIBUTE_HIDDEN       0x00000002
#endif
#ifndef FILE_ATTRIBUTE_ARCHIVE
#define FILE_ATTRIBUTE_ARCHIVE      0x00000020
#endif

typedef struct _WIN32_FIND_DATAA {
    DWORD    dwFileAttributes;
    FILETIME ftCreationTime;
    FILETIME ftLastAccessTime;
    FILETIME ftLastWriteTime;
    DWORD    nFileSizeHigh;
    DWORD    nFileSizeLow;
    DWORD    dwReserved0;
    DWORD    dwReserved1;
    CHAR     cFileName[MAX_PATH];
    CHAR     cAlternateFileName[14];
} WIN32_FIND_DATAA, *PWIN32_FIND_DATAA, *LPWIN32_FIND_DATAA;

typedef WIN32_FIND_DATAA WIN32_FIND_DATA;
typedef LPWIN32_FIND_DATAA LPWIN32_FIND_DATA;

/* Internal structure for directory enumeration */
typedef struct _FF_FIND_HANDLE {
    DIR* dir;
    char pattern[MAX_PATH];
    char basepath[MAX_PATH];
} FF_FIND_HANDLE;

static inline HANDLE FindFirstFileA(LPCSTR lpFileName, LPWIN32_FIND_DATAA lpFindFileData) {
    if (!lpFileName || !lpFindFileData) return INVALID_HANDLE_VALUE;

    /* Extract directory path and pattern */
    char dirpath[MAX_PATH];
    char pattern[MAX_PATH];
    strncpy(dirpath, lpFileName, MAX_PATH - 1);
    dirpath[MAX_PATH - 1] = '\0';

    char* lastslash = strrchr(dirpath, '/');
    char* lastbackslash = strrchr(dirpath, '\\');
    char* sep = (lastslash > lastbackslash) ? lastslash : lastbackslash;

    if (sep) {
        strncpy(pattern, sep + 1, MAX_PATH - 1);
        pattern[MAX_PATH - 1] = '\0';
        *sep = '\0';
    } else {
        strncpy(pattern, dirpath, MAX_PATH - 1);
        pattern[MAX_PATH - 1] = '\0';
        strcpy(dirpath, ".");
    }

    /* Replace backslashes with forward slashes */
    for (char* p = dirpath; *p; p++) {
        if (*p == '\\') *p = '/';
    }

    DIR* dir = opendir(dirpath);
    if (!dir) return INVALID_HANDLE_VALUE;

    FF_FIND_HANDLE* ffh = (FF_FIND_HANDLE*)malloc(sizeof(FF_FIND_HANDLE));
    if (!ffh) {
        closedir(dir);
        return INVALID_HANDLE_VALUE;
    }

    ffh->dir = dir;
    strncpy(ffh->pattern, pattern, MAX_PATH - 1);
    ffh->pattern[MAX_PATH - 1] = '\0';
    strncpy(ffh->basepath, dirpath, MAX_PATH - 1);
    ffh->basepath[MAX_PATH - 1] = '\0';

    /* Find first matching entry */
    struct dirent* entry;
    while ((entry = readdir(ffh->dir)) != NULL) {
        if (fnmatch(ffh->pattern, entry->d_name, FNM_CASEFOLD) == 0) {
            memset(lpFindFileData, 0, sizeof(*lpFindFileData));
            strncpy(lpFindFileData->cFileName, entry->d_name, MAX_PATH - 1);

            /* Get file attributes */
            char fullpath[MAX_PATH * 2];
            snprintf(fullpath, sizeof(fullpath), "%s/%s", ffh->basepath, entry->d_name);

            struct stat st;
            if (stat(fullpath, &st) == 0) {
                if (S_ISDIR(st.st_mode)) {
                    lpFindFileData->dwFileAttributes = FILE_ATTRIBUTE_DIRECTORY;
                } else {
                    lpFindFileData->dwFileAttributes = FILE_ATTRIBUTE_NORMAL;
                }
                lpFindFileData->nFileSizeLow = (DWORD)(st.st_size & 0xFFFFFFFF);
                lpFindFileData->nFileSizeHigh = (DWORD)(st.st_size >> 32);
            }

            return (HANDLE)ffh;
        }
    }

    /* No matching files found */
    closedir(ffh->dir);
    free(ffh);
    return INVALID_HANDLE_VALUE;
}

#define FindFirstFile FindFirstFileA

static inline BOOL FindNextFileA(HANDLE hFindFile, LPWIN32_FIND_DATAA lpFindFileData) {
    if (hFindFile == INVALID_HANDLE_VALUE || !lpFindFileData) return FALSE;

    FF_FIND_HANDLE* ffh = (FF_FIND_HANDLE*)hFindFile;
    struct dirent* entry;

    while ((entry = readdir(ffh->dir)) != NULL) {
        if (fnmatch(ffh->pattern, entry->d_name, FNM_CASEFOLD) == 0) {
            memset(lpFindFileData, 0, sizeof(*lpFindFileData));
            strncpy(lpFindFileData->cFileName, entry->d_name, MAX_PATH - 1);

            /* Get file attributes */
            char fullpath[MAX_PATH * 2];
            snprintf(fullpath, sizeof(fullpath), "%s/%s", ffh->basepath, entry->d_name);

            struct stat st;
            if (stat(fullpath, &st) == 0) {
                if (S_ISDIR(st.st_mode)) {
                    lpFindFileData->dwFileAttributes = FILE_ATTRIBUTE_DIRECTORY;
                } else {
                    lpFindFileData->dwFileAttributes = FILE_ATTRIBUTE_NORMAL;
                }
                lpFindFileData->nFileSizeLow = (DWORD)(st.st_size & 0xFFFFFFFF);
                lpFindFileData->nFileSizeHigh = (DWORD)(st.st_size >> 32);
            }

            return TRUE;
        }
    }

    return FALSE;
}

#define FindNextFile FindNextFileA

static inline BOOL FindClose(HANDLE hFindFile) {
    if (hFindFile == INVALID_HANDLE_VALUE) return FALSE;

    FF_FIND_HANDLE* ffh = (FF_FIND_HANDLE*)hFindFile;
    closedir(ffh->dir);
    free(ffh);
    return TRUE;
}

/* ============================================================
 * Current Directory functions
 * ============================================================ */

static inline BOOL SetCurrentDirectoryA(LPCSTR lpPathName) {
    if (!lpPathName) return FALSE;
    return chdir(lpPathName) == 0;
}
#define SetCurrentDirectory SetCurrentDirectoryA

static inline DWORD GetCurrentDirectoryA(DWORD nBufferLength, LPSTR lpBuffer) {
    if (!lpBuffer || nBufferLength == 0) return 0;
    if (getcwd(lpBuffer, nBufferLength) != NULL) {
        return (DWORD)strlen(lpBuffer);
    }
    return 0;
}
#define GetCurrentDirectory GetCurrentDirectoryA

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINBASE_H */
