/*
 * FreeFalcon Linux Port - Compatibility Types
 *
 * This header provides Windows type definitions for Linux builds.
 * On Windows, these come from windows.h and related headers.
 */

#ifndef FF_COMPAT_TYPES_H
#define FF_COMPAT_TYPES_H

#ifdef FF_LINUX

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <wchar.h>
#include <limits.h>
#include <strings.h>

/* String comparison - Windows uses stricmp, Linux uses strcasecmp */
#define stricmp strcasecmp
#define strnicmp strncasecmp
#define _stricmp strcasecmp
#define _strnicmp strncasecmp

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Basic Windows Types
 * ============================================================ */

/* Integer types */
typedef int8_t          INT8;
typedef int16_t         INT16;
typedef int32_t         INT32;
typedef int64_t         INT64;
typedef int16_t         SHORT;
typedef int32_t         INT;
typedef int32_t         LONG;
typedef int64_t         LONGLONG;

typedef uint8_t         UINT8;
typedef uint16_t        UINT16;
typedef uint32_t        UINT32;
typedef uint64_t        UINT64;
typedef uint16_t        USHORT;
typedef uint32_t        UINT;
typedef uint32_t        ULONG;
typedef uint64_t        ULONGLONG;
typedef uint32_t        DWORD;
typedef uint16_t        WORD;
typedef uint8_t         BYTE;

typedef int32_t         BOOL;
typedef unsigned char   BOOLEAN;
typedef float           FLOAT;
typedef double          DOUBLE;
typedef void            VOID;

/* Microsoft-specific integer types */
#define __int8          int8_t
#define __int16         int16_t
#define __int32         int32_t
#define __int64         int64_t

typedef char            CHAR;
typedef unsigned char   UCHAR;
typedef wchar_t         WCHAR;
typedef char            TCHAR;  /* Assuming ANSI builds */

/* Pointer types */
typedef void*           LPVOID;
typedef const void*     LPCVOID;
typedef void*           PVOID;
typedef DWORD*          LPDWORD;
typedef DWORD*          PDWORD;
typedef WORD*           LPWORD;
typedef WORD*           PWORD;
typedef BYTE*           LPBYTE;
typedef BYTE*           PBYTE;
typedef LONG*           LPLONG;
typedef LONG*           PLONG;
typedef BOOL*           LPBOOL;
typedef BOOL*           PBOOL;
typedef INT*            LPINT;
typedef INT*            PINT;
typedef UINT*           LPUINT;
typedef UINT*           PUINT;

/* String types */
typedef char*           LPSTR;
typedef const char*     LPCSTR;
typedef char*           PSTR;
typedef const char*     PCSTR;
typedef wchar_t*        LPWSTR;
typedef const wchar_t*  LPCWSTR;
typedef wchar_t*        PWSTR;
typedef const wchar_t*  PCWSTR;
typedef char*           LPTSTR;
typedef const char*     LPCTSTR;

/* Size types */
typedef size_t          SIZE_T;
typedef intptr_t        INT_PTR;
typedef uintptr_t       UINT_PTR;
typedef intptr_t        LONG_PTR;
typedef uintptr_t       ULONG_PTR;
typedef uintptr_t       DWORD_PTR;

/* Handle types - use void* on Linux */
typedef void*           HANDLE;
typedef void*           HWND;
typedef void*           HDC;
typedef void*           HINSTANCE;
typedef void*           HMODULE;
typedef void*           HBITMAP;
typedef void*           HBRUSH;
typedef void*           HCURSOR;
typedef void*           HFONT;
typedef void*           HICON;
typedef void*           HMENU;
typedef void*           HPALETTE;
typedef void*           HPEN;
typedef void*           HRGN;
typedef void*           HKEY;
typedef void*           HGLOBAL;
typedef void*           HLOCAL;
typedef void*           HRESOURCE;
typedef void*           HRSRC;
typedef void*           HGDIOBJ;
typedef void*           HACCEL;
typedef void*           HDWP;
typedef void*           HFILE;
typedef void*           HMETAFILE;
typedef void*           HENHMETAFILE;
typedef void*           HTASK;
typedef void*           HCOLORSPACE;
typedef void*           HGLRC;
typedef void*           HMONITOR;

/* Special handle values */
#define INVALID_HANDLE_VALUE    ((HANDLE)(intptr_t)-1)
#define INVALID_FILE_SIZE       ((DWORD)0xFFFFFFFF)
#define INVALID_SET_FILE_POINTER ((DWORD)-1)
#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)

/* HRESULT - COM return type */
typedef int32_t         HRESULT;

/* Success/failure macros for HRESULT */
#define SUCCEEDED(hr)   (((HRESULT)(hr)) >= 0)
#define FAILED(hr)      (((HRESULT)(hr)) < 0)

/* Common HRESULT values */
#define S_OK            ((HRESULT)0)
#define S_FALSE         ((HRESULT)1)
#define E_FAIL          ((HRESULT)0x80004005)
#define E_INVALIDARG    ((HRESULT)0x80070057)
#define E_OUTOFMEMORY   ((HRESULT)0x8007000E)
#define E_NOTIMPL       ((HRESULT)0x80004001)
#define E_POINTER       ((HRESULT)0x80004003)
#define E_NOINTERFACE   ((HRESULT)0x80004002)
#define E_UNEXPECTED    ((HRESULT)0x8000FFFF)
#define E_ACCESSDENIED  ((HRESULT)0x80070005)
#define E_HANDLE        ((HRESULT)0x80070006)
#define E_ABORT         ((HRESULT)0x80004004)
#define E_PENDING       ((HRESULT)0x8000000A)

/* BOOL values */
#ifndef FALSE
#define FALSE           0
#endif
#ifndef TRUE
#define TRUE            1
#endif

/* NULL */
#ifndef NULL
#ifdef __cplusplus
#define NULL            nullptr
#else
#define NULL            ((void*)0)
#endif
#endif

/* Callback conventions - no-op on Linux */
#define CALLBACK
#define WINAPI
#define APIENTRY
#define APIPRIVATE
#define PASCAL
#define CDECL
#define __cdecl
#define _cdecl
#define __stdcall
#define _stdcall
#define __fastcall
#define _fastcall
#define FAR
#define NEAR
#define CONST           const

/* Path/filename limits */
#ifndef _MAX_PATH
#define _MAX_PATH       260
#define _MAX_DRIVE      3
#define _MAX_DIR        256
#define _MAX_FNAME      256
#define _MAX_EXT        256
#define MAX_PATH        _MAX_PATH
#endif

/* Export/import - no-op on Linux */
#define DECLSPEC_IMPORT
#define DECLSPEC_EXPORT
#define WINBASEAPI
#define WINUSERAPI
#define WINGDIAPI

/* Function pointer types - must be after CALLBACK/WINAPI definitions */
typedef INT_PTR (WINAPI *FARPROC)(void);
typedef INT_PTR (WINAPI *NEARPROC)(void);
typedef INT_PTR (WINAPI *PROC)(void);

/* Inline */
#ifndef FORCEINLINE
#define FORCEINLINE     inline __attribute__((always_inline))
#endif

/* SSE alignment macro */
#ifndef _MM_ALIGN16
#define _MM_ALIGN16     __attribute__((aligned(16)))
#endif

/* Struct packing */
#define UNALIGNED

/* Wide string literal */
#define _T(x)           x
#define TEXT(x)         x
#define __TEXT(x)       x

/* min/max - DANGER: These macros conflict with C++ std::min/max and
 * std::numeric_limits<>::min()/max(). They are required by legacy Windows code.
 *
 * IMPORTANT: Files that include C++ standard headers should define NOMINMAX
 * before including this header to avoid conflicts.
 */
#ifdef __cplusplus
} /* Close extern "C" for C++ code below */
#endif

/* min/max - Note: Defining these as macros conflicts with C++ STL.
 * Instead, we define NOMINMAX globally and use std::min/std::max.
 * For mixed-type calls, use explicit casts or the ff_min/ff_max templates.
 */
#define NOMINMAX
#ifdef __cplusplus
#include <algorithm>
/* Templates for mixed-type min/max like Windows macros provide */
template<typename T, typename U>
inline auto ff_min(T a, U b) -> decltype(a < b ? a : b) { return a < b ? a : b; }
template<typename T, typename U>
inline auto ff_max(T a, U b) -> decltype(a > b ? a : b) { return a > b ? a : b; }
using std::min;
using std::max;
#else
/* C mode - use macros */
#ifndef min
#define min(a,b)        (((a) < (b)) ? (a) : (b))
#endif
#ifndef max
#define max(a,b)        (((a) > (b)) ? (a) : (b))
#endif
#endif /* __cplusplus */

#ifdef __cplusplus
extern "C" { /* Reopen extern "C" */
#endif

/* MAKEWORD, MAKELONG, etc. */
#define MAKEWORD(a, b)      ((WORD)(((BYTE)(((DWORD_PTR)(a)) & 0xff)) | ((WORD)((BYTE)(((DWORD_PTR)(b)) & 0xff))) << 8))
#define MAKELONG(a, b)      ((LONG)(((WORD)(((DWORD_PTR)(a)) & 0xffff)) | ((DWORD)((WORD)(((DWORD_PTR)(b)) & 0xffff))) << 16))
#define LOWORD(l)           ((WORD)(((DWORD_PTR)(l)) & 0xffff))
#define HIWORD(l)           ((WORD)((((DWORD_PTR)(l)) >> 16) & 0xffff))
#define LOBYTE(w)           ((BYTE)(((DWORD_PTR)(w)) & 0xff))
#define HIBYTE(w)           ((BYTE)((((DWORD_PTR)(w)) >> 8) & 0xff))

/* RGB macro */
#define RGB(r,g,b)          ((DWORD)(((BYTE)(r)|((WORD)((BYTE)(g))<<8))|(((DWORD)(BYTE)(b))<<16)))
#define GetRValue(rgb)      (LOBYTE(rgb))
#define GetGValue(rgb)      (LOBYTE(((WORD)(rgb)) >> 8))
#define GetBValue(rgb)      (LOBYTE((rgb)>>16))

/* COLORREF */
typedef DWORD           COLORREF;
typedef DWORD*          LPCOLORREF;

/* WPARAM/LPARAM for message handling */
typedef UINT_PTR        WPARAM;
typedef LONG_PTR        LPARAM;
typedef LONG_PTR        LRESULT;

/* ATOM */
typedef WORD            ATOM;

/* Large integer */
typedef union _LARGE_INTEGER {
    struct {
        DWORD LowPart;
        LONG  HighPart;
    } u;
    struct {
        DWORD LowPart;
        LONG  HighPart;
    };
    LONGLONG QuadPart;
} LARGE_INTEGER, *PLARGE_INTEGER;

typedef union _ULARGE_INTEGER {
    struct {
        DWORD LowPart;
        DWORD HighPart;
    } u;
    struct {
        DWORD LowPart;
        DWORD HighPart;
    };
    ULONGLONG QuadPart;
} ULARGE_INTEGER, *PULARGE_INTEGER;

/* GUID structure */
typedef struct _GUID {
    DWORD   Data1;
    WORD    Data2;
    WORD    Data3;
    BYTE    Data4[8];
} GUID, *LPGUID;

typedef GUID IID;
typedef GUID CLSID;
#ifdef __cplusplus
typedef const GUID& REFGUID;
#else
typedef const GUID* REFGUID;
#endif
typedef const GUID* LPCGUID;

/* REFIID and REFCLSID differ between C and C++:
 * In C:   const pointer to GUID
 * In C++: const reference to GUID (allows passing GUID by value)
 */
#ifdef __cplusplus
typedef const IID& REFIID;
typedef const CLSID& REFCLSID;
#else
typedef const IID* REFIID;
typedef const CLSID* REFCLSID;
#endif

/* GUID comparison macros/functions */
#ifdef __cplusplus
} /* close extern "C" for C++ inline functions */

/* GUID_NULL - empty GUID */
static const GUID GUID_NULL = {0, 0, 0, {0, 0, 0, 0, 0, 0, 0, 0}};

/* IsEqualGUID - compare two GUIDs */
static inline bool IsEqualGUID(const GUID& g1, const GUID& g2) {
    return g1.Data1 == g2.Data1 && g1.Data2 == g2.Data2 && g1.Data3 == g2.Data3 &&
           g1.Data4[0] == g2.Data4[0] && g1.Data4[1] == g2.Data4[1] &&
           g1.Data4[2] == g2.Data4[2] && g1.Data4[3] == g2.Data4[3] &&
           g1.Data4[4] == g2.Data4[4] && g1.Data4[5] == g2.Data4[5] &&
           g1.Data4[6] == g2.Data4[6] && g1.Data4[7] == g2.Data4[7];
}

/* IsEqualIID - compare two IIDs (same as GUIDs) */
#define IsEqualIID(iid1, iid2) IsEqualGUID(iid1, iid2)
#define IsEqualCLSID(clsid1, clsid2) IsEqualGUID(clsid1, clsid2)

extern "C" { /* reopen extern "C" */
#else
/* C version using memcmp */
#define GUID_NULL ((GUID){0, 0, 0, {0, 0, 0, 0, 0, 0, 0, 0}})
#define IsEqualGUID(g1, g2) (memcmp(&(g1), &(g2), sizeof(GUID)) == 0)
#define IsEqualIID(iid1, iid2) IsEqualGUID(iid1, iid2)
#define IsEqualCLSID(clsid1, clsid2) IsEqualGUID(clsid1, clsid2)
#endif

/* RECT structure */
typedef struct tagRECT {
    LONG left;
    LONG top;
    LONG right;
    LONG bottom;
} RECT, *PRECT, *LPRECT;
typedef const RECT* LPCRECT;

/* POINT structure */
typedef struct tagPOINT {
    LONG x;
    LONG y;
} POINT, *PPOINT, *LPPOINT;

/* SIZE structure */
typedef struct tagSIZE {
    LONG cx;
    LONG cy;
} SIZE, *PSIZE, *LPSIZE;

/* POINTS structure */
typedef struct tagPOINTS {
    SHORT x;
    SHORT y;
} POINTS, *PPOINTS, *LPPOINTS;

/* FILETIME structure */
typedef struct _FILETIME {
    DWORD dwLowDateTime;
    DWORD dwHighDateTime;
} FILETIME, *PFILETIME, *LPFILETIME;

/* SYSTEMTIME structure */
typedef struct _SYSTEMTIME {
    WORD wYear;
    WORD wMonth;
    WORD wDayOfWeek;
    WORD wDay;
    WORD wHour;
    WORD wMinute;
    WORD wSecond;
    WORD wMilliseconds;
} SYSTEMTIME, *PSYSTEMTIME, *LPSYSTEMTIME;

/* Critical section - will need proper implementation */
typedef struct _RTL_CRITICAL_SECTION {
    void* DebugInfo;
    LONG LockCount;
    LONG RecursionCount;
    HANDLE OwningThread;
    HANDLE LockSemaphore;
    ULONG_PTR SpinCount;
} RTL_CRITICAL_SECTION, *PRTL_CRITICAL_SECTION;

typedef RTL_CRITICAL_SECTION CRITICAL_SECTION;
typedef PRTL_CRITICAL_SECTION PCRITICAL_SECTION;
typedef PRTL_CRITICAL_SECTION LPCRITICAL_SECTION;

/* Security attributes */
typedef struct _SECURITY_ATTRIBUTES {
    DWORD nLength;
    LPVOID lpSecurityDescriptor;
    BOOL bInheritHandle;
} SECURITY_ATTRIBUTES, *PSECURITY_ATTRIBUTES, *LPSECURITY_ATTRIBUTES;

/* Overlapped structure for async I/O */
typedef struct _OVERLAPPED {
    ULONG_PTR Internal;
    ULONG_PTR InternalHigh;
    union {
        struct {
            DWORD Offset;
            DWORD OffsetHigh;
        };
        PVOID Pointer;
    };
    HANDLE hEvent;
} OVERLAPPED, *LPOVERLAPPED;

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_TYPES_H */
