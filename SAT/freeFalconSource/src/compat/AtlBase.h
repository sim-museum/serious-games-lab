/*
 * FreeFalcon Linux Port - ATL Base compatibility stub
 *
 * Windows ATL (Active Template Library) replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_ATLBASE_H
#define FF_COMPAT_ATLBASE_H

#ifdef FF_LINUX

#include <windows.h>
#include "wtypes.h"
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

/* OLE string functions - stub implementations */
static inline BSTR SysAllocString(const OLECHAR* sz) {
    if (!sz) return NULL;
    size_t len = wcslen(sz);
    BSTR result = (BSTR)malloc((len + 1) * sizeof(OLECHAR));
    if (result) {
        wcscpy(result, sz);
    }
    return result;
}

static inline BSTR SysAllocStringLen(const OLECHAR* str, unsigned int len) {
    BSTR result = (BSTR)malloc((len + 1) * sizeof(OLECHAR));
    if (result) {
        if (str) {
            wcsncpy(result, str, len);
        }
        result[len] = L'\0';
    }
    return result;
}

static inline void SysFreeString(BSTR bstr) {
    if (bstr) free(bstr);
}

/* COM smart pointer template stub */
template <typename T>
class CComPtr {
public:
    T* p;
    CComPtr() : p(NULL) {}
    CComPtr(T* lp) : p(lp) { if (p) p->AddRef(); }
    ~CComPtr() { if (p) p->Release(); }
    T* operator->() const { return p; }
    operator T*() const { return p; }
    T** operator&() { return &p; }
    T* operator=(T* lp) {
        if (p) p->Release();
        p = lp;
        if (p) p->AddRef();
        return p;
    }
};

/* CComBSTR stub */
class CComBSTR {
public:
    BSTR m_str;
    CComBSTR() : m_str(NULL) {}
    CComBSTR(const char* str) { m_str = SysAllocString((const OLECHAR*)str); }
    CComBSTR(int len, const char* str) { m_str = SysAllocStringLen((const OLECHAR*)str, len); }
    ~CComBSTR() { if (m_str) SysFreeString(m_str); }
    operator BSTR() const { return m_str; }
};

/* COM Object map - stub */
struct _ATL_OBJMAP_ENTRY {
    const void* pclsid;
    void* pfnGetClassObject;
    void* pfnCreateInstance;
    void* pCF;
    DWORD dwRegister;
    void* pfnGetObjectDescription;
    void* pfnGetCategoryMap;
    void (*pfnObjectMain)(bool bStarting);
};

typedef _ATL_OBJMAP_ENTRY ATL_OBJMAP_ENTRY;

/* BEGIN_OBJECT_MAP and END_OBJECT_MAP macros */
#define BEGIN_OBJECT_MAP(x) static _ATL_OBJMAP_ENTRY x[] = {
#define END_OBJECT_MAP() {NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL}};
#define OBJECT_ENTRY(clsid, class) {NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL},

/* CComModule stub */
class CComModule {
public:
    HINSTANCE m_hInst;

    void Init(_ATL_OBJMAP_ENTRY* p, HINSTANCE h, void* = NULL) {
        (void)p;
        m_hInst = h;
    }

    void Term() {}

    HINSTANCE GetModuleInstance() { return m_hInst; }
};

/* BEGIN_COM_MAP, COM_INTERFACE_ENTRY, END_COM_MAP stubs */
#define BEGIN_COM_MAP(x)
#define COM_INTERFACE_ENTRY(x)
#define END_COM_MAP()

/* DECLARE_REGISTRY_RESOURCEID stub */
#define DECLARE_REGISTRY_RESOURCEID(x)

/* Extern _Module declaration support */
extern CComModule _Module;

#endif /* FF_LINUX */
#endif /* FF_COMPAT_ATLBASE_H */
