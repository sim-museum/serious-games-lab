/*
 * FreeFalcon Linux Port - vfw.h compatibility
 *
 * Video for Windows API stub for Linux.
 */

#ifndef FF_COMPAT_VFW_H
#define FF_COMPAT_VFW_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "mmsystem.h"       /* For FOURCC type */
#include "compat_wingdi.h"  /* For BITMAPINFOHEADER, RGBQUAD, BITMAPINFO */

/* Ensure FOURCC is defined (in case mmsystem.h wasn't processed) */
#ifndef _FOURCC_DEFINED
typedef DWORD FOURCC;
#define _FOURCC_DEFINED
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* AVI file handle */
typedef HANDLE PAVIFILE;
typedef HANDLE PAVISTREAM;
typedef HANDLE PGETFRAME;
#ifndef _HWND_DEFINED
typedef HANDLE HWND;
#define _HWND_DEFINED
#endif

/* CLSID type for COM */
typedef GUID CLSID;
typedef CLSID* LPCLSID;

/* Main AVI header */
typedef struct _MainAVIHeader {
    DWORD dwMicroSecPerFrame;
    DWORD dwMaxBytesPerSec;
    DWORD dwPaddingGranularity;
    DWORD dwFlags;
    DWORD dwTotalFrames;
    DWORD dwInitialFrames;
    DWORD dwStreams;
    DWORD dwSuggestedBufferSize;
    DWORD dwWidth;
    DWORD dwHeight;
    DWORD dwReserved[4];
} MainAVIHeader;

/* AVI stream header */
typedef struct _AVIStreamHeader {
    FOURCC fccType;
    FOURCC fccHandler;
    DWORD dwFlags;
    WORD wPriority;
    WORD wLanguage;
    DWORD dwInitialFrames;
    DWORD dwScale;
    DWORD dwRate;
    DWORD dwStart;
    DWORD dwLength;
    DWORD dwSuggestedBufferSize;
    DWORD dwQuality;
    DWORD dwSampleSize;
    struct {
        short left;
        short top;
        short right;
        short bottom;
    } rcFrame;
} AVIStreamHeader;

/* AVI stream info */
typedef struct _AVISTREAMINFOA {
    DWORD fccType;
    DWORD fccHandler;
    DWORD dwFlags;
    DWORD dwCaps;
    WORD wPriority;
    WORD wLanguage;
    DWORD dwScale;
    DWORD dwRate;
    DWORD dwStart;
    DWORD dwLength;
    DWORD dwInitialFrames;
    DWORD dwSuggestedBufferSize;
    DWORD dwQuality;
    DWORD dwSampleSize;
    RECT rcFrame;
    DWORD dwEditCount;
    DWORD dwFormatChangeCount;
    char szName[64];
} AVISTREAMINFOA, *LPAVISTREAMINFOA, *PAVISTREAMINFOA;

typedef AVISTREAMINFOA AVISTREAMINFO;
typedef LPAVISTREAMINFOA LPAVISTREAMINFO;

/* AVI file info */
typedef struct _AVIFILEINFOA {
    DWORD dwMaxBytesPerSec;
    DWORD dwFlags;
    DWORD dwCaps;
    DWORD dwStreams;
    DWORD dwSuggestedBufferSize;
    DWORD dwWidth;
    DWORD dwHeight;
    DWORD dwScale;
    DWORD dwRate;
    DWORD dwLength;
    DWORD dwEditCount;
    char szFileType[64];
} AVIFILEINFOA, *LPAVIFILEINFOA, *PAVIFILEINFOA;

typedef AVIFILEINFOA AVIFILEINFO;
typedef LPAVIFILEINFOA LPAVIFILEINFO;

/* Stream types */
#define streamtypeVIDEO         mmioFOURCC('v', 'i', 'd', 's')
#define streamtypeAUDIO         mmioFOURCC('a', 'u', 'd', 's')
#define streamtypeMIDI          mmioFOURCC('m', 'i', 'd', 's')
#define streamtypeTEXT          mmioFOURCC('t', 'x', 't', 's')

/* AVI error codes */
#define AVIERR_OK               0
#define AVIERR_UNSUPPORTED      0x80044065
#define AVIERR_BADFORMAT        0x80044066
#define AVIERR_MEMORY           0x80044067
#define AVIERR_INTERNAL         0x80044068
#define AVIERR_BADFLAGS         0x80044069
#define AVIERR_BADPARAM         0x8004406A
#define AVIERR_BADSIZE          0x8004406B
#define AVIERR_BADHANDLE        0x8004406C
#define AVIERR_FILEREAD         0x8004406D
#define AVIERR_FILEWRITE        0x8004406E
#define AVIERR_FILEOPEN         0x8004406F
#define AVIERR_COMPRESSOR       0x80044070
#define AVIERR_NOCOMPRESSOR     0x80044071
#define AVIERR_READONLY         0x80044072
#define AVIERR_NODATA           0x80044073
#define AVIERR_BUFFERTOOSMALL   0x80044074
#define AVIERR_CANTCOMPRESS     0x80044075
#define AVIERR_USERABORT        0x800440C6
#define AVIERR_ERROR            0x800440C7

/* AVI flags */
#define OF_READ                 0x00000000
#define OF_WRITE                0x00000001
#define OF_READWRITE            0x00000002
#define OF_CREATE               0x00001000
#define OF_SHARE_DENY_NONE      0x00000040
#define OF_SHARE_DENY_READ      0x00000030
#define OF_SHARE_DENY_WRITE     0x00000020
#define OF_SHARE_EXCLUSIVE      0x00000010

/* Stub functions */
static inline void AVIFileInit(void) {}
static inline void AVIFileExit(void) {}

static inline HRESULT AVIFileOpenA(PAVIFILE* ppfile, LPCSTR szFile, UINT uMode, LPCLSID lpHandler) {
    (void)ppfile; (void)szFile; (void)uMode; (void)lpHandler;
    return AVIERR_UNSUPPORTED;
}
#define AVIFileOpen AVIFileOpenA

static inline ULONG AVIFileRelease(PAVIFILE pfile) { (void)pfile; return 0; }

static inline HRESULT AVIFileGetStream(PAVIFILE pfile, PAVISTREAM* ppavi, DWORD fccType, LONG lParam) {
    (void)pfile; (void)ppavi; (void)fccType; (void)lParam;
    return AVIERR_UNSUPPORTED;
}

static inline HRESULT AVIStreamInfoA(PAVISTREAM pavi, LPAVISTREAMINFOA psi, LONG lSize) {
    (void)pavi; (void)psi; (void)lSize;
    return AVIERR_UNSUPPORTED;
}
#define AVIStreamInfo AVIStreamInfoA

static inline ULONG AVIStreamRelease(PAVISTREAM pavi) { (void)pavi; return 0; }

static inline PGETFRAME AVIStreamGetFrameOpen(PAVISTREAM pavi, LPBITMAPINFOHEADER lpbiWanted) {
    (void)pavi; (void)lpbiWanted;
    return NULL;
}

static inline LPVOID AVIStreamGetFrame(PGETFRAME pg, LONG lPos) {
    (void)pg; (void)lPos;
    return NULL;
}

static inline HRESULT AVIStreamGetFrameClose(PGETFRAME pg) {
    (void)pg;
    return AVIERR_OK;
}

static inline LONG AVIStreamStart(PAVISTREAM pavi) { (void)pavi; return 0; }
static inline LONG AVIStreamLength(PAVISTREAM pavi) { (void)pavi; return 0; }

static inline HRESULT AVIStreamReadFormat(PAVISTREAM pavi, LONG lPos, LPVOID lpFormat, LONG* lpcbFormat) {
    (void)pavi; (void)lPos; (void)lpFormat; (void)lpcbFormat;
    return AVIERR_UNSUPPORTED;
}

static inline HRESULT AVIStreamRead(PAVISTREAM pavi, LONG lStart, LONG lSamples,
                                    LPVOID lpBuffer, LONG cbBuffer, LONG* plBytes, LONG* plSamples) {
    (void)pavi; (void)lStart; (void)lSamples; (void)lpBuffer; (void)cbBuffer;
    (void)plBytes; (void)plSamples;
    return AVIERR_UNSUPPORTED;
}

/* BI compression types */
#define BI_RGB          0
#define BI_RLE8         1
#define BI_RLE4         2
#define BI_BITFIELDS    3

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_VFW_H */
