/*
 * FreeFalcon Linux Port - ocidl.h compatibility stub
 *
 * Windows OLE Control IDL headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_OCIDL_H
#define FF_COMPAT_OCIDL_H

#ifdef FF_LINUX

#include <windows.h>
#include "objbase.h"
#include "oaidl.h"

/* Forward declarations for OLE control interfaces */
typedef struct IConnectionPoint IConnectionPoint;
typedef struct IConnectionPointContainer IConnectionPointContainer;
typedef struct IEnumConnectionPoints IEnumConnectionPoints;
typedef struct IEnumConnections IEnumConnections;
typedef struct IPropertyNotifySink IPropertyNotifySink;
typedef struct IProvideClassInfo IProvideClassInfo;
typedef struct IProvideClassInfo2 IProvideClassInfo2;
typedef struct IOleControl IOleControl;
typedef struct IOleControlSite IOleControlSite;
typedef struct ISimpleFrameSite ISimpleFrameSite;
typedef struct IErrorLog IErrorLog;
typedef struct IPropertyBag IPropertyBag;
typedef struct IPersistPropertyBag IPersistPropertyBag;
typedef struct IPersistStreamInit IPersistStreamInit;
typedef struct IPersistMemory IPersistMemory;

/* CONNECTDATA structure */
typedef struct tagCONNECTDATA {
    IUnknown* pUnk;
    DWORD dwCookie;
} CONNECTDATA, *LPCONNECTDATA;

/* CAUUID structure */
typedef struct tagCAUUID {
    ULONG cElems;
    GUID* pElems;
} CAUUID, *LPCAUUID;

/* PROPPAGEINFO structure */
typedef struct tagPROPPAGEINFO {
    ULONG cb;
    LPOLESTR pszTitle;
    SIZE size;
    LPOLESTR pszDocString;
    LPOLESTR pszHelpFile;
    DWORD dwHelpContext;
} PROPPAGEINFO, *LPPROPPAGEINFO;

/* CONTROLINFO structure */
typedef struct tagCONTROLINFO {
    ULONG cb;
    HACCEL hAccel;
    USHORT cAccel;
    DWORD dwFlags;
} CONTROLINFO, *LPCONTROLINFO;

/* POINTF structure */
typedef struct tagPOINTF {
    FLOAT x;
    FLOAT y;
} POINTF, *LPPOINTF;

/* OLE_COLOR */
typedef DWORD OLE_COLOR;

/* XFORMCOORDS values */
#define XFORMCOORDS_POSITION            0x1
#define XFORMCOORDS_SIZE                0x2
#define XFORMCOORDS_HIMETRICTOCONTAINER 0x4
#define XFORMCOORDS_CONTAINERTOHIMETRIC 0x8
#define XFORMCOORDS_EVENTCOMPAT         0x10

/* CTRLINFO values */
#define CTRLINFO_EATS_RETURN    1
#define CTRLINFO_EATS_ESCAPE    2

/* GUIDKIND values */
#define GUIDKIND_DEFAULT_SOURCE_DISP_IID    1

/* PROPPAGESTATUS values */
#define PROPPAGESTATUS_DIRTY    0x1
#define PROPPAGESTATUS_VALIDATE 0x2
#define PROPPAGESTATUS_CLEAN    0x4

/* QACONTAINER flags */
#define QACONTAINER_SHOWHATCHING        0x1
#define QACONTAINER_SHOWGRABHANDLES     0x2
#define QACONTAINER_USERMODE            0x4
#define QACONTAINER_DISPLAYASDEFAULT    0x8
#define QACONTAINER_UIDEAD              0x10
#define QACONTAINER_AUTOCLIP            0x20
#define QACONTAINER_MESSAGEREFLECT      0x40
#define QACONTAINER_SUPPORTSMNEMONICS   0x80

/* IEnumConnectionPoints interface */
#undef INTERFACE
#define INTERFACE IEnumConnectionPoints

DECLARE_INTERFACE_(IEnumConnectionPoints, IUnknown)
{
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void** ppvObject) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
    STDMETHOD(Next)(THIS_ ULONG cConnections, IConnectionPoint** ppCP, ULONG* pcFetched) PURE;
    STDMETHOD(Skip)(THIS_ ULONG cConnections) PURE;
    STDMETHOD(Reset)(THIS) PURE;
    STDMETHOD(Clone)(THIS_ IEnumConnectionPoints** ppEnum) PURE;
};

/* IConnectionPointContainer interface */
#undef INTERFACE
#define INTERFACE IConnectionPointContainer

DECLARE_INTERFACE_(IConnectionPointContainer, IUnknown)
{
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void** ppvObject) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
    STDMETHOD(EnumConnectionPoints)(THIS_ IEnumConnectionPoints** ppEnum) PURE;
    STDMETHOD(FindConnectionPoint)(THIS_ REFIID riid, IConnectionPoint** ppCP) PURE;
};

/* IConnectionPoint interface */
#undef INTERFACE
#define INTERFACE IConnectionPoint

DECLARE_INTERFACE_(IConnectionPoint, IUnknown)
{
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void** ppvObject) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
    STDMETHOD(GetConnectionInterface)(THIS_ IID* pIID) PURE;
    STDMETHOD(GetConnectionPointContainer)(THIS_ IConnectionPointContainer** ppCPC) PURE;
    STDMETHOD(Advise)(THIS_ IUnknown* pUnkSink, DWORD* pdwCookie) PURE;
    STDMETHOD(Unadvise)(THIS_ DWORD dwCookie) PURE;
    STDMETHOD(EnumConnections)(THIS_ IEnumConnections** ppEnum) PURE;
};

#endif /* FF_LINUX */
#endif /* FF_COMPAT_OCIDL_H */
