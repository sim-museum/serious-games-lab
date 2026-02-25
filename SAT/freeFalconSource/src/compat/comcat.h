/*
 * FreeFalcon Linux Port - comcat.h stub
 *
 * Component Category COM interfaces - stub implementation.
 * These are Windows-specific COM interfaces for component categorization.
 */

#ifndef FF_COMPAT_COMCAT_H
#define FF_COMPAT_COMCAT_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "objbase.h"

#ifdef __cplusplus
extern "C" {
#endif

/* LCID - Locale ID (must be defined before use) */
#ifndef LCID
typedef DWORD LCID;
#endif

/* CATID is same as GUID */
typedef GUID CATID;
typedef const CATID* REFCATID;

/* CATEGORYINFO structure */
typedef struct tagCATEGORYINFO {
    CATID  catid;
    LCID   lcid;
    WCHAR  szDescription[128];
} CATEGORYINFO, *LPCATEGORYINFO;

/* Standard Component Categories Manager CLSID */
static const CLSID CLSID_StdComponentCategoriesMgr =
    {0x0002E005, 0x0000, 0x0000, {0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};

/* ICatRegister interface - stub */
#ifdef __cplusplus
struct ICatRegister {
    virtual HRESULT RegisterCategories(ULONG cCategories, CATEGORYINFO rgCategoryInfo[]) = 0;
    virtual HRESULT UnRegisterCategories(ULONG cCategories, CATID rgcatid[]) = 0;
    virtual HRESULT RegisterClassImplCategories(REFCLSID rclsid, ULONG cCategories, CATID rgcatid[]) = 0;
    virtual HRESULT UnRegisterClassImplCategories(REFCLSID rclsid, ULONG cCategories, CATID rgcatid[]) = 0;
    virtual HRESULT RegisterClassReqCategories(REFCLSID rclsid, ULONG cCategories, CATID rgcatid[]) = 0;
    virtual HRESULT UnRegisterClassReqCategories(REFCLSID rclsid, ULONG cCategories, CATID rgcatid[]) = 0;
    virtual ULONG AddRef() = 0;
    virtual ULONG Release() = 0;
};
#endif

/* ICatRegister IID */
static const IID IID_ICatRegister =
    {0x0002E012, 0x0000, 0x0000, {0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_COMCAT_H */
