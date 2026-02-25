/*
 * FreeFalcon Linux Port - oaidl.h compatibility stub
 *
 * Windows OLE Automation IDL headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_OAIDL_H
#define FF_COMPAT_OAIDL_H

#ifdef FF_LINUX

#include <windows.h>
#include "objbase.h"

/* VARIANT type */
typedef unsigned short VARTYPE;

/* VARIANT type constants */
#define VT_EMPTY            0
#define VT_NULL             1
#define VT_I2               2
#define VT_I4               3
#define VT_R4               4
#define VT_R8               5
#define VT_CY               6
#define VT_DATE             7
#define VT_BSTR             8
#define VT_DISPATCH         9
#define VT_ERROR            10
#define VT_BOOL             11
#define VT_VARIANT          12
#define VT_UNKNOWN          13
#define VT_DECIMAL          14
#define VT_I1               16
#define VT_UI1              17
#define VT_UI2              18
#define VT_UI4              19
#define VT_I8               20
#define VT_UI8              21
#define VT_INT              22
#define VT_UINT             23
#define VT_VOID             24
#define VT_HRESULT          25
#define VT_PTR              26
#define VT_SAFEARRAY        27
#define VT_CARRAY           28
#define VT_USERDEFINED      29
#define VT_LPSTR            30
#define VT_LPWSTR           31
#define VT_RECORD           36
#define VT_FILETIME         64
#define VT_BLOB             65
#define VT_STREAM           66
#define VT_STORAGE          67
#define VT_STREAMED_OBJECT  68
#define VT_STORED_OBJECT    69
#define VT_BLOB_OBJECT      70
#define VT_CF               71
#define VT_CLSID            72
#define VT_BSTR_BLOB        0x0fff
#define VT_VECTOR           0x1000
#define VT_ARRAY            0x2000
#define VT_BYREF            0x4000
#define VT_RESERVED         0x8000

/* VARIANT_BOOL */
typedef short VARIANT_BOOL;
#define VARIANT_TRUE  ((VARIANT_BOOL)-1)
#define VARIANT_FALSE ((VARIANT_BOOL)0)

/* Currency type */
typedef struct tagCY {
    LONGLONG int64;
} CY;

/* Date type */
typedef double DATE;

/* DECIMAL type */
typedef struct tagDEC {
    USHORT wReserved;
    union {
        struct {
            BYTE scale;
            BYTE sign;
        } s;
        USHORT signscale;
    } u;
    ULONG Hi32;
    union {
        struct {
            ULONG Lo32;
            ULONG Mid32;
        } s2;
        ULONGLONG Lo64;
    } u2;
} DECIMAL;

/* Forward declarations */
typedef struct IDispatch IDispatch;
typedef struct ITypeInfo ITypeInfo;
typedef struct ITypeLib ITypeLib;
typedef struct IRecordInfo IRecordInfo;

/* SAFEARRAY */
typedef struct tagSAFEARRAYBOUND {
    ULONG cElements;
    LONG lLbound;
} SAFEARRAYBOUND, *LPSAFEARRAYBOUND;

typedef struct tagSAFEARRAY {
    USHORT cDims;
    USHORT fFeatures;
    ULONG cbElements;
    ULONG cLocks;
    PVOID pvData;
    SAFEARRAYBOUND rgsabound[1];
} SAFEARRAY, *LPSAFEARRAY;

/* VARIANT structure */
typedef struct tagVARIANT {
    VARTYPE vt;
    WORD wReserved1;
    WORD wReserved2;
    WORD wReserved3;
    union {
        LONGLONG llVal;
        LONG lVal;
        BYTE bVal;
        SHORT iVal;
        FLOAT fltVal;
        DOUBLE dblVal;
        VARIANT_BOOL boolVal;
        SCODE scode;
        CY cyVal;
        DATE date;
        BSTR bstrVal;
        IUnknown* punkVal;
        IDispatch* pdispVal;
        SAFEARRAY* parray;
        BYTE* pbVal;
        SHORT* piVal;
        LONG* plVal;
        LONGLONG* pllVal;
        FLOAT* pfltVal;
        DOUBLE* pdblVal;
        VARIANT_BOOL* pboolVal;
        SCODE* pscode;
        CY* pcyVal;
        DATE* pdate;
        BSTR* pbstrVal;
        IUnknown** ppunkVal;
        IDispatch** ppdispVal;
        SAFEARRAY** pparray;
        struct tagVARIANT* pvarVal;
        PVOID byref;
        CHAR cVal;
        USHORT uiVal;
        ULONG ulVal;
        ULONGLONG ullVal;
        INT intVal;
        UINT uintVal;
        DECIMAL* pdecVal;
        CHAR* pcVal;
        USHORT* puiVal;
        ULONG* pulVal;
        ULONGLONG* pullVal;
        INT* pintVal;
        UINT* puintVal;
    } n1;
} VARIANT, *LPVARIANT;

typedef VARIANT VARIANTARG;
typedef VARIANTARG* LPVARIANTARG;

/* DISPID */
typedef LONG DISPID;
typedef DISPID MEMBERID;
#define DISPID_UNKNOWN     (-1)
#define DISPID_VALUE       0
#define DISPID_PROPERTYPUT (-3)
#define DISPID_NEWENUM     (-4)
#define DISPID_EVALUATE    (-5)
#define DISPID_CONSTRUCTOR (-6)
#define DISPID_DESTRUCTOR  (-7)
#define DISPID_COLLECT     (-8)

/* DISPPARAMS */
typedef struct tagDISPPARAMS {
    VARIANTARG* rgvarg;
    DISPID* rgdispidNamedArgs;
    UINT cArgs;
    UINT cNamedArgs;
} DISPPARAMS;

/* EXCEPINFO */
typedef struct tagEXCEPINFO {
    WORD wCode;
    WORD wReserved;
    BSTR bstrSource;
    BSTR bstrDescription;
    BSTR bstrHelpFile;
    DWORD dwHelpContext;
    PVOID pvReserved;
    HRESULT (__stdcall *pfnDeferredFillIn)(struct tagEXCEPINFO*);
    SCODE scode;
} EXCEPINFO, *LPEXCEPINFO;

/* IDispatch interface */
#undef INTERFACE
#define INTERFACE IDispatch

DECLARE_INTERFACE_(IDispatch, IUnknown)
{
    /* IUnknown */
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void** ppvObject) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
    /* IDispatch */
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void** ppvObject) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
};

/* Variant helper functions */
static inline void VariantInit(VARIANT* pvarg) {
    if (pvarg) {
        pvarg->vt = VT_EMPTY;
    }
}

static inline HRESULT VariantClear(VARIANT* pvarg) {
    if (pvarg) {
        pvarg->vt = VT_EMPTY;
    }
    return S_OK;
}

static inline HRESULT VariantCopy(VARIANT* pvargDest, const VARIANT* pvargSrc) {
    if (pvargDest && pvargSrc) {
        *pvargDest = *pvargSrc;
    }
    return S_OK;
}

#endif /* FF_LINUX */
#endif /* FF_COMPAT_OAIDL_H */
