/*
 * FreeFalcon Linux Port - wingdi.h compatibility
 *
 * GDI function stubs - most will be replaced by SDL2/OpenGL
 */

#ifndef FF_COMPAT_WINGDI_H
#define FF_COMPAT_WINGDI_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * GDI Constants
 * ============================================================ */

/* Ternary raster operations */
#define SRCCOPY             0x00CC0020
#define SRCPAINT            0x00EE0086
#define SRCAND              0x008800C6
#define SRCINVERT           0x00660046
#define SRCERASE            0x00440328
#define NOTSRCCOPY          0x00330008
#define NOTSRCERASE         0x001100A6
#define MERGECOPY           0x00C000CA
#define MERGEPAINT          0x00BB0226
#define PATCOPY             0x00F00021
#define PATPAINT            0x00FB0A09
#define PATINVERT           0x005A0049
#define DSTINVERT           0x00550009
#define BLACKNESS           0x00000042
#define WHITENESS           0x00FF0062

/* Stock objects */
#define WHITE_BRUSH         0
#define LTGRAY_BRUSH        1
#define GRAY_BRUSH          2
#define DKGRAY_BRUSH        3
#define BLACK_BRUSH         4
#define NULL_BRUSH          5
#define HOLLOW_BRUSH        NULL_BRUSH
#define WHITE_PEN           6
#define BLACK_PEN           7
#define NULL_PEN            8
#define OEM_FIXED_FONT      10
#define ANSI_FIXED_FONT     11
#define ANSI_VAR_FONT       12
#define SYSTEM_FONT         13
#define DEVICE_DEFAULT_FONT 14
#define DEFAULT_PALETTE     15
#define SYSTEM_FIXED_FONT   16

/* Background modes */
#define TRANSPARENT         1
#define OPAQUE              2

/* Mapping modes */
#define MM_TEXT             1
#define MM_LOMETRIC         2
#define MM_HIMETRIC         3
#define MM_LOENGLISH        4
#define MM_HIENGLISH        5
#define MM_TWIPS            6
#define MM_ISOTROPIC        7
#define MM_ANISOTROPIC      8

/* DIB color modes */
#define DIB_RGB_COLORS      0
#define DIB_PAL_COLORS      1

/* BitBlt modes */
#define BLACKONWHITE        1
#define WHITEONBLACK        2
#define COLORONCOLOR        3
#define HALFTONE            4

/* Pen styles */
#define PS_SOLID            0
#define PS_DASH             1
#define PS_DOT              2
#define PS_DASHDOT          3
#define PS_DASHDOTDOT       4
#define PS_NULL             5
#define PS_INSIDEFRAME      6

/* Brush styles */
#define BS_SOLID            0
#define BS_NULL             1
#define BS_HOLLOW           BS_NULL
#define BS_HATCHED          2
#define BS_PATTERN          3
#define BS_INDEXED          4
#define BS_DIBPATTERN       5

/* Font weights */
#define FW_DONTCARE         0
#define FW_THIN             100
#define FW_EXTRALIGHT       200
#define FW_LIGHT            300
#define FW_NORMAL           400
#define FW_MEDIUM           500
#define FW_SEMIBOLD         600
#define FW_BOLD             700
#define FW_EXTRABOLD        800
#define FW_HEAVY            900
/* Font weight aliases */
#define FW_ULTRALIGHT       FW_EXTRALIGHT
#define FW_REGULAR          FW_NORMAL
#define FW_DEMIBOLD         FW_SEMIBOLD
#define FW_ULTRABOLD        FW_EXTRABOLD
#define FW_BLACK            FW_HEAVY

/* Font pitch */
#define DEFAULT_PITCH       0
#define FIXED_PITCH         1
#define VARIABLE_PITCH      2

/* Font family */
#define FF_DONTCARE         (0<<4)
#define FF_ROMAN            (1<<4)
#define FF_SWISS            (2<<4)
#define FF_MODERN           (3<<4)
#define FF_SCRIPT           (4<<4)
#define FF_DECORATIVE       (5<<4)

/* Character sets */
#define ANSI_CHARSET        0
#define DEFAULT_CHARSET     1
#define SYMBOL_CHARSET      2
#define OEM_CHARSET         255

/* ============================================================
 * GDI Structures
 * ============================================================ */

typedef struct tagBITMAPINFOHEADER {
    DWORD biSize;
    LONG  biWidth;
    LONG  biHeight;
    WORD  biPlanes;
    WORD  biBitCount;
    DWORD biCompression;
    DWORD biSizeImage;
    LONG  biXPelsPerMeter;
    LONG  biYPelsPerMeter;
    DWORD biClrUsed;
    DWORD biClrImportant;
} BITMAPINFOHEADER, *LPBITMAPINFOHEADER, *PBITMAPINFOHEADER;

/* Bitmap compression values for biCompression */
#define BI_RGB          0
#define BI_RLE8         1
#define BI_RLE4         2
#define BI_BITFIELDS    3
#define BI_JPEG         4
#define BI_PNG          5

typedef struct tagRGBQUAD {
    BYTE rgbBlue;
    BYTE rgbGreen;
    BYTE rgbRed;
    BYTE rgbReserved;
} RGBQUAD, *LPRGBQUAD;

typedef struct tagBITMAPINFO {
    BITMAPINFOHEADER bmiHeader;
    RGBQUAD          bmiColors[1];
} BITMAPINFO, *LPBITMAPINFO, *PBITMAPINFO;

typedef struct tagBITMAPFILEHEADER {
    WORD  bfType;
    DWORD bfSize;
    WORD  bfReserved1;
    WORD  bfReserved2;
    DWORD bfOffBits;
} __attribute__((packed)) BITMAPFILEHEADER, *LPBITMAPFILEHEADER, *PBITMAPFILEHEADER;

typedef struct tagBITMAP {
    LONG   bmType;
    LONG   bmWidth;
    LONG   bmHeight;
    LONG   bmWidthBytes;
    WORD   bmPlanes;
    WORD   bmBitsPixel;
    LPVOID bmBits;
} BITMAP, *PBITMAP, *LPBITMAP;

/* Font constants */
#define LF_FACESIZE         32
#define LF_FULLFACESIZE     64

/* Output precision for LOGFONT */
#define OUT_DEFAULT_PRECIS          0
#define OUT_STRING_PRECIS           1
#define OUT_CHARACTER_PRECIS        2
#define OUT_STROKE_PRECIS           3
#define OUT_TT_PRECIS               4
#define OUT_DEVICE_PRECIS           5
#define OUT_RASTER_PRECIS           6
#define OUT_TT_ONLY_PRECIS          7
#define OUT_OUTLINE_PRECIS          8
#define OUT_SCREEN_OUTLINE_PRECIS   9
#define OUT_PS_ONLY_PRECIS          10

/* Clipping precision for LOGFONT */
#define CLIP_DEFAULT_PRECIS         0
#define CLIP_CHARACTER_PRECIS       1
#define CLIP_STROKE_PRECIS          2
#define CLIP_MASK                   0x0f
#define CLIP_LH_ANGLES              (1<<4)
#define CLIP_TT_ALWAYS              (2<<4)
#define CLIP_DFA_DISABLE            (4<<4)
#define CLIP_EMBEDDED               (8<<4)

/* Quality for LOGFONT */
#define DEFAULT_QUALITY         0
#define DRAFT_QUALITY           1
#define PROOF_QUALITY           2
#define NONANTIALIASED_QUALITY  3
#define ANTIALIASED_QUALITY     4
#define CLEARTYPE_QUALITY       5
#define CLEARTYPE_NATURAL_QUALITY 6

/* Font pitch and family */
#define DEFAULT_PITCH           0
#define FIXED_PITCH             1
#define VARIABLE_PITCH          2
#define FF_DONTCARE             (0<<4)
#define FF_ROMAN                (1<<4)
#define FF_SWISS                (2<<4)
#define FF_MODERN               (3<<4)
#define FF_SCRIPT               (4<<4)
#define FF_DECORATIVE           (5<<4)

/* Character sets for LOGFONT */
#define ANSI_CHARSET            0
#define DEFAULT_CHARSET         1
#define SYMBOL_CHARSET          2
#define SHIFTJIS_CHARSET        128
#define HANGEUL_CHARSET         129
#define HANGUL_CHARSET          129
#define JOHAB_CHARSET           130
#define GB2312_CHARSET          134
#define CHINESEBIG5_CHARSET     136
#define GREEK_CHARSET           161
#define TURKISH_CHARSET         162
#define VIETNAMESE_CHARSET      163
#define HEBREW_CHARSET          177
#define ARABIC_CHARSET          178
#define BALTIC_CHARSET          186
#define RUSSIAN_CHARSET         204
#define THAI_CHARSET            222
#define EASTEUROPE_CHARSET      238
#define OEM_CHARSET             255
#define MAC_CHARSET             77

typedef struct tagLOGFONTA {
    LONG  lfHeight;
    LONG  lfWidth;
    LONG  lfEscapement;
    LONG  lfOrientation;
    LONG  lfWeight;
    BYTE  lfItalic;
    BYTE  lfUnderline;
    BYTE  lfStrikeOut;
    BYTE  lfCharSet;
    BYTE  lfOutPrecision;
    BYTE  lfClipPrecision;
    BYTE  lfQuality;
    BYTE  lfPitchAndFamily;
    CHAR  lfFaceName[32];
} LOGFONTA, *PLOGFONTA, *LPLOGFONTA;

typedef LOGFONTA LOGFONT;
typedef PLOGFONTA PLOGFONT;
typedef LPLOGFONTA LPLOGFONT;

typedef struct tagLOGPEN {
    UINT   lopnStyle;
    POINT  lopnWidth;
    COLORREF lopnColor;
} LOGPEN, *PLOGPEN, *LPLOGPEN;

typedef struct tagLOGBRUSH {
    UINT     lbStyle;
    COLORREF lbColor;
    ULONG_PTR lbHatch;
} LOGBRUSH, *PLOGBRUSH, *LPLOGBRUSH;

typedef struct tagPALETTEENTRY {
    BYTE peRed;
    BYTE peGreen;
    BYTE peBlue;
    BYTE peFlags;
} PALETTEENTRY, *PPALETTEENTRY, *LPPALETTEENTRY;

typedef struct tagLOGPALETTE {
    WORD palVersion;
    WORD palNumEntries;
    PALETTEENTRY palPalEntry[1];
} LOGPALETTE, *PLOGPALETTE, *LPLOGPALETTE;

typedef struct tagTEXTMETRICA {
    LONG tmHeight;
    LONG tmAscent;
    LONG tmDescent;
    LONG tmInternalLeading;
    LONG tmExternalLeading;
    LONG tmAveCharWidth;
    LONG tmMaxCharWidth;
    LONG tmWeight;
    LONG tmOverhang;
    LONG tmDigitizedAspectX;
    LONG tmDigitizedAspectY;
    BYTE tmFirstChar;
    BYTE tmLastChar;
    BYTE tmDefaultChar;
    BYTE tmBreakChar;
    BYTE tmItalic;
    BYTE tmUnderlined;
    BYTE tmStruckOut;
    BYTE tmPitchAndFamily;
    BYTE tmCharSet;
} TEXTMETRICA, *PTEXTMETRICA, *LPTEXTMETRICA;

typedef TEXTMETRICA TEXTMETRIC;
typedef PTEXTMETRICA PTEXTMETRIC;
typedef LPTEXTMETRICA LPTEXTMETRIC;

/* ============================================================
 * GDI Function Stubs
 * ============================================================ */

/* These are all stubs - real implementations will use SDL2/OpenGL */

static inline HDC GetDC(HWND hWnd) { (void)hWnd; return NULL; }
static inline int ReleaseDC(HWND hWnd, HDC hDC) { (void)hWnd; (void)hDC; return 1; }
static inline HDC CreateCompatibleDC(HDC hdc) { (void)hdc; return NULL; }
static inline BOOL DeleteDC(HDC hdc) { (void)hdc; return TRUE; }

static inline HBITMAP CreateCompatibleBitmap(HDC hdc, int cx, int cy) { (void)hdc; (void)cx; (void)cy; return NULL; }
static inline HBITMAP CreateBitmap(int nWidth, int nHeight, UINT nPlanes, UINT nBitCount, const void *lpBits) {
    (void)nWidth; (void)nHeight; (void)nPlanes; (void)nBitCount; (void)lpBits; return NULL;
}
static inline HBITMAP CreateDIBSection(HDC hdc, const BITMAPINFO *pbmi, UINT usage, void **ppvBits, HANDLE hSection, DWORD offset) {
    (void)hdc; (void)pbmi; (void)usage; (void)ppvBits; (void)hSection; (void)offset; return NULL;
}

static inline HGDIOBJ SelectObject(HDC hdc, HGDIOBJ h) { (void)hdc; (void)h; return NULL; }
static inline BOOL DeleteObject(HGDIOBJ ho) { (void)ho; return TRUE; }
static inline HGDIOBJ GetStockObject(int i) { (void)i; return NULL; }

static inline BOOL BitBlt(HDC hdc, int x, int y, int cx, int cy, HDC hdcSrc, int x1, int y1, DWORD rop) {
    (void)hdc; (void)x; (void)y; (void)cx; (void)cy; (void)hdcSrc; (void)x1; (void)y1; (void)rop;
    return TRUE;
}
static inline BOOL StretchBlt(HDC hdcDest, int xDest, int yDest, int wDest, int hDest,
                              HDC hdcSrc, int xSrc, int ySrc, int wSrc, int hSrc, DWORD rop) {
    (void)hdcDest; (void)xDest; (void)yDest; (void)wDest; (void)hDest;
    (void)hdcSrc; (void)xSrc; (void)ySrc; (void)wSrc; (void)hSrc; (void)rop;
    return TRUE;
}

static inline COLORREF SetPixel(HDC hdc, int x, int y, COLORREF color) { (void)hdc; (void)x; (void)y; return color; }
static inline COLORREF GetPixel(HDC hdc, int x, int y) { (void)hdc; (void)x; (void)y; return 0; }

static inline HFONT CreateFontA(int cHeight, int cWidth, int cEscapement, int cOrientation, int cWeight,
                                DWORD bItalic, DWORD bUnderline, DWORD bStrikeOut, DWORD iCharSet,
                                DWORD iOutPrecision, DWORD iClipPrecision, DWORD iQuality,
                                DWORD iPitchAndFamily, LPCSTR pszFaceName) {
    (void)cHeight; (void)cWidth; (void)cEscapement; (void)cOrientation; (void)cWeight;
    (void)bItalic; (void)bUnderline; (void)bStrikeOut; (void)iCharSet;
    (void)iOutPrecision; (void)iClipPrecision; (void)iQuality;
    (void)iPitchAndFamily; (void)pszFaceName;
    return NULL;
}
#define CreateFont CreateFontA

static inline HFONT CreateFontIndirectA(const LOGFONTA *lplf) { (void)lplf; return NULL; }
#define CreateFontIndirect CreateFontIndirectA

static inline HPEN CreatePen(int iStyle, int cWidth, COLORREF color) { (void)iStyle; (void)cWidth; (void)color; return NULL; }
static inline HBRUSH CreateSolidBrush(COLORREF color) { (void)color; return NULL; }
static inline HBRUSH CreatePatternBrush(HBITMAP hbm) { (void)hbm; return NULL; }

static inline COLORREF SetTextColor(HDC hdc, COLORREF color) { (void)hdc; return color; }
static inline COLORREF SetBkColor(HDC hdc, COLORREF color) { (void)hdc; return color; }
static inline int SetBkMode(HDC hdc, int mode) { (void)hdc; return mode; }

static inline BOOL TextOutA(HDC hdc, int x, int y, LPCSTR lpString, int c) {
    (void)hdc; (void)x; (void)y; (void)lpString; (void)c; return TRUE;
}
#define TextOut TextOutA

static inline BOOL GetTextExtentPoint32A(HDC hdc, LPCSTR lpString, int c, LPSIZE psizl) {
    (void)hdc; (void)lpString; (void)c;
    if (psizl) { psizl->cx = 0; psizl->cy = 0; }
    return TRUE;
}
#define GetTextExtentPoint32 GetTextExtentPoint32A

static inline BOOL GetTextMetricsA(HDC hdc, LPTEXTMETRICA lptm) {
    (void)hdc;
    if (lptm) memset(lptm, 0, sizeof(*lptm));
    return TRUE;
}
#define GetTextMetrics GetTextMetricsA

static inline int GetDeviceCaps(HDC hdc, int index) { (void)hdc; (void)index; return 0; }

static inline HPALETTE CreatePalette(const LOGPALETTE *plpal) { (void)plpal; return NULL; }
static inline HPALETTE SelectPalette(HDC hdc, HPALETTE hPal, BOOL bForceBkgd) {
    (void)hdc; (void)hPal; (void)bForceBkgd; return NULL;
}
static inline UINT RealizePalette(HDC hdc) { (void)hdc; return 0; }

#define HORZRES     8
#define VERTRES     10
#define BITSPIXEL   12
#define PLANES      14
#define NUMCOLORS   24
#define LOGPIXELSX  88
#define LOGPIXELSY  90

/* Line drawing functions */
static inline BOOL MoveToEx(HDC hdc, int x, int y, LPPOINT lppt) {
    (void)hdc; (void)x; (void)y;
    if (lppt) { lppt->x = 0; lppt->y = 0; }
    return TRUE;
}
static inline BOOL LineTo(HDC hdc, int x, int y) {
    (void)hdc; (void)x; (void)y;
    return TRUE;
}
static inline BOOL Polyline(HDC hdc, const POINT *apt, int cpt) {
    (void)hdc; (void)apt; (void)cpt;
    return TRUE;
}
static inline BOOL Rectangle(HDC hdc, int left, int top, int right, int bottom) {
    (void)hdc; (void)left; (void)top; (void)right; (void)bottom;
    return TRUE;
}
static inline BOOL Ellipse(HDC hdc, int left, int top, int right, int bottom) {
    (void)hdc; (void)left; (void)top; (void)right; (void)bottom;
    return TRUE;
}
static inline int FillRect(HDC hdc, const RECT *lprc, HBRUSH hbr) {
    (void)hdc; (void)lprc; (void)hbr;
    return 1;
}
static inline int FrameRect(HDC hdc, const RECT *lprc, HBRUSH hbr) {
    (void)hdc; (void)lprc; (void)hbr;
    return 1;
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINGDI_H */
