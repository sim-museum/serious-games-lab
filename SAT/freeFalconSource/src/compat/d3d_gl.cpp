/*
 * FreeFalcon Linux Port - D3D7 to OpenGL Translation Layer
 *
 * This file implements the Direct3D 7 interfaces using OpenGL,
 * allowing the game's rendering code to work on Linux.
 */

#ifdef FF_LINUX

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <map>

#include <GL/glew.h>
#include <GL/gl.h>
#include <SDL2/SDL.h>

#include "compat_types.h"
#include "compat_wingdi.h"  // For LPPALETTEENTRY
#include "objbase.h"  // For STDMETHODCALLTYPE
#include "ddraw.h"
#include "d3dtypes.h"
#include "d3d.h"

#include "ffviper/ff_linux_debug.h"
// External frame counter for correlated debug output
extern unsigned long g_RenderFrameCount;

// Missing type definitions for stub functions
typedef void* LPDDBLTBATCH;

// D3D capability flags (not all are in d3dtypes.h)
#ifndef D3DPMISCCAPS_CULLNONE
#define D3DPMISCCAPS_CULLNONE           0x00000010
#define D3DPMISCCAPS_CULLCW             0x00000020
#define D3DPMISCCAPS_CULLCCW            0x00000040
#endif

#ifndef D3DPRASTERCAPS_DITHER
#define D3DPRASTERCAPS_DITHER           0x00000001
#define D3DPRASTERCAPS_ZTEST            0x00000010
#define D3DPRASTERCAPS_FOGVERTEX        0x00000080
#define D3DPRASTERCAPS_FOGTABLE         0x00000100
#define D3DPRASTERCAPS_MIPMAPLODBIAS    0x00002000
#endif

#ifndef D3DPCMPCAPS_ALWAYS
#define D3DPCMPCAPS_NEVER               0x00000001
#define D3DPCMPCAPS_LESS                0x00000002
#define D3DPCMPCAPS_EQUAL               0x00000004
#define D3DPCMPCAPS_LESSEQUAL           0x00000008
#define D3DPCMPCAPS_GREATER             0x00000010
#define D3DPCMPCAPS_NOTEQUAL            0x00000020
#define D3DPCMPCAPS_GREATEREQUAL        0x00000040
#define D3DPCMPCAPS_ALWAYS              0x00000080
#endif

#ifndef D3DPBLENDCAPS_ZERO
#define D3DPBLENDCAPS_ZERO              0x00000001
#define D3DPBLENDCAPS_ONE               0x00000002
#define D3DPBLENDCAPS_SRCCOLOR          0x00000004
#define D3DPBLENDCAPS_INVSRCCOLOR       0x00000008
#define D3DPBLENDCAPS_SRCALPHA          0x00000010
#define D3DPBLENDCAPS_INVSRCALPHA       0x00000020
#define D3DPBLENDCAPS_DESTALPHA         0x00000040
#define D3DPBLENDCAPS_INVDESTALPHA      0x00000080
#define D3DPBLENDCAPS_DESTCOLOR         0x00000100
#define D3DPBLENDCAPS_INVDESTCOLOR      0x00000200
#define D3DPBLENDCAPS_SRCALPHASAT       0x00000400
#endif

#ifndef D3DPSHADECAPS_COLORGOURAUDRGB
#define D3DPSHADECAPS_COLORGOURAUDRGB   0x00000008
#define D3DPSHADECAPS_SPECULARGOURAUDRGB 0x00000200
#define D3DPSHADECAPS_ALPHAGOURAUDBLEND 0x00004000
#define D3DPSHADECAPS_FOGGOURAUD        0x00080000
#endif

#ifndef D3DPTEXTURECAPS_PERSPECTIVE
#define D3DPTEXTURECAPS_PERSPECTIVE     0x00000001
#define D3DPTEXTURECAPS_ALPHA           0x00000004
#define D3DPTEXTURECAPS_TRANSPARENCY    0x00000008
#define D3DPTEXTURECAPS_TEXREPEATNOTSCALEDBYSIZE 0x00000040
#endif

#ifndef D3DPTFILTERCAPS_NEAREST
#define D3DPTFILTERCAPS_NEAREST         0x00000001
#define D3DPTFILTERCAPS_LINEAR          0x00000002
#define D3DPTFILTERCAPS_MIPNEAREST      0x00000004
#define D3DPTFILTERCAPS_MIPLINEAR       0x00000008
#define D3DPTFILTERCAPS_LINEARMIPNEAREST 0x00000010
#define D3DPTFILTERCAPS_LINEARMIPLINEAR 0x00000020
#endif

#ifndef D3DDEVCAPS_FLOATTLVERTEX
#define D3DDEVCAPS_FLOATTLVERTEX        0x00000001
#define D3DDEVCAPS_EXECUTESYSTEMMEMORY  0x00000010
#define D3DDEVCAPS_EXECUTEVIDEOMEMORY   0x00000020
#define D3DDEVCAPS_TLVERTEXSYSTEMMEMORY 0x00000040
#define D3DDEVCAPS_TLVERTEXVIDEOMEMORY  0x00000080
#define D3DDEVCAPS_TEXTURESYSTEMMEMORY  0x00000100
#define D3DDEVCAPS_TEXTUREVIDEOMEMORY   0x00000200
#define D3DDEVCAPS_DRAWPRIMTLVERTEX     0x00000400
#define D3DDEVCAPS_CANRENDERAFTERFLIP   0x00000800
#define D3DDEVCAPS_TEXTURENONLOCALVIDMEM 0x00001000
#define D3DDEVCAPS_DRAWPRIMITIVES2      0x00002000
#define D3DDEVCAPS_DRAWPRIMITIVES2EX    0x00008000
#define D3DDEVCAPS_HWRASTERIZATION      0x00080000
#define D3DDEVCAPS_HWTRANSFORMANDLIGHT  0x00010000
#endif

// Debug logging
#define D3DGL_DEBUG 0
#if D3DGL_DEBUG
#define D3DGL_LOG(fmt, ...) printf("[D3DGL] " fmt "\n", ##__VA_ARGS__)
#else
#define D3DGL_LOG(fmt, ...) do {} while(0)
#endif

// Maximum number of lights
#define MAX_GL_LIGHTS 8

// Maximum texture stages
#define MAX_TEXTURE_STAGES 8

// Stencil state tracking (D3D sets params individually, GL needs them together)
static GLenum g_stencilFunc = GL_ALWAYS;
static GLint  g_stencilRef = 0;
static GLuint g_stencilMask = 0xFFFFFFFF;
static GLenum g_stencilFail = GL_KEEP;
static GLenum g_stencilZFail = GL_KEEP;
static GLenum g_stencilPass = GL_KEEP;

static GLenum D3DCmpToGL(DWORD d3dcmp) {
    switch (d3dcmp) {
        case D3DCMP_NEVER:        return GL_NEVER;
        case D3DCMP_LESS:         return GL_LESS;
        case D3DCMP_EQUAL:        return GL_EQUAL;
        case D3DCMP_LESSEQUAL:    return GL_LEQUAL;
        case D3DCMP_GREATER:      return GL_GREATER;
        case D3DCMP_NOTEQUAL:     return GL_NOTEQUAL;
        case D3DCMP_GREATEREQUAL: return GL_GEQUAL;
        case D3DCMP_ALWAYS:       return GL_ALWAYS;
        default:                  return GL_ALWAYS;
    }
}

static GLenum D3DStencilOpToGL(DWORD d3dop) {
    switch (d3dop) {
        case D3DSTENCILOP_KEEP:    return GL_KEEP;
        case D3DSTENCILOP_ZERO:    return GL_ZERO;
        case D3DSTENCILOP_REPLACE: return GL_REPLACE;
        case D3DSTENCILOP_INCRSAT: return GL_INCR;
        case D3DSTENCILOP_DECRSAT: return GL_DECR;
        case D3DSTENCILOP_INVERT:  return GL_INVERT;
        case D3DSTENCILOP_INCR:    return GL_INCR_WRAP;
        case D3DSTENCILOP_DECR:    return GL_DECR_WRAP;
        default:                   return GL_KEEP;
    }
}

// Maximum state blocks
#define MAX_STATE_BLOCKS 256

// Forward declarations
struct D3D7Device;
struct D3D7VertexBuffer;
struct D3D7Interface;
struct D3D7Surface;

// Forward declaration of the vtable (defined later)
extern const IDirectDrawSurface7Vtbl g_DDS7Vtbl;

// ============================================================
// D3D7 Surface (texture) implementation
// ============================================================
struct D3D7Surface : public IDirectDrawSurface7 {
    GLuint glTexture;
    int width;
    int height;
    DWORD caps;
    DDPIXELFORMAT pixelFormat;
    LONG refCount;

    // Pixel buffer for Lock/Unlock and Blt operations
    unsigned char* pixelData;
    int pitch;  // Bytes per row
    bool isLocked;
    bool isDirty;  // Needs texture upload
    bool isPrimary;  // Is this the primary (front) surface?

    // FF_LINUX: DDS/DXT compressed texture support
    // When a surface is created with DDPF_FOURCC, the pixel data is DXT compressed
    // and must be uploaded via glCompressedTexImage2D instead of glTexImage2D.
    GLenum dxtFormat;       // GL_COMPRESSED_RGB_S3TC_DXT1_EXT, etc. 0 = not DXT
    int    dxtDataSize;     // Size of compressed data in bytes

    // FF_LINUX: FBO support for render-to-texture
    GLuint fboId;           // OpenGL Framebuffer Object ID (0 = none)

    // FF_LINUX: Color key (chroma key) support
    bool hasColorKey;       // True if SetColorKey was called with a valid key
    DWORD colorKeyLow;      // Low value of the color key range (BGRA pixel value)

    D3D7Surface() : glTexture(0), width(0), height(0), caps(0), refCount(1),
                    pixelData(nullptr), pitch(0), isLocked(false), isDirty(false), isPrimary(false),
                    dxtFormat(0), dxtDataSize(0), fboId(0),
                    hasColorKey(false), colorKeyLow(0) {
        // Initialize inherited lpVtbl to the correct vtable
        lpVtbl = const_cast<IDirectDrawSurface7Vtbl*>(&g_DDS7Vtbl);
        memset(&pixelFormat, 0, sizeof(pixelFormat));
        pixelFormat.dwSize = sizeof(DDPIXELFORMAT);
    }

    ~D3D7Surface() {
        if (fboId) {
            glDeleteFramebuffers(1, &fboId);
        }
        if (glTexture) {
            glDeleteTextures(1, &glTexture);
        }
        if (pixelData) {
            delete[] pixelData;
        }
    }

    void AllocatePixelBuffer() {
        if (!pixelData && width > 0 && height > 0) {
            if (dxtFormat != 0) {
                // DXT compressed: allocate enough for the compressed data
                // DXT1: 8 bytes per 4x4 block, DXT3/5: 16 bytes per 4x4 block
                int blockW = (width + 3) / 4;
                int blockH = (height + 3) / 4;
                int blockSize = (dxtFormat == GL_COMPRESSED_RGB_S3TC_DXT1_EXT ||
                                 dxtFormat == GL_COMPRESSED_RGBA_S3TC_DXT1_EXT) ? 8 : 16;
                dxtDataSize = blockW * blockH * blockSize;
                pitch = blockW * blockSize;  // "pitch" per block row
                pixelData = new unsigned char[dxtDataSize];
                memset(pixelData, 0, dxtDataSize);
            } else {
                int bpp = pixelFormat.dwRGBBitCount ? pixelFormat.dwRGBBitCount / 8 : 4;
                pitch = width * bpp;
                // Align pitch to 4 bytes
                pitch = (pitch + 3) & ~3;
                pixelData = new unsigned char[pitch * height];
                memset(pixelData, 0, pitch * height);
            }
        }
    }
};

// Global primary surface for screen presentation
static D3D7Surface* g_pPrimarySurface = nullptr;

// ============================================================
// Render state storage for state blocks
// ============================================================
struct RenderStateBlock {
    bool active;
    DWORD blockType;  // D3DSBT_ALL, D3DSBT_PIXELSTATE, or D3DSBT_VERTEXSTATE
    std::map<D3DRENDERSTATETYPE, DWORD> renderStates;
    std::map<std::pair<DWORD, D3DTEXTURESTAGESTATETYPE>, DWORD> textureStageStates;
    D3DMATERIAL7 material;
    D3DLIGHT7 lights[MAX_GL_LIGHTS];
    bool lightEnabled[MAX_GL_LIGHTS];
    D3DMATRIX projMatrix;
    D3DMATRIX viewMatrix;
    D3DMATRIX worldMatrix;
    D3DVIEWPORT7 viewport;

    RenderStateBlock() : active(false), blockType(0) {
        memset(&material, 0, sizeof(material));
        memset(lights, 0, sizeof(lights));
        memset(lightEnabled, 0, sizeof(lightEnabled));
        memset(&projMatrix, 0, sizeof(projMatrix));
        memset(&viewMatrix, 0, sizeof(viewMatrix));
        memset(&worldMatrix, 0, sizeof(worldMatrix));
        memset(&viewport, 0, sizeof(viewport));
    }
};

// ============================================================
// D3D7 Device implementation
// ============================================================
struct D3D7Device : public IDirect3DDevice7 {
    LONG refCount;
    D3D7Interface* d3d;
    D3D7Surface* renderTarget;
    D3D7Surface* defaultRenderTarget;  // FF_LINUX: The initial RT (screen back buffer)

    // Current state
    D3DMATRIX projMatrix;
    D3DMATRIX viewMatrix;
    D3DMATRIX worldMatrix;
    D3DVIEWPORT7 viewport;
    D3DMATERIAL7 currentMaterial;
    D3DLIGHT7 lights[MAX_GL_LIGHTS];
    bool lightEnabled[MAX_GL_LIGHTS];
    D3D7Surface* textures[MAX_TEXTURE_STAGES];

    // Render state cache
    std::map<D3DRENDERSTATETYPE, DWORD> renderStates;
    std::map<std::pair<DWORD, D3DTEXTURESTAGESTATETYPE>, DWORD> textureStageStates;

    // State blocks
    RenderStateBlock stateBlocks[MAX_STATE_BLOCKS];
    DWORD nextStateBlockHandle;
    bool recordingStateBlock;
    DWORD recordingStateBlockHandle;

    // Scene state
    bool inScene;

    D3D7Device();
    void ApplyRenderState(D3DRENDERSTATETYPE state, DWORD value);
    void ApplyTextureStageState(DWORD stage, D3DTEXTURESTAGESTATETYPE type, DWORD value);
    void ApplyMaterial();
    void ApplyLights();
    void ApplyMatrices();
    void SetupVertexFormat(DWORD fvf);
    void DrawVertices(D3DPRIMITIVETYPE primType, DWORD fvf, const void* vertices, DWORD count);
    GLenum GetGLPrimitiveType(D3DPRIMITIVETYPE d3dType);
};

// ============================================================
// D3D7 Vertex Buffer implementation
// ============================================================
struct D3D7VertexBuffer : public IDirect3DVertexBuffer7 {
    LONG refCount;
    D3DVERTEXBUFFERDESC desc;
    void* data;
    DWORD dataSize;
    bool locked;

    D3D7VertexBuffer() : refCount(1), data(nullptr), dataSize(0), locked(false) {
        memset(&desc, 0, sizeof(desc));
    }

    ~D3D7VertexBuffer() {
        if (data) {
            free(data);
        }
    }
};

// ============================================================
// D3D7 Interface implementation
// ============================================================
struct DD7Interface;  // Forward declaration

struct D3D7Interface : public IDirect3D7 {
    LONG refCount;
    DD7Interface* dd7;  // Parent DD7 interface

    D3D7Interface() : refCount(1), dd7(nullptr) {}
};

// ============================================================
// Helper functions
// ============================================================
static int GetVertexSize(DWORD fvf) {
    int size = 0;

    // Position (required)
    if (fvf & D3DFVF_XYZ) size += 3 * sizeof(float);
    else if (fvf & D3DFVF_XYZRHW) size += 4 * sizeof(float);

    // Normal
    if (fvf & D3DFVF_NORMAL) size += 3 * sizeof(float);

    // Diffuse color
    if (fvf & D3DFVF_DIFFUSE) size += sizeof(DWORD);

    // Specular color
    if (fvf & D3DFVF_SPECULAR) size += sizeof(DWORD);

    // Texture coordinates
    int texCount = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
    size += texCount * 2 * sizeof(float);

    return size;
}

static void D3DColorToGL(D3DCOLOR color, float* r, float* g, float* b, float* a) {
    *a = ((color >> 24) & 0xFF) / 255.0f;
    *r = ((color >> 16) & 0xFF) / 255.0f;
    *g = ((color >> 8) & 0xFF) / 255.0f;
    *b = (color & 0xFF) / 255.0f;
}

static void D3DColorValueToGL(const D3DCOLORVALUE& cv, float* rgba) {
    rgba[0] = cv.r;
    rgba[1] = cv.g;
    rgba[2] = cv.b;
    rgba[3] = cv.a;
}

// ============================================================
// IDirect3DDevice7 vtable implementation
// ============================================================
static HRESULT STDMETHODCALLTYPE D3D7Dev_QueryInterface(IDirect3DDevice7* This, REFIID riid, void** ppv) {
    D3DGL_LOG("QueryInterface");
    *ppv = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE D3D7Dev_AddRef(IDirect3DDevice7* This) {
    D3D7Device* dev = (D3D7Device*)This;
    return ++dev->refCount;
}

static ULONG STDMETHODCALLTYPE D3D7Dev_Release(IDirect3DDevice7* This) {
    D3D7Device* dev = (D3D7Device*)This;
    LONG ref = --dev->refCount;
    if (ref == 0) {
        delete dev;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetCaps(IDirect3DDevice7* This, LPD3DDEVICEDESC7 lpDesc) {
    D3DGL_LOG("GetCaps");
    if (!lpDesc) return DDERR_INVALIDPARAMS;

    memset(lpDesc, 0, sizeof(D3DDEVICEDESC7));

    // Report capabilities that we support
    lpDesc->dwDevCaps = D3DDEVCAPS_EXECUTESYSTEMMEMORY |
                        D3DDEVCAPS_TLVERTEXSYSTEMMEMORY |
                        D3DDEVCAPS_TEXTUREVIDEOMEMORY |
                        D3DDEVCAPS_DRAWPRIMTLVERTEX |
                        D3DDEVCAPS_CANRENDERAFTERFLIP |
                        D3DDEVCAPS_DRAWPRIMITIVES2 |
                        D3DDEVCAPS_DRAWPRIMITIVES2EX;

    lpDesc->dpcTriCaps.dwShadeCaps = D3DPSHADECAPS_COLORGOURAUDRGB | D3DPSHADECAPS_SPECULARGOURAUDRGB;
    lpDesc->dpcTriCaps.dwTextureCaps = D3DPTEXTURECAPS_PERSPECTIVE | D3DPTEXTURECAPS_ALPHA;
    lpDesc->dpcTriCaps.dwTextureFilterCaps = D3DPTFILTERCAPS_LINEAR | D3DPTFILTERCAPS_NEAREST;
    lpDesc->dpcTriCaps.dwTextureBlendCaps = 0x02 | 0x04;  // MODULATE | ADD
    lpDesc->dpcTriCaps.dwTextureAddressCaps = 0x01 | 0x04;  // WRAP | CLAMP
    lpDesc->dpcTriCaps.dwRasterCaps = D3DPRASTERCAPS_FOGTABLE | D3DPRASTERCAPS_FOGVERTEX | D3DPRASTERCAPS_ZBUFFERLESSHSR;
    lpDesc->dpcTriCaps.dwZCmpCaps = D3DPCMPCAPS_LESSEQUAL | D3DPCMPCAPS_LESS | D3DPCMPCAPS_ALWAYS;
    // FF_LINUX: Report ALL alpha compare caps (0xFF). The original code checks
    // `dwAlphaCmpCaps & D3DCMP_GREATEREQUAL` (enum value 7) instead of the correct
    // `D3DPCMPCAPS_GREATEREQUAL` (bit flag 0x40). Real Windows drivers return 0xFF
    // (all caps), making the buggy check pass. We must match this behavior.
    lpDesc->dpcTriCaps.dwAlphaCmpCaps = 0xFF;
    lpDesc->dpcTriCaps.dwSrcBlendCaps = D3DPBLENDCAPS_SRCALPHA | D3DPBLENDCAPS_ONE | D3DPBLENDCAPS_ZERO;
    lpDesc->dpcTriCaps.dwDestBlendCaps = D3DPBLENDCAPS_INVSRCALPHA | D3DPBLENDCAPS_ONE | D3DPBLENDCAPS_ZERO;

    lpDesc->dwMaxTextureWidth = 2048;
    lpDesc->dwMaxTextureHeight = 2048;
    lpDesc->wMaxTextureBlendStages = MAX_TEXTURE_STAGES;
    lpDesc->wMaxSimultaneousTextures = MAX_TEXTURE_STAGES;
    lpDesc->dwMaxActiveLights = MAX_GL_LIGHTS;

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_EnumTextureFormats(IDirect3DDevice7* This, void* cb, LPVOID arg) {
    D3DGL_LOG("EnumTextureFormats");
    // Enumerate supported texture formats
    typedef HRESULT (CALLBACK *LPDDENUMTEXTUREFORMATSCALLBACK)(LPDDPIXELFORMAT lpDDPixFmt, LPVOID lpContext);
    LPDDENUMTEXTUREFORMATSCALLBACK callback = (LPDDENUMTEXTUREFORMATSCALLBACK)cb;

    DDPIXELFORMAT pf;
    HRESULT hr;

    // 32-bit XRGB (no alpha) - needed for DEFAULT texture category
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_RGB;  // No DDPF_ALPHAPIXELS
    pf.dwRGBBitCount = 32;
    pf.dwRBitMask = 0x00FF0000;
    pf.dwGBitMask = 0x0000FF00;
    pf.dwBBitMask = 0x000000FF;
    pf.dwRGBAlphaBitMask = 0x00000000;  // No alpha
    hr = callback(&pf, arg);
    if (hr == DDENUMRET_CANCEL) return D3D_OK;

    // 32-bit ARGB (with 8-bit alpha) - needed for CHROMA/ALPHA/CHROMA_ALPHA
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    pf.dwRGBBitCount = 32;
    pf.dwRBitMask = 0x00FF0000;
    pf.dwGBitMask = 0x0000FF00;
    pf.dwBBitMask = 0x000000FF;
    pf.dwRGBAlphaBitMask = 0xFF000000;
    hr = callback(&pf, arg);
    if (hr == DDENUMRET_CANCEL) return D3D_OK;

    // 16-bit RGB565 (no alpha)
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_RGB;
    pf.dwRGBBitCount = 16;
    pf.dwRBitMask = 0xF800;
    pf.dwGBitMask = 0x07E0;
    pf.dwBBitMask = 0x001F;
    pf.dwRGBAlphaBitMask = 0x0000;
    hr = callback(&pf, arg);
    if (hr == DDENUMRET_CANCEL) return D3D_OK;

    // 16-bit ARGB4444 (with 4-bit alpha)
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    pf.dwRGBBitCount = 16;
    pf.dwRBitMask = 0x0F00;
    pf.dwGBitMask = 0x00F0;
    pf.dwBBitMask = 0x000F;
    pf.dwRGBAlphaBitMask = 0xF000;
    hr = callback(&pf, arg);
    if (hr == DDENUMRET_CANCEL) return D3D_OK;

    // 16-bit ARGB1555 (with 1-bit alpha)
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    pf.dwRGBBitCount = 16;
    pf.dwRBitMask = 0x7C00;
    pf.dwGBitMask = 0x03E0;
    pf.dwBBitMask = 0x001F;
    pf.dwRGBAlphaBitMask = 0x8000;
    hr = callback(&pf, arg);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_BeginScene(IDirect3DDevice7* This) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("BeginScene");

    if (dev->inScene) return D3DERR_SCENE_IN_SCENE;
    dev->inScene = true;

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_EndScene(IDirect3DDevice7* This) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("EndScene");

    if (!dev->inScene) return D3DERR_SCENE_NOT_IN_SCENE;
    dev->inScene = false;

    glFlush();
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetDirect3D(IDirect3DDevice7* This, LPDIRECT3D7* lplpD3D) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("GetDirect3D");

    if (!lplpD3D) return DDERR_INVALIDPARAMS;
    *lplpD3D = dev->d3d;
    if (dev->d3d) dev->d3d->lpVtbl->AddRef(dev->d3d);
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetRenderTarget(IDirect3DDevice7* This, LPDIRECTDRAWSURFACE7 lpNewRT, DWORD dwFlags) {
    D3D7Device* dev = (D3D7Device*)This;
    D3D7Surface* newTarget = (D3D7Surface*)lpNewRT;
    D3DGL_LOG("SetRenderTarget surf=%p isPrimary=%d", (void*)newTarget, newTarget ? newTarget->isPrimary : -1);
    dev->renderTarget = newTarget;


    // FF_LINUX: FBO-based render target switching for RTT (render-to-texture)
    // Use defaultRenderTarget to distinguish screen vs off-screen surfaces
    if (newTarget && newTarget != dev->defaultRenderTarget) {
        // Rendering to an off-screen surface - need FBO
        if (!newTarget->fboId) {
            // Create FBO
            glGenFramebuffers(1, &newTarget->fboId);
            glBindFramebuffer(GL_FRAMEBUFFER, newTarget->fboId);

            // Ensure the surface has a GL texture
            if (!newTarget->glTexture) {
                glGenTextures(1, &newTarget->glTexture);
                glBindTexture(GL_TEXTURE_2D, newTarget->glTexture);
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, newTarget->width, newTarget->height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            }

            // Attach texture as color attachment
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, newTarget->glTexture, 0);

            // Attach depth renderbuffer (needed for D3D7 depth test compatibility)
            GLuint depthRB = 0;
            glGenRenderbuffers(1, &depthRB);
            glBindRenderbuffer(GL_RENDERBUFFER, depthRB);
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, newTarget->width, newTarget->height);
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthRB);

            GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
            if (status != GL_FRAMEBUFFER_COMPLETE) {
                fprintf(stderr, "[SetRenderTarget] FBO incomplete: 0x%x for surface %p (%dx%d)\n",
                        status, (void*)newTarget, newTarget->width, newTarget->height);
            }
        } else {
            glBindFramebuffer(GL_FRAMEBUFFER, newTarget->fboId);
        }
    } else {
        // Rendering to the default framebuffer (screen back buffer)
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetRenderTarget(IDirect3DDevice7* This, LPDIRECTDRAWSURFACE7* lplpRT) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("GetRenderTarget");
    if (!lplpRT) return DDERR_INVALIDPARAMS;
    *lplpRT = dev->renderTarget;
    return D3D_OK;
}

int g_ClearCallCount = 0;
int g_DrawPrimitiveCount = 0;
static HRESULT STDMETHODCALLTYPE D3D7Dev_Clear(IDirect3DDevice7* This, DWORD dwCount, LPD3DRECT lpRects, DWORD dwFlags, D3DCOLOR dwColor, D3DVALUE dvZ, DWORD dwStencil) {
    D3DGL_LOG("Clear flags=0x%x color=0x%x", dwFlags, dwColor);
    g_ClearCallCount++;

    GLbitfield clearMask = 0;

    if (dwFlags & D3DCLEAR_TARGET) {
        float r, g, b, a;
        D3DColorToGL(dwColor, &r, &g, &b, &a);
        glClearColor(r, g, b, a);
        clearMask |= GL_COLOR_BUFFER_BIT;
    }

    if (dwFlags & D3DCLEAR_ZBUFFER) {
        glClearDepth(dvZ);
        clearMask |= GL_DEPTH_BUFFER_BIT;
    }

    if (dwFlags & D3DCLEAR_STENCIL) {
        glClearStencil(dwStencil);
        clearMask |= GL_STENCIL_BUFFER_BIT;
    }

    if (clearMask) {
        if (dwCount == 0 || lpRects == nullptr) {
            glClear(clearMask);
        } else {
            // Clear specific rectangles
            glEnable(GL_SCISSOR_TEST);
            for (DWORD i = 0; i < dwCount; i++) {
                glScissor(lpRects[i].x1, lpRects[i].y1,
                         lpRects[i].x2 - lpRects[i].x1,
                         lpRects[i].y2 - lpRects[i].y1);
                glClear(clearMask);
            }
            glDisable(GL_SCISSOR_TEST);
        }
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetTransform(IDirect3DDevice7* This, D3DTRANSFORMSTATETYPE state, LPD3DMATRIX lpMatrix) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetTransform type=%d", state);

    if (!lpMatrix) return DDERR_INVALIDPARAMS;

    switch (state) {
        case D3DTRANSFORMSTATE_WORLD:
            memcpy(&dev->worldMatrix, lpMatrix, sizeof(D3DMATRIX));
            break;
        case D3DTRANSFORMSTATE_VIEW:
            memcpy(&dev->viewMatrix, lpMatrix, sizeof(D3DMATRIX));
            break;
        case D3DTRANSFORMSTATE_PROJECTION:
            memcpy(&dev->projMatrix, lpMatrix, sizeof(D3DMATRIX));
            break;
        default:
            D3DGL_LOG("Unknown transform state: %d", state);
            break;
    }

    dev->ApplyMatrices();
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetTransform(IDirect3DDevice7* This, D3DTRANSFORMSTATETYPE state, LPD3DMATRIX lpMatrix) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("GetTransform type=%d", state);

    if (!lpMatrix) return DDERR_INVALIDPARAMS;

    switch (state) {
        case D3DTRANSFORMSTATE_WORLD:
            memcpy(lpMatrix, &dev->worldMatrix, sizeof(D3DMATRIX));
            break;
        case D3DTRANSFORMSTATE_VIEW:
            memcpy(lpMatrix, &dev->viewMatrix, sizeof(D3DMATRIX));
            break;
        case D3DTRANSFORMSTATE_PROJECTION:
            memcpy(lpMatrix, &dev->projMatrix, sizeof(D3DMATRIX));
            break;
        default:
            return DDERR_INVALIDPARAMS;
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetViewport(IDirect3DDevice7* This, LPD3DVIEWPORT7 lpViewport) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetViewport %dx%d", lpViewport->dwWidth, lpViewport->dwHeight);

    if (!lpViewport) return DDERR_INVALIDPARAMS;

    // FF_LINUX: Only make GL calls if context is current on this thread.
    // Do NOT call SDL_GL_MakeCurrent here - it would steal the context from the sim thread.
    extern SDL_GLContext g_GLContext;
    extern SDL_Window* g_SDLWindow;
    if (!g_GLContext || !SDL_GL_GetCurrentContext()) {
        // No GL context at all - just store the viewport data, skip GL calls
        memcpy(&dev->viewport, lpViewport, sizeof(D3DVIEWPORT7));
        return D3D_OK;
    }

    memcpy(&dev->viewport, lpViewport, sizeof(D3DVIEWPORT7));

    // FF_LINUX: D3D viewport Y is from top of window, but OpenGL viewport Y is from bottom.
    // We must flip the Y coordinate: glY = targetHeight - d3dY - d3dHeight
    // When rendering to an FBO, use the FBO texture dimensions instead of the window size.
    int targetH;
    D3D7Surface* rt = dev->renderTarget;
    if (rt && rt != dev->defaultRenderTarget && rt->fboId) {
        // Rendering to FBO - use texture dimensions
        targetH = rt->height;
    } else {
        // Rendering to screen - use window dimensions
        int winW;
        SDL_GetWindowSize(g_SDLWindow, &winW, &targetH);
    }
    int glY = targetH - (int)lpViewport->dwY - (int)lpViewport->dwHeight;
    if (glY < 0) glY = 0;
    glViewport(lpViewport->dwX, glY, lpViewport->dwWidth, lpViewport->dwHeight);
    glDepthRange(lpViewport->dvMinZ, lpViewport->dvMaxZ);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_MultiplyTransform(IDirect3DDevice7* This, D3DTRANSFORMSTATETYPE state, LPD3DMATRIX lpMatrix) {
    D3DGL_LOG("MultiplyTransform");
    // TODO: Implement matrix multiplication
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetViewport(IDirect3DDevice7* This, LPD3DVIEWPORT7 lpViewport) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lpViewport) return DDERR_INVALIDPARAMS;
    memcpy(lpViewport, &dev->viewport, sizeof(D3DVIEWPORT7));
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetMaterial(IDirect3DDevice7* This, LPD3DMATERIAL7 lpMaterial) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetMaterial");

    if (!lpMaterial) return DDERR_INVALIDPARAMS;

    memcpy(&dev->currentMaterial, lpMaterial, sizeof(D3DMATERIAL7));
    dev->ApplyMaterial();

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetMaterial(IDirect3DDevice7* This, LPD3DMATERIAL7 lpMaterial) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lpMaterial) return DDERR_INVALIDPARAMS;
    memcpy(lpMaterial, &dev->currentMaterial, sizeof(D3DMATERIAL7));
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetLight(IDirect3DDevice7* This, DWORD dwLightIndex, LPD3DLIGHT7 lpLight) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetLight %d type=%d", dwLightIndex, lpLight ? lpLight->dltType : -1);

    if (!lpLight || dwLightIndex >= MAX_GL_LIGHTS) return DDERR_INVALIDPARAMS;

    memcpy(&dev->lights[dwLightIndex], lpLight, sizeof(D3DLIGHT7));

    // Apply light to OpenGL
    GLenum glLight = GL_LIGHT0 + dwLightIndex;

    float ambient[4], diffuse[4], specular[4];
    D3DColorValueToGL(lpLight->dcvAmbient, ambient);
    D3DColorValueToGL(lpLight->dcvDiffuse, diffuse);
    D3DColorValueToGL(lpLight->dcvSpecular, specular);

    glLightfv(glLight, GL_AMBIENT, ambient);
    glLightfv(glLight, GL_DIFFUSE, diffuse);
    glLightfv(glLight, GL_SPECULAR, specular);

    if (lpLight->dltType == D3DLIGHT_DIRECTIONAL) {
        // Directional light - position w=0 means direction
        float dir[4] = { -lpLight->dvDirection.x, -lpLight->dvDirection.y, -lpLight->dvDirection.z, 0.0f };
        glLightfv(glLight, GL_POSITION, dir);
    } else if (lpLight->dltType == D3DLIGHT_POINT) {
        float pos[4] = { lpLight->dvPosition.x, lpLight->dvPosition.y, lpLight->dvPosition.z, 1.0f };
        glLightfv(glLight, GL_POSITION, pos);
        glLightf(glLight, GL_CONSTANT_ATTENUATION, lpLight->dvAttenuation0);
        glLightf(glLight, GL_LINEAR_ATTENUATION, lpLight->dvAttenuation1);
        glLightf(glLight, GL_QUADRATIC_ATTENUATION, lpLight->dvAttenuation2);
    } else if (lpLight->dltType == D3DLIGHT_SPOT) {
        float pos[4] = { lpLight->dvPosition.x, lpLight->dvPosition.y, lpLight->dvPosition.z, 1.0f };
        float dir[3] = { lpLight->dvDirection.x, lpLight->dvDirection.y, lpLight->dvDirection.z };
        glLightfv(glLight, GL_POSITION, pos);
        glLightfv(glLight, GL_SPOT_DIRECTION, dir);
        glLightf(glLight, GL_SPOT_CUTOFF, lpLight->dvPhi * 180.0f / 3.14159f);
        glLightf(glLight, GL_SPOT_EXPONENT, lpLight->dvFalloff);
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetLight(IDirect3DDevice7* This, DWORD dwLightIndex, LPD3DLIGHT7 lpLight) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lpLight || dwLightIndex >= MAX_GL_LIGHTS) return DDERR_INVALIDPARAMS;
    memcpy(lpLight, &dev->lights[dwLightIndex], sizeof(D3DLIGHT7));
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetRenderState(IDirect3DDevice7* This, D3DRENDERSTATETYPE dwState, DWORD dwValue) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetRenderState %d = %d", dwState, dwValue);

    // Store in cache
    dev->renderStates[dwState] = dwValue;

    // If recording state block, don't apply immediately
    if (dev->recordingStateBlock) {
        dev->stateBlocks[dev->recordingStateBlockHandle].renderStates[dwState] = dwValue;
        return D3D_OK;
    }

    dev->ApplyRenderState(dwState, dwValue);
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetRenderState(IDirect3DDevice7* This, D3DRENDERSTATETYPE dwState, LPDWORD lpdwValue) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lpdwValue) return DDERR_INVALIDPARAMS;

    auto it = dev->renderStates.find(dwState);
    if (it != dev->renderStates.end()) {
        *lpdwValue = it->second;
    } else {
        *lpdwValue = 0;
    }
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_BeginStateBlock(IDirect3DDevice7* This) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("BeginStateBlock");

    // Find free state block
    for (DWORD i = 1; i < MAX_STATE_BLOCKS; i++) {
        if (!dev->stateBlocks[i].active) {
            dev->recordingStateBlock = true;
            dev->recordingStateBlockHandle = i;
            dev->stateBlocks[i].active = true;
            return D3D_OK;
        }
    }

    return DDERR_OUTOFMEMORY;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_EndStateBlock(IDirect3DDevice7* This, LPDWORD lpdwBlockHandle) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("EndStateBlock");

    if (!dev->recordingStateBlock) return DDERR_INVALIDPARAMS;

    *lpdwBlockHandle = dev->recordingStateBlockHandle;
    dev->recordingStateBlock = false;

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_PreLoad(IDirect3DDevice7* This, LPDIRECTDRAWSURFACE7 lpddsTexture) {
    D3DGL_LOG("PreLoad");
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawPrimitive(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, DWORD dwFlags) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("DrawPrimitive type=%d fvf=0x%x count=%d", dptPrimitiveType, dwVertexTypeDesc, dwVertexCount);

    g_DrawPrimitiveCount++;

    dev->DrawVertices(dptPrimitiveType, dwVertexTypeDesc, lpvVertices, dwVertexCount);
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawIndexedPrimitive(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("DrawIndexedPrimitive type=%d count=%d", dptPrimitiveType, dwIndexCount);

    // FF_LINUX: Use the correct DrawVertices which handles XYZRHW and attribute ordering properly
    // Build a temporary contiguous vertex array from the indexed vertices
    int vertexSize = GetVertexSize(dwVertexTypeDesc);

    // For indexed draws, delegate to DrawVertices one primitive at a time via the index buffer
    bool isXYZRHW = (dwVertexTypeDesc & D3DFVF_XYZRHW) != 0;
    GLenum primType = dev->GetGLPrimitiveType(dptPrimitiveType);

    // FF_LINUX: Disable GL_TEXTURE_2D when no texture coordinates in FVF.
    // Otherwise stale textures from previous draws modulate vertex colors.
    int texCountDIP = (dwVertexTypeDesc & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
    GLboolean prevDIP_Texture2D = GL_FALSE;
    if (texCountDIP == 0) {
        prevDIP_Texture2D = glIsEnabled(GL_TEXTURE_2D);
        if (prevDIP_Texture2D) {
            glDisable(GL_TEXTURE_2D);
        }
    }

    // FF_LINUX: Save GL state that XYZRHW handling will modify
    GLboolean prevDIP_DepthTest = GL_FALSE, prevDIP_Lighting = GL_FALSE, prevDIP_Fog = GL_FALSE;
    GLint savedViewportDIP[4] = {0};
    bool restoredViewportDIP = false;
    GLboolean prevScissorDIP = GL_FALSE;
    GLint savedScissorDIP[4] = {0};
    GLint savedFogModeDIP = GL_EXP; GLfloat savedFogStartDIP = 0, savedFogEndDIP = 1;
    if (isXYZRHW) {
        prevDIP_DepthTest = glIsEnabled(GL_DEPTH_TEST);
        prevDIP_Lighting = glIsEnabled(GL_LIGHTING);
        prevDIP_Fog = glIsEnabled(GL_FOG);

        // FF_LINUX: In D3D7, XYZRHW vertices are in absolute pixel coordinates.
        // Use render target dimensions for ortho, not viewport dimensions.
        DWORD orthoW, orthoH;
        D3D7Surface* rt = dev->renderTarget;
        if (rt && rt != dev->defaultRenderTarget && rt->fboId) {
            orthoW = rt->width;
            orthoH = rt->height;
            glGetIntegerv(GL_VIEWPORT, savedViewportDIP);
            restoredViewportDIP = true;
            glViewport(0, 0, orthoW, orthoH);
        } else {
            DDSURFACEDESC2 rtDesc;
            memset(&rtDesc, 0, sizeof(rtDesc));
            rtDesc.dwSize = sizeof(rtDesc);
            if (rt) rt->GetSurfaceDesc(&rtDesc);
            orthoW = rtDesc.dwWidth;
            orthoH = rtDesc.dwHeight;
            if (orthoW == 0 || orthoH == 0) {
                orthoW = 1024; orthoH = 768;
            }
            glGetIntegerv(GL_VIEWPORT, savedViewportDIP);
            if ((DWORD)savedViewportDIP[2] != orthoW || (DWORD)savedViewportDIP[3] != orthoH) {
                restoredViewportDIP = true;
                prevScissorDIP = glIsEnabled(GL_SCISSOR_TEST);
                glGetIntegerv(GL_SCISSOR_BOX, savedScissorDIP);
                glEnable(GL_SCISSOR_TEST);
                glScissor(savedViewportDIP[0], savedViewportDIP[1],
                          savedViewportDIP[2], savedViewportDIP[3]);
                glViewport(0, 0, orthoW, orthoH);
            }
        }

        if (orthoW == 0 || orthoH == 0) {
            if (texCountDIP == 0 && prevDIP_Texture2D) glEnable(GL_TEXTURE_2D);
            return D3D_OK;
        }

        glMatrixMode(GL_PROJECTION);
        glPushMatrix();
        glLoadIdentity();
        if (rt && rt != dev->defaultRenderTarget && rt->fboId) {
            glOrtho(0, orthoW, 0, orthoH, 0, -1);
        } else {
            glOrtho(0, orthoW, orthoH, 0, 0, -1);
        }
        glMatrixMode(GL_MODELVIEW);
        glPushMatrix();
        glLoadIdentity();
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_LIGHTING);

        // FF_LINUX: D3D7 uses the specular color alpha byte as per-vertex fog factor
        // (0xFF = no fog, 0x00 = full fog). The software rasterizer ALWAYS computes
        // fog values in specular alpha, even in clear weather when FOGENABLE isn't set.
        // D3D7 hardware applies this automatically for TLVERTEX; GL needs explicit setup.
        // Save fog params so we can restore them for subsequent depth-based fog draws.
        if ((dwVertexTypeDesc & D3DFVF_SPECULAR) && !restoredViewportDIP) {
            glGetIntegerv(GL_FOG_MODE, &savedFogModeDIP);
            glGetFloatv(GL_FOG_START, &savedFogStartDIP);
            glGetFloatv(GL_FOG_END, &savedFogEndDIP);
            glEnable(GL_FOG);
            glFogi(GL_FOG_COORD_SRC, GL_FOG_COORD);
            glFogi(GL_FOG_MODE, GL_LINEAR);
            glFogf(GL_FOG_START, 1.0f);
            glFogf(GL_FOG_END, 0.0f);
        } else {
            glDisable(GL_FOG);
        }
    }

#ifdef FF_LINUX
    // FF_LINUX: Fix chroma key transparency (see DrawIndexedPrimitiveVB for details)
    if (isXYZRHW && dev->textures[0] && glIsEnabled(GL_ALPHA_TEST)) {
        glActiveTexture(GL_TEXTURE0);
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
        glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE);
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
        glAlphaFunc(GL_GEQUAL, 0.5f);
    }
#endif

    glBegin(primType);
    for (DWORD i = 0; i < dwIndexCount; i++) {
        WORD idx = lpwIndices[i];
        const char* vertex = (const char*)lpvVertices + idx * vertexSize;

        int offset = 0;

        // Calculate position size
        int posSize = 0;
        if (dwVertexTypeDesc & D3DFVF_XYZ) posSize = 3 * sizeof(float);
        else if (dwVertexTypeDesc & D3DFVF_XYZRHW) posSize = 4 * sizeof(float);
        offset = posSize;

        // Texture coords (must be set BEFORE glVertex in GL immediate mode)
        int texOffset = posSize;
        if (dwVertexTypeDesc & D3DFVF_NORMAL) texOffset += 3 * sizeof(float);
        if (dwVertexTypeDesc & D3DFVF_DIFFUSE) texOffset += sizeof(DWORD);
        if (dwVertexTypeDesc & D3DFVF_SPECULAR) texOffset += sizeof(DWORD);
        int texCount = (dwVertexTypeDesc & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
        if (texCount > 0) {
            const float* tc = (const float*)(vertex + texOffset);
            glTexCoord2fv(tc);
        }

        // Normal
        if (dwVertexTypeDesc & D3DFVF_NORMAL) {
            const float* norm = (const float*)(vertex + offset);
            glNormal3fv(norm);
            offset += 3 * sizeof(float);
        }

        // Diffuse color
        if (dwVertexTypeDesc & D3DFVF_DIFFUSE) {
            DWORD color = *(const DWORD*)(vertex + offset);
            float r, g, b, a;
            D3DColorToGL(color, &r, &g, &b, &a);
            glColor4f(r, g, b, a);
            offset += sizeof(DWORD);
        }

        // Specular color - extract alpha byte as per-vertex fog factor
        if (dwVertexTypeDesc & D3DFVF_SPECULAR) {
            DWORD specular = *(const DWORD*)(vertex + offset);
            if (isXYZRHW) {
                glFogCoordf((float)(specular >> 24) / 255.0f);
            }
            offset += sizeof(DWORD);
        }

        // Position (MUST be last in GL immediate mode - triggers vertex submission)
        if (dwVertexTypeDesc & D3DFVF_XYZ) {
            const float* pos = (const float*)vertex;
            glVertex3fv(pos);
        } else if (dwVertexTypeDesc & D3DFVF_XYZRHW) {
            const float* pos = (const float*)vertex;
            glVertex3f(pos[0], pos[1], pos[2]);
        }
    }
    glEnd();

    if (isXYZRHW) {
        glMatrixMode(GL_MODELVIEW);
        glPopMatrix();
        glMatrixMode(GL_PROJECTION);
        glPopMatrix();
        // Restore previous state
        if (prevDIP_DepthTest) glEnable(GL_DEPTH_TEST); else glDisable(GL_DEPTH_TEST);
        if (prevDIP_Lighting) glEnable(GL_LIGHTING); else glDisable(GL_LIGHTING);
        // Restore fog to previous state
        if (prevDIP_Fog) glEnable(GL_FOG); else glDisable(GL_FOG);
        if ((dwVertexTypeDesc & D3DFVF_SPECULAR) && !restoredViewportDIP) {
            glFogi(GL_FOG_COORD_SRC, GL_FRAGMENT_DEPTH);
            glFogi(GL_FOG_MODE, savedFogModeDIP);
            glFogf(GL_FOG_START, savedFogStartDIP);
            glFogf(GL_FOG_END, savedFogEndDIP);
        }
        // Restore viewport and scissor state
        if (restoredViewportDIP) {
            glViewport(savedViewportDIP[0], savedViewportDIP[1], savedViewportDIP[2], savedViewportDIP[3]);
            if (prevScissorDIP) {
                glScissor(savedScissorDIP[0], savedScissorDIP[1], savedScissorDIP[2], savedScissorDIP[3]);
            } else {
                glDisable(GL_SCISSOR_TEST);
            }
        }
    }

    // Restore GL_TEXTURE_2D state if we disabled it
    if (texCountDIP == 0 && prevDIP_Texture2D) {
        glEnable(GL_TEXTURE_2D);
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetClipStatus(IDirect3DDevice7* This, void* lpD3DClipStatus) {
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetClipStatus(IDirect3DDevice7* This, void* lpD3DClipStatus) {
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawPrimitiveStrided(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, void* lpVertexArray, DWORD dwVertexCount, DWORD dwFlags) {
    D3DGL_LOG("DrawPrimitiveStrided");
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawIndexedPrimitiveStrided(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, void* lpVertexArray, DWORD dwVertexCount, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags) {
    D3DGL_LOG("DrawIndexedPrimitiveStrided");
    return D3D_OK;
}

int g_DrawPrimitiveVBCount = 0;
int g_DrawIdxPrimVBCount = 0;
int g_FF_PitModeActive = 0;  // Set by DXEngine FlushObjects when drawing pit geometry

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawPrimitiveVB(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, DWORD dwFlags) {
    D3D7Device* dev = (D3D7Device*)This;
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)lpd3dVertexBuffer;
    D3DGL_LOG("DrawPrimitiveVB type=%d start=%d count=%d", dptPrimitiveType, dwStartVertex, dwNumVertices);

    if (!vb || !vb->data) return DDERR_INVALIDPARAMS;

    int vertexSize = GetVertexSize(vb->desc.dwFVF);
    const char* startVertex = (const char*)vb->data + dwStartVertex * vertexSize;

    g_DrawPrimitiveVBCount++;

    // FF_LINUX: NDC diagnostic for pit draws via DrawPrimitiveVB (point lists only; indexed VB handles triangles)
    // Removed - DX engine uses DrawIndexedPrimitiveVB for pit geometry (INDEXED_MODE_ENGINE)

    dev->DrawVertices(dptPrimitiveType, vb->desc.dwFVF, startVertex, dwNumVertices);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DrawIndexedPrimitiveVB(IDirect3DDevice7* This, D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags) {
    D3D7Device* dev = (D3D7Device*)This;
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)lpd3dVertexBuffer;
    D3DGL_LOG("DrawIndexedPrimitiveVB type=%d start=%d count=%d idxCount=%d", dptPrimitiveType, dwStartVertex, dwNumVertices, dwIndexCount);

    if (!vb || !vb->data) return DDERR_INVALIDPARAMS;

    DWORD fvf = vb->desc.dwFVF;
    int vertexSize = GetVertexSize(fvf);
    GLenum primType = dev->GetGLPrimitiveType(dptPrimitiveType);
    bool isXYZRHW = (fvf & D3DFVF_XYZRHW) != 0;

    // FF_LINUX: Track DrawIndexedPrimitiveVB calls
    g_DrawIdxPrimVBCount++;

    // Pit NDC diagnostic removed - cockpit rendering working

    // FF_LINUX: Ensure we're operating on texture unit 0.
    // SetTexture(1, NULL) in SelectTexture1 leaves GL_TEXTURE1 as active unit,
    // which causes all subsequent glIsEnabled/glTexEnvi calls to target the wrong unit.
    glActiveTexture(GL_TEXTURE0);

    // FF_LINUX: Disable GL_TEXTURE_2D when no texture coordinates in FVF.
    // Otherwise stale textures from previous draws modulate vertex colors.
    int texCountVB = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
    GLboolean prevVB_Texture2D = GL_FALSE;
    if (texCountVB == 0) {
        prevVB_Texture2D = glIsEnabled(GL_TEXTURE_2D);
        if (prevVB_Texture2D) {
            glDisable(GL_TEXTURE_2D);
        }
    }

    // FF_LINUX: Save and set up orthographic projection for XYZRHW vertices
    GLboolean prevLighting2 = GL_FALSE, prevFog2 = GL_FALSE, prevDepthTest2 = GL_FALSE;
    GLint savedViewportVB[4] = {0};
    bool restoredViewportVB = false;
    GLboolean prevScissorVB = GL_FALSE;
    GLint savedScissorVB[4] = {0};
    GLint savedFogModeVB = GL_EXP; GLfloat savedFogStartVB = 0, savedFogEndVB = 1;
    if (isXYZRHW) {
        // FF_LINUX: In D3D7, XYZRHW vertices are in absolute pixel coordinates and
        // bypass the viewport transform. Our GL emulation must match this by using
        // the actual render target dimensions for glOrtho and glViewport.
        // The GL viewport is temporarily expanded to the full render target, and
        // GL_SCISSOR_TEST clips to the original viewport area (for MFDs etc.).
        DWORD orthoW, orthoH;
        D3D7Surface* rt = dev->renderTarget;
        if (rt && rt != dev->defaultRenderTarget && rt->fboId) {
            // Rendering to FBO - use FBO texture dimensions for 1:1 pixel mapping
            orthoW = rt->width;
            orthoH = rt->height;
            glGetIntegerv(GL_VIEWPORT, savedViewportVB);
            restoredViewportVB = true;
            glViewport(0, 0, orthoW, orthoH);
        } else {
            // Screen rendering: use render target surface dimensions for ortho
            DDSURFACEDESC2 rtDesc;
            memset(&rtDesc, 0, sizeof(rtDesc));
            rtDesc.dwSize = sizeof(rtDesc);
            if (rt) rt->GetSurfaceDesc(&rtDesc);
            orthoW = rtDesc.dwWidth;
            orthoH = rtDesc.dwHeight;
            if (orthoW == 0 || orthoH == 0) {
                orthoW = 1024; orthoH = 768;
            }
            // Save and expand GL viewport to full render target
            glGetIntegerv(GL_VIEWPORT, savedViewportVB);
            if ((DWORD)savedViewportVB[2] != orthoW || (DWORD)savedViewportVB[3] != orthoH) {
                restoredViewportVB = true;
                prevScissorVB = glIsEnabled(GL_SCISSOR_TEST);
                glGetIntegerv(GL_SCISSOR_BOX, savedScissorVB);
                glEnable(GL_SCISSOR_TEST);
                glScissor(savedViewportVB[0], savedViewportVB[1],
                          savedViewportVB[2], savedViewportVB[3]);
                glViewport(0, 0, orthoW, orthoH);
            }
        }

        if (orthoW == 0 || orthoH == 0) {
            if (texCountVB == 0 && prevVB_Texture2D) glEnable(GL_TEXTURE_2D);
            return D3D_OK; // Skip draw - no valid dimensions
        }

        prevLighting2 = glIsEnabled(GL_LIGHTING);
        prevFog2 = glIsEnabled(GL_FOG);

        glMatrixMode(GL_PROJECTION);
        glPushMatrix();
        glLoadIdentity();
        // FF_LINUX: D3D XYZRHW z in [0,1] where 0=near, 1=far.
        // glOrtho(0,w,h,0, near=0, far=-1) gives z_ndc = 2*z - 1: z=0→-1, z=1→+1.
        if (rt && rt != dev->defaultRenderTarget && rt->fboId) {
            // FBO rendering: DON'T flip Y so texture v=0 reads what was drawn at D3D y=0
            glOrtho(0, orthoW, 0, orthoH, 0, -1);
        } else {
            // Screen rendering: flip Y so D3D y=0 is at top of screen
            glOrtho(0, orthoW, orthoH, 0, 0, -1);
        }
        glMatrixMode(GL_MODELVIEW);
        glPushMatrix();
        glLoadIdentity();
        // XYZRHW bypasses lighting and depth testing when rendering to FBO
        // (cockpit instruments are 2D overlays that should always render)
        glDisable(GL_LIGHTING);

        // FF_LINUX: D3D7 uses the specular color alpha byte as per-vertex fog factor.
        // The software rasterizer ALWAYS computes fog values in specular alpha, even
        // in clear weather. Don't apply fog in FBO rendering (cockpit instruments).
        // Save fog params so we can restore them for subsequent depth-based fog draws.
        if ((fvf & D3DFVF_SPECULAR) && !restoredViewportVB) {
            glGetIntegerv(GL_FOG_MODE, &savedFogModeVB);
            glGetFloatv(GL_FOG_START, &savedFogStartVB);
            glGetFloatv(GL_FOG_END, &savedFogEndVB);
            glEnable(GL_FOG);
            glFogi(GL_FOG_COORD_SRC, GL_FOG_COORD);
            glFogi(GL_FOG_MODE, GL_LINEAR);
            glFogf(GL_FOG_START, 1.0f);
            glFogf(GL_FOG_END, 0.0f);
        } else {
            glDisable(GL_FOG);
        }

        if (restoredViewportVB) {
            // FBO rendering - disable depth test for 2D instrument overlays
            prevDepthTest2 = glIsEnabled(GL_DEPTH_TEST);
            glDisable(GL_DEPTH_TEST);
        }

    }

    // Calculate position size for offset computation
    int posSize = 0;
    if (fvf & D3DFVF_XYZ) posSize = 3 * sizeof(float);
    else if (fvf & D3DFVF_XYZRHW) posSize = 4 * sizeof(float);

    // Calculate texture coordinate offset
    int texOffset = posSize;
    if (fvf & D3DFVF_NORMAL) texOffset += 3 * sizeof(float);
    if (fvf & D3DFVF_DIFFUSE) texOffset += sizeof(DWORD);
    if (fvf & D3DFVF_SPECULAR) texOffset += sizeof(DWORD);
    int texCount = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;

    // FF_LINUX: If the device has no texture bound on stage 0 but GL_TEXTURE_2D is still
    // enabled (can happen because ApplyStateBlock doesn't capture SetTexture calls),
    // we must disable GL_TEXTURE_2D. Otherwise the draw gets modulated by a stale/empty
    // texture, causing non-textured primitives (like the sky) to render as black.
    GLboolean prevTex2D_forNullCheck = GL_FALSE;
    bool disabledTexForNullBinding = false;
    if (!dev->textures[0] && glIsEnabled(GL_TEXTURE_2D)) {
        prevTex2D_forNullCheck = GL_TRUE;
        disabledTexForNullBinding = true;
        glDisable(GL_TEXTURE_2D);
    }

#ifdef FF_LINUX
    // FF_LINUX: Fix chroma key transparency for cockpit panels.
    // When alpha test is enabled (chroma key) and a texture is bound, ensure:
    // 1. Fragment alpha comes from the texture (not vertex primary color)
    // 2. Alpha ref is 0.5 to robustly discard alpha=0 chroma pixels
    //    while keeping alpha=0xFF real pixels. The state-block-set ref of 1/255
    //    doesn't survive to draw time due to D3D device lifetime issues.
    if (isXYZRHW && dev->textures[0] && glIsEnabled(GL_ALPHA_TEST)) {
        glActiveTexture(GL_TEXTURE0);
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
        glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE);
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
        glAlphaFunc(GL_GEQUAL, 0.5f);
    }
#endif

    glBegin(primType);
    for (DWORD i = 0; i < dwIndexCount; i++) {
        WORD idx = lpwIndices[i] + dwStartVertex;
        const char* vertex = (const char*)vb->data + idx * vertexSize;

        int offset = posSize;

        // FF_LINUX: In GL immediate mode, glVertex* MUST be called LAST.
        // Set all other attributes first.

        // Texture coords first
        if (texCount > 0) {
            const float* tc = (const float*)(vertex + texOffset);
            glTexCoord2fv(tc);
        }

        // Normal
        if (fvf & D3DFVF_NORMAL) {
            const float* norm = (const float*)(vertex + offset);
            glNormal3fv(norm);
            offset += 3 * sizeof(float);
        }

        // Diffuse color
        if (fvf & D3DFVF_DIFFUSE) {
            DWORD color = *(const DWORD*)(vertex + offset);
            float r, g, b, a;
            D3DColorToGL(color, &r, &g, &b, &a);
            // FF_LINUX: Force alpha=1 when rendering XYZRHW to FBO.
            // D3D7 2D rendering often uses colors without alpha (e.g., 0x00FF00),
            // relying on the alpha channel being ignored. In GL with alpha blending,
            // alpha=0 makes content invisible. Force opaque for FBO instrument rendering.
            if (restoredViewportVB && a == 0.0f) a = 1.0f;
            glColor4f(r, g, b, a);
            offset += sizeof(DWORD);
        }

        // Specular color - extract alpha byte as per-vertex fog factor
        if (fvf & D3DFVF_SPECULAR) {
            DWORD specular = *(const DWORD*)(vertex + offset);
            // Always submit fog coord for XYZRHW screen draws (not FBO)
            if (isXYZRHW && !restoredViewportVB) {
                glFogCoordf((float)(specular >> 24) / 255.0f);
            }
            offset += sizeof(DWORD);
        }

        // Position (MUST be last - triggers vertex submission)
        if (fvf & D3DFVF_XYZ) {
            const float* pos = (const float*)vertex;
            glVertex3fv(pos);
        } else if (isXYZRHW) {
            const float* pos = (const float*)vertex;
            glVertex3f(pos[0], pos[1], pos[2]);
        }
    }
    glEnd();

    // FF_LINUX: Restore GL_TEXTURE_2D if we disabled it for a null-texture draw
    if (disabledTexForNullBinding) {
        glEnable(GL_TEXTURE_2D);
    }

    if (isXYZRHW) {
        glMatrixMode(GL_MODELVIEW);
        glPopMatrix();
        glMatrixMode(GL_PROJECTION);
        glPopMatrix();
        // Restore previous state
        if (prevLighting2) glEnable(GL_LIGHTING); else glDisable(GL_LIGHTING);
        // Restore fog to previous state
        if (prevFog2) glEnable(GL_FOG); else glDisable(GL_FOG);
        if ((fvf & D3DFVF_SPECULAR) && !restoredViewportVB) {
            glFogi(GL_FOG_COORD_SRC, GL_FRAGMENT_DEPTH);
            glFogi(GL_FOG_MODE, savedFogModeVB);
            glFogf(GL_FOG_START, savedFogStartVB);
            glFogf(GL_FOG_END, savedFogEndVB);
        }
        // Restore glViewport and depth test if we changed them
        if (restoredViewportVB) {
            glViewport(savedViewportVB[0], savedViewportVB[1], savedViewportVB[2], savedViewportVB[3]);
            if (prevDepthTest2) glEnable(GL_DEPTH_TEST);
            // Restore scissor state
            if (prevScissorVB) {
                glScissor(savedScissorVB[0], savedScissorVB[1], savedScissorVB[2], savedScissorVB[3]);
            } else {
                glDisable(GL_SCISSOR_TEST);
            }
        }
    }

    // Restore GL_TEXTURE_2D state if we disabled it
    if (texCountVB == 0 && prevVB_Texture2D) {
        glEnable(GL_TEXTURE_2D);
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_ComputeSphereVisibility(IDirect3DDevice7* This, LPD3DVECTOR lpCenters, LPD3DVALUE lpRadii, DWORD dwNumSpheres, DWORD dwFlags, LPDWORD lpdwReturnValues) {
    D3DGL_LOG("ComputeSphereVisibility count=%d", dwNumSpheres);

    // Simple implementation - mark all as visible
    for (DWORD i = 0; i < dwNumSpheres; i++) {
        lpdwReturnValues[i] = 0;  // 0 = visible
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetTexture(IDirect3DDevice7* This, DWORD dwStage, LPDIRECTDRAWSURFACE7* lplpTexture) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lplpTexture || dwStage >= MAX_TEXTURE_STAGES) return DDERR_INVALIDPARAMS;
    *lplpTexture = dev->textures[dwStage];
    return D3D_OK;
}

static int g_SetTextureCount = 0;
static int g_SetTextureWithData = 0;
static int g_SetTextureNullCount = 0;      // SetTexture with NULL ptr (disable)
static int g_SetTextureNoPixelCount = 0;   // SetTexture with surface but no pixelData
static int g_SetTextureDirtyCount = 0;     // SetTexture with dirty data (upload needed)
static int g_SetTextureCleanCount = 0;     // SetTexture with clean data (already uploaded)
static HRESULT STDMETHODCALLTYPE D3D7Dev_SetTexture(IDirect3DDevice7* This, DWORD dwStage, LPDIRECTDRAWSURFACE7 lpTexture) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetTexture stage=%d tex=%p", dwStage, lpTexture);
    g_SetTextureCount++;
    if (lpTexture) {
        D3D7Surface* s = (D3D7Surface*)lpTexture;
        if (s->pixelData) {
            g_SetTextureWithData++;
            if (s->isDirty)
                g_SetTextureDirtyCount++;
            else
                g_SetTextureCleanCount++;
        } else {
            g_SetTextureNoPixelCount++;
        }
    } else {
        g_SetTextureNullCount++;
    }

    if (dwStage >= MAX_TEXTURE_STAGES) return DDERR_INVALIDPARAMS;

    dev->textures[dwStage] = (D3D7Surface*)lpTexture;

    // Bind texture to OpenGL
    glActiveTexture(GL_TEXTURE0 + dwStage);
    if (!lpTexture) {
        // FF_LINUX: Unbind texture and disable texturing when NULL is passed.
        // This must be done for ALL stages, not just stage 0. If stage 1 has
        // GL_TEXTURE_2D enabled (set by STATE_MULTITEXTURE's D3DTOP_ADD), it
        // will ADD a stale/default texture to the stage 0 output, producing
        // bright white patches on terrain blocks that don't use multitexture.
        glBindTexture(GL_TEXTURE_2D, 0);
        glDisable(GL_TEXTURE_2D);
        // FF_LINUX: Always restore active unit to GL_TEXTURE0 so subsequent
        // glTexEnvi/glEnable(GL_TEXTURE_2D)/glIsEnabled calls target unit 0.
        // Without this, SetTexture(1, NULL) leaves GL_TEXTURE1 active, causing
        // all texture state queries and modifications to target the wrong unit.
        glActiveTexture(GL_TEXTURE0);
        return D3D_OK;
    }
    if (lpTexture) {
        D3D7Surface* surf = (D3D7Surface*)lpTexture;

        // FF_LINUX: Lazily create GL texture if it wasn't created yet.
        // This handles the case where DD7_CreateSurface was called on a thread
        // without a GL context (the GL calls fail silently, leaving glTexture=0).
        if (surf->glTexture == 0 && surf->width > 0 && surf->height > 0) {
            glGenTextures(1, &surf->glTexture);
            if (surf->glTexture) {
                glBindTexture(GL_TEXTURE_2D, surf->glTexture);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
                surf->isDirty = true;  // Force upload of existing pixel data
            }
        }

        glBindTexture(GL_TEXTURE_2D, surf->glTexture);
        glEnable(GL_TEXTURE_2D);


        // FF_LINUX: Upload dirty texture data from CPU to GPU
        if (surf->isDirty && surf->pixelData && surf->width > 0 && surf->height > 0) {

            // Clear any stale GL errors before upload
            while (glGetError() != GL_NO_ERROR) {}

            bool uploadOK = true;

            if (surf->dxtFormat != 0 && surf->dxtDataSize > 0) {
                // DXT compressed texture upload
                // DXT1/3/5 alpha is already baked into the compressed data
                glCompressedTexImage2D(GL_TEXTURE_2D, 0, surf->dxtFormat,
                                       surf->width, surf->height, 0,
                                       surf->dxtDataSize, surf->pixelData);
            } else {
                // Uncompressed texture upload
                int bpp = surf->pixelFormat.dwRGBBitCount ? surf->pixelFormat.dwRGBBitCount / 8 : 4;
                GLenum format = GL_RGBA;
                GLenum type = GL_UNSIGNED_BYTE;

                if (bpp == 4) {
                    format = GL_BGRA;
                    type = GL_UNSIGNED_INT_8_8_8_8_REV;
                } else if (bpp == 2) {
                    if (surf->pixelFormat.dwRBitMask == 0xF800) {
                        format = GL_RGB;
                        type = GL_UNSIGNED_SHORT_5_6_5;
                    } else if (surf->pixelFormat.dwRBitMask == 0x7C00) {
                        format = GL_BGRA;
                        type = GL_UNSIGNED_SHORT_1_5_5_5_REV;
                    } else if (surf->pixelFormat.dwRBitMask == 0x0F00) {
                        format = GL_BGRA;
                        type = GL_UNSIGNED_SHORT_4_4_4_4_REV;
                    }
                }

                // FF_LINUX: Apply color key - set alpha=0 for pixels matching
                // the color key, alpha=0xFF for non-matching pixels.
                // This implements DirectDraw's DDCKEY_SRCBLT transparency.
                if (surf->hasColorKey && bpp == 4) {
                    DWORD rgbMask = surf->pixelFormat.dwRBitMask |
                                    surf->pixelFormat.dwGBitMask |
                                    surf->pixelFormat.dwBBitMask;
                    DWORD ckRGB = surf->colorKeyLow & rgbMask;
                    int numPixels = surf->width * surf->height;
                    DWORD* pixels = (DWORD*)surf->pixelData;
                    // Handle pitch != width*bpp (rows may have padding)
                    int pixelsPerRow = surf->pitch / 4;
                    for (int y = 0; y < surf->height; y++) {
                        DWORD* row = pixels + y * pixelsPerRow;
                        for (int x = 0; x < surf->width; x++) {
                            if ((row[x] & rgbMask) == ckRGB) {
                                row[x] &= rgbMask;  // Set alpha to 0
                            } else {
                                row[x] |= ~rgbMask; // Set alpha to 0xFF
                            }
                        }
                    }
                }
                // FF_LINUX: For X8R8G8B8 surfaces without DDPF_ALPHAPIXELS,
                // force alpha to 0xFF. In D3D7 the "X" byte is ignored, but OpenGL
                // reads it as alpha. Skip for surfaces with color key (chroma) -
                // Reload() already set alpha=0 for chroma and alpha=0xFF for opaque.
                else if (bpp == 4 && !(surf->pixelFormat.dwFlags & DDPF_ALPHAPIXELS)
                         && !surf->hasColorKey) {
                    int pixelsPerRow = surf->pitch / 4;
                    DWORD* pixels = (DWORD*)surf->pixelData;
                    for (int y = 0; y < surf->height; y++) {
                        DWORD* row = pixels + y * pixelsPerRow;
                        for (int x = 0; x < surf->width; x++) {
                            row[x] |= 0xFF000000;
                        }
                    }
                }

                int expectedPitch = surf->width * bpp;
                if (surf->pitch == expectedPitch) {
                    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
                    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
                } else {
                    glPixelStorei(GL_UNPACK_ROW_LENGTH, surf->pitch / bpp);
                    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
                }

                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surf->width, surf->height, 0,
                             format, type, surf->pixelData);

                glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
                glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
            }

            GLenum texErr = glGetError();
            if (texErr != GL_NO_ERROR) {
                uploadOK = false;
            }

            // Only clear dirty flag on successful upload
            if (uploadOK) {
                surf->isDirty = false;
            }
        }
    }
    // else: texture is already bound (line 1293) with valid GL data from a
    // previous upload - keep the binding, don't unbind or disable texturing.
    glActiveTexture(GL_TEXTURE0);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetTextureStageState(IDirect3DDevice7* This, DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, LPDWORD lpdwState) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!lpdwState) return DDERR_INVALIDPARAMS;

    auto key = std::make_pair(dwStage, d3dTexStageStateType);
    auto it = dev->textureStageStates.find(key);
    if (it != dev->textureStageStates.end()) {
        *lpdwState = it->second;
    } else {
        *lpdwState = 0;
    }
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetTextureStageState(IDirect3DDevice7* This, DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, DWORD dwState) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("SetTextureStageState stage=%d type=%d value=%d", dwStage, d3dTexStageStateType, dwState);

    auto key = std::make_pair(dwStage, d3dTexStageStateType);
    dev->textureStageStates[key] = dwState;

    if (dev->recordingStateBlock) {
        dev->stateBlocks[dev->recordingStateBlockHandle].textureStageStates[key] = dwState;
        return D3D_OK;
    }

    dev->ApplyTextureStageState(dwStage, d3dTexStageStateType, dwState);
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_ValidateDevice(IDirect3DDevice7* This, LPDWORD lpdwPasses) {
    if (lpdwPasses) *lpdwPasses = 1;
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_ApplyStateBlock(IDirect3DDevice7* This, DWORD dwBlockHandle) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("ApplyStateBlock %d", dwBlockHandle);

    if (dwBlockHandle == 0 || dwBlockHandle >= MAX_STATE_BLOCKS) return DDERR_INVALIDPARAMS;
    if (!dev->stateBlocks[dwBlockHandle].active) {
        return DDERR_INVALIDPARAMS;
    }

    RenderStateBlock& sb = dev->stateBlocks[dwBlockHandle];

    // FF_LINUX: Ensure texture unit 0 is active before applying state.
    // SetTexture(1, NULL) can leave GL_TEXTURE1 active, causing glTexEnvi/glEnable
    // in ApplyTextureStageState to target the wrong unit.
    glActiveTexture(GL_TEXTURE0);

    // Apply all stored render states
    for (auto& pair : sb.renderStates) {
        dev->ApplyRenderState(pair.first, pair.second);
    }

    // Apply all stored texture stage states
    for (auto& pair : sb.textureStageStates) {
        dev->ApplyTextureStageState(pair.first.first, pair.first.second, pair.second);
    }

    // Lights, material, transforms, viewport only for D3DSBT_ALL blocks.
    // D3DSBT_PIXELSTATE only captures pixel-related render states and texture stage states.
    if (sb.blockType == D3DSBT_ALL) {
        // Restore lights
        for (DWORD i = 0; i < MAX_GL_LIGHTS; i++) {
            GLenum glLight = GL_LIGHT0 + i;
            float ambient[4], diffuse[4], specular[4];
            D3DColorValueToGL(sb.lights[i].dcvAmbient, ambient);
            D3DColorValueToGL(sb.lights[i].dcvDiffuse, diffuse);
            D3DColorValueToGL(sb.lights[i].dcvSpecular, specular);
            glLightfv(glLight, GL_AMBIENT, ambient);
            glLightfv(glLight, GL_DIFFUSE, diffuse);
            glLightfv(glLight, GL_SPECULAR, specular);

            if (sb.lights[i].dltType == D3DLIGHT_DIRECTIONAL) {
                float dir[4] = { -sb.lights[i].dvDirection.x, -sb.lights[i].dvDirection.y, -sb.lights[i].dvDirection.z, 0.0f };
                glLightfv(glLight, GL_POSITION, dir);
            } else if (sb.lights[i].dltType == D3DLIGHT_POINT || sb.lights[i].dltType == D3DLIGHT_SPOT) {
                float pos[4] = { sb.lights[i].dvPosition.x, sb.lights[i].dvPosition.y, sb.lights[i].dvPosition.z, 1.0f };
                glLightfv(glLight, GL_POSITION, pos);
            }

            if (sb.lightEnabled[i]) {
                glEnable(glLight);
            } else {
                glDisable(glLight);
            }
            memcpy(&dev->lights[i], &sb.lights[i], sizeof(D3DLIGHT7));
            dev->lightEnabled[i] = sb.lightEnabled[i];
        }

        // Restore material
        dev->currentMaterial = sb.material;
        float matDiffuse[4], matAmbient[4], matSpecular[4], matEmissive[4];
        D3DColorValueToGL(sb.material.dcvDiffuse, matDiffuse);
        D3DColorValueToGL(sb.material.dcvAmbient, matAmbient);
        D3DColorValueToGL(sb.material.dcvSpecular, matSpecular);
        D3DColorValueToGL(sb.material.dcvEmissive, matEmissive);
        glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, matDiffuse);
        glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, matAmbient);
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, matSpecular);
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, matEmissive);
        glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, sb.material.dvPower);

        // Restore transforms
        dev->projMatrix = sb.projMatrix;
        dev->viewMatrix = sb.viewMatrix;
        dev->worldMatrix = sb.worldMatrix;
        dev->ApplyMatrices();

        // FF_LINUX: Do NOT restore viewport from state blocks.
        // In real D3D7, state blocks only capture render states and texture stage states,
        // NOT the viewport. Our state blocks were typically created during init when
        // the viewport was 0x0, so restoring it would zero out the viewport set by
        // UpdateViewport(), causing all XYZRHW cockpit draws to be silently dropped.
        // The viewport is managed independently via SetViewport/UpdateViewport.
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_CaptureStateBlock(IDirect3DDevice7* This, DWORD dwBlockHandle) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("CaptureStateBlock %d", dwBlockHandle);

    if (dwBlockHandle == 0 || dwBlockHandle >= MAX_STATE_BLOCKS) return DDERR_INVALIDPARAMS;

    RenderStateBlock& sb = dev->stateBlocks[dwBlockHandle];

    // Always capture render states and texture stage states
    sb.renderStates = dev->renderStates;
    sb.textureStageStates = dev->textureStageStates;

    // Only capture transforms, viewport, lights, material for D3DSBT_ALL blocks
    if (sb.blockType == D3DSBT_ALL) {
        sb.material = dev->currentMaterial;
        memcpy(sb.lights, dev->lights, sizeof(sb.lights));
        memcpy(sb.lightEnabled, dev->lightEnabled, sizeof(sb.lightEnabled));
        sb.projMatrix = dev->projMatrix;
        sb.viewMatrix = dev->viewMatrix;
        sb.worldMatrix = dev->worldMatrix;
        // FF_LINUX: Do NOT capture viewport - it's managed independently
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_DeleteStateBlock(IDirect3DDevice7* This, DWORD dwBlockHandle) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("DeleteStateBlock %d", dwBlockHandle);

    if (dwBlockHandle == 0 || dwBlockHandle >= MAX_STATE_BLOCKS) return DDERR_INVALIDPARAMS;

    dev->stateBlocks[dwBlockHandle] = RenderStateBlock();
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_CreateStateBlock(IDirect3DDevice7* This, DWORD d3dsbType, LPDWORD lpdwBlockHandle) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("CreateStateBlock type=%d", d3dsbType);

    if (!lpdwBlockHandle) return DDERR_INVALIDPARAMS;

    // Find free state block
    for (DWORD i = 1; i < MAX_STATE_BLOCKS; i++) {
        if (!dev->stateBlocks[i].active) {
            dev->stateBlocks[i].active = true;

            // Capture current state based on type
            RenderStateBlock& sb = dev->stateBlocks[i];
            sb.blockType = d3dsbType;

            // Render states and texture stage states are always captured
            sb.renderStates = dev->renderStates;
            sb.textureStageStates = dev->textureStageStates;

            // Viewport, transforms, lights, material only for D3DSBT_ALL
            if (d3dsbType == D3DSBT_ALL) {
                sb.material = dev->currentMaterial;
                memcpy(sb.lights, dev->lights, sizeof(sb.lights));
                memcpy(sb.lightEnabled, dev->lightEnabled, sizeof(sb.lightEnabled));
                sb.projMatrix = dev->projMatrix;
                sb.viewMatrix = dev->viewMatrix;
                sb.worldMatrix = dev->worldMatrix;
                // FF_LINUX: Do NOT capture viewport - it's managed independently
                // (see comment in ApplyStateBlock)
            }

            *lpdwBlockHandle = i;
            return D3D_OK;
        }
    }

    return DDERR_OUTOFMEMORY;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_Load(IDirect3DDevice7* This, LPDIRECTDRAWSURFACE7 lpDestTex, LPPOINT lpDestPoint, LPDIRECTDRAWSURFACE7 lpSrcTex, LPRECT lprcSrcRect, DWORD dwFlags) {
    D3DGL_LOG("Load");
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_LightEnable(IDirect3DDevice7* This, DWORD dwLightIndex, BOOL bEnable) {
    D3D7Device* dev = (D3D7Device*)This;
    D3DGL_LOG("LightEnable %d = %d", dwLightIndex, bEnable);

    if (dwLightIndex >= MAX_GL_LIGHTS) return DDERR_INVALIDPARAMS;

    dev->lightEnabled[dwLightIndex] = bEnable;

    if (bEnable) {
        glEnable(GL_LIGHT0 + dwLightIndex);
    } else {
        glDisable(GL_LIGHT0 + dwLightIndex);
    }

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetLightEnable(IDirect3DDevice7* This, DWORD dwLightIndex, BOOL* pbEnable) {
    D3D7Device* dev = (D3D7Device*)This;
    if (!pbEnable || dwLightIndex >= MAX_GL_LIGHTS) return DDERR_INVALIDPARAMS;
    *pbEnable = dev->lightEnabled[dwLightIndex];
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_SetClipPlane(IDirect3DDevice7* This, DWORD dwIndex, D3DVALUE* pPlaneEquation) {
    D3DGL_LOG("SetClipPlane");
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetClipPlane(IDirect3DDevice7* This, DWORD dwIndex, D3DVALUE* pPlaneEquation) {
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7Dev_GetInfo(IDirect3DDevice7* This, DWORD dwDevInfoID, LPVOID pDevInfoStruct, DWORD dwSize) {
    return D3D_OK;
}

// VTable
static const IDirect3DDevice7Vtbl g_D3D7DeviceVtbl = {
    D3D7Dev_QueryInterface,
    D3D7Dev_AddRef,
    D3D7Dev_Release,
    D3D7Dev_GetCaps,
    D3D7Dev_EnumTextureFormats,
    D3D7Dev_BeginScene,
    D3D7Dev_EndScene,
    D3D7Dev_GetDirect3D,
    D3D7Dev_SetRenderTarget,
    D3D7Dev_GetRenderTarget,
    D3D7Dev_Clear,
    D3D7Dev_SetTransform,
    D3D7Dev_GetTransform,
    D3D7Dev_SetViewport,
    D3D7Dev_MultiplyTransform,
    D3D7Dev_GetViewport,
    D3D7Dev_SetMaterial,
    D3D7Dev_GetMaterial,
    D3D7Dev_SetLight,
    D3D7Dev_GetLight,
    D3D7Dev_SetRenderState,
    D3D7Dev_GetRenderState,
    D3D7Dev_BeginStateBlock,
    D3D7Dev_EndStateBlock,
    D3D7Dev_PreLoad,
    D3D7Dev_DrawPrimitive,
    D3D7Dev_DrawIndexedPrimitive,
    D3D7Dev_SetClipStatus,
    D3D7Dev_GetClipStatus,
    D3D7Dev_DrawPrimitiveStrided,
    D3D7Dev_DrawIndexedPrimitiveStrided,
    D3D7Dev_DrawPrimitiveVB,
    D3D7Dev_DrawIndexedPrimitiveVB,
    D3D7Dev_ComputeSphereVisibility,
    D3D7Dev_GetTexture,
    D3D7Dev_SetTexture,
    D3D7Dev_GetTextureStageState,
    D3D7Dev_SetTextureStageState,
    D3D7Dev_ValidateDevice,
    D3D7Dev_ApplyStateBlock,
    D3D7Dev_CaptureStateBlock,
    D3D7Dev_DeleteStateBlock,
    D3D7Dev_CreateStateBlock,
    D3D7Dev_Load,
    D3D7Dev_LightEnable,
    D3D7Dev_GetLightEnable,
    D3D7Dev_SetClipPlane,
    D3D7Dev_GetClipPlane,
    D3D7Dev_GetInfo
};

// ============================================================
// D3D7Device implementation
// ============================================================
D3D7Device::D3D7Device() : refCount(1), d3d(nullptr), renderTarget(nullptr),
                           defaultRenderTarget(nullptr),
                           nextStateBlockHandle(1), recordingStateBlock(false),
                           recordingStateBlockHandle(0), inScene(false) {
    lpVtbl = &g_D3D7DeviceVtbl;

    // Initialize identity matrices
    memset(&projMatrix, 0, sizeof(projMatrix));
    memset(&viewMatrix, 0, sizeof(viewMatrix));
    memset(&worldMatrix, 0, sizeof(worldMatrix));
    projMatrix._11 = projMatrix._22 = projMatrix._33 = projMatrix._44 = 1.0f;
    viewMatrix._11 = viewMatrix._22 = viewMatrix._33 = viewMatrix._44 = 1.0f;
    worldMatrix._11 = worldMatrix._22 = worldMatrix._33 = worldMatrix._44 = 1.0f;

    memset(&viewport, 0, sizeof(viewport));
    memset(&currentMaterial, 0, sizeof(currentMaterial));
    memset(lights, 0, sizeof(lights));
    memset(lightEnabled, 0, sizeof(lightEnabled));
    memset(textures, 0, sizeof(textures));
}

void D3D7Device::ApplyRenderState(D3DRENDERSTATETYPE state, DWORD value) {
    switch (state) {
        case D3DRENDERSTATE_ZENABLE:
            if (value) glEnable(GL_DEPTH_TEST);
            else glDisable(GL_DEPTH_TEST);
            break;

        case D3DRENDERSTATE_ZWRITEENABLE:
            glDepthMask(value ? GL_TRUE : GL_FALSE);
            break;

        case D3DRENDERSTATE_ZFUNC:
            switch (value) {
                case D3DCMP_NEVER: glDepthFunc(GL_NEVER); break;
                case D3DCMP_LESS: glDepthFunc(GL_LESS); break;
                case D3DCMP_EQUAL: glDepthFunc(GL_EQUAL); break;
                case D3DCMP_LESSEQUAL: glDepthFunc(GL_LEQUAL); break;
                case D3DCMP_GREATER: glDepthFunc(GL_GREATER); break;
                case D3DCMP_NOTEQUAL: glDepthFunc(GL_NOTEQUAL); break;
                case D3DCMP_GREATEREQUAL: glDepthFunc(GL_GEQUAL); break;
                case D3DCMP_ALWAYS: glDepthFunc(GL_ALWAYS); break;
            }
            break;

        case D3DRENDERSTATE_ALPHABLENDENABLE:
            if (value) glEnable(GL_BLEND);
            else glDisable(GL_BLEND);
            break;

        case D3DRENDERSTATE_SRCBLEND:
            {
                GLenum src = GL_ONE;
                switch (value) {
                    case D3DBLEND_ZERO: src = GL_ZERO; break;
                    case D3DBLEND_ONE: src = GL_ONE; break;
                    case D3DBLEND_SRCCOLOR: src = GL_SRC_COLOR; break;
                    case D3DBLEND_INVSRCCOLOR: src = GL_ONE_MINUS_SRC_COLOR; break;
                    case D3DBLEND_SRCALPHA: src = GL_SRC_ALPHA; break;
                    case D3DBLEND_INVSRCALPHA: src = GL_ONE_MINUS_SRC_ALPHA; break;
                    case D3DBLEND_DESTALPHA: src = GL_DST_ALPHA; break;
                    case D3DBLEND_INVDESTALPHA: src = GL_ONE_MINUS_DST_ALPHA; break;
                    case D3DBLEND_DESTCOLOR: src = GL_DST_COLOR; break;
                    case D3DBLEND_INVDESTCOLOR: src = GL_ONE_MINUS_DST_COLOR; break;
                    case D3DBLEND_SRCALPHASAT: src = GL_SRC_ALPHA_SATURATE; break;
                }
                GLint dst;
                glGetIntegerv(GL_BLEND_DST, &dst);
                glBlendFunc(src, dst);
            }
            break;

        case D3DRENDERSTATE_DESTBLEND:
            {
                GLenum dst = GL_ZERO;
                switch (value) {
                    case D3DBLEND_ZERO: dst = GL_ZERO; break;
                    case D3DBLEND_ONE: dst = GL_ONE; break;
                    case D3DBLEND_SRCCOLOR: dst = GL_SRC_COLOR; break;
                    case D3DBLEND_INVSRCCOLOR: dst = GL_ONE_MINUS_SRC_COLOR; break;
                    case D3DBLEND_SRCALPHA: dst = GL_SRC_ALPHA; break;
                    case D3DBLEND_INVSRCALPHA: dst = GL_ONE_MINUS_SRC_ALPHA; break;
                    case D3DBLEND_DESTALPHA: dst = GL_DST_ALPHA; break;
                    case D3DBLEND_INVDESTALPHA: dst = GL_ONE_MINUS_DST_ALPHA; break;
                    case D3DBLEND_DESTCOLOR: dst = GL_DST_COLOR; break;
                    case D3DBLEND_INVDESTCOLOR: dst = GL_ONE_MINUS_DST_COLOR; break;
                }
                GLint src;
                glGetIntegerv(GL_BLEND_SRC, &src);
                glBlendFunc(src, dst);
            }
            break;

        case D3DRENDERSTATE_CULLMODE:
            switch (value) {
                case D3DCULL_NONE:
                    glDisable(GL_CULL_FACE);
                    break;
                case D3DCULL_CW:
                    glEnable(GL_CULL_FACE);
#ifdef FF_LINUX
                    glFrontFace(GL_CW);   // FF_LINUX: Flip matrix (det=-1) reverses winding
#else
                    glFrontFace(GL_CCW);
#endif
                    glCullFace(GL_BACK);
                    break;
                case D3DCULL_CCW:
                    glEnable(GL_CULL_FACE);
#ifdef FF_LINUX
                    glFrontFace(GL_CCW);  // FF_LINUX: Flip matrix (det=-1) reverses winding
#else
                    glFrontFace(GL_CW);
#endif
                    glCullFace(GL_BACK);
                    break;
            }
            break;

        case D3DRENDERSTATE_LIGHTING:
            if (value) glEnable(GL_LIGHTING);
            else glDisable(GL_LIGHTING);
            break;

        case D3DRENDERSTATE_SHADEMODE:
            if (value == D3DSHADE_FLAT) glShadeModel(GL_FLAT);
            else glShadeModel(GL_SMOOTH);
            break;

        case D3DRENDERSTATE_FILLMODE:
            switch (value) {
                case D3DFILL_POINT: glPolygonMode(GL_FRONT_AND_BACK, GL_POINT); break;
                case D3DFILL_WIREFRAME: glPolygonMode(GL_FRONT_AND_BACK, GL_LINE); break;
                case D3DFILL_SOLID: glPolygonMode(GL_FRONT_AND_BACK, GL_FILL); break;
            }
            break;

        case D3DRENDERSTATE_FOGENABLE:
            if (value) glEnable(GL_FOG);
            else glDisable(GL_FOG);
            break;

        case D3DRENDERSTATE_FOGCOLOR:
            {
                float r, g, b, a;
                D3DColorToGL(value, &r, &g, &b, &a);
                float fogColor[4] = {r, g, b, a};
                glFogfv(GL_FOG_COLOR, fogColor);
            }
            break;

        case D3DRENDERSTATE_FOGSTART:
            glFogf(GL_FOG_START, *(float*)&value);
            break;

        case D3DRENDERSTATE_FOGEND:
            glFogf(GL_FOG_END, *(float*)&value);
            break;

        case D3DRENDERSTATE_FOGVERTEXMODE:
        case D3DRENDERSTATE_FOGTABLEMODE:
            switch (value) {
                case D3DFOG_NONE: break;
                case D3DFOG_LINEAR: glFogi(GL_FOG_MODE, GL_LINEAR); break;
                case D3DFOG_EXP: glFogi(GL_FOG_MODE, GL_EXP); break;
                case D3DFOG_EXP2: glFogi(GL_FOG_MODE, GL_EXP2); break;
            }
            break;

        case D3DRENDERSTATE_ALPHATESTENABLE:
            if (value) glEnable(GL_ALPHA_TEST);
            else glDisable(GL_ALPHA_TEST);
            break;

        case D3DRENDERSTATE_ALPHAFUNC:
            {
                // FF_LINUX: Preserve current alpha ref value when changing function.
                // The old code used hardcoded 0, which made alpha test always pass.
                GLfloat currentRef;
                glGetFloatv(GL_ALPHA_TEST_REF, &currentRef);
                switch (value) {
                    case D3DCMP_NEVER: glAlphaFunc(GL_NEVER, currentRef); break;
                    case D3DCMP_LESS: glAlphaFunc(GL_LESS, currentRef); break;
                    case D3DCMP_EQUAL: glAlphaFunc(GL_EQUAL, currentRef); break;
                    case D3DCMP_LESSEQUAL: glAlphaFunc(GL_LEQUAL, currentRef); break;
                    case D3DCMP_GREATER: glAlphaFunc(GL_GREATER, currentRef); break;
                    case D3DCMP_NOTEQUAL: glAlphaFunc(GL_NOTEQUAL, currentRef); break;
                    case D3DCMP_GREATEREQUAL: glAlphaFunc(GL_GEQUAL, currentRef); break;
                    case D3DCMP_ALWAYS: glAlphaFunc(GL_ALWAYS, currentRef); break;
                }
            }
            break;

        case D3DRENDERSTATE_ALPHAREF:
            {
                GLint func;
                glGetIntegerv(GL_ALPHA_TEST_FUNC, &func);
                glAlphaFunc(func, value / 255.0f);
            }
            break;

        case D3DRENDERSTATE_STENCILENABLE:
            if (value) glEnable(GL_STENCIL_TEST);
            else glDisable(GL_STENCIL_TEST);
            break;

        case D3DRENDERSTATE_STENCILFUNC:
            g_stencilFunc = D3DCmpToGL(value);
            glStencilFunc(g_stencilFunc, g_stencilRef, g_stencilMask);
            break;

        case D3DRENDERSTATE_STENCILREF:
            g_stencilRef = (GLint)value;
            glStencilFunc(g_stencilFunc, g_stencilRef, g_stencilMask);
            break;

        case D3DRENDERSTATE_STENCILMASK:
            g_stencilMask = (GLuint)value;
            glStencilFunc(g_stencilFunc, g_stencilRef, g_stencilMask);
            break;

        case D3DRENDERSTATE_STENCILWRITEMASK:
            glStencilMask((GLuint)value);
            break;

        case D3DRENDERSTATE_STENCILFAIL:
            g_stencilFail = D3DStencilOpToGL(value);
            glStencilOp(g_stencilFail, g_stencilZFail, g_stencilPass);
            break;

        case D3DRENDERSTATE_STENCILZFAIL:
            g_stencilZFail = D3DStencilOpToGL(value);
            glStencilOp(g_stencilFail, g_stencilZFail, g_stencilPass);
            break;

        case D3DRENDERSTATE_STENCILPASS:
            g_stencilPass = D3DStencilOpToGL(value);
            glStencilOp(g_stencilFail, g_stencilZFail, g_stencilPass);
            break;

        case D3DRENDERSTATE_SPECULARENABLE:
            if (value) {
                glLightModeli(GL_LIGHT_MODEL_COLOR_CONTROL, GL_SEPARATE_SPECULAR_COLOR);
            } else {
                glLightModeli(GL_LIGHT_MODEL_COLOR_CONTROL, GL_SINGLE_COLOR);
            }
            break;

        case D3DRENDERSTATE_AMBIENT:
            {
                float r, g, b, a;
                D3DColorToGL(value, &r, &g, &b, &a);
                float amb[4] = {r, g, b, a};
                glLightModelfv(GL_LIGHT_MODEL_AMBIENT, amb);
            }
            break;

        case D3DRENDERSTATE_COLORVERTEX:
            if (value) {
                glEnable(GL_COLOR_MATERIAL);
                // Default: vertex color drives ambient and diffuse
                glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE);
            } else {
                glDisable(GL_COLOR_MATERIAL);
            }
            break;

        case D3DRENDERSTATE_DIFFUSEMATERIALSOURCE:
        case D3DRENDERSTATE_AMBIENTMATERIALSOURCE:
            // D3DMCS_COLOR1 (vertex diffuse) = use vertex color for this property
            // D3DMCS_COLOR2 (vertex specular) = use specular color
            // D3DMCS_MATERIAL = use material property
            // For OpenGL, glColorMaterial controls which property tracks vertex color
            // The most common combo is DIFFUSE=COLOR1, AMBIENT=COLOR1 → GL_AMBIENT_AND_DIFFUSE
            if (value == 0 /* D3DMCS_MATERIAL */) {
                // Material property used, don't track vertex color for this
                // (We approximate by leaving GL_COLOR_MATERIAL as-is)
            } else {
                // Vertex color tracks diffuse+ambient (the common case)
                glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE);
            }
            break;

        case D3DRENDERSTATE_SPECULARMATERIALSOURCE:
        case D3DRENDERSTATE_EMISSIVEMATERIALSOURCE:
            // These are harder to map to OpenGL's fixed-function pipeline
            // glColorMaterial only tracks one pair. The game primarily uses
            // DIFFUSE+AMBIENT from vertex color, so we accept this limitation.
            break;

        case D3DRENDERSTATE_ZBIAS:
            // Map to glPolygonOffset to prevent z-fighting
            if (value) {
                glEnable(GL_POLYGON_OFFSET_FILL);
                glPolygonOffset(0.0f, -(float)value);
            } else {
                glDisable(GL_POLYGON_OFFSET_FILL);
            }
            break;

        case D3DRENDERSTATE_TEXTUREFACTOR:
            // Store for use in texture combine
            // OpenGL handles this differently - through glTexEnv
            break;

        default:
            D3DGL_LOG("Unhandled render state: %d = %d", state, value);
            break;
    }
}

void D3D7Device::ApplyTextureStageState(DWORD stage, D3DTEXTURESTAGESTATETYPE type, DWORD value) {
    glActiveTexture(GL_TEXTURE0 + stage);

    switch (type) {
        case D3DTSS_COLOROP:
            switch (value) {
                case D3DTOP_DISABLE:
                    // FF_LINUX: Do NOT call glDisable(GL_TEXTURE_2D) here.
                    // Only SetTexture() should control GL_TEXTURE_2D enable/disable.
                    // COLOROP=DISABLE in D3D7 means "skip this stage, use vertex color."
                    // Instead of disabling the texture unit (which leaks state into
                    // subsequent draws that expect GL_TEXTURE_2D to still be enabled),
                    // set GL_COMBINE to pass through vertex color. The null-texture check
                    // in DrawIndexedPrimitiveVB handles the case where no texture is bound.
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_RGB, GL_REPLACE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_PRIMARY_COLOR);
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PRIMARY_COLOR);
                    break;
                case D3DTOP_SELECTARG1:
                    // FF_LINUX: Do NOT call glEnable(GL_TEXTURE_2D) here.
                    // Only SetTexture() should control GL_TEXTURE_2D enable/disable.
                    // ApplyStateBlock applies COLOROP for every polygon, but SetTexture1()
                    // caches and may skip the actual SetTexture(0, NULL) call for consecutive
                    // gouraud polygons. If we re-enable GL_TEXTURE_2D here, the cached
                    // SetTexture1(-1) won't disable it, causing stale textures to render
                    // on untextured (gouraud) terrain → white patches.
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_RGB, GL_REPLACE);
                    break;
                case D3DTOP_MODULATE:
                case D3DTOP_MODULATE2X:
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_RGB, GL_MODULATE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_TEXTURE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_RGB, GL_PRIMARY_COLOR);
                    if (value == D3DTOP_MODULATE2X)
                        glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, 2);
                    else
                        glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, 1);
                    break;
                case D3DTOP_ADD:
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_RGB, GL_ADD);
                    break;
                default:
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE);
                    break;
            }
            break;

        case D3DTSS_MAGFILTER:
            if (value == D3DTFG_POINT || value == D3DTFN_POINT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
            else
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            break;

        case D3DTSS_MINFILTER:
            if (value == D3DTFG_POINT || value == D3DTFN_POINT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
            else
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            break;

        case D3DTSS_MIPFILTER:
            // MIP filter combined with min filter
            break;

        case D3DTSS_ADDRESS:
        case D3DTSS_ADDRESSU:
            if (value == D3DTADDRESS_WRAP)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
            else if (value == D3DTADDRESS_CLAMP)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            break;

        case D3DTSS_ADDRESSV:
            if (value == D3DTADDRESS_WRAP)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
            else if (value == D3DTADDRESS_CLAMP)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
            break;

        case D3DTSS_COLORARG1:
            // Set source 0 for GL_COMBINE color operation
            glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
            if (value == D3DTA_TEXTURE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_TEXTURE);
            else if (value == D3DTA_DIFFUSE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_PRIMARY_COLOR);
            else if (value == D3DTA_CURRENT)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_PREVIOUS);
            else if (value == D3DTA_TFACTOR)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_CONSTANT);
            break;

        case D3DTSS_COLORARG2:
            // Set source 1 for GL_COMBINE color operation
            glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
            if (value == D3DTA_TEXTURE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_RGB, GL_TEXTURE);
            else if (value == D3DTA_DIFFUSE || value == D3DTA_CURRENT)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_RGB, GL_PRIMARY_COLOR);
            else if (value == D3DTA_TFACTOR)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_RGB, GL_CONSTANT);
            break;

        case D3DTSS_ALPHAOP:
            switch (value) {
                case D3DTOP_DISABLE:
                    break;
                case D3DTOP_SELECTARG1:
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE);
                    // FF_LINUX: Must also set SOURCE0_ALPHA based on current ALPHAARG1.
                    // State blocks don't include ALPHAARG1, so a previous state's
                    // COLOROP=DISABLE may have left SOURCE0_ALPHA=GL_PRIMARY_COLOR,
                    // causing fragment alpha to come from vertex color (always 1.0)
                    // instead of texture alpha. This breaks chroma key transparency.
                    {
                        auto arg1Key = std::make_pair(stage, (D3DTEXTURESTAGESTATETYPE)D3DTSS_ALPHAARG1);
                        auto it = textureStageStates.find(arg1Key);
                        DWORD arg1 = (it != textureStageStates.end()) ? it->second : D3DTA_TEXTURE;
                        if (arg1 == D3DTA_TEXTURE)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
                        else if (arg1 == D3DTA_DIFFUSE)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PRIMARY_COLOR);
                        else if (arg1 == D3DTA_CURRENT)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PREVIOUS);
                    }
                    break;
                case D3DTOP_MODULATE:
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_MODULATE);
                    // FF_LINUX: Set sources for modulate too
                    {
                        auto arg1Key = std::make_pair(stage, (D3DTEXTURESTAGESTATETYPE)D3DTSS_ALPHAARG1);
                        auto it = textureStageStates.find(arg1Key);
                        DWORD arg1 = (it != textureStageStates.end()) ? it->second : D3DTA_TEXTURE;
                        if (arg1 == D3DTA_TEXTURE)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
                        else if (arg1 == D3DTA_DIFFUSE)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PRIMARY_COLOR);
                        else if (arg1 == D3DTA_CURRENT)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PREVIOUS);

                        auto arg2Key = std::make_pair(stage, (D3DTEXTURESTAGESTATETYPE)D3DTSS_ALPHAARG2);
                        auto it2 = textureStageStates.find(arg2Key);
                        DWORD arg2 = (it2 != textureStageStates.end()) ? it2->second : D3DTA_CURRENT;
                        if (arg2 == D3DTA_TEXTURE)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_ALPHA, GL_TEXTURE);
                        else if (arg2 == D3DTA_DIFFUSE || arg2 == D3DTA_CURRENT)
                            glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_ALPHA, GL_PRIMARY_COLOR);
                    }
                    break;
                default:
                    glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_MODULATE);
                    break;
            }
            break;

        case D3DTSS_ALPHAARG1:
            if (value == D3DTA_TEXTURE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
            else if (value == D3DTA_DIFFUSE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PRIMARY_COLOR);
            else if (value == D3DTA_CURRENT)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PREVIOUS);
            break;

        case D3DTSS_ALPHAARG2:
            if (value == D3DTA_TEXTURE)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_ALPHA, GL_TEXTURE);
            else if (value == D3DTA_DIFFUSE || value == D3DTA_CURRENT)
                glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_ALPHA, GL_PRIMARY_COLOR);
            break;

        default:
            break;
    }

    glActiveTexture(GL_TEXTURE0);
}

void D3D7Device::ApplyMaterial() {
    float ambient[4], diffuse[4], specular[4], emissive[4];
    D3DColorValueToGL(currentMaterial.ambient, ambient);
    D3DColorValueToGL(currentMaterial.diffuse, diffuse);
    D3DColorValueToGL(currentMaterial.specular, specular);
    D3DColorValueToGL(currentMaterial.emissive, emissive);

    glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, ambient);
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, diffuse);
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular);
    glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, emissive);
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, currentMaterial.power);
}

void D3D7Device::ApplyLights() {
    for (int i = 0; i < MAX_GL_LIGHTS; i++) {
        if (lightEnabled[i]) {
            glEnable(GL_LIGHT0 + i);
        } else {
            glDisable(GL_LIGHT0 + i);
        }
    }
}

void D3D7Device::ApplyMatrices() {
    // Apply projection matrix
    glMatrixMode(GL_PROJECTION);
    glLoadMatrixf((const float*)&projMatrix);

    // Apply modelview matrix using GL operations for correct D3D→GL convention.
    // D3D uses row-major matrices with row vectors: v' = v * W * V
    // glLoadMatrixf implicitly transposes (reads row-major as column-major).
    // glLoadMatrixf(V) gives V_gl = V_d3d^T, glMultMatrixf(W) gives V_gl * W_gl.
    // Result: V_d3d^T * W_d3d^T = correct GL modelview.
    glMatrixMode(GL_MODELVIEW);
    glLoadMatrixf((const float*)&viewMatrix);
    glMultMatrixf((const float*)&worldMatrix);
}

void D3D7Device::SetupVertexFormat(DWORD fvf) {
    // For immediate mode rendering, no setup needed
}

GLenum D3D7Device::GetGLPrimitiveType(D3DPRIMITIVETYPE d3dType) {
    switch (d3dType) {
        case D3DPT_POINTLIST: return GL_POINTS;
        case D3DPT_LINELIST: return GL_LINES;
        case D3DPT_LINESTRIP: return GL_LINE_STRIP;
        case D3DPT_TRIANGLELIST: return GL_TRIANGLES;
        case D3DPT_TRIANGLESTRIP: return GL_TRIANGLE_STRIP;
        case D3DPT_TRIANGLEFAN: return GL_TRIANGLE_FAN;
        default: return GL_TRIANGLES;
    }
}

int g_DrawVerticesCount = 0;
static int g_RHWDrawCount_local = 0;
static int g_WorldDrawCount_local = 0;
void D3D7Device::DrawVertices(D3DPRIMITIVETYPE primType, DWORD fvf, const void* vertices, DWORD count) {
    int vertexSize = GetVertexSize(fvf);
    GLenum glPrimType = GetGLPrimitiveType(primType);
    g_DrawVerticesCount++;
    bool isRHW = (fvf & D3DFVF_XYZRHW) != 0;
    if (isRHW) g_RHWDrawCount_local++; else g_WorldDrawCount_local++;

    // FF_LINUX: XYZRHW vertices are pre-transformed screen coordinates in DirectX.
    // They bypass the transformation pipeline entirely. In OpenGL, we need to:
    // 1. Set up orthographic projection matching the viewport
    // 2. Set modelview to identity
    // 3. Use glVertex3f with x, y, z directly (not glVertex4f which divides by w)
    bool isXYZRHW = (fvf & D3DFVF_XYZRHW) != 0;

    // FF_LINUX: Save GL state that XYZRHW handling will modify
    GLboolean prevLighting = GL_FALSE, prevFog = GL_FALSE;

    // FF_LINUX: Ensure we're operating on texture unit 0.
    // SetTexture(1, NULL) in SelectTexture1 leaves GL_TEXTURE1 as active unit.
    glActiveTexture(GL_TEXTURE0);

    // FF_LINUX: Disable GL_TEXTURE_2D when no texture coordinates in FVF.
    // Otherwise stale textures from previous draws would modulate the vertex colors.
    int texCountCheck = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
    GLboolean prevTexture2D = GL_FALSE;
    if (texCountCheck == 0) {
        prevTexture2D = glIsEnabled(GL_TEXTURE_2D);
        if (prevTexture2D) {
            glDisable(GL_TEXTURE_2D);
        }
    }

    GLint savedViewportDV[4] = {0};
    bool restoredViewportDV = false;
    GLboolean prevDepthTestDV = GL_FALSE;
    GLboolean prevScissorDV = GL_FALSE;
    GLint savedScissorDV[4] = {0};
    GLint savedFogModeDV = GL_EXP; GLfloat savedFogStartDV = 0, savedFogEndDV = 1;
    if (isXYZRHW) {
        // FF_LINUX: In D3D7, XYZRHW vertices are in absolute pixel coordinates and
        // bypass the viewport transform. Our GL emulation must match this by using
        // the actual render target dimensions for glOrtho and glViewport.
        // The GL viewport is temporarily expanded to the full render target, and
        // GL_SCISSOR_TEST clips to the original viewport area (for MFDs etc.).
        DWORD vpW, vpH;
        D3D7Surface* rt = renderTarget;
        if (rt && rt != defaultRenderTarget && rt->fboId) {
            // Rendering to FBO - use FBO texture dimensions for 1:1 pixel mapping
            vpW = rt->width;
            vpH = rt->height;
            glGetIntegerv(GL_VIEWPORT, savedViewportDV);
            restoredViewportDV = true;
            glViewport(0, 0, vpW, vpH);
            prevDepthTestDV = glIsEnabled(GL_DEPTH_TEST);
            glDisable(GL_DEPTH_TEST);
        } else {
            // Screen rendering: use render target surface dimensions for ortho,
            // and temporarily expand GL viewport to full screen. Use scissor test
            // to clip to the original viewport area (needed for MFD sub-viewports).
            DDSURFACEDESC2 rtDesc;
            memset(&rtDesc, 0, sizeof(rtDesc));
            rtDesc.dwSize = sizeof(rtDesc);
            if (rt) rt->GetSurfaceDesc(&rtDesc);
            vpW = rtDesc.dwWidth;
            vpH = rtDesc.dwHeight;
            if (vpW == 0 || vpH == 0) {
                vpW = 1024; vpH = 768; // Fallback
            }
            // Save and expand GL viewport to full render target
            glGetIntegerv(GL_VIEWPORT, savedViewportDV);
            if ((DWORD)savedViewportDV[2] != vpW || (DWORD)savedViewportDV[3] != vpH) {
                restoredViewportDV = true;
                // Enable scissor test to clip to original viewport area
                prevScissorDV = glIsEnabled(GL_SCISSOR_TEST);
                glGetIntegerv(GL_SCISSOR_BOX, savedScissorDV);
                glEnable(GL_SCISSOR_TEST);
                glScissor(savedViewportDV[0], savedViewportDV[1],
                          savedViewportDV[2], savedViewportDV[3]);
                glViewport(0, 0, vpW, vpH);
            }
        }
        if (vpW == 0 || vpH == 0) {
            if (texCountCheck == 0 && prevTexture2D) glEnable(GL_TEXTURE_2D);
            return;
        }

        prevLighting = glIsEnabled(GL_LIGHTING);
        prevFog = glIsEnabled(GL_FOG);

        glMatrixMode(GL_PROJECTION);
        glPushMatrix();
        glLoadIdentity();
        // FF_LINUX: D3D XYZRHW z values are in [0,1] where 0=near and 1=far.
        // glOrtho(0,w,h,0, near=0, far=-1) gives z_ndc = 2*z - 1: z=0→-1, z=1→+1.
        if (rt && rt != defaultRenderTarget && rt->fboId) {
            // FBO rendering: DON'T flip Y so texture v=0 reads what was drawn at D3D y=0
            glOrtho(0, vpW, 0, vpH, 0, -1);
        } else {
            // Screen rendering: flip Y so D3D y=0 is at top of screen
            glOrtho(0, vpW, vpH, 0, 0, -1);
        }

        glMatrixMode(GL_MODELVIEW);
        glPushMatrix();
        glLoadIdentity();

        // XYZRHW bypasses D3D lighting pipeline only
        glDisable(GL_LIGHTING);

        // FF_LINUX: D3D7 uses the specular color alpha byte as per-vertex fog factor
        // (0xFF = no fog, 0x00 = full fog). The software rasterizer ALWAYS computes
        // fog values in specular alpha (via SetSpecularFog/m_colFOG), even in clear
        // weather when FOGENABLE isn't set. D3D7 hardware/drivers apply this
        // automatically for TLVERTEX; GL needs explicit fog coord setup.
        // When specular alpha is 0xFF (no fog), fog_factor=1.0, no visual change.
        // Save fog params so we can restore them for subsequent depth-based fog draws.
        if (fvf & D3DFVF_SPECULAR) {
            glGetIntegerv(GL_FOG_MODE, &savedFogModeDV);
            glGetFloatv(GL_FOG_START, &savedFogStartDV);
            glGetFloatv(GL_FOG_END, &savedFogEndDV);
            glEnable(GL_FOG);
            glFogi(GL_FOG_COORD_SRC, GL_FOG_COORD);
            glFogi(GL_FOG_MODE, GL_LINEAR);
            glFogf(GL_FOG_START, 1.0f);
            glFogf(GL_FOG_END, 0.0f);
            // DIAG: Log GL_TEXTURE_2D state for terrain draws
            {
                static int texDiagDV = 0;
                static unsigned long lastFrame = 0;
                if (g_RenderFrameCount != lastFrame && g_RenderFrameCount == 3) {
                    lastFrame = g_RenderFrameCount;
                    texDiagDV = 0;
                }
                if (texDiagDV < 40 && g_RenderFrameCount == 3) {
                    GLboolean tex2dOn = glIsEnabled(GL_TEXTURE_2D);
                    GLint boundTex = 0;
                    glGetIntegerv(GL_TEXTURE_BINDING_2D, &boundTex);
                    // Sample first vertex diffuse and specular
                    DWORD diff0 = 0, spec0 = 0;
                    if (count > 0) {
                        int off = 4*sizeof(float); // skip XYZRHW
                        if (fvf & D3DFVF_DIFFUSE) { diff0 = *(const DWORD*)((const char*)vertices + off); off += sizeof(DWORD); }
                        if (fvf & D3DFVF_SPECULAR) { spec0 = *(const DWORD*)((const char*)vertices + off); }
                    }
                    const float* pos0 = (const float*)vertices;
                    fprintf(stderr, "[TEX_DIAG] DV#%d: tex2d=%d boundTex=%d verts=%d diff=0x%08X spec=0x%08X pos=(%.0f,%.0f,%.4f)\n",
                            texDiagDV, tex2dOn, boundTex, count, diff0, spec0, pos0[0], pos0[1], pos0[2]);
                    texDiagDV++;
                }
            }
        } else {
            glDisable(GL_FOG);
        }

    }

    // FF_LINUX: If the device has no texture bound on stage 0 but GL_TEXTURE_2D is still
    // enabled (can happen because ApplyStateBlock doesn't capture SetTexture calls),
    // we must disable GL_TEXTURE_2D. Otherwise non-textured primitives render as black.
    bool disabledTexForNull_DV = false;
    if (!textures[0] && glIsEnabled(GL_TEXTURE_2D)) {
        disabledTexForNull_DV = true;
        glDisable(GL_TEXTURE_2D);
    }

#ifdef FF_LINUX
    // FF_LINUX: Fix chroma key transparency (see DrawIndexedPrimitiveVB for details)
    if (isXYZRHW && textures[0] && glIsEnabled(GL_ALPHA_TEST)) {
        glActiveTexture(GL_TEXTURE0);
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE);
        glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE);
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_TEXTURE);
        glAlphaFunc(GL_GEQUAL, 0.5f);
    }
#endif

    glBegin(glPrimType);

    for (DWORD i = 0; i < count; i++) {
        const char* vertex = (const char*)vertices + i * vertexSize;
        int offset = 0;

        // Texture coords first (for proper GL state)
        int texOffset = 0;
        if (fvf & D3DFVF_XYZ) texOffset += 3 * sizeof(float);
        else if (fvf & D3DFVF_XYZRHW) texOffset += 4 * sizeof(float);
        if (fvf & D3DFVF_NORMAL) texOffset += 3 * sizeof(float);
        if (fvf & D3DFVF_DIFFUSE) texOffset += sizeof(DWORD);
        if (fvf & D3DFVF_SPECULAR) texOffset += sizeof(DWORD);

        int texCount = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
        if (texCount > 0) {
            const float* tc = (const float*)(vertex + texOffset);
            glTexCoord2fv(tc);
        }

        // Normal
        if (fvf & D3DFVF_XYZ) {
            offset = 3 * sizeof(float);
        } else if (fvf & D3DFVF_XYZRHW) {
            offset = 4 * sizeof(float);
        }

        if (fvf & D3DFVF_NORMAL) {
            const float* norm = (const float*)(vertex + offset);
            glNormal3fv(norm);
            offset += 3 * sizeof(float);
        }

        // Diffuse color
        if (fvf & D3DFVF_DIFFUSE) {
            DWORD color = *(const DWORD*)(vertex + offset);
            float r, g, b, a;
            D3DColorToGL(color, &r, &g, &b, &a);
            // FF_LINUX: Force alpha=1 for FBO XYZRHW rendering (see DrawIndexedPrimitiveVB)
            if (restoredViewportDV && a == 0.0f) a = 1.0f;
            glColor4f(r, g, b, a);
            offset += sizeof(DWORD);
        }

        // Specular color - extract alpha byte as per-vertex fog factor
        if (fvf & D3DFVF_SPECULAR) {
            DWORD specular = *(const DWORD*)(vertex + offset);
            // D3D7: specular alpha = fog factor (0xFF=no fog, 0x00=full fog)
            // Always submit fog coord for XYZRHW - we unconditionally enable GL_FOG above
            if (isXYZRHW) {
                glFogCoordf((float)(specular >> 24) / 255.0f);
            }
            offset += sizeof(DWORD);
        }

        // Position (must be last for glVertex)
        if (fvf & D3DFVF_XYZ) {
            const float* pos = (const float*)vertex;
            glVertex3fv(pos);
        } else if (fvf & D3DFVF_XYZRHW) {
            // XYZRHW: x, y are screen coords, z is depth (0-1), w is RHW (1/W)
            // Use x, y, z directly without the RHW component
            const float* pos = (const float*)vertex;
            glVertex3f(pos[0], pos[1], pos[2]);
        }
    }

    glEnd();

    // Restore GL_TEXTURE_2D if we disabled it for null-texture draw
    if (disabledTexForNull_DV) {
        glEnable(GL_TEXTURE_2D);
    }

    if (isXYZRHW) {
        // Restore matrices
        glMatrixMode(GL_MODELVIEW);
        glPopMatrix();
        glMatrixMode(GL_PROJECTION);
        glPopMatrix();

        // Restore previous GL state (don't blindly enable - that corrupts state for subsequent draws)
        if (prevLighting) glEnable(GL_LIGHTING); else glDisable(GL_LIGHTING);
        // Restore fog to previous state. We may have enabled it for specular-alpha fog.
        if (prevFog) glEnable(GL_FOG); else glDisable(GL_FOG);
        if (fvf & D3DFVF_SPECULAR) {
            // Restore fog coord source and parameters for subsequent depth-based fog draws
            glFogi(GL_FOG_COORD_SRC, GL_FRAGMENT_DEPTH);
            glFogi(GL_FOG_MODE, savedFogModeDV);
            glFogf(GL_FOG_START, savedFogStartDV);
            glFogf(GL_FOG_END, savedFogEndDV);
        }
        // Restore glViewport and depth test if we changed them
        if (restoredViewportDV) {
            glViewport(savedViewportDV[0], savedViewportDV[1], savedViewportDV[2], savedViewportDV[3]);
            if (prevDepthTestDV) glEnable(GL_DEPTH_TEST);
            // Restore scissor state (may have been enabled for sub-viewport clipping)
            if (prevScissorDV) {
                glScissor(savedScissorDV[0], savedScissorDV[1], savedScissorDV[2], savedScissorDV[3]);
            } else {
                glDisable(GL_SCISSOR_TEST);
            }
        }
    }

    // Restore GL_TEXTURE_2D state if we disabled it
    if (texCountCheck == 0 && prevTexture2D) {
        glEnable(GL_TEXTURE_2D);
    }

#ifdef FF_LINUX_DEBUG_RENDER
    // Check for OpenGL errors after drawing (only in render debug mode)
    GLenum err = glGetError();
    if (err != GL_NO_ERROR) {
        FF_DEBUG_RENDER_FRAME(g_RenderFrameCount, "  GL ERROR after DrawVertices: 0x%x count=%u primType=%d\n",
                              err, count, primType);
        FF_DEBUG_RENDER_FLUSH();
    }
#endif
}

// ============================================================
// IDirect3DVertexBuffer7 vtable implementation
// ============================================================
static HRESULT STDMETHODCALLTYPE D3D7VB_QueryInterface(IDirect3DVertexBuffer7* This, REFIID riid, void** ppv) {
    *ppv = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE D3D7VB_AddRef(IDirect3DVertexBuffer7* This) {
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)This;
    return ++vb->refCount;
}

static ULONG STDMETHODCALLTYPE D3D7VB_Release(IDirect3DVertexBuffer7* This) {
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)This;
    LONG ref = --vb->refCount;
    if (ref == 0) {
        delete vb;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_Lock(IDirect3DVertexBuffer7* This, DWORD dwFlags, LPVOID* lplpData, LPDWORD lpdwSize) {
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)This;
    D3DGL_LOG("VB Lock flags=0x%x", dwFlags);

    if (!lplpData) return DDERR_INVALIDPARAMS;

    *lplpData = vb->data;
    if (lpdwSize) *lpdwSize = vb->dataSize;
    vb->locked = true;

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_Unlock(IDirect3DVertexBuffer7* This) {
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)This;
    D3DGL_LOG("VB Unlock");
    vb->locked = false;
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_ProcessVertices(IDirect3DVertexBuffer7* This, DWORD dwVertexOp, DWORD dwDestIndex, DWORD dwCount, IDirect3DVertexBuffer7* lpSrcBuffer, DWORD dwSrcIndex, IDirect3DDevice7* lpD3DDevice, DWORD dwFlags) {
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_GetVertexBufferDesc(IDirect3DVertexBuffer7* This, LPD3DVERTEXBUFFERDESC lpVBDesc) {
    D3D7VertexBuffer* vb = (D3D7VertexBuffer*)This;
    if (!lpVBDesc) return DDERR_INVALIDPARAMS;
    memcpy(lpVBDesc, &vb->desc, sizeof(D3DVERTEXBUFFERDESC));
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_Optimize(IDirect3DVertexBuffer7* This, IDirect3DDevice7* lpD3DDevice, DWORD dwFlags) {
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7VB_ProcessVerticesStrided(IDirect3DVertexBuffer7* This, DWORD dwVertexOp, DWORD dwDestIndex, DWORD dwCount, void* lpVertexArray, DWORD dwSrcIndex, IDirect3DDevice7* lpD3DDevice, DWORD dwFlags) {
    return D3D_OK;
}

static const IDirect3DVertexBuffer7Vtbl g_D3D7VBVtbl = {
    D3D7VB_QueryInterface,
    D3D7VB_AddRef,
    D3D7VB_Release,
    D3D7VB_Lock,
    D3D7VB_Unlock,
    D3D7VB_ProcessVertices,
    D3D7VB_GetVertexBufferDesc,
    D3D7VB_Optimize,
    D3D7VB_ProcessVerticesStrided
};

// ============================================================
// IDirect3D7 vtable implementation
// ============================================================
static HRESULT STDMETHODCALLTYPE D3D7_QueryInterface(IDirect3D7* This, REFIID riid, void** ppv) {
    *ppv = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE D3D7_AddRef(IDirect3D7* This) {
    D3D7Interface* d3d = (D3D7Interface*)This;
    return ++d3d->refCount;
}

static ULONG STDMETHODCALLTYPE D3D7_Release(IDirect3D7* This) {
    D3D7Interface* d3d = (D3D7Interface*)This;
    LONG ref = --d3d->refCount;
    if (ref == 0) {
        delete d3d;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE D3D7_EnumDevices(IDirect3D7* This, void* cb, LPVOID arg) {
    D3DGL_LOG("EnumDevices");

    typedef HRESULT (CALLBACK *LPD3DENUMDEVICESCALLBACK7)(LPSTR lpDeviceDescription, LPSTR lpDeviceName, LPD3DDEVICEDESC7 lpD3DHWDeviceDesc, LPVOID lpContext);
    LPD3DENUMDEVICESCALLBACK7 callback = (LPD3DENUMDEVICESCALLBACK7)cb;

    if (!callback) return D3D_OK;

    // Report our OpenGL-backed D3D device
    D3DDEVICEDESC7 desc;
    memset(&desc, 0, sizeof(desc));

    // Report hardware T&L capability which FreeFalcon checks for
    desc.dwDevCaps = D3DDEVCAPS_HWRASTERIZATION | D3DDEVCAPS_HWTRANSFORMANDLIGHT;
    desc.dpcTriCaps.dwTextureCaps = D3DPTEXTURECAPS_PERSPECTIVE | D3DPTEXTURECAPS_ALPHA;
    desc.dpcTriCaps.dwShadeCaps = D3DPSHADECAPS_COLORGOURAUDRGB | D3DPSHADECAPS_ALPHAGOURAUDBLEND;
    desc.dpcTriCaps.dwZCmpCaps = D3DPCMPCAPS_LESSEQUAL | D3DPCMPCAPS_ALWAYS;
    desc.dpcTriCaps.dwAlphaCmpCaps = 0xFF;  // All alpha compare caps (see D3D7Dev_GetCaps comment)
    desc.dpcTriCaps.dwSrcBlendCaps = D3DPBLENDCAPS_SRCALPHA | D3DPBLENDCAPS_ONE | D3DPBLENDCAPS_ZERO;
    desc.dpcTriCaps.dwDestBlendCaps = D3DPBLENDCAPS_INVSRCALPHA | D3DPBLENDCAPS_ONE | D3DPBLENDCAPS_ZERO;

    desc.dwMaxTextureWidth = 2048;
    desc.dwMaxTextureHeight = 2048;
    desc.wMaxTextureBlendStages = 4;
    desc.wMaxSimultaneousTextures = 4;

    callback((LPSTR)"FreeFalcon OpenGL Device", (LPSTR)"OpenGL", &desc, arg);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7_CreateDevice(IDirect3D7* This, REFCLSID rclsid, LPDIRECTDRAWSURFACE7 lpDDS, LPDIRECT3DDEVICE7* lplpD3DDevice) {
    D3DGL_LOG("CreateDevice");

    if (!lplpD3DDevice) return DDERR_INVALIDPARAMS;

    D3D7Device* dev = new D3D7Device();
    dev->d3d = (D3D7Interface*)This;
    dev->d3d->lpVtbl->AddRef(dev->d3d);
    dev->renderTarget = (D3D7Surface*)lpDDS;
    dev->defaultRenderTarget = (D3D7Surface*)lpDDS;  // FF_LINUX: Track initial RT for FBO unbinding

    *lplpD3DDevice = dev;
    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7_CreateVertexBuffer(IDirect3D7* This, LPD3DVERTEXBUFFERDESC lpVBDesc, LPDIRECT3DVERTEXBUFFER7* lplpD3DVertexBuffer, DWORD dwFlags) {
    D3DGL_LOG("CreateVertexBuffer fvf=0x%x numVerts=%d", lpVBDesc->dwFVF, lpVBDesc->dwNumVertices);

    if (!lpVBDesc || !lplpD3DVertexBuffer) return DDERR_INVALIDPARAMS;

    D3D7VertexBuffer* vb = new D3D7VertexBuffer();
    memcpy(&vb->desc, lpVBDesc, sizeof(D3DVERTEXBUFFERDESC));

    int vertexSize = GetVertexSize(lpVBDesc->dwFVF);
    vb->dataSize = vertexSize * lpVBDesc->dwNumVertices;
    vb->data = malloc(vb->dataSize);
    memset(vb->data, 0, vb->dataSize);

    vb->lpVtbl = &g_D3D7VBVtbl;
    *lplpD3DVertexBuffer = vb;

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7_EnumZBufferFormats(IDirect3D7* This, REFCLSID riidDevice, void* cb, LPVOID ctx) {
    D3DGL_LOG("EnumZBufferFormats");

    typedef HRESULT (CALLBACK *LPDDENUMTEXTUREFORMATSCALLBACK)(LPDDPIXELFORMAT lpDDPixFmt, LPVOID lpContext);
    LPDDENUMTEXTUREFORMATSCALLBACK callback = (LPDDENUMTEXTUREFORMATSCALLBACK)cb;

    DDPIXELFORMAT pf;

    // 16-bit Z buffer
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_ZBUFFER;
    pf.dwZBufferBitDepth = 16;
    pf.dwZBitMask = 0xFFFF;
    callback(&pf, ctx);

    // 24-bit Z buffer
    memset(&pf, 0, sizeof(pf));
    pf.dwSize = sizeof(DDPIXELFORMAT);
    pf.dwFlags = DDPF_ZBUFFER;
    pf.dwZBufferBitDepth = 24;
    pf.dwZBitMask = 0xFFFFFF;
    callback(&pf, ctx);

    return D3D_OK;
}

static HRESULT STDMETHODCALLTYPE D3D7_EvictManagedTextures(IDirect3D7* This) {
    D3DGL_LOG("EvictManagedTextures");
    return D3D_OK;
}

static const IDirect3D7Vtbl g_D3D7Vtbl = {
    D3D7_QueryInterface,
    D3D7_AddRef,
    D3D7_Release,
    D3D7_EnumDevices,
    D3D7_CreateDevice,
    D3D7_CreateVertexBuffer,
    D3D7_EnumZBufferFormats,
    D3D7_EvictManagedTextures
};

// ============================================================
// IDirectDrawSurface7 vtable implementation
// ============================================================
static HRESULT STDMETHODCALLTYPE DDS7_QueryInterface(IDirectDrawSurface7* This, REFIID riid, void** ppvObject) {
    D3DGL_LOG("DDS7 QueryInterface");
    if (!ppvObject) return E_POINTER;
    *ppvObject = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE DDS7_AddRef(IDirectDrawSurface7* This) {
    D3D7Surface* surf = (D3D7Surface*)This;
    return ++surf->refCount;
}

static ULONG STDMETHODCALLTYPE DDS7_Release(IDirectDrawSurface7* This) {
    D3D7Surface* surf = (D3D7Surface*)This;
    LONG ref = --surf->refCount;
    if (ref <= 0) {
        delete surf;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE DDS7_AddAttachedSurface(IDirectDrawSurface7* This, IDirectDrawSurface7* pDDS) {
    D3DGL_LOG("DDS7 AddAttachedSurface");
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_AddOverlayDirtyRect(IDirectDrawSurface7* This, LPRECT pRect) {
    return DD_OK;
}

// Helper function to copy pixels between surfaces
static void CopySurfacePixels(D3D7Surface* dst, int dstX, int dstY, int dstW, int dstH,
                               D3D7Surface* src, int srcX, int srcY, int srcW, int srcH) {
    static int copyCount = 0;
    copyCount++;

    if (!dst || !src) {
        if (copyCount <= 3) fprintf(stderr, "[CopySurface] dst=%p, src=%p - NULL surface!\n", (void*)dst, (void*)src);
        return;
    }
    if (!dst->pixelData || !src->pixelData) {
        if (copyCount <= 3) fprintf(stderr, "[CopySurface] dst->pixelData=%p, src->pixelData=%p - NULL buffer!\n",
                (void*)dst->pixelData, (void*)src->pixelData);
        return;
    }

    int dstBpp = dst->pixelFormat.dwRGBBitCount ? dst->pixelFormat.dwRGBBitCount / 8 : 4;
    int srcBpp = src->pixelFormat.dwRGBBitCount ? src->pixelFormat.dwRGBBitCount / 8 : 4;

    // Simple copy - same bit depth, no stretching
    int copyW = (srcW < dstW) ? srcW : dstW;
    int copyH = (srcH < dstH) ? srcH : dstH;

    // Clip to surface bounds
    if (dstX < 0) { srcX -= dstX; copyW += dstX; dstX = 0; }
    if (dstY < 0) { srcY -= dstY; copyH += dstY; dstY = 0; }
    if (dstX + copyW > dst->width) copyW = dst->width - dstX;
    if (dstY + copyH > dst->height) copyH = dst->height - dstY;
    if (srcX + copyW > src->width) copyW = src->width - srcX;
    if (srcY + copyH > src->height) copyH = src->height - srcY;

    if (copyW <= 0 || copyH <= 0) {
        if (copyCount <= 3) fprintf(stderr, "[CopySurface] copyW=%d copyH=%d - nothing to copy!\n", copyW, copyH);
        return;
    }

    for (int y = 0; y < copyH; y++) {
        unsigned char* dstRow = dst->pixelData + ((dstY + y) * dst->pitch) + (dstX * dstBpp);
        unsigned char* srcRow = src->pixelData + ((srcY + y) * src->pitch) + (srcX * srcBpp);

        if (srcBpp == dstBpp) {
            memcpy(dstRow, srcRow, copyW * dstBpp);
        } else {
            // Convert between formats if needed
            for (int x = 0; x < copyW; x++) {
                // Simple copy - just copy min(srcBpp, dstBpp) bytes
                int copyBytes = (srcBpp < dstBpp) ? srcBpp : dstBpp;
                memcpy(dstRow + x * dstBpp, srcRow + x * srcBpp, copyBytes);
            }
        }
    }
}

static HRESULT STDMETHODCALLTYPE DDS7_Blt(IDirectDrawSurface7* This, LPRECT lpDestRect,
    IDirectDrawSurface7* lpDDSrcSurface, LPRECT lpSrcRect, DWORD dwFlags, LPDDBLTFX lpDDBltFx) {
    D3DGL_LOG("DDS7 Blt flags=0x%x", dwFlags);

    D3D7Surface* dst = (D3D7Surface*)This;
    dst->AllocatePixelBuffer();

    int dstX = lpDestRect ? lpDestRect->left : 0;
    int dstY = lpDestRect ? lpDestRect->top : 0;
    int dstW = lpDestRect ? (lpDestRect->right - lpDestRect->left) : dst->width;
    int dstH = lpDestRect ? (lpDestRect->bottom - lpDestRect->top) : dst->height;

    // Handle color fill
    if (dwFlags & DDBLT_COLORFILL) {
        if (dst->pixelData && lpDDBltFx) {
            DWORD fillColor = lpDDBltFx->dwFillColor;
            int bpp = dst->pixelFormat.dwRGBBitCount ? dst->pixelFormat.dwRGBBitCount / 8 : 4;

            for (int y = dstY; y < dstY + dstH && y < dst->height; y++) {
                unsigned char* row = dst->pixelData + (y * dst->pitch) + (dstX * bpp);
                for (int x = 0; x < dstW && (dstX + x) < dst->width; x++) {
                    if (bpp == 2) {
                        *(unsigned short*)(row + x * 2) = (unsigned short)fillColor;
                    } else if (bpp == 4) {
                        *(unsigned int*)(row + x * 4) = fillColor;
                    }
                }
            }
            dst->isDirty = true;
        }
        return DD_OK;
    }

    // Handle source blit
    if (lpDDSrcSurface) {
        D3D7Surface* src = (D3D7Surface*)lpDDSrcSurface;
        src->AllocatePixelBuffer();

        int srcX = lpSrcRect ? lpSrcRect->left : 0;
        int srcY = lpSrcRect ? lpSrcRect->top : 0;
        int srcW = lpSrcRect ? (lpSrcRect->right - lpSrcRect->left) : src->width;
        int srcH = lpSrcRect ? (lpSrcRect->bottom - lpSrcRect->top) : src->height;

        CopySurfacePixels(dst, dstX, dstY, dstW, dstH, src, srcX, srcY, srcW, srcH);
        dst->isDirty = true;
    }

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_BltBatch(IDirectDrawSurface7* This, LPDDBLTBATCH lpDDBltBatch, DWORD dwCount, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_BltFast(IDirectDrawSurface7* This, DWORD dwX, DWORD dwY, IDirectDrawSurface7* lpDDSrcSurface, LPRECT lpSrcRect, DWORD dwTrans) {
    D3DGL_LOG("DDS7 BltFast %d,%d", dwX, dwY);

    if (!lpDDSrcSurface) return DDERR_INVALIDPARAMS;

    D3D7Surface* dst = (D3D7Surface*)This;
    D3D7Surface* src = (D3D7Surface*)lpDDSrcSurface;

    dst->AllocatePixelBuffer();
    src->AllocatePixelBuffer();

    int srcX = lpSrcRect ? lpSrcRect->left : 0;
    int srcY = lpSrcRect ? lpSrcRect->top : 0;
    int srcW = lpSrcRect ? (lpSrcRect->right - lpSrcRect->left) : src->width;
    int srcH = lpSrcRect ? (lpSrcRect->bottom - lpSrcRect->top) : src->height;

    CopySurfacePixels(dst, dwX, dwY, srcW, srcH, src, srcX, srcY, srcW, srcH);
    dst->isDirty = true;

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_DeleteAttachedSurface(IDirectDrawSurface7* This, DWORD dwFlags, IDirectDrawSurface7* lpDDSAttachedSurface) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_EnumAttachedSurfaces(IDirectDrawSurface7* This, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7 lpEnumSurfacesCallback) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_EnumOverlayZOrders(IDirectDrawSurface7* This, DWORD dwFlags, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7 lpfnCallback) {
    return DD_OK;
}

// FF_LINUX DIAGNOSTIC: Draw test quads using raw GL to verify XYZRHW path
// Save primary surface as BMP for debugging
static void SavePrimarySurfaceAsBMP(const char* filename) {
    if (!g_pPrimarySurface || !g_pPrimarySurface->pixelData) return;

    D3D7Surface* surf = g_pPrimarySurface;
    int width = surf->width;
    int height = surf->height;
    int bpp = surf->pixelFormat.dwRGBBitCount ? surf->pixelFormat.dwRGBBitCount / 8 : 4;

    // BMP header structures
    #pragma pack(push, 1)
    struct BMPHeader {
        uint16_t type;
        uint32_t size;
        uint16_t reserved1;
        uint16_t reserved2;
        uint32_t offset;
    };
    struct BMPInfoHeader {
        uint32_t size;
        int32_t width;
        int32_t height;
        uint16_t planes;
        uint16_t bitCount;
        uint32_t compression;
        uint32_t sizeImage;
        int32_t xPelsPerMeter;
        int32_t yPelsPerMeter;
        uint32_t clrUsed;
        uint32_t clrImportant;
    };
    #pragma pack(pop)

    FILE* f = fopen(filename, "wb");
    if (!f) return;

    int rowSize = ((width * 3 + 3) / 4) * 4;  // Padded to 4 bytes
    int imageSize = rowSize * height;

    BMPHeader header = { 0x4D42, (uint32_t)(54 + imageSize), 0, 0, 54 };
    BMPInfoHeader info = { 40, width, height, 1, 24, 0, (uint32_t)imageSize, 2835, 2835, 0, 0 };

    fwrite(&header, sizeof(header), 1, f);
    fwrite(&info, sizeof(info), 1, f);

    // Write pixel data (BMP is bottom-up, BGR format)
    unsigned char* row = new unsigned char[rowSize];
    for (int y = height - 1; y >= 0; y--) {
        memset(row, 0, rowSize);
        for (int x = 0; x < width; x++) {
            unsigned char* src = surf->pixelData + (y * surf->pitch) + (x * bpp);
            unsigned char* dst = row + (x * 3);
            if (bpp == 4) {
                dst[0] = src[0];  // B
                dst[1] = src[1];  // G
                dst[2] = src[2];  // R
            } else if (bpp == 2) {
                // 565 format
                uint16_t pixel = *(uint16_t*)src;
                dst[2] = ((pixel >> 11) & 0x1F) << 3;  // R
                dst[1] = ((pixel >> 5) & 0x3F) << 2;   // G
                dst[0] = (pixel & 0x1F) << 3;          // B
            }
        }
        fwrite(row, rowSize, 1, f);
    }
    delete[] row;
    fclose(f);
    fprintf(stderr, "[DEBUG] Saved screenshot to %s (%dx%d, %d bpp)\n", filename, width, height, bpp * 8);
}

// External function to ensure GL context is current (from main_linux.cpp)
extern void FF_AcquireGLContext();

// Present the primary surface to the screen via OpenGL
void FF_PresentPrimarySurface() {
    static int frameCount = 0;
    frameCount++;

    // Validate surface
    if (!g_pPrimarySurface || !g_pPrimarySurface->pixelData) {
        return;
    }

    D3D7Surface* surf = g_pPrimarySurface;

    // Validate surface dimensions
    if (surf->width <= 0 || surf->height <= 0 || surf->width > 4096 || surf->height > 4096) {
        return;
    }

    // Ensure GL context is current on this thread
    FF_AcquireGLContext();

    // Clear any pending GL errors
    while (glGetError() != GL_NO_ERROR) {}

    // FF_LINUX: Ensure we're rendering to the default framebuffer, not an FBO.
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    // FF_LINUX: Ensure viewport covers the full window for UI rendering.
    // The sim may have set a partial viewport (e.g., [0,183,1024,585] for 3D scene).
    glViewport(0, 0, surf->width, surf->height);

    // Create texture if needed
    if (!surf->glTexture) {
        glGenTextures(1, &surf->glTexture);
        GLenum err = glGetError();
        if (err != GL_NO_ERROR) {
            return;
        }
    }

    // Set up 2D orthographic projection
    glMatrixMode(GL_PROJECTION);
    glPushMatrix();
    glLoadIdentity();
    glOrtho(0, surf->width, surf->height, 0, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadIdentity();

    // Minimal state setup for 2D textured rendering
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_LIGHTING);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);
    glDisable(GL_ALPHA_TEST);
    glDisable(GL_STENCIL_TEST);
    glDisable(GL_FOG);

    // Enable texturing and bind the surface texture
    glActiveTexture(GL_TEXTURE0);
    glEnable(GL_TEXTURE_2D);
    // Reset texture environment to simple replace mode
    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);
    glBindTexture(GL_TEXTURE_2D, surf->glTexture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    // Upload surface data to texture (BGRA format, 32-bit)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surf->width, surf->height, 0,
                 GL_BGRA, GL_UNSIGNED_BYTE, surf->pixelData);

    // FF_LINUX: Skip glColor4f(1,1,1,1) which crashes in NVIDIA driver 535.x
    // after glTexImage2D. The default color state is white, which is correct
    // for drawing the textured UI surface at full brightness.
    // See: Known NVIDIA driver issue with immediate mode color after texture upload.

    // Draw fullscreen quad with texture
    glBegin(GL_QUADS);
        glTexCoord2f(0.0f, 0.0f); glVertex2f(0.0f, 0.0f);
        glTexCoord2f(1.0f, 0.0f); glVertex2f((float)surf->width, 0.0f);
        glTexCoord2f(1.0f, 1.0f); glVertex2f((float)surf->width, (float)surf->height);
        glTexCoord2f(0.0f, 1.0f); glVertex2f(0.0f, (float)surf->height);
    glEnd();

    glDisable(GL_TEXTURE_2D);

    // Restore matrices
    glMatrixMode(GL_MODELVIEW);
    glPopMatrix();
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();

    surf->isDirty = false;
}

// External flag: are we in UI mode? (defined in ui/src/winmain.cpp)
extern int doUI;
// Swap buffers via SDL (defined in main_linux.cpp)
extern void FF_SwapBuffers();

// FF_LINUX: Per-frame diagnostic summary and counter reset
// Called from ImageBuffer::SwapBuffers() on the sim swap path (which bypasses DDS7_Flip)
int g_SimFrameCount = 0;

// Forward declarations for GetHandle stats
extern "C" void FF_GetHandleStats(int* ok, int* lazy, int* noImage, int* createFail, int* release, int* invalid);
extern "C" void FF_GetHandleStatsReset();

void SaveGLFramebufferAsBMP(const char* filename) {
    GLint vp[4];
    glGetIntegerv(GL_VIEWPORT, vp);
    int w = vp[2], h = vp[3];
    if (w <= 0 || h <= 0) return;

    unsigned char* pixels = (unsigned char*)malloc(w * h * 3);
    if (!pixels) return;
    glReadPixels(0, 0, w, h, GL_BGR, GL_UNSIGNED_BYTE, pixels);

    #pragma pack(push, 1)
    struct { uint16_t type; uint32_t size; uint16_t r1, r2; uint32_t offset; } bh;
    struct { uint32_t size; int32_t w, h; uint16_t planes, bpp; uint32_t comp, imgsize, xppm, yppm, clr, imp; } bi;
    #pragma pack(pop)
    int rowBytes = (w * 3 + 3) & ~3;
    bh.type = 0x4D42; bh.size = 54 + rowBytes * h; bh.r1 = bh.r2 = 0; bh.offset = 54;
    bi.size = 40; bi.w = w; bi.h = h; bi.planes = 1; bi.bpp = 24;
    bi.comp = bi.xppm = bi.yppm = bi.clr = bi.imp = 0; bi.imgsize = rowBytes * h;

    FILE* f = fopen(filename, "wb");
    if (f) {
        fwrite(&bh, sizeof(bh), 1, f);
        fwrite(&bi, sizeof(bi), 1, f);
        // GL reads bottom-up which matches BMP format
        unsigned char* row = (unsigned char*)malloc(rowBytes);
        memset(row, 0, rowBytes);
        for (int y = 0; y < h; y++) {
            memcpy(row, pixels + y * w * 3, w * 3);
            fwrite(row, rowBytes, 1, f);
        }
        free(row);
        fclose(f);
        fprintf(stderr, "[Screenshot] Saved %dx%d framebuffer to %s\n", w, h, filename);
    }
    free(pixels);
}

void FF_SimFrameEnd() {
    g_SimFrameCount++;

    // Reset per-frame counters
    g_ClearCallCount = 0;
    g_SetTextureCount = 0;
    g_SetTextureWithData = 0;
    g_SetTextureNullCount = 0;
    g_SetTextureNoPixelCount = 0;
    g_SetTextureDirtyCount = 0;
    g_SetTextureCleanCount = 0;
    g_DrawVerticesCount = 0;
    g_DrawPrimitiveCount = 0;
    g_DrawPrimitiveVBCount = 0;
    g_DrawIdxPrimVBCount = 0;
    g_RHWDrawCount_local = 0;
    g_WorldDrawCount_local = 0;
}

static HRESULT STDMETHODCALLTYPE DDS7_Flip(IDirectDrawSurface7* This, IDirectDrawSurface7* lpDDSurfaceTargetOverride, DWORD dwFlags) {
    D3DGL_LOG("DDS7 Flip");

    D3D7Surface* surf = (D3D7Surface*)This;
    if (surf->isPrimary) {
        static int flipCount = 0;
        flipCount++;

        if (!doUI) {
            FF_SimFrameEnd();
            FF_SwapBuffers();

            // (framebuffer save removed - DDS7_Flip is not used in sim mode)
        }
        // In UI mode, FF_PresentPrimarySurface is called from render_frame() in main loop
    }

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetAttachedSurface(IDirectDrawSurface7* This, LPDDSCAPS2 lpDDSCaps, IDirectDrawSurface7** lplpDDAttachedSurface) {
    D3DGL_LOG("DDS7 GetAttachedSurface");
    if (!lplpDDAttachedSurface) return DDERR_INVALIDPARAMS;
    *lplpDDAttachedSurface = nullptr;
    return DDERR_NOTFOUND;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetBltStatus(IDirectDrawSurface7* This, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetCaps(IDirectDrawSurface7* This, LPDDSCAPS2 lpDDSCaps) {
    D3DGL_LOG("DDS7 GetCaps");
    if (!lpDDSCaps) return DDERR_INVALIDPARAMS;
    D3D7Surface* surf = (D3D7Surface*)This;
    lpDDSCaps->dwCaps = surf->caps;
    lpDDSCaps->dwCaps2 = 0;
    lpDDSCaps->dwCaps3 = 0;
    lpDDSCaps->dwCaps4 = 0;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetClipper(IDirectDrawSurface7* This, LPDIRECTDRAWCLIPPER* lplpDDClipper) {
    return DDERR_NOCLIPPERATTACHED;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetColorKey(IDirectDrawSurface7* This, DWORD dwFlags, LPDDCOLORKEY lpDDColorKey) {
    return DDERR_NOCOLORKEY;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetDC(IDirectDrawSurface7* This, HDC* lphDC) {
    return DDERR_GENERIC;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetFlipStatus(IDirectDrawSurface7* This, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetOverlayPosition(IDirectDrawSurface7* This, LPLONG lplX, LPLONG lplY) {
    return DDERR_NOTAOVERLAYSURFACE;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetPalette(IDirectDrawSurface7* This, LPDIRECTDRAWPALETTE* lplpDDPalette) {
    return DDERR_NOPALETTEATTACHED;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetPixelFormat(IDirectDrawSurface7* This, LPDDPIXELFORMAT lpDDPixelFormat) {
    D3DGL_LOG("DDS7 GetPixelFormat");
    if (!lpDDPixelFormat) return DDERR_INVALIDPARAMS;

    D3D7Surface* surf = (D3D7Surface*)This;

    // Return a standard 32-bit ARGB pixel format
    memset(lpDDPixelFormat, 0, sizeof(DDPIXELFORMAT));
    lpDDPixelFormat->dwSize = sizeof(DDPIXELFORMAT);
    lpDDPixelFormat->dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    lpDDPixelFormat->dwRGBBitCount = 32;
    lpDDPixelFormat->dwRBitMask = 0x00FF0000;
    lpDDPixelFormat->dwGBitMask = 0x0000FF00;
    lpDDPixelFormat->dwBBitMask = 0x000000FF;
    lpDDPixelFormat->dwRGBAlphaBitMask = 0xFF000000;

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetSurfaceDesc(IDirectDrawSurface7* This, LPDDSURFACEDESC2 lpDDSurfaceDesc) {
    D3DGL_LOG("DDS7 GetSurfaceDesc");
    if (!lpDDSurfaceDesc) return DDERR_INVALIDPARAMS;

    D3D7Surface* surf = (D3D7Surface*)This;

    // Calculate pitch if not already set (surface not yet locked)
    int effectivePitch = surf->pitch;
    if (effectivePitch == 0 && surf->width > 0 && surf->height > 0) {
        int bpp = surf->pixelFormat.dwRGBBitCount ? surf->pixelFormat.dwRGBBitCount / 8 : 4;
        effectivePitch = surf->width * bpp;
        // Align pitch to 4 bytes
        effectivePitch = (effectivePitch + 3) & ~3;
        // Store it so subsequent calls are consistent
        surf->pitch = effectivePitch;
    }

    memset(lpDDSurfaceDesc, 0, sizeof(DDSURFACEDESC2));
    lpDDSurfaceDesc->dwSize = sizeof(DDSURFACEDESC2);
    lpDDSurfaceDesc->dwFlags = DDSD_WIDTH | DDSD_HEIGHT | DDSD_CAPS | DDSD_PIXELFORMAT | DDSD_PITCH;
    lpDDSurfaceDesc->dwWidth = surf->width;
    lpDDSurfaceDesc->dwHeight = surf->height;
    lpDDSurfaceDesc->lPitch = effectivePitch;  // Return the surface pitch (bytes per row)
    lpDDSurfaceDesc->ddsCaps.dwCaps = surf->caps;

    // Pixel format
    lpDDSurfaceDesc->ddpfPixelFormat.dwSize = sizeof(DDPIXELFORMAT);
    lpDDSurfaceDesc->ddpfPixelFormat.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    lpDDSurfaceDesc->ddpfPixelFormat.dwRGBBitCount = 32;
    lpDDSurfaceDesc->ddpfPixelFormat.dwRBitMask = 0x00FF0000;
    lpDDSurfaceDesc->ddpfPixelFormat.dwGBitMask = 0x0000FF00;
    lpDDSurfaceDesc->ddpfPixelFormat.dwBBitMask = 0x000000FF;
    lpDDSurfaceDesc->ddpfPixelFormat.dwRGBAlphaBitMask = 0xFF000000;

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_Initialize(IDirectDrawSurface7* This, LPDIRECTDRAW lpDD, LPDDSURFACEDESC2 lpDDSurfaceDesc) {
    return DDERR_ALREADYINITIALIZED;
}

static HRESULT STDMETHODCALLTYPE DDS7_IsLost(IDirectDrawSurface7* This) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_Lock(IDirectDrawSurface7* This, LPRECT lpDestRect, LPDDSURFACEDESC2 lpDDSurfaceDesc, DWORD dwFlags, HANDLE hEvent) {
    D3DGL_LOG("DDS7 Lock %dx%d", ((D3D7Surface*)This)->width, ((D3D7Surface*)This)->height);

    if (!lpDDSurfaceDesc) return DDERR_INVALIDPARAMS;

    D3D7Surface* surf = (D3D7Surface*)This;

    if (surf->isLocked) return DDERR_SURFACEBUSY;

    // Allocate pixel buffer if needed
    surf->AllocatePixelBuffer();

    if (!surf->pixelData) return DDERR_OUTOFMEMORY;

    // Fill in the surface description
    memset(lpDDSurfaceDesc, 0, sizeof(DDSURFACEDESC2));
    lpDDSurfaceDesc->dwSize = sizeof(DDSURFACEDESC2);
    lpDDSurfaceDesc->dwFlags = DDSD_WIDTH | DDSD_HEIGHT | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_LPSURFACE;
    lpDDSurfaceDesc->dwWidth = surf->width;
    lpDDSurfaceDesc->dwHeight = surf->height;
    lpDDSurfaceDesc->lPitch = surf->pitch;
    lpDDSurfaceDesc->ddpfPixelFormat = surf->pixelFormat;

    // Calculate the starting pointer based on lpDestRect
    if (lpDestRect && surf->dxtFormat == 0) {
        int bpp = surf->pixelFormat.dwRGBBitCount ? surf->pixelFormat.dwRGBBitCount / 8 : 4;
        lpDDSurfaceDesc->lpSurface = surf->pixelData + (lpDestRect->top * surf->pitch) + (lpDestRect->left * bpp);
    } else {
        // For DXT surfaces or no rect, just return the base pointer
        lpDDSurfaceDesc->lpSurface = surf->pixelData;
    }

    surf->isLocked = true;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_ReleaseDC(IDirectDrawSurface7* This, HDC hDC) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_Restore(IDirectDrawSurface7* This) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetClipper(IDirectDrawSurface7* This, LPDIRECTDRAWCLIPPER lpDDClipper) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetColorKey(IDirectDrawSurface7* This, DWORD dwFlags, LPDDCOLORKEY lpDDColorKey) {
    D3D7Surface* surf = (D3D7Surface*)This;
    if (lpDDColorKey && (dwFlags & DDCKEY_SRCBLT)) {
        surf->hasColorKey = true;
        surf->colorKeyLow = lpDDColorKey->dwColorSpaceLowValue;
        surf->isDirty = true;  // Force re-upload with alpha modification
    }
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetOverlayPosition(IDirectDrawSurface7* This, LONG lX, LONG lY) {
    return DDERR_NOTAOVERLAYSURFACE;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetPalette(IDirectDrawSurface7* This, LPDIRECTDRAWPALETTE lpDDPalette) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_Unlock(IDirectDrawSurface7* This, LPRECT lpRect) {
    D3DGL_LOG("DDS7 Unlock");

    D3D7Surface* surf = (D3D7Surface*)This;
    surf->isLocked = false;
    surf->isDirty = true;  // Mark for texture upload on next use
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_UpdateOverlay(IDirectDrawSurface7* This, LPRECT lpSrcRect, IDirectDrawSurface7* lpDDDestSurface, LPRECT lpDestRect, DWORD dwFlags, LPDDOVERLAYFX lpDDOverlayFx) {
    return DDERR_NOTAOVERLAYSURFACE;
}

static HRESULT STDMETHODCALLTYPE DDS7_UpdateOverlayDisplay(IDirectDrawSurface7* This, DWORD dwFlags) {
    return DDERR_NOTAOVERLAYSURFACE;
}

static HRESULT STDMETHODCALLTYPE DDS7_UpdateOverlayZOrder(IDirectDrawSurface7* This, DWORD dwFlags, IDirectDrawSurface7* lpDDSReference) {
    return DDERR_NOTAOVERLAYSURFACE;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetDDInterface(IDirectDrawSurface7* This, LPVOID* lplpDD) {
    D3DGL_LOG("DDS7 GetDDInterface");
    // This is called to get the IDirectDraw7 interface from a surface
    // Return our global DD interface
    extern IDirectDraw7* g_pGlobalDD7;
    if (lplpDD && g_pGlobalDD7) {
        *lplpDD = g_pGlobalDD7;
        g_pGlobalDD7->lpVtbl->AddRef(g_pGlobalDD7);
        return DD_OK;
    }
    return DDERR_GENERIC;
}

static HRESULT STDMETHODCALLTYPE DDS7_PageLock(IDirectDrawSurface7* This, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_PageUnlock(IDirectDrawSurface7* This, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetSurfaceDesc(IDirectDrawSurface7* This, LPDDSURFACEDESC2 lpDDsd2, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetPrivateData(IDirectDrawSurface7* This, REFGUID guidTag, LPVOID lpData, DWORD cbSize, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetPrivateData(IDirectDrawSurface7* This, REFGUID guidTag, LPVOID lpBuffer, LPDWORD lpcbBufferSize) {
    return DDERR_NOTFOUND;
}

static HRESULT STDMETHODCALLTYPE DDS7_FreePrivateData(IDirectDrawSurface7* This, REFGUID guidTag) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetUniquenessValue(IDirectDrawSurface7* This, LPDWORD lpValue) {
    if (lpValue) *lpValue = 1;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_ChangeUniquenessValue(IDirectDrawSurface7* This) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetPriority(IDirectDrawSurface7* This, DWORD dwPriority) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetPriority(IDirectDrawSurface7* This, LPDWORD lpdwPriority) {
    if (lpdwPriority) *lpdwPriority = 0;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_SetLOD(IDirectDrawSurface7* This, DWORD dwMaxLOD) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDS7_GetLOD(IDirectDrawSurface7* This, LPDWORD lpdwMaxLOD) {
    if (lpdwMaxLOD) *lpdwMaxLOD = 0;
    return DD_OK;
}

const IDirectDrawSurface7Vtbl g_DDS7Vtbl = {
    DDS7_QueryInterface,
    DDS7_AddRef,
    DDS7_Release,
    DDS7_AddAttachedSurface,
    DDS7_AddOverlayDirtyRect,
    DDS7_Blt,
    DDS7_BltBatch,
    DDS7_BltFast,
    DDS7_DeleteAttachedSurface,
    DDS7_EnumAttachedSurfaces,
    DDS7_EnumOverlayZOrders,
    DDS7_Flip,
    DDS7_GetAttachedSurface,
    DDS7_GetBltStatus,
    DDS7_GetCaps,
    DDS7_GetClipper,
    DDS7_GetColorKey,
    DDS7_GetDC,
    DDS7_GetFlipStatus,
    DDS7_GetOverlayPosition,
    DDS7_GetPalette,
    DDS7_GetPixelFormat,
    DDS7_GetSurfaceDesc,
    DDS7_Initialize,
    DDS7_IsLost,
    DDS7_Lock,
    DDS7_ReleaseDC,
    DDS7_Restore,
    DDS7_SetClipper,
    DDS7_SetColorKey,
    DDS7_SetOverlayPosition,
    DDS7_SetPalette,
    DDS7_Unlock,
    DDS7_UpdateOverlay,
    DDS7_UpdateOverlayDisplay,
    DDS7_UpdateOverlayZOrder,
    DDS7_GetDDInterface,
    DDS7_PageLock,
    DDS7_PageUnlock,
    DDS7_SetSurfaceDesc,
    DDS7_SetPrivateData,
    DDS7_GetPrivateData,
    DDS7_FreePrivateData,
    DDS7_GetUniquenessValue,
    DDS7_ChangeUniquenessValue,
    DDS7_SetPriority,
    DDS7_GetPriority,
    DDS7_SetLOD,
    DDS7_GetLOD
};

// ============================================================
// IDirectDraw7 implementation
// ============================================================
struct DD7Interface : public IDirectDraw7 {
    LONG refCount;
    int displayWidth;
    int displayHeight;
    int displayBpp;
    D3D7Interface* d3d7;  // Cached D3D7 interface

    DD7Interface() : refCount(1), displayWidth(1024), displayHeight(768), displayBpp(32), d3d7(nullptr) {}
};

// Global DD7 interface for GetDDInterface calls
IDirectDraw7* g_pGlobalDD7 = nullptr;

static HRESULT STDMETHODCALLTYPE DD7_QueryInterface(IDirectDraw7* This, REFIID riid, void** ppvObject) {
    D3DGL_LOG("DD7 QueryInterface");
    if (!ppvObject) return E_POINTER;

    DD7Interface* dd = (DD7Interface*)This;

    // Check if IDirect3D7 interface is being requested
    if (IsEqualIID(riid, IID_IDirect3D7)) {
        // Create a D3D7 interface if we don't have one cached
        if (!dd->d3d7) {
            D3D7Interface* d3d7 = new D3D7Interface();
            d3d7->lpVtbl = &g_D3D7Vtbl;
            d3d7->dd7 = dd;
            dd->d3d7 = d3d7;
        }
        *ppvObject = dd->d3d7;
        dd->d3d7->lpVtbl->AddRef((IDirect3D7*)dd->d3d7);
        return S_OK;
    }

    // Default: return this
    *ppvObject = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE DD7_AddRef(IDirectDraw7* This) {
    DD7Interface* dd = (DD7Interface*)This;
    return ++dd->refCount;
}

static ULONG STDMETHODCALLTYPE DD7_Release(IDirectDraw7* This) {
    DD7Interface* dd = (DD7Interface*)This;
    LONG ref = --dd->refCount;
    if (ref <= 0) {
        if (g_pGlobalDD7 == This) g_pGlobalDD7 = nullptr;
        if (dd->d3d7) {
            delete dd->d3d7;
            dd->d3d7 = nullptr;
        }
        delete dd;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE DD7_Compact(IDirectDraw7* This) { return DD_OK; }

// ============================================================
// IDirectDrawClipper implementation
// ============================================================
struct DDClipperImpl : public IDirectDrawClipper {
    LONG refCount;
    HWND hWnd;

    DDClipperImpl() : refCount(1), hWnd(nullptr) {}
};

static HRESULT STDMETHODCALLTYPE DDClipper_QueryInterface(IDirectDrawClipper* This, REFIID riid, LPVOID* ppvObj) {
    if (!ppvObj) return E_POINTER;
    *ppvObj = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE DDClipper_AddRef(IDirectDrawClipper* This) {
    DDClipperImpl* clip = (DDClipperImpl*)This;
    return ++clip->refCount;
}

static ULONG STDMETHODCALLTYPE DDClipper_Release(IDirectDrawClipper* This) {
    DDClipperImpl* clip = (DDClipperImpl*)This;
    LONG ref = --clip->refCount;
    if (ref <= 0) {
        delete clip;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE DDClipper_GetClipList(IDirectDrawClipper* This, LPRECT lpRect, LPVOID lpClipList, LPDWORD lpdwSize) {
    return DDERR_GENERIC;
}

static HRESULT STDMETHODCALLTYPE DDClipper_GetHWnd(IDirectDrawClipper* This, HWND* lphWnd) {
    if (!lphWnd) return DDERR_INVALIDPARAMS;
    DDClipperImpl* clip = (DDClipperImpl*)This;
    *lphWnd = clip->hWnd;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDClipper_Initialize(IDirectDrawClipper* This, LPDIRECTDRAW lpDD, DWORD dwFlags) {
    return DDERR_ALREADYINITIALIZED;
}

static HRESULT STDMETHODCALLTYPE DDClipper_IsClipListChanged(IDirectDrawClipper* This, LPBOOL lpbChanged) {
    if (!lpbChanged) return DDERR_INVALIDPARAMS;
    *lpbChanged = FALSE;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDClipper_SetClipList(IDirectDrawClipper* This, LPVOID lpClipList, DWORD dwFlags) {
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDClipper_SetHWnd(IDirectDrawClipper* This, DWORD dwFlags, HWND hWnd) {
    (void)dwFlags;
    DDClipperImpl* clip = (DDClipperImpl*)This;
    clip->hWnd = hWnd;
    return DD_OK;
}

static const IDirectDrawClipperVtbl g_DDClipperVtbl = {
    DDClipper_QueryInterface,
    DDClipper_AddRef,
    DDClipper_Release,
    DDClipper_GetClipList,
    DDClipper_GetHWnd,
    DDClipper_Initialize,
    DDClipper_IsClipListChanged,
    DDClipper_SetClipList,
    DDClipper_SetHWnd
};

static HRESULT STDMETHODCALLTYPE DD7_CreateClipper(IDirectDraw7* This, DWORD dwFlags, LPDIRECTDRAWCLIPPER* lplpDDClipper, IUnknown* pUnkOuter) {
    D3DGL_LOG("DD7_CreateClipper");
    if (!lplpDDClipper) return DDERR_INVALIDPARAMS;

    DDClipperImpl* clip = new DDClipperImpl();
    clip->lpVtbl = const_cast<IDirectDrawClipperVtbl*>(&g_DDClipperVtbl);
    *lplpDDClipper = clip;
    return DD_OK;
}

// ============================================================================
// IDirectDrawPalette implementation
// ============================================================================

struct DDPaletteImpl : public IDirectDrawPalette {
    LONG refCount;
    DWORD flags;
    PALETTEENTRY entries[256];

    DDPaletteImpl(DWORD f) : refCount(1), flags(f) {
        memset(entries, 0, sizeof(entries));
    }
};

static HRESULT STDMETHODCALLTYPE DDPalette_QueryInterface(IDirectDrawPalette* This, REFIID riid, LPVOID* ppvObj) {
    if (!ppvObj) return E_POINTER;
    *ppvObj = This;
    This->lpVtbl->AddRef(This);
    return S_OK;
}

static ULONG STDMETHODCALLTYPE DDPalette_AddRef(IDirectDrawPalette* This) {
    DDPaletteImpl* pal = (DDPaletteImpl*)This;
    return ++pal->refCount;
}

static ULONG STDMETHODCALLTYPE DDPalette_Release(IDirectDrawPalette* This) {
    DDPaletteImpl* pal = (DDPaletteImpl*)This;
    LONG ref = --pal->refCount;
    if (ref <= 0) {
        delete pal;
    }
    return ref;
}

static HRESULT STDMETHODCALLTYPE DDPalette_GetCaps(IDirectDrawPalette* This, LPDWORD lpdwCaps) {
    if (!lpdwCaps) return DDERR_INVALIDPARAMS;
    DDPaletteImpl* pal = (DDPaletteImpl*)This;
    *lpdwCaps = pal->flags;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDPalette_GetEntries(IDirectDrawPalette* This, DWORD dwFlags, DWORD dwBase, DWORD dwNumEntries, LPPALETTEENTRY lpEntries) {
    if (!lpEntries) return DDERR_INVALIDPARAMS;
    DDPaletteImpl* pal = (DDPaletteImpl*)This;
    if (dwBase + dwNumEntries > 256) return DDERR_INVALIDPARAMS;
    memcpy(lpEntries, &pal->entries[dwBase], dwNumEntries * sizeof(PALETTEENTRY));
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DDPalette_Initialize(IDirectDrawPalette* This, LPDIRECTDRAW lpDD, DWORD dwFlags, LPPALETTEENTRY lpDDColorTable) {
    return DDERR_ALREADYINITIALIZED;
}

static HRESULT STDMETHODCALLTYPE DDPalette_SetEntries(IDirectDrawPalette* This, DWORD dwFlags, DWORD dwStartingEntry, DWORD dwCount, LPPALETTEENTRY lpEntries) {
    if (!lpEntries) return DDERR_INVALIDPARAMS;
    DDPaletteImpl* pal = (DDPaletteImpl*)This;
    if (dwStartingEntry + dwCount > 256) return DDERR_INVALIDPARAMS;
    memcpy(&pal->entries[dwStartingEntry], lpEntries, dwCount * sizeof(PALETTEENTRY));
    return DD_OK;
}

static const IDirectDrawPaletteVtbl g_DDPaletteVtbl = {
    DDPalette_QueryInterface,
    DDPalette_AddRef,
    DDPalette_Release,
    DDPalette_GetCaps,
    DDPalette_GetEntries,
    DDPalette_Initialize,
    DDPalette_SetEntries
};

static HRESULT STDMETHODCALLTYPE DD7_CreatePalette(IDirectDraw7* This, DWORD dwFlags, LPPALETTEENTRY lpDDColorArray, LPDIRECTDRAWPALETTE* lplpDDPalette, IUnknown* pUnkOuter) {
    if (!lplpDDPalette) return DDERR_INVALIDPARAMS;

    DDPaletteImpl* pal = new DDPaletteImpl(dwFlags);
    pal->lpVtbl = const_cast<IDirectDrawPaletteVtbl*>(&g_DDPaletteVtbl);

    // Copy initial palette entries if provided
    if (lpDDColorArray) {
        DWORD numEntries = 256;
        if (dwFlags & DDPCAPS_4BIT) numEntries = 16;
        else if (dwFlags & DDPCAPS_1BIT) numEntries = 2;
        memcpy(pal->entries, lpDDColorArray, numEntries * sizeof(PALETTEENTRY));
    }

    *lplpDDPalette = pal;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DD7_CreateSurface(IDirectDraw7* This, LPDDSURFACEDESC2 lpDDSurfaceDesc, IDirectDrawSurface7** lplpDDSurface, IUnknown* pUnkOuter) {
    D3DGL_LOG("DD7 CreateSurface %dx%d", lpDDSurfaceDesc ? lpDDSurfaceDesc->dwWidth : 0, lpDDSurfaceDesc ? lpDDSurfaceDesc->dwHeight : 0);

    if (!lpDDSurfaceDesc || !lplpDDSurface) {
        return DDERR_INVALIDPARAMS;
    }

    D3D7Surface* surf = new D3D7Surface();
    // Constructor already sets lpVtbl, but set it again for safety
    surf->lpVtbl = const_cast<IDirectDrawSurface7Vtbl*>(&g_DDS7Vtbl);
    surf->caps = lpDDSurfaceDesc->ddsCaps.dwCaps;

    // For primary surfaces, use the display mode dimensions (not the desc which may be 0x0)
    if (surf->caps & DDSCAPS_PRIMARYSURFACE) {
        DD7Interface* dd = (DD7Interface*)This;
        surf->width = dd->displayWidth;
        surf->height = dd->displayHeight;
    } else {
        surf->width = lpDDSurfaceDesc->dwWidth;
        surf->height = lpDDSurfaceDesc->dwHeight;
    }

    // Copy pixel format if provided
    if (lpDDSurfaceDesc->dwFlags & DDSD_PIXELFORMAT) {
        surf->pixelFormat = lpDDSurfaceDesc->ddpfPixelFormat;

        // FF_LINUX: Detect DXT compressed texture format from FOURCC
        if (surf->pixelFormat.dwFlags & DDPF_FOURCC) {
            DWORD fcc = surf->pixelFormat.dwFourCC;
            if (fcc == MAKEFOURCC('D','X','T','1')) {
                surf->dxtFormat = GL_COMPRESSED_RGB_S3TC_DXT1_EXT;
            } else if (fcc == MAKEFOURCC('D','X','T','3')) {
                surf->dxtFormat = GL_COMPRESSED_RGBA_S3TC_DXT3_EXT;
            } else if (fcc == MAKEFOURCC('D','X','T','5')) {
                surf->dxtFormat = GL_COMPRESSED_RGBA_S3TC_DXT5_EXT;
            }
        }
    } else {
        // Default to 32-bit ARGB
        surf->pixelFormat.dwSize = sizeof(DDPIXELFORMAT);
        surf->pixelFormat.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
        surf->pixelFormat.dwRGBBitCount = 32;
        surf->pixelFormat.dwRBitMask = 0x00FF0000;
        surf->pixelFormat.dwGBitMask = 0x0000FF00;
        surf->pixelFormat.dwBBitMask = 0x000000FF;
        surf->pixelFormat.dwRGBAlphaBitMask = 0xFF000000;
    }

    // Track primary surface for screen presentation
    if (surf->caps & DDSCAPS_PRIMARYSURFACE) {
        surf->isPrimary = true;
        g_pPrimarySurface = surf;
        // Pre-allocate pixel buffer for primary surface
        surf->AllocatePixelBuffer();
    }

    // Create OpenGL texture if this is a texture surface
    if (surf->caps & DDSCAPS_TEXTURE) {
        glGenTextures(1, &surf->glTexture);
        glBindTexture(GL_TEXTURE_2D, surf->glTexture);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);

        // Allocate initial texture storage
        if (surf->dxtFormat == 0) {
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surf->width, surf->height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        } else {
            // FF_LINUX: Pre-allocate compressed texture storage with zeros.
            // This ensures the GL texture has valid dimensions even before the first
            // data upload, preventing undefined behavior if it's used before upload.
            surf->AllocatePixelBuffer();
            if (surf->pixelData && surf->dxtDataSize > 0) {
                glCompressedTexImage2D(GL_TEXTURE_2D, 0, surf->dxtFormat,
                                       surf->width, surf->height, 0,
                                       surf->dxtDataSize, surf->pixelData);
            }
        }
    }

    *lplpDDSurface = surf;
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DD7_DuplicateSurface(IDirectDraw7* This, IDirectDrawSurface7* lpDDSurface, IDirectDrawSurface7** lplpDupDDSurface) { return DDERR_GENERIC; }

static HRESULT STDMETHODCALLTYPE DD7_EnumDisplayModes(IDirectDraw7* This, DWORD dwFlags, LPDDSURFACEDESC2 lpDDSurfaceDesc, LPVOID lpContext, LPDDENUMMODESCALLBACK2 lpEnumModesCallback) {
    D3DGL_LOG("DD7 EnumDisplayModes");
    if (!lpEnumModesCallback) return DD_OK;

    // Common display modes that FreeFalcon might use
    struct DisplayMode {
        DWORD width;
        DWORD height;
        DWORD bpp;
    };

    static const DisplayMode modes[] = {
        { 640, 480, 16 },
        { 640, 480, 32 },
        { 800, 600, 16 },
        { 800, 600, 32 },
        { 1024, 768, 16 },
        { 1024, 768, 32 },
        { 1280, 1024, 16 },
        { 1280, 1024, 32 },
        { 1920, 1080, 16 },
        { 1920, 1080, 32 },
    };

    for (const auto& mode : modes) {
        DDSURFACEDESC2 ddsd;
        memset(&ddsd, 0, sizeof(ddsd));
        ddsd.dwSize = sizeof(ddsd);
        ddsd.dwFlags = DDSD_WIDTH | DDSD_HEIGHT | DDSD_PIXELFORMAT | DDSD_PITCH;
        ddsd.dwWidth = mode.width;
        ddsd.dwHeight = mode.height;
        ddsd.lPitch = mode.width * (mode.bpp / 8);

        ddsd.ddpfPixelFormat.dwSize = sizeof(DDPIXELFORMAT);
        ddsd.ddpfPixelFormat.dwFlags = DDPF_RGB;
        ddsd.ddpfPixelFormat.dwRGBBitCount = mode.bpp;

        if (mode.bpp == 16) {
            // 565 format
            ddsd.ddpfPixelFormat.dwRBitMask = 0xF800;
            ddsd.ddpfPixelFormat.dwGBitMask = 0x07E0;
            ddsd.ddpfPixelFormat.dwBBitMask = 0x001F;
        } else {
            // 32-bit ARGB
            ddsd.ddpfPixelFormat.dwFlags |= DDPF_ALPHAPIXELS;
            ddsd.ddpfPixelFormat.dwRBitMask = 0x00FF0000;
            ddsd.ddpfPixelFormat.dwGBitMask = 0x0000FF00;
            ddsd.ddpfPixelFormat.dwBBitMask = 0x000000FF;
            ddsd.ddpfPixelFormat.dwRGBAlphaBitMask = 0xFF000000;
        }

        if (lpEnumModesCallback(&ddsd, lpContext) == DDENUMRET_CANCEL) {
            break;
        }
    }

    return DD_OK;
}
static HRESULT STDMETHODCALLTYPE DD7_EnumSurfaces(IDirectDraw7* This, DWORD dwFlags, LPDDSURFACEDESC2 lpDDSD, LPVOID lpContext, LPDDENUMSURFACESCALLBACK7 lpEnumSurfacesCallback) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_FlipToGDISurface(IDirectDraw7* This) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_GetCaps(IDirectDraw7* This, LPDDCAPS lpDDDriverCaps, LPDDCAPS lpDDHELCaps) {
    D3DGL_LOG("DD7 GetCaps");
    if (lpDDDriverCaps) {
        memset(lpDDDriverCaps, 0, sizeof(DDCAPS));
        lpDDDriverCaps->dwSize = sizeof(DDCAPS);
        lpDDDriverCaps->dwCaps = DDCAPS_3D | DDCAPS_BLT | DDCAPS_BLTCOLORFILL;
        lpDDDriverCaps->dwCaps2 = DDCAPS2_CANRENDERWINDOWED;
        lpDDDriverCaps->ddsCaps.dwCaps = DDSCAPS_3DDEVICE | DDSCAPS_TEXTURE | DDSCAPS_ZBUFFER;
    }
    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DD7_GetDisplayMode(IDirectDraw7* This, LPDDSURFACEDESC2 lpDDSurfaceDesc) {
    D3DGL_LOG("DD7 GetDisplayMode");
    if (!lpDDSurfaceDesc) return DDERR_INVALIDPARAMS;

    DD7Interface* dd = (DD7Interface*)This;

    memset(lpDDSurfaceDesc, 0, sizeof(DDSURFACEDESC2));
    lpDDSurfaceDesc->dwSize = sizeof(DDSURFACEDESC2);
    lpDDSurfaceDesc->dwFlags = DDSD_WIDTH | DDSD_HEIGHT | DDSD_PIXELFORMAT;
    lpDDSurfaceDesc->dwWidth = dd->displayWidth;
    lpDDSurfaceDesc->dwHeight = dd->displayHeight;
    lpDDSurfaceDesc->ddpfPixelFormat.dwSize = sizeof(DDPIXELFORMAT);
    lpDDSurfaceDesc->ddpfPixelFormat.dwFlags = DDPF_RGB;
    lpDDSurfaceDesc->ddpfPixelFormat.dwRGBBitCount = dd->displayBpp;
    lpDDSurfaceDesc->ddpfPixelFormat.dwRBitMask = 0x00FF0000;
    lpDDSurfaceDesc->ddpfPixelFormat.dwGBitMask = 0x0000FF00;
    lpDDSurfaceDesc->ddpfPixelFormat.dwBBitMask = 0x000000FF;

    return DD_OK;
}

static HRESULT STDMETHODCALLTYPE DD7_GetFourCCCodes(IDirectDraw7* This, LPDWORD lpNumCodes, LPDWORD lpCodes) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_GetGDISurface(IDirectDraw7* This, IDirectDrawSurface7** lplpGDIDDSSurface) { return DDERR_GENERIC; }
static HRESULT STDMETHODCALLTYPE DD7_GetMonitorFrequency(IDirectDraw7* This, LPDWORD lpdwFrequency) { if(lpdwFrequency) *lpdwFrequency = 60; return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_GetScanLine(IDirectDraw7* This, LPDWORD lpdwScanLine) { return DDERR_GENERIC; }
static HRESULT STDMETHODCALLTYPE DD7_GetVerticalBlankStatus(IDirectDraw7* This, LPBOOL lpbIsInVB) { if(lpbIsInVB) *lpbIsInVB = FALSE; return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_Initialize(IDirectDraw7* This, GUID* lpGUID) { return DDERR_ALREADYINITIALIZED; }
static HRESULT STDMETHODCALLTYPE DD7_RestoreDisplayMode(IDirectDraw7* This) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_SetCooperativeLevel(IDirectDraw7* This, HWND hWnd, DWORD dwFlags) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_SetDisplayMode(IDirectDraw7* This, DWORD dwWidth, DWORD dwHeight, DWORD dwBPP, DWORD dwRefreshRate, DWORD dwFlags) {
    D3DGL_LOG("DD7_SetDisplayMode %dx%d @ %d bpp", dwWidth, dwHeight, dwBPP);
    DD7Interface* dd = (DD7Interface*)This;
    dd->displayWidth = dwWidth;
    dd->displayHeight = dwHeight;
    dd->displayBpp = dwBPP;

    // If primary surface already exists, we need to resize it
    if (g_pPrimarySurface) {
        g_pPrimarySurface->width = dwWidth;
        g_pPrimarySurface->height = dwHeight;
        // Reallocate pixel buffer
        if (g_pPrimarySurface->pixelData) {
            delete[] g_pPrimarySurface->pixelData;
            g_pPrimarySurface->pixelData = nullptr;
        }
        g_pPrimarySurface->AllocatePixelBuffer();
    }

    return DD_OK;
}
static HRESULT STDMETHODCALLTYPE DD7_WaitForVerticalBlank(IDirectDraw7* This, DWORD dwFlags, HANDLE hEvent) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_GetAvailableVidMem(IDirectDraw7* This, LPDDSCAPS2 lpDDSCaps2, LPDWORD lpdwTotal, LPDWORD lpdwFree) {
    if(lpdwTotal) *lpdwTotal = 256*1024*1024;
    if(lpdwFree) *lpdwFree = 128*1024*1024;
    return DD_OK;
}
static HRESULT STDMETHODCALLTYPE DD7_GetSurfaceFromDC(IDirectDraw7* This, HDC hdc, IDirectDrawSurface7** lpDDS) { return DDERR_GENERIC; }
static HRESULT STDMETHODCALLTYPE DD7_RestoreAllSurfaces(IDirectDraw7* This) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_TestCooperativeLevel(IDirectDraw7* This) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_GetDeviceIdentifier(IDirectDraw7* This, LPDDDEVICEIDENTIFIER2 lpdddi, DWORD dwFlags) {
    D3DGL_LOG("DD7 GetDeviceIdentifier");
    if (!lpdddi) return DDERR_INVALIDPARAMS;
    memset(lpdddi, 0, sizeof(DDDEVICEIDENTIFIER2));
    strcpy(lpdddi->szDriver, "OpenGL");
    strcpy(lpdddi->szDescription, "FreeFalcon OpenGL Renderer");
    lpdddi->dwVendorId = 0x10DE; // NVIDIA
    lpdddi->dwDeviceId = 0x1234;
    return DD_OK;
}
static HRESULT STDMETHODCALLTYPE DD7_StartModeTest(IDirectDraw7* This, LPSIZE lpModesToTest, DWORD dwNumEntries, DWORD dwFlags) { return DD_OK; }
static HRESULT STDMETHODCALLTYPE DD7_EvaluateMode(IDirectDraw7* This, DWORD dwFlags, DWORD* pSecondsUntilTimeout) { return DD_OK; }

static const IDirectDraw7Vtbl g_DD7Vtbl = {
    DD7_QueryInterface,
    DD7_AddRef,
    DD7_Release,
    DD7_Compact,
    DD7_CreateClipper,
    DD7_CreatePalette,
    DD7_CreateSurface,
    DD7_DuplicateSurface,
    DD7_EnumDisplayModes,
    DD7_EnumSurfaces,
    DD7_FlipToGDISurface,
    DD7_GetCaps,
    DD7_GetDisplayMode,
    DD7_GetFourCCCodes,
    DD7_GetGDISurface,
    DD7_GetMonitorFrequency,
    DD7_GetScanLine,
    DD7_GetVerticalBlankStatus,
    DD7_Initialize,
    DD7_RestoreDisplayMode,
    DD7_SetCooperativeLevel,
    DD7_SetDisplayMode,
    DD7_WaitForVerticalBlank,
    DD7_GetAvailableVidMem,
    DD7_GetSurfaceFromDC,
    DD7_RestoreAllSurfaces,
    DD7_TestCooperativeLevel,
    DD7_GetDeviceIdentifier,
    DD7_StartModeTest,
    DD7_EvaluateMode
};

// ============================================================
// Factory functions - exported for use by main_linux.cpp
// ============================================================
#include "graphics/include/context.h"

extern "C" {

IDirect3D7* FF_CreateDirect3D7(void) {
    printf("[D3DGL] Creating Direct3D7 interface\n");
    D3D7Interface* d3d = new D3D7Interface();
    d3d->lpVtbl = &g_D3D7Vtbl;
    return d3d;
}

IDirect3DDevice7* FF_CreateDirect3DDevice7(IDirect3D7* d3d, IDirectDrawSurface7* renderTarget) {
    printf("[D3DGL] Creating Direct3DDevice7 interface\n");

    D3D7Device* dev = new D3D7Device();
    dev->d3d = (D3D7Interface*)d3d;
    if (dev->d3d) dev->d3d->lpVtbl->AddRef(dev->d3d);
    dev->renderTarget = (D3D7Surface*)renderTarget;
    dev->defaultRenderTarget = (D3D7Surface*)renderTarget;  // FF_LINUX: Track initial RT for FBO unbinding

    // Assign the vtable to the render target if it doesn't have one
    if (renderTarget && !renderTarget->lpVtbl) {
        ((D3D7Surface*)renderTarget)->lpVtbl = &g_DDS7Vtbl;
    }

    // Set up default OpenGL state
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
#ifdef FF_LINUX
    glFrontFace(GL_CW);   // FF_LINUX: Default cull is D3DCULL_CW; Flip matrix reverses winding
#else
    glFrontFace(GL_CCW);
#endif
    glShadeModel(GL_SMOOTH);

    return dev;
}

IDirectDraw7* FF_CreateDirectDraw7(void) {
    printf("[D3DGL] Creating DirectDraw7 interface\n");
    DD7Interface* dd = new DD7Interface();
    dd->lpVtbl = &g_DD7Vtbl;
    g_pGlobalDD7 = dd;
    return dd;
}

IDirectDrawSurface7* FF_CreateRenderTargetSurface(int width, int height) {
    printf("[D3DGL] Creating render target surface %dx%d\n", width, height);

    D3D7Surface* surf = new D3D7Surface();
    surf->lpVtbl = &g_DDS7Vtbl;
    surf->width = width;
    surf->height = height;
    surf->caps = DDSCAPS_PRIMARYSURFACE | DDSCAPS_3DDEVICE;

    // Set up default pixel format for the render target
    surf->pixelFormat.dwSize = sizeof(DDPIXELFORMAT);
    surf->pixelFormat.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS;
    surf->pixelFormat.dwRGBBitCount = 32;
    surf->pixelFormat.dwRBitMask = 0x00FF0000;
    surf->pixelFormat.dwGBitMask = 0x0000FF00;
    surf->pixelFormat.dwBBitMask = 0x000000FF;
    surf->pixelFormat.dwRGBAlphaBitMask = 0xFF000000;

    return surf;
}

// Create and initialize a DXContext for Linux (OpenGL backend)
DXContext* FF_CreateDXContext(int width, int height, IDirect3D7* d3d, IDirect3DDevice7* d3dDevice, IDirectDraw7* dd) {
    printf("[D3DGL] Creating DXContext for Linux (%dx%d)\n", width, height);

    DXContext* ctx = new DXContext();

    // Set the D3D interfaces
    ctx->m_pDD = dd;
    ctx->m_pD3D = d3d;
    ctx->m_pD3DD = d3dDevice;
    ctx->m_nWidth = width;
    ctx->m_nHeight = height;
    ctx->m_bFullscreen = false;
    ctx->m_hWnd = nullptr;

    // Set device category to hardware (OpenGL is hardware accelerated)
    ctx->m_eDeviceCategory = DXContext::D3DDeviceCategory_Hardware;

    // Initialize device caps - these will be allocated by DXContext constructor
    if (ctx->m_pcapsDD) {
        memset(ctx->m_pcapsDD, 0, sizeof(DDCAPS));
        ctx->m_pcapsDD->dwSize = sizeof(DDCAPS);
        ctx->m_pcapsDD->dwCaps = DDCAPS_3D | DDCAPS_BLT | DDCAPS_BLTCOLORFILL;
        ctx->m_pcapsDD->dwCaps2 = DDCAPS2_CANRENDERWINDOWED;
        ctx->m_pcapsDD->ddsCaps.dwCaps = DDSCAPS_3DDEVICE | DDSCAPS_TEXTURE | DDSCAPS_ZBUFFER | DDSCAPS_MIPMAP;
    }

    // Initialize D3D device caps
    if (ctx->m_pD3DHWDeviceDesc) {
        memset(ctx->m_pD3DHWDeviceDesc, 0, sizeof(D3DDEVICEDESC7));

        // Triangle caps
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwSize = sizeof(D3DPRIMCAPS);
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwMiscCaps = D3DPMISCCAPS_CULLNONE | D3DPMISCCAPS_CULLCW | D3DPMISCCAPS_CULLCCW;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwRasterCaps = D3DPRASTERCAPS_DITHER | D3DPRASTERCAPS_ZTEST |
            D3DPRASTERCAPS_FOGVERTEX | D3DPRASTERCAPS_FOGTABLE | D3DPRASTERCAPS_MIPMAPLODBIAS;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwZCmpCaps = D3DPCMPCAPS_ALWAYS | D3DPCMPCAPS_LESS | D3DPCMPCAPS_LESSEQUAL |
            D3DPCMPCAPS_EQUAL | D3DPCMPCAPS_GREATEREQUAL | D3DPCMPCAPS_GREATER | D3DPCMPCAPS_NOTEQUAL | D3DPCMPCAPS_NEVER;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwSrcBlendCaps = D3DPBLENDCAPS_ZERO | D3DPBLENDCAPS_ONE |
            D3DPBLENDCAPS_SRCCOLOR | D3DPBLENDCAPS_INVSRCCOLOR | D3DPBLENDCAPS_SRCALPHA |
            D3DPBLENDCAPS_INVSRCALPHA | D3DPBLENDCAPS_DESTALPHA | D3DPBLENDCAPS_INVDESTALPHA |
            D3DPBLENDCAPS_DESTCOLOR | D3DPBLENDCAPS_INVDESTCOLOR | D3DPBLENDCAPS_SRCALPHASAT;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwDestBlendCaps = ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwSrcBlendCaps;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwAlphaCmpCaps = ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwZCmpCaps;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps = D3DPSHADECAPS_COLORGOURAUDRGB | D3DPSHADECAPS_SPECULARGOURAUDRGB |
            D3DPSHADECAPS_ALPHAGOURAUDBLEND | D3DPSHADECAPS_FOGGOURAUD;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps = D3DPTEXTURECAPS_PERSPECTIVE | D3DPTEXTURECAPS_ALPHA |
            D3DPTEXTURECAPS_TRANSPARENCY | D3DPTEXTURECAPS_TEXREPEATNOTSCALEDBYSIZE;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureFilterCaps = D3DPTFILTERCAPS_NEAREST | D3DPTFILTERCAPS_LINEAR |
            D3DPTFILTERCAPS_MIPNEAREST | D3DPTFILTERCAPS_MIPLINEAR |
            D3DPTFILTERCAPS_LINEARMIPNEAREST | D3DPTFILTERCAPS_LINEARMIPLINEAR;
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureBlendCaps = 0x02 | 0x04; // MODULATE | DECAL
        ctx->m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureAddressCaps = 0x01 | 0x04; // WRAP | CLAMP

        // Line caps - same as triangle caps
        ctx->m_pD3DHWDeviceDesc->dpcLineCaps = ctx->m_pD3DHWDeviceDesc->dpcTriCaps;

        // Device caps
        ctx->m_pD3DHWDeviceDesc->dwDevCaps = D3DDEVCAPS_FLOATTLVERTEX | D3DDEVCAPS_EXECUTESYSTEMMEMORY |
            D3DDEVCAPS_EXECUTEVIDEOMEMORY | D3DDEVCAPS_TLVERTEXSYSTEMMEMORY |
            D3DDEVCAPS_TLVERTEXVIDEOMEMORY | D3DDEVCAPS_TEXTURESYSTEMMEMORY |
            D3DDEVCAPS_TEXTUREVIDEOMEMORY | D3DDEVCAPS_DRAWPRIMTLVERTEX |
            D3DDEVCAPS_CANRENDERAFTERFLIP | D3DDEVCAPS_TEXTURENONLOCALVIDMEM |
            D3DDEVCAPS_DRAWPRIMITIVES2 | D3DDEVCAPS_DRAWPRIMITIVES2EX |
            D3DDEVCAPS_HWRASTERIZATION | D3DDEVCAPS_HWTRANSFORMANDLIGHT;

        // Texture limits
        ctx->m_pD3DHWDeviceDesc->dwMinTextureWidth = 1;
        ctx->m_pD3DHWDeviceDesc->dwMinTextureHeight = 1;
        ctx->m_pD3DHWDeviceDesc->dwMaxTextureWidth = 4096;
        ctx->m_pD3DHWDeviceDesc->dwMaxTextureHeight = 4096;
        ctx->m_pD3DHWDeviceDesc->dwMaxTextureRepeat = 8192;
        ctx->m_pD3DHWDeviceDesc->dwMaxTextureAspectRatio = 4096;
        ctx->m_pD3DHWDeviceDesc->dwMaxAnisotropy = 16;
        ctx->m_pD3DHWDeviceDesc->wMaxTextureBlendStages = 8;
        ctx->m_pD3DHWDeviceDesc->wMaxSimultaneousTextures = 8;
        ctx->m_pD3DHWDeviceDesc->wMaxUserClipPlanes = 6;
        ctx->m_pD3DHWDeviceDesc->wMaxVertexBlendMatrices = 4;
        ctx->m_pD3DHWDeviceDesc->dwMaxActiveLights = 8;
    }

    // Initialize device identifier
    if (ctx->m_pDevID) {
        memset(ctx->m_pDevID, 0, sizeof(DDDEVICEIDENTIFIER2));
        strcpy(ctx->m_pDevID->szDriver, "OpenGL");
        strcpy(ctx->m_pDevID->szDescription, "FreeFalcon OpenGL Renderer");
        ctx->m_pDevID->dwVendorId = 0x10DE; // NVIDIA vendor ID
        ctx->m_pDevID->dwDeviceId = 0x1234;
    }

    printf("[D3DGL] DXContext created successfully\n");
    return ctx;
}

} // extern "C"

#endif // FF_LINUX
