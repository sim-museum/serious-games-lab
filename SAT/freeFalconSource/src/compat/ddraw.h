/*
 * FreeFalcon Linux Port - ddraw.h compatibility
 *
 * DirectDraw stub interface - will be replaced by SDL2 + OpenGL
 */

#ifndef FF_COMPAT_DDRAW_H
#define FF_COMPAT_DDRAW_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * DirectDraw Constants
 * ============================================================ */

/* DirectDraw Surface Caps */
#define DDSCAPS_RESERVED1               0x00000001
#define DDSCAPS_ALPHA                   0x00000002
#define DDSCAPS_BACKBUFFER              0x00000004
#define DDSCAPS_COMPLEX                 0x00000008
#define DDSCAPS_FLIP                    0x00000010
#define DDSCAPS_FRONTBUFFER             0x00000020
#define DDSCAPS_OFFSCREENPLAIN          0x00000040
#define DDSCAPS_OVERLAY                 0x00000080
#define DDSCAPS_PALETTE                 0x00000100
#define DDSCAPS_PRIMARYSURFACE          0x00000200
#define DDSCAPS_SYSTEMMEMORY            0x00000800
#define DDSCAPS_TEXTURE                 0x00001000
#define DDSCAPS_3DDEVICE                0x00002000
#define DDSCAPS_VIDEOMEMORY             0x00004000
#define DDSCAPS_VISIBLE                 0x00008000
#define DDSCAPS_WRITEONLY               0x00010000
#define DDSCAPS_ZBUFFER                 0x00020000
#define DDSCAPS_OWNDC                   0x00040000
#define DDSCAPS_LIVEVIDEO               0x00080000
#define DDSCAPS_HWCODEC                 0x00100000
#define DDSCAPS_MODEX                   0x00200000
#define DDSCAPS_MIPMAP                  0x00400000
#define DDSCAPS_ALLOCONLOAD             0x04000000
#define DDSCAPS_VIDEOPORT               0x08000000
#define DDSCAPS_LOCALVIDMEM             0x10000000
#define DDSCAPS_NONLOCALVIDMEM          0x20000000
#define DDSCAPS_STANDARDVGAMODE         0x40000000
#define DDSCAPS_OPTIMIZED               0x80000000

/* DirectDraw Surface Desc flags */
#define DDSD_CAPS                       0x00000001
#define DDSD_HEIGHT                     0x00000002
#define DDSD_WIDTH                      0x00000004
#define DDSD_PITCH                      0x00000008
#define DDSD_BACKBUFFERCOUNT            0x00000020
#define DDSD_ZBUFFERBITDEPTH            0x00000040
#define DDSD_ALPHABITDEPTH              0x00000080
#define DDSD_LPSURFACE                  0x00000800
#define DDSD_PIXELFORMAT                0x00001000
#define DDSD_CKDESTOVERLAY              0x00002000
#define DDSD_CKDESTBLT                  0x00004000
#define DDSD_CKSRCOVERLAY               0x00008000
#define DDSD_CKSRCBLT                   0x00010000
#define DDSD_MIPMAPCOUNT                0x00020000
#define DDSD_REFRESHRATE                0x00040000
#define DDSD_LINEARSIZE                 0x00080000
#define DDSD_TEXTURESTAGE               0x00100000
#define DDSD_ALL                        0x001ff9ee

/* Pixel format flags */
#define DDPF_ALPHAPIXELS                0x00000001
#define DDPF_ALPHA                      0x00000002
#define DDPF_FOURCC                     0x00000004
#define DDPF_PALETTEINDEXED4            0x00000008
#define DDPF_PALETTEINDEXEDTO8          0x00000010
#define DDPF_PALETTEINDEXED8            0x00000020
#define DDPF_RGB                        0x00000040
#define DDPF_COMPRESSED                 0x00000080
#define DDPF_RGBTOYUV                   0x00000100
#define DDPF_YUV                        0x00000200
#define DDPF_ZBUFFER                    0x00000400
#define DDPF_PALETTEINDEXED1            0x00000800
#define DDPF_PALETTEINDEXED2            0x00001000
#define DDPF_ZPIXELS                    0x00002000
#define DDPF_STENCILBUFFER              0x00004000
#define DDPF_LUMINANCE                  0x00020000
#define DDPF_BUMPLUMINANCE              0x00040000
#define DDPF_BUMPDUDV                   0x00080000

/* Lock flags */
#define DDLOCK_SURFACEMEMORYPTR         0x00000000
#define DDLOCK_WAIT                     0x00000001
#define DDLOCK_EVENT                    0x00000002
#define DDLOCK_READONLY                 0x00000010
#define DDLOCK_WRITEONLY                0x00000020
#define DDLOCK_NOSYSLOCK                0x00000800
#define DDLOCK_NOOVERWRITE              0x00001000
#define DDLOCK_DISCARDCONTENTS          0x00002000
#define DDLOCK_DONOTWAIT                0x00004000

/* Blt flags */
#define DDBLT_ALPHADEST                 0x00000001
#define DDBLT_ALPHADESTCONSTOVERRIDE    0x00000002
#define DDBLT_ALPHADESTNEG              0x00000004
#define DDBLT_ALPHADESTSURFACEOVERRIDE  0x00000008
#define DDBLT_ALPHAEDGEBLEND            0x00000010
#define DDBLT_ALPHASRC                  0x00000020
#define DDBLT_ALPHASRCCONSTOVERRIDE     0x00000040
#define DDBLT_ALPHASRCNEG               0x00000080
#define DDBLT_ALPHASRCSURFACEOVERRIDE   0x00000100
#define DDBLT_ASYNC                     0x00000200
#define DDBLT_COLORFILL                 0x00000400
#define DDBLT_DDFX                      0x00000800
#define DDBLT_DDROPS                    0x00001000
#define DDBLT_KEYDEST                   0x00002000
#define DDBLT_KEYDESTOVERRIDE           0x00004000
#define DDBLT_KEYSRC                    0x00008000
#define DDBLT_KEYSRCOVERRIDE            0x00010000
#define DDBLT_ROP                       0x00020000
#define DDBLT_ROTATIONANGLE             0x00040000
#define DDBLT_ZBUFFER                   0x00080000
#define DDBLT_ZBUFFERDESTCONSTOVERRIDE  0x00100000
#define DDBLT_ZBUFFERDESTOVERRIDE       0x00200000
#define DDBLT_ZBUFFERSRCCONSTOVERRIDE   0x00400000
#define DDBLT_ZBUFFERSRCOVERRIDE        0x00800000
#define DDBLT_WAIT                      0x01000000
#define DDBLT_DEPTHFILL                 0x02000000
#define DDBLT_DONOTWAIT                 0x08000000

/* Blt fast flags */
#define DDBLTFAST_NOCOLORKEY            0x00000000
#define DDBLTFAST_SRCCOLORKEY           0x00000001
#define DDBLTFAST_DESTCOLORKEY          0x00000002
#define DDBLTFAST_WAIT                  0x00000010
#define DDBLTFAST_DONOTWAIT             0x00000020

/* Flip flags */
#define DDFLIP_WAIT                     0x00000001
#define DDFLIP_EVEN                     0x00000002
#define DDFLIP_ODD                      0x00000004
#define DDFLIP_NOVSYNC                  0x00000008
#define DDFLIP_INTERVAL2                0x02000000
#define DDFLIP_INTERVAL3                0x03000000
#define DDFLIP_INTERVAL4                0x04000000
#define DDFLIP_STEREO                   0x00000010
#define DDFLIP_DONOTWAIT                0x00000020

/* GetFlipStatus flags */
#define DDGFS_CANFLIP                   0x00000001
#define DDGFS_ISFLIPDONE                0x00000002

/* GetBltStatus flags */
#define DDGBS_CANBLT                    0x00000001
#define DDGBS_ISBLTDONE                 0x00000002

/* Cooperative level flags */
#define DDSCL_FULLSCREEN                0x00000001
#define DDSCL_ALLOWREBOOT               0x00000002
#define DDSCL_NOWINDOWCHANGES           0x00000004
#define DDSCL_NORMAL                    0x00000008
#define DDSCL_EXCLUSIVE                 0x00000010
#define DDSCL_ALLOWMODEX                0x00000040
#define DDSCL_SETFOCUSWINDOW            0x00000080
#define DDSCL_SETDEVICEWINDOW           0x00000100
#define DDSCL_CREATEDEVICEWINDOW        0x00000200
#define DDSCL_MULTITHREADED             0x00000400
#define DDSCL_FPUSETUP                  0x00000800
#define DDSCL_FPUPRESERVE               0x00001000

/* Color key flags */
#define DDCKEY_COLORSPACE               0x00000001
#define DDCKEY_DESTBLT                  0x00000002
#define DDCKEY_DESTOVERLAY              0x00000004
#define DDCKEY_SRCBLT                   0x00000008
#define DDCKEY_SRCOVERLAY               0x00000010

/* DDCAPS - General capability flags (dwCaps) */
#define DDCAPS_3D                       0x00000001
#define DDCAPS_ALIGNBOUNDARYDEST        0x00000002
#define DDCAPS_ALIGNSIZEDEST            0x00000004
#define DDCAPS_ALIGNBOUNDARYSRC         0x00000008
#define DDCAPS_ALIGNSIZESRC             0x00000010
#define DDCAPS_ALIGNSTRIDE              0x00000020
#define DDCAPS_BLT                      0x00000040
#define DDCAPS_BLTQUEUE                 0x00000080
#define DDCAPS_BLTFOURCC                0x00000100
#define DDCAPS_BLTSTRETCH               0x00000200
#define DDCAPS_GDI                      0x00000400
#define DDCAPS_OVERLAY                  0x00000800
#define DDCAPS_OVERLAYCANTCLIP          0x00001000
#define DDCAPS_OVERLAYFOURCC            0x00002000
#define DDCAPS_OVERLAYSTRETCH           0x00004000
#define DDCAPS_PALETTE                  0x00008000
#define DDCAPS_PALETTEVSYNC             0x00010000
#define DDCAPS_READSCANLINE             0x00020000
#define DDCAPS_RESERVED1                0x00040000
#define DDCAPS_VBI                      0x00080000
#define DDCAPS_ZBLTS                    0x00100000
#define DDCAPS_ZOVERLAYS                0x00200000
#define DDCAPS_COLORKEY                 0x00400000
#define DDCAPS_ALPHA                    0x00800000
#define DDCAPS_COLORKEYHWASSIST         0x01000000
#define DDCAPS_NOHARDWARE               0x02000000
#define DDCAPS_BLTCOLORFILL             0x04000000
#define DDCAPS_BANKSWITCHED             0x08000000
#define DDCAPS_BLTDEPTHFILL             0x10000000
#define DDCAPS_CANCLIP                  0x20000000
#define DDCAPS_CANCLIPSTRETCHED         0x40000000
#define DDCAPS_CANBLTSYSMEM             0x80000000

/* DDCAPS - Color key capability flags (dwCKeyCaps) */
#define DDCKEYCAPS_DESTBLT              0x00000001
#define DDCKEYCAPS_DESTBLTCLRSPACE      0x00000002
#define DDCKEYCAPS_DESTBLTCLRSPACEYUV   0x00000004
#define DDCKEYCAPS_DESTBLTYUV           0x00000008
#define DDCKEYCAPS_DESTOVERLAY          0x00000010
#define DDCKEYCAPS_DESTOVERLAYCLRSPACE  0x00000020
#define DDCKEYCAPS_DESTOVERLAYCLRSPACEYUV 0x00000040
#define DDCKEYCAPS_DESTOVERLAYONEACTIVE 0x00000080
#define DDCKEYCAPS_DESTOVERLAYYUV       0x00000100
#define DDCKEYCAPS_SRCBLT               0x00000200
#define DDCKEYCAPS_SRCBLTCLRSPACE       0x00000400
#define DDCKEYCAPS_SRCBLTCLRSPACEYUV    0x00000800
#define DDCKEYCAPS_SRCBLTYUV            0x00001000
#define DDCKEYCAPS_SRCOVERLAY           0x00002000
#define DDCKEYCAPS_SRCOVERLAYCLRSPACE   0x00004000
#define DDCKEYCAPS_SRCOVERLAYCLRSPACEYUV 0x00008000
#define DDCKEYCAPS_SRCOVERLAYONEACTIVE  0x00010000
#define DDCKEYCAPS_SRCOVERLAYYUV        0x00020000
#define DDCKEYCAPS_NOCOSTOVERLAY        0x00040000

/* DDCAPS2 - Extended capability flags (dwCaps2) */
#define DDCAPS2_CERTIFIED               0x00000001
#define DDCAPS2_NO2DDURING3DSCENE       0x00000002
#define DDCAPS2_VIDEOPORT               0x00000004
#define DDCAPS2_AUTOFLIPOVERLAY         0x00000008
#define DDCAPS2_CANBOBINTERLEAVED       0x00000010
#define DDCAPS2_CANBOBNONINTERLEAVED    0x00000020
#define DDCAPS2_COLORCONTROLOVERLAY     0x00000040
#define DDCAPS2_COLORCONTROLPRIMARY     0x00000080
#define DDCAPS2_CANDROPZ16BIT           0x00000100
#define DDCAPS2_NONLOCALVIDMEM          0x00000200
#define DDCAPS2_NONLOCALVIDMEMCAPS      0x00000400
#define DDCAPS2_NOPAGELOCKREQUIRED      0x00000800
#define DDCAPS2_WIDESURFACES            0x00001000
#define DDCAPS2_CANFLIPODDEVEN          0x00002000
#define DDCAPS2_CANBOBHARDWARE          0x00004000
#define DDCAPS2_COPYFOURCC              0x00008000
#define DDCAPS2_PRIMARYGAMMA            0x00020000
#define DDCAPS2_CANRENDERWINDOWED       0x00080000
#define DDCAPS2_CANCALIBRATEGAMMA       0x00100000
#define DDCAPS2_FLIPINTERVAL            0x00200000
#define DDCAPS2_FLIPNOVSYNC             0x00400000
#define DDCAPS2_CANMANAGETEXTURE        0x00800000
#define DDCAPS2_TEXMANINNONLOCALVIDMEM  0x01000000
#define DDCAPS2_STEREO                  0x02000000
#define DDCAPS2_SYSTONONLOCAL_AS_SYSTOLOCAL 0x04000000
#define DDCAPS2_TEXTUREMANAGE           0x08000000
#define DDCAPS2_HINTSTATIC              0x10000000
#define DDCAPS2_HINTDYNAMIC             0x20000000
#define DDCAPS2_DONOTPERSIST            0x40000000

/* Alternate caps names used for surface capabilities */
#define DDSCAPS2_TEXTUREMANAGE          DDCAPS2_TEXTUREMANAGE
#define DDSCAPS2_HINTSTATIC             DDCAPS2_HINTSTATIC
#define DDSCAPS2_HINTDYNAMIC            DDCAPS2_HINTDYNAMIC
#define DDSCAPS2_DONOTPERSIST           DDCAPS2_DONOTPERSIST

/* DDPCAPS - Palette capability flags */
#define DDPCAPS_4BIT                    0x00000001
#define DDPCAPS_8BITENTRIES             0x00000002
#define DDPCAPS_8BIT                    0x00000004
#define DDPCAPS_INITIALIZE              0x00000008
#define DDPCAPS_PRIMARYSURFACE          0x00000010
#define DDPCAPS_PRIMARYSURFACELEFT      0x00000020
#define DDPCAPS_ALLOW256                0x00000040
#define DDPCAPS_VSYNC                   0x00000080
#define DDPCAPS_1BIT                    0x00000100
#define DDPCAPS_2BIT                    0x00000200
#define DDPCAPS_ALPHA                   0x00000400

/* DDBD - DirectDraw Bit Depths */
#define DDBD_1                          0x00004000
#define DDBD_2                          0x00002000
#define DDBD_4                          0x00001000
#define DDBD_8                          0x00000800
#define DDBD_16                         0x00000400
#define DDBD_24                         0x00000200
#define DDBD_32                         0x00000100

/* DirectDraw enumeration flags */
#define DDENUM_ATTACHEDSECONDARYDEVICES 0x00000001
#define DDENUM_DETACHEDSECONDARYDEVICES 0x00000002
#define DDENUM_NONDISPLAYDEVICES        0x00000004

/* Return values */
#define DD_OK                           0
#define DD_FALSE                        1

/* Enumeration return values */
#define DDENUMRET_CANCEL                0
#define DDENUMRET_OK                    1
#define DDERR_ALREADYINITIALIZED        0x88760005
#define DDERR_BLTFASTCANTCLIP           0x88760006
#define DDERR_CANNOTATTACHSURFACE       0x88760007
#define DDERR_CANNOTDETACHSURFACE       0x88760008
#define DDERR_CURRENTLYNOTAVAIL         0x88760009
#define DDERR_EXCEPTION                 0x8876000A
#define DDERR_GENERIC                   E_FAIL
#define DDERR_HEIGHTALIGN               0x8876000B
#define DDERR_INCOMPATIBLEPRIMARY       0x8876000C
#define DDERR_INVALIDCAPS               0x8876000D
#define DDERR_INVALIDCLIPLIST           0x8876000E
#define DDERR_INVALIDMODE               0x8876000F
#define DDERR_INVALIDOBJECT             0x88760010
#define DDERR_INVALIDPARAMS             E_INVALIDARG
#define DDERR_INVALIDPIXELFORMAT        0x88760011
#define DDERR_INVALIDRECT               0x88760012
#define DDERR_LOCKEDSURFACES            0x88760013
#define DDERR_NO3D                      0x88760014
#define DDERR_NOALPHAHW                 0x88760015
#define DDERR_NOSTEREOHARDWARE          0x88760016
#define DDERR_NOSURFACELEFT             0x88760017
#define DDERR_NOCLIPLIST                0x88760018
#define DDERR_NOCOLORCONVHW             0x88760019
#define DDERR_NOCOOPERATIVELEVELSET     0x8876001A
#define DDERR_NOCOLORKEY                0x8876001B
#define DDERR_NOCOLORKEYHW              0x8876001C
#define DDERR_NODIRECTDRAWSUPPORT       0x8876001D
#define DDERR_NOEXCLUSIVEMODE           0x8876001E
#define DDERR_NOFLIPHW                  0x8876001F
#define DDERR_NOGDI                     0x88760020
#define DDERR_NOMIRRORHW                0x88760021
#define DDERR_NOTFOUND                  0x88760022
#define DDERR_NOOVERLAYHW               0x88760023
#define DDERR_NORASTEROPHW              0x88760024
#define DDERR_NOROTATIONHW              0x88760025
#define DDERR_NOSTRETCHHW               0x88760026
#define DDERR_NOT4BITCOLOR              0x88760027
#define DDERR_NOT4BITCOLORINDEX         0x88760028
#define DDERR_NOT8BITCOLOR              0x88760029
#define DDERR_NOTEXTUREHW               0x8876002A
#define DDERR_NOVSYNCHW                 0x8876002B
#define DDERR_NOZBUFFERHW               0x8876002C
#define DDERR_NOZOVERLAYHW              0x8876002D
#define DDERR_OUTOFCAPS                 0x8876002E
#define DDERR_OUTOFMEMORY               E_OUTOFMEMORY
#define DDERR_OUTOFVIDEOMEMORY          0x88760030
#define DDERR_OVERLAYCANTCLIP           0x88760031
#define DDERR_OVERLAYCOLORKEYONLYONEACTIVE 0x88760032
#define DDERR_PALETTEBUSY               0x88760033
#define DDERR_COLORKEYNOTSET            0x88760034
#define DDERR_SURFACEALREADYATTACHED    0x88760035
#define DDERR_SURFACEALREADYDEPENDENT   0x88760036
#define DDERR_SURFACEBUSY               0x88760037
#define DDERR_SURFACEISOBSCURED         0x88760038
#define DDERR_SURFACELOST               0x88760039
#define DDERR_SURFACENOTATTACHED        0x8876003A
#define DDERR_TOOBIGHEIGHT              0x8876003B
#define DDERR_TOOBIGSIZE                0x8876003C
#define DDERR_TOOBIGWIDTH               0x8876003D
#define DDERR_UNSUPPORTED               E_NOTIMPL
#define DDERR_UNSUPPORTEDFORMAT         0x8876003F
#define DDERR_UNSUPPORTEDMASK           0x88760040
#define DDERR_UNSUPPORTEDMODE           0x88760041
#define DDERR_VERTICALBLANKINPROGRESS   0x88760042
#define DDERR_WASSTILLDRAWING           0x88760043
#define DDERR_XALIGN                    0x88760044
#define DDERR_INVALIDDIRECTDRAWGUID     0x88760045
#define DDERR_DIRECTDRAWALREADYCREATED  0x88760046
#define DDERR_NODIRECTDRAWHW            0x88760047
#define DDERR_PRIMARYSURFACEALREADYEXISTS 0x88760048
#define DDERR_NOEMULATION               0x88760049
#define DDERR_REGIONTOOSMALL            0x8876004A
#define DDERR_CLIPPERISUSINGHWND        0x8876004B
#define DDERR_NOCLIPPERATTACHED         0x8876004C
#define DDERR_NOHWND                    0x8876004D
#define DDERR_HWNDSUBCLASSED            0x8876004E
#define DDERR_HWNDALREADYSET            0x8876004F
#define DDERR_NOPALETTEATTACHED         0x88760050
#define DDERR_NOPALETTEHW               0x88760051
#define DDERR_BLTFASTCANTCLIP           0x88760006
#define DDERR_NOBLTHW                   0x88760052
#define DDERR_OVERLAYNOTVISIBLE         0x88760053
#define DDERR_CANTCREATEDC              0x88760054
#define DDERR_CANTDUPLICATE             0x88760055
#define DDERR_EXCLUSIVEMODEALREADYSET   0x88760056
#define DDERR_IMPLICITLYCREATED         0x88760057
#define DDERR_INVALIDPOSITION           0x88760058
#define DDERR_NODC                      0x88760059
#define DDERR_NODDROPSHW                0x8876005A
#define DDERR_NOOVERLAYDEST             0x8876005B
#define DDERR_NOTAOVERLAYSURFACE        0x8876005C
#define DDERR_NOTFLIPPABLE              0x8876005D
#define DDERR_NOTLOCKED                 0x8876005E
#define DDERR_NOTPALETTIZED             0x8876005F
#define DDERR_WRONGMODE                 0x88760060
#define DDERR_DCALREADYCREATED          0x88760061
#define DDERR_DDSCAPSCOMPLEXREQUIRED    0x88760062
#define DDERR_INVALIDSURFACETYPE        0x88760063
#define DDERR_MOREDATA                  0x88760064
#define DDERR_VIDEONOTACTIVE            0x88760065
#define DDERR_DEVICEDOESNTOWNSURFACE    0x88760066

/* ============================================================
 * DirectDraw Structures
 * ============================================================ */

typedef struct _DDCOLORKEY {
    DWORD dwColorSpaceLowValue;
    DWORD dwColorSpaceHighValue;
} DDCOLORKEY, *LPDDCOLORKEY;

typedef struct _DDPIXELFORMAT {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwFourCC;
    union {
        DWORD dwRGBBitCount;
        DWORD dwYUVBitCount;
        DWORD dwZBufferBitDepth;
        DWORD dwAlphaBitDepth;
        DWORD dwLuminanceBitCount;
        DWORD dwBumpBitCount;
    };
    union {
        DWORD dwRBitMask;
        DWORD dwYBitMask;
        DWORD dwStencilBitDepth;
        DWORD dwLuminanceBitMask;
        DWORD dwBumpDuBitMask;
    };
    union {
        DWORD dwGBitMask;
        DWORD dwUBitMask;
        DWORD dwZBitMask;
        DWORD dwBumpDvBitMask;
    };
    union {
        DWORD dwBBitMask;
        DWORD dwVBitMask;
        DWORD dwStencilBitMask;
        DWORD dwBumpLuminanceBitMask;
    };
    union {
        DWORD dwRGBAlphaBitMask;
        DWORD dwYUVAlphaBitMask;
        DWORD dwLuminanceAlphaBitMask;
        DWORD dwRGBZBitMask;
        DWORD dwYUVZBitMask;
    };
} DDPIXELFORMAT, *LPDDPIXELFORMAT;

typedef struct _DDSCAPS {
    DWORD dwCaps;
} DDSCAPS, *LPDDSCAPS;

typedef struct _DDSCAPS2 {
    DWORD dwCaps;
    DWORD dwCaps2;
    DWORD dwCaps3;
    union {
        DWORD dwCaps4;
        DWORD dwVolumeDepth;
    };
} DDSCAPS2, *LPDDSCAPS2;

typedef struct _DDSURFACEDESC {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwHeight;
    DWORD dwWidth;
    union {
        LONG  lPitch;
        DWORD dwLinearSize;
    };
    DWORD dwBackBufferCount;
    union {
        DWORD dwMipMapCount;
        DWORD dwZBufferBitDepth;
        DWORD dwRefreshRate;
    };
    DWORD dwAlphaBitDepth;
    DWORD dwReserved;
    LPVOID lpSurface;
    DDCOLORKEY ddckCKDestOverlay;
    DDCOLORKEY ddckCKDestBlt;
    DDCOLORKEY ddckCKSrcOverlay;
    DDCOLORKEY ddckCKSrcBlt;
    DDPIXELFORMAT ddpfPixelFormat;
    DDSCAPS ddsCaps;
} DDSURFACEDESC, *LPDDSURFACEDESC;

typedef struct _DDSURFACEDESC2 {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwHeight;
    DWORD dwWidth;
    union {
        LONG  lPitch;
        DWORD dwLinearSize;
    };
    union {
        DWORD dwBackBufferCount;
        DWORD dwDepth;
    };
    union {
        DWORD dwMipMapCount;
        DWORD dwRefreshRate;
        DWORD dwSrcVBHandle;
    };
    DWORD dwAlphaBitDepth;
    DWORD dwReserved;
    LPVOID lpSurface;
    union {
        DDCOLORKEY ddckCKDestOverlay;
        DWORD dwEmptyFaceColor;
    };
    DDCOLORKEY ddckCKDestBlt;
    DDCOLORKEY ddckCKSrcOverlay;
    DDCOLORKEY ddckCKSrcBlt;
    union {
        DDPIXELFORMAT ddpfPixelFormat;
        DWORD dwFVF;
    };
    DDSCAPS2 ddsCaps;
    DWORD dwTextureStage;
} DDSURFACEDESC2, *LPDDSURFACEDESC2;

#ifdef FF_LINUX
/* FF_LINUX: DDS file header with fixed 124-byte layout for reading DDS files.
 * DDSURFACEDESC2 has LPVOID lpSurface (8 bytes on 64-bit Linux) which makes
 * sizeof(DDSURFACEDESC2) = 132 instead of the expected 124 bytes in DDS files.
 * This struct replaces the pointer with reserved DWORDs to match the file format. */
#pragma pack(push, 1)
typedef struct _DDS_FILE_HEADER {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwHeight;
    DWORD dwWidth;
    union { int32_t lPitch; DWORD dwLinearSize; };
    DWORD dwDepth;
    DWORD dwMipMapCount;
    DWORD dwReserved1[11];
    DDPIXELFORMAT ddpfPixelFormat;
    DDSCAPS2 ddsCaps;
    DWORD dwReserved2;
} DDS_FILE_HEADER;
#pragma pack(pop)
#endif

/* DDCAPS / _DDCAPS_DX7 - DirectDraw capabilities
 * Note: struct tag is _DDCAPS_DX7 so forward declarations work */
typedef struct _DDCAPS_DX7 {
    DWORD dwSize;
    DWORD dwCaps;
    DWORD dwCaps2;
    DWORD dwCKeyCaps;
    DWORD dwFXCaps;
    DWORD dwFXAlphaCaps;
    DWORD dwPalCaps;
    DWORD dwSVCaps;
    DWORD dwAlphaBltConstBitDepths;
    DWORD dwAlphaBltPixelBitDepths;
    DWORD dwAlphaBltSurfaceBitDepths;
    DWORD dwAlphaOverlayConstBitDepths;
    DWORD dwAlphaOverlayPixelBitDepths;
    DWORD dwAlphaOverlaySurfaceBitDepths;
    DWORD dwZBufferBitDepths;
    DWORD dwVidMemTotal;
    DWORD dwVidMemFree;
    DWORD dwMaxVisibleOverlays;
    DWORD dwCurrVisibleOverlays;
    DWORD dwNumFourCCCodes;
    DWORD dwAlignBoundarySrc;
    DWORD dwAlignSizeSrc;
    DWORD dwAlignBoundaryDest;
    DWORD dwAlignSizeDest;
    DWORD dwAlignStrideAlign;
    DWORD dwRops[8];
    DDSCAPS ddsOldCaps;
    DWORD dwMinOverlayStretch;
    DWORD dwMaxOverlayStretch;
    DWORD dwMinLiveVideoStretch;
    DWORD dwMaxLiveVideoStretch;
    DWORD dwMinHwCodecStretch;
    DWORD dwMaxHwCodecStretch;
    DWORD dwReserved1;
    DWORD dwReserved2;
    DWORD dwReserved3;
    DWORD dwSVBCaps;
    DWORD dwSVBCKeyCaps;
    DWORD dwSVBFXCaps;
    DWORD dwSVBRops[8];
    DWORD dwVSBCaps;
    DWORD dwVSBCKeyCaps;
    DWORD dwVSBFXCaps;
    DWORD dwVSBRops[8];
    DWORD dwSSBCaps;
    DWORD dwSSBCKeyCaps;
    DWORD dwSSBFXCaps;
    DWORD dwSSBRops[8];
    DWORD dwMaxVideoPorts;
    DWORD dwCurrVideoPorts;
    DWORD dwSVBCaps2;
    DWORD dwNLVBCaps;
    DWORD dwNLVBCaps2;
    DWORD dwNLVBCKeyCaps;
    DWORD dwNLVBFXCaps;
    DWORD dwNLVBRops[8];
    DDSCAPS2 ddsCaps;
} DDCAPS, DDCAPS_DX7, *LPDDCAPS, *LPDDCAPS_DX7;

/* DDDEVICEIDENTIFIER2 - Device identifier */
typedef struct tagDDDEVICEIDENTIFIER2 {
    char szDriver[512];
    char szDescription[512];
    LARGE_INTEGER liDriverVersion;
    DWORD dwVendorId;
    DWORD dwDeviceId;
    DWORD dwSubSysId;
    DWORD dwRevision;
    GUID guidDeviceIdentifier;
    DWORD dwWHQLLevel;
} DDDEVICEIDENTIFIER2, *LPDDDEVICEIDENTIFIER2;

/* ============================================================
 * DirectDraw Interface Declarations
 * ============================================================ */

/* Forward declarations */
struct IDirectDraw;
struct IDirectDraw2;
struct IDirectDraw4;
struct IDirectDraw7;
struct IDirectDrawSurface;
struct IDirectDrawSurface2;
struct IDirectDrawSurface3;
struct IDirectDrawSurface4;
struct IDirectDrawSurface7;
struct IDirectDrawPalette;
struct IDirectDrawClipper;

typedef struct IDirectDraw         *LPDIRECTDRAW;
typedef struct IDirectDraw2        *LPDIRECTDRAW2;
typedef struct IDirectDraw4        *LPDIRECTDRAW4;
typedef struct IDirectDraw7        *LPDIRECTDRAW7;
typedef struct IDirectDrawSurface  *LPDIRECTDRAWSURFACE;
typedef struct IDirectDrawSurface2 *LPDIRECTDRAWSURFACE2;
typedef struct IDirectDrawSurface3 *LPDIRECTDRAWSURFACE3;
typedef struct IDirectDrawSurface4 *LPDIRECTDRAWSURFACE4;
typedef struct IDirectDrawSurface7 *LPDIRECTDRAWSURFACE7;
typedef struct IDirectDrawPalette  *LPDIRECTDRAWPALETTE;
typedef struct IDirectDrawClipper  *LPDIRECTDRAWCLIPPER;

/* DDBLTFX structure for Blt operations */
typedef struct _DDBLTFX {
    DWORD dwSize;
    DWORD dwDDFX;
    DWORD dwROP;
    DWORD dwDDROP;
    DWORD dwRotationAngle;
    DWORD dwZBufferOpCode;
    DWORD dwZBufferLow;
    DWORD dwZBufferHigh;
    DWORD dwZBufferBaseDest;
    DWORD dwZDestConstBitDepth;
    union {
        DWORD dwZDestConst;
        LPDIRECTDRAWSURFACE7 lpDDSZBufferDest;
    };
    DWORD dwZSrcConstBitDepth;
    union {
        DWORD dwZSrcConst;
        LPDIRECTDRAWSURFACE7 lpDDSZBufferSrc;
    };
    DWORD dwAlphaEdgeBlendBitDepth;
    DWORD dwAlphaEdgeBlend;
    DWORD dwReserved;
    DWORD dwAlphaDestConstBitDepth;
    union {
        DWORD dwAlphaDestConst;
        LPDIRECTDRAWSURFACE7 lpDDSAlphaDest;
    };
    DWORD dwAlphaSrcConstBitDepth;
    union {
        DWORD dwAlphaSrcConst;
        LPDIRECTDRAWSURFACE7 lpDDSAlphaSrc;
    };
    union {
        DWORD dwFillColor;
        DWORD dwFillDepth;
        DWORD dwFillPixel;
        LPDIRECTDRAWSURFACE7 lpDDSPattern;
    };
    DDCOLORKEY ddckDestColorkey;
    DDCOLORKEY ddckSrcColorkey;
} DDBLTFX, *LPDDBLTFX;

/* DDOVERLAYFX structure */
typedef struct _DDOVERLAYFX {
    DWORD dwSize;
    DWORD dwAlphaEdgeBlendBitDepth;
    DWORD dwAlphaEdgeBlend;
    DWORD dwReserved;
    DWORD dwAlphaDestConstBitDepth;
    union {
        DWORD dwAlphaDestConst;
        LPDIRECTDRAWSURFACE7 lpDDSAlphaDest;
    };
    DWORD dwAlphaSrcConstBitDepth;
    union {
        DWORD dwAlphaSrcConst;
        LPDIRECTDRAWSURFACE7 lpDDSAlphaSrc;
    };
    DDCOLORKEY dckDestColorkey;
    DDCOLORKEY dckSrcColorkey;
    DWORD dwDDFX;
    DWORD dwFlags;
} DDOVERLAYFX, *LPDDOVERLAYFX;

/* Callback type for EnumAttachedSurfaces/EnumOverlayZOrders */
typedef HRESULT (CALLBACK *LPDDENUMSURFACESCALLBACK7)(LPDIRECTDRAWSURFACE7, LPDDSURFACEDESC2, LPVOID);

/* ============================================================
 * IDirectDrawSurface7 Interface
 * ============================================================ */

#undef INTERFACE
#define INTERFACE IDirectDrawSurface7

typedef struct IDirectDrawSurface7Vtbl {
    /* IUnknown methods */
    HRESULT (WINAPI *QueryInterface)(INTERFACE *This, REFIID riid, LPVOID *ppvObj);
    ULONG   (WINAPI *AddRef)(INTERFACE *This);
    ULONG   (WINAPI *Release)(INTERFACE *This);
    /* IDirectDrawSurface7 methods */
    HRESULT (WINAPI *AddAttachedSurface)(INTERFACE *This, LPDIRECTDRAWSURFACE7 lpDDSAttachedSurface);
    HRESULT (WINAPI *AddOverlayDirtyRect)(INTERFACE *This, LPRECT lpRect);
    HRESULT (WINAPI *Blt)(INTERFACE *This, LPRECT lpDestRect, LPDIRECTDRAWSURFACE7 lpDDSrcSurface, LPRECT lpSrcRect, DWORD dwFlags, LPDDBLTFX lpDDBltFx);
    HRESULT (WINAPI *BltBatch)(INTERFACE *This, LPVOID lpDDBltBatch, DWORD dwCount, DWORD dwFlags);
    HRESULT (WINAPI *BltFast)(INTERFACE *This, DWORD dwX, DWORD dwY, LPDIRECTDRAWSURFACE7 lpDDSrcSurface, LPRECT lpSrcRect, DWORD dwTrans);
    HRESULT (WINAPI *DeleteAttachedSurface)(INTERFACE *This, DWORD dwFlags, LPDIRECTDRAWSURFACE7 lpDDSAttachedSurface);
    HRESULT (WINAPI *EnumAttachedSurfaces)(INTERFACE *This, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7 lpEnumSurfacesCallback);
    HRESULT (WINAPI *EnumOverlayZOrders)(INTERFACE *This, DWORD dwFlags, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7 lpfnCallback);
    HRESULT (WINAPI *Flip)(INTERFACE *This, LPDIRECTDRAWSURFACE7 lpDDSurfaceTargetOverride, DWORD dwFlags);
    HRESULT (WINAPI *GetAttachedSurface)(INTERFACE *This, LPDDSCAPS2 lpDDSCaps, LPDIRECTDRAWSURFACE7 *lplpDDAttachedSurface);
    HRESULT (WINAPI *GetBltStatus)(INTERFACE *This, DWORD dwFlags);
    HRESULT (WINAPI *GetCaps)(INTERFACE *This, LPDDSCAPS2 lpDDSCaps);
    HRESULT (WINAPI *GetClipper)(INTERFACE *This, LPDIRECTDRAWCLIPPER *lplpDDClipper);
    HRESULT (WINAPI *GetColorKey)(INTERFACE *This, DWORD dwFlags, LPDDCOLORKEY lpDDColorKey);
    HRESULT (WINAPI *GetDC)(INTERFACE *This, HDC *lphDC);
    HRESULT (WINAPI *GetFlipStatus)(INTERFACE *This, DWORD dwFlags);
    HRESULT (WINAPI *GetOverlayPosition)(INTERFACE *This, LPLONG lplX, LPLONG lplY);
    HRESULT (WINAPI *GetPalette)(INTERFACE *This, LPDIRECTDRAWPALETTE *lplpDDPalette);
    HRESULT (WINAPI *GetPixelFormat)(INTERFACE *This, LPDDPIXELFORMAT lpDDPixelFormat);
    HRESULT (WINAPI *GetSurfaceDesc)(INTERFACE *This, LPDDSURFACEDESC2 lpDDSurfaceDesc);
    HRESULT (WINAPI *Initialize)(INTERFACE *This, LPDIRECTDRAW lpDD, LPDDSURFACEDESC2 lpDDSurfaceDesc);
    HRESULT (WINAPI *IsLost)(INTERFACE *This);
    HRESULT (WINAPI *Lock)(INTERFACE *This, LPRECT lpDestRect, LPDDSURFACEDESC2 lpDDSurfaceDesc, DWORD dwFlags, HANDLE hEvent);
    HRESULT (WINAPI *ReleaseDC)(INTERFACE *This, HDC hDC);
    HRESULT (WINAPI *Restore)(INTERFACE *This);
    HRESULT (WINAPI *SetClipper)(INTERFACE *This, LPDIRECTDRAWCLIPPER lpDDClipper);
    HRESULT (WINAPI *SetColorKey)(INTERFACE *This, DWORD dwFlags, LPDDCOLORKEY lpDDColorKey);
    HRESULT (WINAPI *SetOverlayPosition)(INTERFACE *This, LONG lX, LONG lY);
    HRESULT (WINAPI *SetPalette)(INTERFACE *This, LPDIRECTDRAWPALETTE lpDDPalette);
    HRESULT (WINAPI *Unlock)(INTERFACE *This, LPRECT lpRect);
    HRESULT (WINAPI *UpdateOverlay)(INTERFACE *This, LPRECT lpSrcRect, LPDIRECTDRAWSURFACE7 lpDDDestSurface, LPRECT lpDestRect, DWORD dwFlags, LPDDOVERLAYFX lpDDOverlayFx);
    HRESULT (WINAPI *UpdateOverlayDisplay)(INTERFACE *This, DWORD dwFlags);
    HRESULT (WINAPI *UpdateOverlayZOrder)(INTERFACE *This, DWORD dwFlags, LPDIRECTDRAWSURFACE7 lpDDSReference);
    /* Added in IDirectDrawSurface2 */
    HRESULT (WINAPI *GetDDInterface)(INTERFACE *This, LPVOID *lplpDD);
    HRESULT (WINAPI *PageLock)(INTERFACE *This, DWORD dwFlags);
    HRESULT (WINAPI *PageUnlock)(INTERFACE *This, DWORD dwFlags);
    /* Added in IDirectDrawSurface3 */
    HRESULT (WINAPI *SetSurfaceDesc)(INTERFACE *This, LPDDSURFACEDESC2 lpddsd2, DWORD dwFlags);
    /* Added in IDirectDrawSurface4 */
    HRESULT (WINAPI *SetPrivateData)(INTERFACE *This, REFGUID guidTag, LPVOID lpData, DWORD cbSize, DWORD dwFlags);
    HRESULT (WINAPI *GetPrivateData)(INTERFACE *This, REFGUID guidTag, LPVOID lpBuffer, LPDWORD lpcbBufferSize);
    HRESULT (WINAPI *FreePrivateData)(INTERFACE *This, REFGUID guidTag);
    HRESULT (WINAPI *GetUniquenessValue)(INTERFACE *This, LPDWORD lpValue);
    HRESULT (WINAPI *ChangeUniquenessValue)(INTERFACE *This);
    /* Added in IDirectDrawSurface7 */
    HRESULT (WINAPI *SetPriority)(INTERFACE *This, DWORD dwPriority);
    HRESULT (WINAPI *GetPriority)(INTERFACE *This, LPDWORD lpdwPriority);
    HRESULT (WINAPI *SetLOD)(INTERFACE *This, DWORD dwMaxLOD);
    HRESULT (WINAPI *GetLOD)(INTERFACE *This, LPDWORD lpdwMaxLOD);
} IDirectDrawSurface7Vtbl;

struct IDirectDrawSurface7 {
    IDirectDrawSurface7Vtbl *lpVtbl;
#ifdef __cplusplus
    /* C++ helper methods */
    HRESULT QueryInterface(REFIID riid, LPVOID *ppvObj) { return lpVtbl->QueryInterface(this, riid, ppvObj); }
    ULONG   AddRef() { return lpVtbl->AddRef(this); }
    ULONG   Release() { return lpVtbl->Release(this); }
    HRESULT AddAttachedSurface(LPDIRECTDRAWSURFACE7 s) { return lpVtbl->AddAttachedSurface(this, s); }
    HRESULT Blt(LPRECT dr, LPDIRECTDRAWSURFACE7 ss, LPRECT sr, DWORD f, LPDDBLTFX fx) { return lpVtbl->Blt(this, dr, ss, sr, f, fx); }
    HRESULT BltFast(DWORD x, DWORD y, LPDIRECTDRAWSURFACE7 ss, LPRECT sr, DWORD t) { return lpVtbl->BltFast(this, x, y, ss, sr, t); }
    HRESULT DeleteAttachedSurface(DWORD f, LPDIRECTDRAWSURFACE7 s) { return lpVtbl->DeleteAttachedSurface(this, f, s); }
    HRESULT EnumAttachedSurfaces(LPVOID ctx, LPDDENUMSURFACESCALLBACK7 cb) { return lpVtbl->EnumAttachedSurfaces(this, ctx, cb); }
    HRESULT Flip(LPDIRECTDRAWSURFACE7 t, DWORD f) { return lpVtbl->Flip(this, t, f); }
    HRESULT GetAttachedSurface(LPDDSCAPS2 caps, LPDIRECTDRAWSURFACE7 *s) { return lpVtbl->GetAttachedSurface(this, caps, s); }
    HRESULT GetBltStatus(DWORD f) { return lpVtbl->GetBltStatus(this, f); }
    HRESULT GetCaps(LPDDSCAPS2 caps) { return lpVtbl->GetCaps(this, caps); }
    HRESULT GetClipper(LPDIRECTDRAWCLIPPER *c) { return lpVtbl->GetClipper(this, c); }
    HRESULT GetColorKey(DWORD f, LPDDCOLORKEY ck) { return lpVtbl->GetColorKey(this, f, ck); }
    HRESULT GetDC(HDC *hdc) { return lpVtbl->GetDC(this, hdc); }
    HRESULT GetFlipStatus(DWORD f) { return lpVtbl->GetFlipStatus(this, f); }
    HRESULT GetOverlayPosition(LPLONG x, LPLONG y) { return lpVtbl->GetOverlayPosition(this, x, y); }
    HRESULT GetPalette(LPDIRECTDRAWPALETTE *p) { return lpVtbl->GetPalette(this, p); }
    HRESULT GetPixelFormat(LPDDPIXELFORMAT pf) { return lpVtbl->GetPixelFormat(this, pf); }
    HRESULT GetSurfaceDesc(LPDDSURFACEDESC2 sd) { return lpVtbl->GetSurfaceDesc(this, sd); }
    HRESULT IsLost() { return lpVtbl->IsLost(this); }
    HRESULT Lock(LPRECT r, LPDDSURFACEDESC2 sd, DWORD f, HANDLE h) { return lpVtbl->Lock(this, r, sd, f, h); }
    HRESULT ReleaseDC(HDC hdc) { return lpVtbl->ReleaseDC(this, hdc); }
    HRESULT Restore() { return lpVtbl->Restore(this); }
    HRESULT SetClipper(LPDIRECTDRAWCLIPPER c) { return lpVtbl->SetClipper(this, c); }
    HRESULT SetColorKey(DWORD f, LPDDCOLORKEY ck) { return lpVtbl->SetColorKey(this, f, ck); }
    HRESULT SetOverlayPosition(LONG x, LONG y) { return lpVtbl->SetOverlayPosition(this, x, y); }
    HRESULT SetPalette(LPDIRECTDRAWPALETTE p) { return lpVtbl->SetPalette(this, p); }
    HRESULT Unlock(LPRECT r) { return lpVtbl->Unlock(this, r); }
    HRESULT GetDDInterface(LPVOID *dd) { return lpVtbl->GetDDInterface(this, dd); }
    HRESULT PageLock(DWORD f) { return lpVtbl->PageLock(this, f); }
    HRESULT PageUnlock(DWORD f) { return lpVtbl->PageUnlock(this, f); }
    HRESULT SetSurfaceDesc(LPDDSURFACEDESC2 sd, DWORD f) { return lpVtbl->SetSurfaceDesc(this, sd, f); }
    HRESULT SetPriority(DWORD p) { return lpVtbl->SetPriority(this, p); }
    HRESULT GetPriority(LPDWORD p) { return lpVtbl->GetPriority(this, p); }
    HRESULT SetLOD(DWORD l) { return lpVtbl->SetLOD(this, l); }
    HRESULT GetLOD(LPDWORD l) { return lpVtbl->GetLOD(this, l); }
#endif
};

/* ============================================================
 * IDirectDrawPalette Interface
 * ============================================================ */

#undef INTERFACE
#define INTERFACE IDirectDrawPalette

typedef struct IDirectDrawPaletteVtbl {
    HRESULT (WINAPI *QueryInterface)(INTERFACE *This, REFIID riid, LPVOID *ppvObj);
    ULONG   (WINAPI *AddRef)(INTERFACE *This);
    ULONG   (WINAPI *Release)(INTERFACE *This);
    HRESULT (WINAPI *GetCaps)(INTERFACE *This, LPDWORD lpdwCaps);
    HRESULT (WINAPI *GetEntries)(INTERFACE *This, DWORD dwFlags, DWORD dwBase, DWORD dwNumEntries, LPVOID lpEntries);
    HRESULT (WINAPI *Initialize)(INTERFACE *This, LPDIRECTDRAW lpDD, DWORD dwFlags, LPVOID lpDDColorTable);
    HRESULT (WINAPI *SetEntries)(INTERFACE *This, DWORD dwFlags, DWORD dwStartingEntry, DWORD dwCount, LPVOID lpEntries);
} IDirectDrawPaletteVtbl;

struct IDirectDrawPalette {
    IDirectDrawPaletteVtbl *lpVtbl;
#ifdef __cplusplus
    HRESULT QueryInterface(REFIID riid, LPVOID *ppvObj) { return lpVtbl->QueryInterface(this, riid, ppvObj); }
    ULONG   AddRef() { return lpVtbl->AddRef(this); }
    ULONG   Release() { return lpVtbl->Release(this); }
    HRESULT GetCaps(LPDWORD c) { return lpVtbl->GetCaps(this, c); }
    HRESULT GetEntries(DWORD f, DWORD b, DWORD n, LPVOID e) { return lpVtbl->GetEntries(this, f, b, n, e); }
    HRESULT SetEntries(DWORD f, DWORD s, DWORD c, LPVOID e) { return lpVtbl->SetEntries(this, f, s, c, e); }
#endif
};

/* ============================================================
 * IDirectDrawClipper Interface
 * ============================================================ */

#undef INTERFACE
#define INTERFACE IDirectDrawClipper

typedef struct IDirectDrawClipperVtbl {
    HRESULT (WINAPI *QueryInterface)(INTERFACE *This, REFIID riid, LPVOID *ppvObj);
    ULONG   (WINAPI *AddRef)(INTERFACE *This);
    ULONG   (WINAPI *Release)(INTERFACE *This);
    HRESULT (WINAPI *GetClipList)(INTERFACE *This, LPRECT lpRect, LPVOID lpClipList, LPDWORD lpdwSize);
    HRESULT (WINAPI *GetHWnd)(INTERFACE *This, HWND *lphWnd);
    HRESULT (WINAPI *Initialize)(INTERFACE *This, LPDIRECTDRAW lpDD, DWORD dwFlags);
    HRESULT (WINAPI *IsClipListChanged)(INTERFACE *This, LPBOOL lpbChanged);
    HRESULT (WINAPI *SetClipList)(INTERFACE *This, LPVOID lpClipList, DWORD dwFlags);
    HRESULT (WINAPI *SetHWnd)(INTERFACE *This, DWORD dwFlags, HWND hWnd);
} IDirectDrawClipperVtbl;

struct IDirectDrawClipper {
    IDirectDrawClipperVtbl *lpVtbl;
#ifdef __cplusplus
    HRESULT QueryInterface(REFIID riid, LPVOID *ppvObj) { return lpVtbl->QueryInterface(this, riid, ppvObj); }
    ULONG   AddRef() { return lpVtbl->AddRef(this); }
    ULONG   Release() { return lpVtbl->Release(this); }
    HRESULT GetClipList(LPRECT r, LPVOID cl, LPDWORD sz) { return lpVtbl->GetClipList(this, r, cl, sz); }
    HRESULT GetHWnd(HWND *h) { return lpVtbl->GetHWnd(this, h); }
    HRESULT IsClipListChanged(LPBOOL b) { return lpVtbl->IsClipListChanged(this, b); }
    HRESULT SetClipList(LPVOID cl, DWORD f) { return lpVtbl->SetClipList(this, cl, f); }
    HRESULT SetHWnd(DWORD f, HWND h) { return lpVtbl->SetHWnd(this, f, h); }
#endif
};

/* ============================================================
 * IDirectDraw7 Interface
 * ============================================================ */

/* Callback types for enumeration */
typedef HRESULT (CALLBACK *LPDDENUMMODESCALLBACK2)(LPDDSURFACEDESC2, LPVOID);
typedef HRESULT (CALLBACK *LPDDENUMSURFACESCALLBACK7_2)(LPDIRECTDRAWSURFACE7, LPDDSURFACEDESC2, LPVOID);

#undef INTERFACE
#define INTERFACE IDirectDraw7

typedef struct IDirectDraw7Vtbl {
    /* IUnknown methods */
    HRESULT (WINAPI *QueryInterface)(INTERFACE *This, REFIID riid, LPVOID *ppvObj);
    ULONG   (WINAPI *AddRef)(INTERFACE *This);
    ULONG   (WINAPI *Release)(INTERFACE *This);
    /* IDirectDraw7 methods */
    HRESULT (WINAPI *Compact)(INTERFACE *This);
    HRESULT (WINAPI *CreateClipper)(INTERFACE *This, DWORD dwFlags, LPDIRECTDRAWCLIPPER *lplpDDClipper, void *pUnkOuter);
    HRESULT (WINAPI *CreatePalette)(INTERFACE *This, DWORD dwFlags, LPVOID lpDDColorArray, LPDIRECTDRAWPALETTE *lplpDDPalette, void *pUnkOuter);
    HRESULT (WINAPI *CreateSurface)(INTERFACE *This, LPDDSURFACEDESC2 lpDDSurfaceDesc2, LPDIRECTDRAWSURFACE7 *lplpDDSurface, void *pUnkOuter);
    HRESULT (WINAPI *DuplicateSurface)(INTERFACE *This, LPDIRECTDRAWSURFACE7 lpDDSurface, LPDIRECTDRAWSURFACE7 *lplpDupDDSurface);
    HRESULT (WINAPI *EnumDisplayModes)(INTERFACE *This, DWORD dwFlags, LPDDSURFACEDESC2 lpDDSurfaceDesc2, LPVOID lpContext, LPDDENUMMODESCALLBACK2 lpEnumModesCallback);
    HRESULT (WINAPI *EnumSurfaces)(INTERFACE *This, DWORD dwFlags, LPDDSURFACEDESC2 lpDDSD2, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7_2 lpEnumSurfacesCallback);
    HRESULT (WINAPI *FlipToGDISurface)(INTERFACE *This);
    HRESULT (WINAPI *GetCaps)(INTERFACE *This, LPDDCAPS lpDDDriverCaps, LPDDCAPS lpDDHELCaps);
    HRESULT (WINAPI *GetDisplayMode)(INTERFACE *This, LPDDSURFACEDESC2 lpDDSurfaceDesc2);
    HRESULT (WINAPI *GetFourCCCodes)(INTERFACE *This, LPDWORD lpNumCodes, LPDWORD lpCodes);
    HRESULT (WINAPI *GetGDISurface)(INTERFACE *This, LPDIRECTDRAWSURFACE7 *lplpGDIDDSSurface);
    HRESULT (WINAPI *GetMonitorFrequency)(INTERFACE *This, LPDWORD lpdwFrequency);
    HRESULT (WINAPI *GetScanLine)(INTERFACE *This, LPDWORD lpdwScanLine);
    HRESULT (WINAPI *GetVerticalBlankStatus)(INTERFACE *This, LPBOOL lpbIsInVB);
    HRESULT (WINAPI *Initialize)(INTERFACE *This, GUID *lpGUID);
    HRESULT (WINAPI *RestoreDisplayMode)(INTERFACE *This);
    HRESULT (WINAPI *SetCooperativeLevel)(INTERFACE *This, HWND hWnd, DWORD dwFlags);
    HRESULT (WINAPI *SetDisplayMode)(INTERFACE *This, DWORD dwWidth, DWORD dwHeight, DWORD dwBPP, DWORD dwRefreshRate, DWORD dwFlags);
    HRESULT (WINAPI *WaitForVerticalBlank)(INTERFACE *This, DWORD dwFlags, HANDLE hEvent);
    /* Added in IDirectDraw2 */
    HRESULT (WINAPI *GetAvailableVidMem)(INTERFACE *This, LPDDSCAPS2 lpDDSCaps2, LPDWORD lpdwTotal, LPDWORD lpdwFree);
    /* Added in IDirectDraw4 */
    HRESULT (WINAPI *GetSurfaceFromDC)(INTERFACE *This, HDC hdc, LPDIRECTDRAWSURFACE7 *lpDDS);
    HRESULT (WINAPI *RestoreAllSurfaces)(INTERFACE *This);
    HRESULT (WINAPI *TestCooperativeLevel)(INTERFACE *This);
    HRESULT (WINAPI *GetDeviceIdentifier)(INTERFACE *This, LPDDDEVICEIDENTIFIER2 lpdddi, DWORD dwFlags);
    /* Added in IDirectDraw7 */
    HRESULT (WINAPI *StartModeTest)(INTERFACE *This, LPSIZE lpModesToTest, DWORD dwNumEntries, DWORD dwFlags);
    HRESULT (WINAPI *EvaluateMode)(INTERFACE *This, DWORD dwFlags, LPDWORD pSecondsUntilTimeout);
} IDirectDraw7Vtbl;

struct IDirectDraw7 {
    IDirectDraw7Vtbl *lpVtbl;
#ifdef __cplusplus
    HRESULT QueryInterface(REFIID riid, LPVOID *ppvObj) { return lpVtbl->QueryInterface(this, riid, ppvObj); }
    ULONG   AddRef() { return lpVtbl->AddRef(this); }
    ULONG   Release() { return lpVtbl->Release(this); }
    HRESULT Compact() { return lpVtbl->Compact(this); }
    HRESULT CreateClipper(DWORD f, LPDIRECTDRAWCLIPPER *c, void *u) { return lpVtbl->CreateClipper(this, f, c, u); }
    HRESULT CreatePalette(DWORD f, LPVOID ca, LPDIRECTDRAWPALETTE *p, void *u) { return lpVtbl->CreatePalette(this, f, ca, p, u); }
    HRESULT CreateSurface(LPDDSURFACEDESC2 sd, LPDIRECTDRAWSURFACE7 *s, void *u) { return lpVtbl->CreateSurface(this, sd, s, u); }
    HRESULT DuplicateSurface(LPDIRECTDRAWSURFACE7 s, LPDIRECTDRAWSURFACE7 *d) { return lpVtbl->DuplicateSurface(this, s, d); }
    HRESULT EnumDisplayModes(DWORD f, LPDDSURFACEDESC2 sd, LPVOID ctx, LPDDENUMMODESCALLBACK2 cb) { return lpVtbl->EnumDisplayModes(this, f, sd, ctx, cb); }
    HRESULT EnumSurfaces(DWORD f, LPDDSURFACEDESC2 sd, LPVOID ctx, LPDDENUMSURFACESCALLBACK7_2 cb) { return lpVtbl->EnumSurfaces(this, f, sd, ctx, cb); }
    HRESULT FlipToGDISurface() { return lpVtbl->FlipToGDISurface(this); }
    HRESULT GetCaps(LPDDCAPS dc, LPDDCAPS hc) { return lpVtbl->GetCaps(this, dc, hc); }
    HRESULT GetDisplayMode(LPDDSURFACEDESC2 sd) { return lpVtbl->GetDisplayMode(this, sd); }
    HRESULT GetFourCCCodes(LPDWORD n, LPDWORD c) { return lpVtbl->GetFourCCCodes(this, n, c); }
    HRESULT GetGDISurface(LPDIRECTDRAWSURFACE7 *s) { return lpVtbl->GetGDISurface(this, s); }
    HRESULT GetMonitorFrequency(LPDWORD f) { return lpVtbl->GetMonitorFrequency(this, f); }
    HRESULT GetScanLine(LPDWORD sl) { return lpVtbl->GetScanLine(this, sl); }
    HRESULT GetVerticalBlankStatus(LPBOOL vb) { return lpVtbl->GetVerticalBlankStatus(this, vb); }
    HRESULT RestoreDisplayMode() { return lpVtbl->RestoreDisplayMode(this); }
    HRESULT SetCooperativeLevel(HWND h, DWORD f) { return lpVtbl->SetCooperativeLevel(this, h, f); }
    HRESULT SetDisplayMode(DWORD w, DWORD h, DWORD bpp, DWORD r, DWORD f) { return lpVtbl->SetDisplayMode(this, w, h, bpp, r, f); }
    HRESULT WaitForVerticalBlank(DWORD f, HANDLE h) { return lpVtbl->WaitForVerticalBlank(this, f, h); }
    HRESULT GetAvailableVidMem(LPDDSCAPS2 caps, LPDWORD t, LPDWORD f) { return lpVtbl->GetAvailableVidMem(this, caps, t, f); }
    HRESULT GetSurfaceFromDC(HDC hdc, LPDIRECTDRAWSURFACE7 *s) { return lpVtbl->GetSurfaceFromDC(this, hdc, s); }
    HRESULT RestoreAllSurfaces() { return lpVtbl->RestoreAllSurfaces(this); }
    HRESULT TestCooperativeLevel() { return lpVtbl->TestCooperativeLevel(this); }
    HRESULT GetDeviceIdentifier(LPDDDEVICEIDENTIFIER2 di, DWORD f) { return lpVtbl->GetDeviceIdentifier(this, di, f); }
    HRESULT StartModeTest(LPSIZE m, DWORD n, DWORD f) { return lpVtbl->StartModeTest(this, m, n, f); }
    HRESULT EvaluateMode(DWORD f, LPDWORD t) { return lpVtbl->EvaluateMode(this, f, t); }
#endif
};

#undef INTERFACE

/* DirectDraw enumeration callback types */
typedef BOOL (CALLBACK *LPDDENUMCALLBACKA)(GUID*, LPSTR, LPSTR, LPVOID);
typedef BOOL (CALLBACK *LPDDENUMCALLBACKEXA)(GUID*, LPSTR, LPSTR, LPVOID, HMONITOR);
typedef LPDDENUMCALLBACKA LPDDENUMCALLBACK;
typedef LPDDENUMCALLBACKEXA LPDDENUMCALLBACKEX;

/* Function pointer types for GetProcAddress */
typedef HRESULT (WINAPI *LPDIRECTDRAWCREATEEX)(GUID*, LPVOID*, REFIID, void*);
typedef HRESULT (WINAPI *LPDIRECTDRAWENUMERATEEXA)(LPDDENUMCALLBACKEXA, LPVOID, DWORD);
typedef LPDIRECTDRAWENUMERATEEXA LPDIRECTDRAWENUMERATEEX;

/* Forward declaration - implemented in d3d_gl.cpp */
extern "C" IDirectDraw7* FF_CreateDirectDraw7(void);

/* Creation functions */
static inline HRESULT DirectDrawCreate(GUID* lpGUID, LPDIRECTDRAW* lplpDD, void* pUnkOuter) {
    (void)lpGUID; (void)lplpDD; (void)pUnkOuter;
    return DDERR_NODIRECTDRAWSUPPORT;
}

static inline HRESULT DirectDrawCreateEx(GUID* lpGUID, LPVOID* lplpDD, REFIID iid, void* pUnkOuter) {
    (void)lpGUID; (void)pUnkOuter;
    if (!lplpDD) return DDERR_INVALIDPARAMS;

    /* Create our OpenGL-backed DirectDraw7 interface */
    IDirectDraw7* pDD7 = FF_CreateDirectDraw7();
    if (!pDD7) return DDERR_NODIRECTDRAWSUPPORT;

    *lplpDD = pDD7;
    return DD_OK;
}

/* Enumeration functions - stubs */
static inline HRESULT DirectDrawEnumerate(LPDDENUMCALLBACK lpCallback, LPVOID lpContext) {
    (void)lpCallback; (void)lpContext;
    return DD_OK;
}

static inline HRESULT DirectDrawEnumerateEx(LPDDENUMCALLBACKEX lpCallback, LPVOID lpContext, DWORD dwFlags) {
    (void)lpCallback; (void)lpContext; (void)dwFlags;
    return DD_OK;
}

/* FOURCC macro */
#ifndef MAKEFOURCC
#define MAKEFOURCC(ch0, ch1, ch2, ch3) \
    ((DWORD)(BYTE)(ch0) | ((DWORD)(BYTE)(ch1) << 8) | \
    ((DWORD)(BYTE)(ch2) << 16) | ((DWORD)(BYTE)(ch3) << 24))
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DDRAW_H */
