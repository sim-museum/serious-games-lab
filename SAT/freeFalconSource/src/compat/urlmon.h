/*
 * FreeFalcon Linux Port - urlmon.h compatibility
 *
 * Windows URL moniker functions replacement (stubs)
 */

#ifndef FF_COMPAT_URLMON_H
#define FF_COMPAT_URLMON_H

#ifdef FF_LINUX

#include "windows.h"

#ifdef __cplusplus
extern "C" {
#endif

/* URLDownloadToFile stub - used only in commented-out code */
static inline HRESULT URLDownloadToFile(
    void* pCaller,
    const char* szURL,
    const char* szFileName,
    DWORD dwReserved,
    void* lpfnCB)
{
    (void)pCaller;
    (void)szURL;
    (void)szFileName;
    (void)dwReserved;
    (void)lpfnCB;
    return E_NOTIMPL; /* Not implemented on Linux */
}

#define URLDownloadToFileA URLDownloadToFile
#define URLDownloadToFileW URLDownloadToFile

/* IsValidURL stub */
static inline HRESULT IsValidURL(
    void* pBC,
    const wchar_t* szURL,
    DWORD dwReserved)
{
    (void)pBC;
    (void)szURL;
    (void)dwReserved;
    return S_FALSE; /* Not a valid URL handler */
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_URLMON_H */
