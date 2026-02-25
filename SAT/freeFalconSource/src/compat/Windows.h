/*
 * FreeFalcon Linux Port - windows.h compatibility
 *
 * This header provides Windows API compatibility for Linux builds.
 * It includes type definitions, macros, and stub/replacement functions.
 */

#ifndef FF_COMPAT_WINDOWS_H
#define FF_COMPAT_WINDOWS_H

#ifdef FF_LINUX

/* Prevent multiple definition issues */
#define _WINDOWS_
#define _WINDEF_
#define _WINBASE_
#define _WINUSER_
#define _WINGDI_
#define _INC_WINDOWS  /* Used by some code to detect windows.h inclusion */

/* Include our type definitions */
#include "compat_types.h"
#include "compat_winbase.h"
#include "compat_wingdi.h"
#include "compat_winuser.h"
#include "compat_mmsystem.h"
#include "io.h"

/* Include standard Linux headers we'll need */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <errno.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <dlfcn.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Additional Windows compatibility macros
 * ============================================================ */

/* Win32 lean and mean - no-op, we're already lean */
#define WIN32_LEAN_AND_MEAN

/* Disable specific warnings - no-op on GCC/Clang */
#define _CRT_SECURE_NO_WARNINGS
#define _CRT_NONSTDC_NO_DEPRECATE

/* DLL import/export - no-op on Linux */
#define __declspec(x)
#define dllimport
#define dllexport

/* Structured exception handling - not supported, use try/catch or signals
 * WARNING: We cannot define __try/__except as macros because GCC's libstdc++
 * uses __try and __catch internally for exception-safe code.
 *
 * Code using SEH will need to be modified to use C++ try/catch or
 * preprocessor blocks with #ifdef _WIN32 / #else / #endif.
 */
#define GetExceptionCode() 0
#define GetExceptionInformation() NULL
#define EXCEPTION_EXECUTE_HANDLER 1

/* For code that needs SEH-like blocks, use these alternative macros */
#define FF_SEH_TRY       if(1)
#define FF_SEH_EXCEPT(x) if(0)
#define FF_SEH_FINALLY

/* Interlocked operations - use GCC builtins */
#define InterlockedIncrement(p)     __sync_add_and_fetch((p), 1)
#define InterlockedDecrement(p)     __sync_sub_and_fetch((p), 1)
#define InterlockedExchange(p, v)   __sync_lock_test_and_set((p), (v))
#define InterlockedExchangeAdd(p,v) __sync_fetch_and_add((p), (v))
#define InterlockedCompareExchange(p, e, c) __sync_val_compare_and_swap((p), (c), (e))

/* Memory barriers */
#define MemoryBarrier()             __sync_synchronize()

/* Debug break */
#define DebugBreak()                __builtin_trap()
#define __debugbreak()              __builtin_trap()

/* MSVC-specific keywords */
#ifndef __forceinline
#define __forceinline inline __attribute__((always_inline))
#endif

/* Output debug string - just print to stderr */
static inline void OutputDebugStringA(LPCSTR lpOutputString) {
    if (lpOutputString) {
        fprintf(stderr, "[DEBUG] %s", lpOutputString);
    }
}
#define OutputDebugString OutputDebugStringA

/* Assertions */
#include <assert.h>
#define ASSERT(x)       assert(x)
#define _ASSERT(x)      assert(x)
#define _ASSERTE(x)     assert(x)

/* ZeroMemory, CopyMemory, etc. */
#define ZeroMemory(dest, size)      memset((dest), 0, (size))
#define FillMemory(dest, size, c)   memset((dest), (c), (size))
#define CopyMemory(dest, src, size) memcpy((dest), (src), (size))
#define MoveMemory(dest, src, size) memmove((dest), (src), (size))

/* String functions */
#define lstrcpy         strcpy
#define lstrcpyA        strcpy
#define lstrcpyn        strncpy
#define lstrcpynA       strncpy
#define lstrcat         strcat
#define lstrcatA        strcat
#define lstrlen         strlen
#define lstrlenA        strlen
#define lstrcmp         strcmp
#define lstrcmpA        strcmp
#define lstrcmpi        strcasecmp
#define lstrcmpiA       strcasecmp

#define _stricmp        strcasecmp
#define _strnicmp       strncasecmp
#define _strcmpi        strcasecmp
#define stricmp         strcasecmp
#define strnicmp        strncasecmp
#define _strlwr         ff_strlwr
#define _strupr         ff_strupr
#define _strdup         strdup
#define _snprintf       snprintf
#define _vsnprintf      vsnprintf
#define sprintf_s       snprintf
#define _itoa           ff_itoa
#define itoa            ff_itoa
#define wsprintf        sprintf
#define wvsprintf       vsprintf
#define wsprintfA       sprintf
#define wvsprintfA      vsprintf

/* Helper string functions */
static inline char* ff_strlwr(char* str) {
    if (str) {
        for (char* p = str; *p; p++) {
            if (*p >= 'A' && *p <= 'Z') *p += 32;
        }
    }
    return str;
}

static inline char* ff_strupr(char* str) {
    if (str) {
        for (char* p = str; *p; p++) {
            if (*p >= 'a' && *p <= 'z') *p -= 32;
        }
    }
    return str;
}

static inline char* ff_itoa(int value, char* str, int base) {
    if (base == 10) {
        sprintf(str, "%d", value);
    } else if (base == 16) {
        sprintf(str, "%x", value);
    } else if (base == 8) {
        sprintf(str, "%o", value);
    } else {
        str[0] = '\0';
    }
    return str;
}

/* File I/O constants */
#define _O_RDONLY       O_RDONLY
#define _O_WRONLY       O_WRONLY
#define _O_RDWR         O_RDWR
#define _O_CREAT        O_CREAT
#define _O_TRUNC        O_TRUNC
#define _O_APPEND       O_APPEND
#define _O_BINARY       0
#define _O_TEXT         0
#define O_BINARY        0
#define O_TEXT          0
#define _S_IREAD        S_IRUSR
#define _S_IWRITE       S_IWUSR

/* POSIX functions with underscore prefix */
#define _open           open
#define _close          close
#define _read           read
#define _write          write
#define _lseek          lseek
#define _unlink         unlink
#define _access         access
#define _mkdir(path)    mkdir(path, 0755)
#define _rmdir          rmdir
#define _getcwd         getcwd
#define _chdir          chdir
#define _stat           stat
#define _fstat          fstat
#define _fileno         fileno
#define _isatty         isatty
#define _dup            dup
#define _dup2           dup2
#define _pipe           pipe
#define _popen          popen
#define _pclose         pclose

/* Sleep function */
static inline void Sleep(DWORD dwMilliseconds) {
    usleep(dwMilliseconds * 1000);
}

/* String functions - Windows-specific */
#define strcmpi     strcasecmp
#define stricmp     strcasecmp
#define _strcmpi    strcasecmp
#define _stricmp    strcasecmp
#define strnicmp    strncasecmp
#define _strnicmp   strncasecmp

/* Windows message functions - defined in compat_winuser.h */
/* NOTE: Cannot define SendMessage macro because it conflicts with VuTargetEntity::SendMessage() */
/* Code that needs to call Windows SendMessage should use SendMessageA directly */

/* ============================================================
 * Windows Registry API stubs
 * ============================================================ */
typedef HANDLE HKEY;
typedef HKEY *PHKEY;

#define HKEY_CLASSES_ROOT       ((HKEY)(ULONG_PTR)0x80000000)
#define HKEY_CURRENT_USER       ((HKEY)(ULONG_PTR)0x80000001)
#define HKEY_LOCAL_MACHINE      ((HKEY)(ULONG_PTR)0x80000002)
#define HKEY_USERS              ((HKEY)(ULONG_PTR)0x80000003)
#define HKEY_CURRENT_CONFIG     ((HKEY)(ULONG_PTR)0x80000005)

#define KEY_QUERY_VALUE         0x0001
#define KEY_SET_VALUE           0x0002
#define KEY_CREATE_SUB_KEY      0x0004
#define KEY_ENUMERATE_SUB_KEYS  0x0008
#define KEY_NOTIFY              0x0010
#define KEY_CREATE_LINK         0x0020
#define KEY_READ                0x20019
#define KEY_WRITE               0x20006
#define KEY_EXECUTE             0x20019
#define KEY_ALL_ACCESS          0xF003F

#define REG_NONE                0
#define REG_SZ                  1
#define REG_EXPAND_SZ           2
#define REG_BINARY              3
#define REG_DWORD               4
#define REG_DWORD_LITTLE_ENDIAN 4
#define REG_DWORD_BIG_ENDIAN    5
#define REG_LINK                6
#define REG_MULTI_SZ            7
#define REG_QWORD               11

/* Registry stubs - always fail on Linux, use config files instead */
static inline LONG RegOpenKeyEx(HKEY hKey, LPCSTR lpSubKey, DWORD ulOptions, DWORD samDesired, PHKEY phkResult) {
    (void)hKey; (void)lpSubKey; (void)ulOptions; (void)samDesired;
    if (phkResult) *phkResult = NULL;
    return ERROR_FILE_NOT_FOUND; /* Registry not available */
}
#define RegOpenKeyExA RegOpenKeyEx

static inline LONG RegQueryValueEx(HKEY hKey, LPCSTR lpValueName, LPDWORD lpReserved, LPDWORD lpType, LPBYTE lpData, LPDWORD lpcbData) {
    (void)hKey; (void)lpValueName; (void)lpReserved; (void)lpType; (void)lpData; (void)lpcbData;
    return ERROR_FILE_NOT_FOUND;
}
#define RegQueryValueExA RegQueryValueEx

static inline LONG RegSetValueEx(HKEY hKey, LPCSTR lpValueName, DWORD Reserved, DWORD dwType, const BYTE* lpData, DWORD cbData) {
    (void)hKey; (void)lpValueName; (void)Reserved; (void)dwType; (void)lpData; (void)cbData;
    return ERROR_FILE_NOT_FOUND;
}
#define RegSetValueExA RegSetValueEx

static inline LONG RegCreateKeyEx(HKEY hKey, LPCSTR lpSubKey, DWORD Reserved, LPSTR lpClass, DWORD dwOptions, DWORD samDesired, void* lpSecurityAttributes, PHKEY phkResult, LPDWORD lpdwDisposition) {
    (void)hKey; (void)lpSubKey; (void)Reserved; (void)lpClass; (void)dwOptions; (void)samDesired; (void)lpSecurityAttributes; (void)lpdwDisposition;
    if (phkResult) *phkResult = NULL;
    return ERROR_FILE_NOT_FOUND;
}
#define RegCreateKeyExA RegCreateKeyEx

static inline LONG RegCloseKey(HKEY hKey) {
    (void)hKey;
    return ERROR_SUCCESS;
}

static inline LONG RegDeleteKey(HKEY hKey, LPCSTR lpSubKey) {
    (void)hKey; (void)lpSubKey;
    return ERROR_FILE_NOT_FOUND;
}
#define RegDeleteKeyA RegDeleteKey

static inline LONG RegDeleteValue(HKEY hKey, LPCSTR lpValueName) {
    (void)hKey; (void)lpValueName;
    return ERROR_FILE_NOT_FOUND;
}
#define RegDeleteValueA RegDeleteValue

#ifdef __cplusplus
}
#endif

#else /* Windows */
/* On Windows, just include the real windows.h */
#include <Windows.h>
#endif /* FF_LINUX */

#endif /* FF_COMPAT_WINDOWS_H */
