/*
 * FreeFalcon Linux Port - ole2.h compatibility stub
 *
 * Windows OLE2 (Object Linking and Embedding) headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_OLE2_H
#define FF_COMPAT_OLE2_H

#ifdef FF_LINUX

#include <windows.h>
#include "objbase.h"

/* OLE initialization */
static inline HRESULT OleInitialize(LPVOID pvReserved) {
    (void)pvReserved;
    return S_OK;
}

static inline void OleUninitialize(void) {}

/* IDropTarget/IDropSource/IDataObject - drag and drop */
typedef struct IDropTarget IDropTarget;
typedef struct IDropSource IDropSource;
typedef struct IDataObject IDataObject;
typedef struct IEnumFORMATETC IEnumFORMATETC;

/* FORMATETC structure */
typedef struct tagFORMATETC {
    CLIPFORMAT cfFormat;
    DVTARGETDEVICE* ptd;
    DWORD dwAspect;
    LONG lindex;
    DWORD tymed;
} FORMATETC, *LPFORMATETC;

/* STGMEDIUM structure */
typedef struct tagSTGMEDIUM {
    DWORD tymed;
    union {
        HBITMAP hBitmap;
        HMETAFILEPICT hMetaFilePict;
        HENHMETAFILE hEnhMetaFile;
        HGLOBAL hGlobal;
        LPOLESTR lpszFileName;
        IStream* pstm;
        IStorage* pstg;
    } u;
    IUnknown* pUnkForRelease;
} STGMEDIUM, *LPSTGMEDIUM;

/* OLE clipboard formats */
#define CF_EMBEDSOURCE          0x8000
#define CF_EMBEDDEDOBJECT       0x8001
#define CF_LINKSOURCE           0x8002
#define CF_OBJECTDESCRIPTOR     0x8003
#define CF_LINKSRCDESCRIPTOR    0x8004

/* OLE drag and drop */
#define DROPEFFECT_NONE         0
#define DROPEFFECT_COPY         1
#define DROPEFFECT_MOVE         2
#define DROPEFFECT_LINK         4
#define DROPEFFECT_SCROLL       0x80000000

/* OLE TYMED values */
#define TYMED_NULL              0
#define TYMED_HGLOBAL           1
#define TYMED_FILE              2
#define TYMED_ISTREAM           4
#define TYMED_ISTORAGE          8
#define TYMED_GDI               16
#define TYMED_MFPICT            32
#define TYMED_ENHMF             64

/* Stub functions */
static inline HRESULT RegisterDragDrop(HWND hwnd, IDropTarget* pDropTarget) {
    (void)hwnd; (void)pDropTarget;
    return S_OK;
}

static inline HRESULT RevokeDragDrop(HWND hwnd) {
    (void)hwnd;
    return S_OK;
}

static inline void ReleaseStgMedium(LPSTGMEDIUM pmedium) {
    (void)pmedium;
}

#endif /* FF_LINUX */
#endif /* FF_COMPAT_OLE2_H */
