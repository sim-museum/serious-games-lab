/*
 * FreeFalcon Linux Port - ATL COM compatibility stub
 *
 * Windows ATL COM support replacement.
 */

#ifndef FF_COMPAT_ATLCOM_H
#define FF_COMPAT_ATLCOM_H

#ifdef FF_LINUX

#include "AtlBase.h"

/* CComObjectRootEx stub */
template <typename ThreadModel>
class CComObjectRootEx {
public:
    ULONG InternalAddRef() { return 1; }
    ULONG InternalRelease() { return 1; }
};

/* CComMultiThreadModel stub */
class CComMultiThreadModel {};
class CComSingleThreadModel {};

/* CComCreator stub */
template <typename T>
class CComCreator {};

/* CComCoClass stub */
template <typename T, const CLSID* pclsid = NULL>
class CComCoClass {};

/* CComObject stub */
template <typename T>
class CComObject : public T {
public:
    static HRESULT CreateInstance(CComObject<T>** pp) {
        *pp = new CComObject<T>();
        return S_OK;
    }
};

#endif /* FF_LINUX */
#endif /* FF_COMPAT_ATLCOM_H */
