/*
 * FreeFalcon Linux Port - wtypes.h compatibility
 *
 * Windows COM base types header stub.
 */

#ifndef FF_COMPAT_WTYPES_H
#define FF_COMPAT_WTYPES_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* OLE/COM base types - most already defined in compat_types.h */

/* Variant types */
typedef unsigned short VARTYPE;

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
#define VT_BSTR_BLOB        0xfff
#define VT_VECTOR           0x1000
#define VT_ARRAY            0x2000
#define VT_BYREF            0x4000
#define VT_RESERVED         0x8000
#define VT_ILLEGAL          0xffff
#define VT_ILLEGALMASKED    0xfff
#define VT_TYPEMASK         0xfff

/* BSTR type */
typedef WCHAR OLECHAR;
typedef OLECHAR *BSTR;
typedef OLECHAR *LPOLESTR;
typedef const OLECHAR *LPCOLESTR;

/* DATE type */
typedef double DATE;

/* CURRENCY type */
typedef struct tagCY {
    LONGLONG int64;
} CY;

/* DECIMAL type */
typedef struct tagDEC {
    USHORT wReserved;
    BYTE scale;
    BYTE sign;
    ULONG Hi32;
    ULONGLONG Lo64;
} DECIMAL;

/* VARIANT_BOOL type */
typedef short VARIANT_BOOL;
#define VARIANT_TRUE    ((VARIANT_BOOL)-1)
#define VARIANT_FALSE   ((VARIANT_BOOL)0)

/* SCODE type */
typedef LONG SCODE;
#define S_OK    ((SCODE)0)

/* CLIPFORMAT */
typedef WORD CLIPFORMAT;

/* PROPVARIANT (simplified) */
typedef struct tagPROPVARIANT {
    VARTYPE vt;
    WORD wReserved1;
    WORD wReserved2;
    WORD wReserved3;
    union {
        CHAR cVal;
        UCHAR bVal;
        SHORT iVal;
        USHORT uiVal;
        LONG lVal;
        ULONG ulVal;
        INT intVal;
        UINT uintVal;
        FLOAT fltVal;
        DOUBLE dblVal;
        VARIANT_BOOL boolVal;
        SCODE scode;
        LONGLONG hVal;
        ULONGLONG uhVal;
        LPSTR pszVal;
        LPWSTR pwszVal;
        BSTR bstrVal;
    };
} PROPVARIANT;

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WTYPES_H */
