/*
 * FreeFalcon Linux Port - objbase.h compatibility
 *
 * Windows COM base header stub.
 */

#ifndef FF_COMPAT_OBJBASE_H
#define FF_COMPAT_OBJBASE_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <string.h>  /* for memcmp */

#ifdef __cplusplus
extern "C" {
#endif

/* Calling conventions - no-op on Linux */
#ifndef STDMETHODCALLTYPE
#define STDMETHODCALLTYPE
#endif
#ifndef STDMETHOD
#define STDMETHOD(method) virtual HRESULT STDMETHODCALLTYPE method
#endif
#ifndef STDMETHOD_
#define STDMETHOD_(type, method) virtual type STDMETHODCALLTYPE method
#endif
#ifndef PURE
#define PURE = 0
#endif

/* COM initialization flags */
#define COINIT_MULTITHREADED     0x0
#define COINIT_APARTMENTTHREADED 0x2
#define COINIT_DISABLE_OLE1DDE   0x4
#define COINIT_SPEED_OVER_MEMORY 0x8

/* CLSCTX - class context flags */
#define CLSCTX_INPROC_SERVER          0x1
#define CLSCTX_INPROC_HANDLER         0x2
#define CLSCTX_LOCAL_SERVER           0x4
#define CLSCTX_INPROC_SERVER16        0x8
#define CLSCTX_REMOTE_SERVER          0x10
#define CLSCTX_INPROC_HANDLER16       0x20
#define CLSCTX_RESERVED1              0x40
#define CLSCTX_RESERVED2              0x80
#define CLSCTX_RESERVED3              0x100
#define CLSCTX_RESERVED4              0x200
#define CLSCTX_NO_CODE_DOWNLOAD       0x400
#define CLSCTX_RESERVED5              0x800
#define CLSCTX_NO_CUSTOM_MARSHAL      0x1000
#define CLSCTX_ENABLE_CODE_DOWNLOAD   0x2000
#define CLSCTX_NO_FAILURE_LOG         0x4000
#define CLSCTX_DISABLE_AAA            0x8000
#define CLSCTX_ENABLE_AAA             0x10000
#define CLSCTX_FROM_DEFAULT_CONTEXT   0x20000
#define CLSCTX_ALL                    (CLSCTX_INPROC_SERVER | CLSCTX_INPROC_HANDLER | CLSCTX_LOCAL_SERVER | CLSCTX_REMOTE_SERVER)
#define CLSCTX_SERVER                 (CLSCTX_INPROC_SERVER | CLSCTX_LOCAL_SERVER | CLSCTX_REMOTE_SERVER)

/* COM initialization stubs */
static inline HRESULT CoInitialize(LPVOID pvReserved) {
    (void)pvReserved;
    return S_OK;
}

static inline HRESULT CoInitializeEx(LPVOID pvReserved, DWORD dwCoInit) {
    (void)pvReserved;
    (void)dwCoInit;
    return S_OK;
}

static inline void CoUninitialize(void) {
}

/* CoCreateInstance stub - always fails since we don't support COM */
static inline HRESULT CoCreateInstance(REFCLSID rclsid, LPVOID pUnkOuter, DWORD dwClsContext, REFIID riid, LPVOID* ppv) {
    (void)rclsid;
    (void)pUnkOuter;
    (void)dwClsContext;
    (void)riid;
    if (ppv) *ppv = NULL;
    return E_NOTIMPL;
}

/* Memory allocation stubs */
static inline void* CoTaskMemAlloc(SIZE_T cb) {
    return malloc(cb);
}

static inline void* CoTaskMemRealloc(LPVOID pv, SIZE_T cb) {
    return realloc(pv, cb);
}

static inline void CoTaskMemFree(LPVOID pv) {
    free(pv);
}

/* GUID comparison - defined in compat_types.h:
 * IsEqualGUID, IsEqualIID, IsEqualCLSID
 */

/* IUnknown interface - base for all COM interfaces */
#ifdef __cplusplus
struct IUnknown {
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) = 0;
    virtual ULONG AddRef() = 0;
    virtual ULONG Release() = 0;
};
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_OBJBASE_H */
