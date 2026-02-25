/*
 * FreeFalcon Linux Port - ATL (Active Template Library) stub
 *
 * ATL is Windows-specific. This provides minimal stubs.
 */

#ifndef FF_COMPAT_ATLBASE_H
#define FF_COMPAT_ATLBASE_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <assert.h>

/* ATL macros */
#ifndef ATLASSERT
#define ATLASSERT(x) assert(x)
#endif

#ifndef ATLTRACE
#define ATLTRACE(...)
#endif

/* CComModule stub */
class CComModule {
public:
    CComModule() {}
    virtual ~CComModule() {}

    HINSTANCE GetModuleInstance() { return NULL; }
    HINSTANCE GetResourceInstance() { return NULL; }
    void Init(void* p, HINSTANCE h) { (void)p; (void)h; }
    void Term() {}
};

#endif /* FF_LINUX */
#endif /* FF_COMPAT_ATLBASE_H */
