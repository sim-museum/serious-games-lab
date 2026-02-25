/*
 * FreeFalcon Linux Port - crashhandler stub
 *
 * Provides empty implementations of crash handler functions for Linux.
 * The Windows crash handler uses SEH and Windows-specific APIs.
 */

#ifdef FF_LINUX

#include "windows.h"

// Stub type for the filter function
typedef LONG(*PFNCHFILTFN)(void* pExPtrs);

extern "C" {

BOOL SetCrashHandlerFilter(PFNCHFILTFN pFn)
{
    (void)pFn;
    return TRUE;  // Pretend success
}

BOOL AddCrashHandlerLimitModule(HMODULE hMod)
{
    (void)hMod;
    return TRUE;
}

UINT GetLimitModuleCount(void)
{
    return 0;
}

int GetLimitModulesArray(HMODULE* pahMod, UINT uiSize)
{
    (void)pahMod;
    (void)uiSize;
    return 1;  // GLMA_SUCCESS
}

LPCTSTR GetFaultReason(void* pExPtrs)
{
    (void)pExPtrs;
    return "Unknown fault (Linux stub)";
}

BOOL GetFaultReasonVB(void* pExPtrs, LPTSTR szBuff, UINT uiSize)
{
    (void)pExPtrs;
    if (szBuff && uiSize > 0) {
        szBuff[0] = '\0';
    }
    return FALSE;
}

LPCTSTR GetFirstStackTraceString(DWORD dwOpts, void* pExPtrs)
{
    (void)dwOpts;
    (void)pExPtrs;
    return NULL;
}

LPCTSTR GetNextStackTraceString(DWORD dwOpts, void* pExPtrs)
{
    (void)dwOpts;
    (void)pExPtrs;
    return NULL;
}

BOOL GetFirstStackTraceStringVB(DWORD dwOpts, void* pExPtrs, LPTSTR szBuff, UINT uiSize)
{
    (void)dwOpts;
    (void)pExPtrs;
    if (szBuff && uiSize > 0) {
        szBuff[0] = '\0';
    }
    return FALSE;
}

BOOL GetNextStackTraceStringVB(DWORD dwOpts, void* pExPtrs, LPTSTR szBuff, UINT uiSize)
{
    (void)dwOpts;
    (void)pExPtrs;
    if (szBuff && uiSize > 0) {
        szBuff[0] = '\0';
    }
    return FALSE;
}

LPCTSTR GetRegisterString(void* pExPtrs)
{
    (void)pExPtrs;
    return NULL;
}

BOOL GetRegisterStringVB(void* pExPtrs, LPTSTR szBuff, UINT uiSize)
{
    (void)pExPtrs;
    if (szBuff && uiSize > 0) {
        szBuff[0] = '\0';
    }
    return FALSE;
}

// MinidumpWriteDump stub
BOOL MiniDumpWriteDump(
    HANDLE hProcess,
    DWORD ProcessId,
    HANDLE hFile,
    int DumpType,
    void* ExceptionParam,
    void* UserStreamParam,
    void* CallbackParam)
{
    (void)hProcess;
    (void)ProcessId;
    (void)hFile;
    (void)DumpType;
    (void)ExceptionParam;
    (void)UserStreamParam;
    (void)CallbackParam;
    return FALSE;
}

}  // extern "C"

#endif  // FF_LINUX
