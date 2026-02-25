/*
 * FreeFalcon Linux Port - d3dx.h compatibility
 *
 * Direct3D Extension stub - will be replaced by OpenGL
 */

#ifndef FF_COMPAT_D3DX_H
#define FF_COMPAT_D3DX_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* D3D Matrix */
typedef struct _D3DMATRIX {
    union {
        struct {
            float _11, _12, _13, _14;
            float _21, _22, _23, _24;
            float _31, _32, _33, _34;
            float _41, _42, _43, _44;
        };
        float m[4][4];
    };
} D3DMATRIX, *LPD3DMATRIX;

typedef D3DMATRIX D3DXMATRIX;
typedef D3DXMATRIX *LPD3DXMATRIX;

/* D3D Vector types */
typedef struct _D3DXVECTOR2 {
    float x, y;
} D3DXVECTOR2, *LPD3DXVECTOR2;

typedef struct _D3DXVECTOR3 {
    float x, y, z;
} D3DXVECTOR3, *LPD3DXVECTOR3;

typedef struct _D3DXVECTOR4 {
    float x, y, z, w;
} D3DXVECTOR4, *LPD3DXVECTOR4;

/* D3D Color */
typedef struct _D3DCOLORVALUE {
    float r, g, b, a;
} D3DCOLORVALUE, *LPD3DCOLORVALUE;

typedef DWORD D3DCOLOR;

#define D3DCOLOR_ARGB(a,r,g,b) \
    ((D3DCOLOR)((((a)&0xff)<<24)|(((r)&0xff)<<16)|(((g)&0xff)<<8)|((b)&0xff)))
#define D3DCOLOR_RGBA(r,g,b,a) D3DCOLOR_ARGB(a,r,g,b)
#define D3DCOLOR_XRGB(r,g,b)   D3DCOLOR_ARGB(0xff,r,g,b)
#define D3DCOLOR_COLORVALUE(r,g,b,a) \
    D3DCOLOR_RGBA((DWORD)((r)*255.f),(DWORD)((g)*255.f),(DWORD)((b)*255.f),(DWORD)((a)*255.f))

/* D3D Viewport */
typedef struct _D3DVIEWPORT8 {
    DWORD X;
    DWORD Y;
    DWORD Width;
    DWORD Height;
    float MinZ;
    float MaxZ;
} D3DVIEWPORT8, *LPD3DVIEWPORT8;

/* D3D Light */
typedef struct _D3DLIGHT8 {
    DWORD Type;
    D3DCOLORVALUE Diffuse;
    D3DCOLORVALUE Specular;
    D3DCOLORVALUE Ambient;
    D3DXVECTOR3 Position;
    D3DXVECTOR3 Direction;
    float Range;
    float Falloff;
    float Attenuation0;
    float Attenuation1;
    float Attenuation2;
    float Theta;
    float Phi;
} D3DLIGHT8, *LPD3DLIGHT8;

#define D3DLIGHT_POINT          1
#define D3DLIGHT_SPOT           2
#define D3DLIGHT_DIRECTIONAL    3

/* D3D Material */
typedef struct _D3DMATERIAL8 {
    D3DCOLORVALUE Diffuse;
    D3DCOLORVALUE Ambient;
    D3DCOLORVALUE Specular;
    D3DCOLORVALUE Emissive;
    float Power;
} D3DMATERIAL8, *LPD3DMATERIAL8;

/* D3D Primitive types */
typedef enum _D3DPRIMITIVETYPE {
    D3DPT_POINTLIST = 1,
    D3DPT_LINELIST = 2,
    D3DPT_LINESTRIP = 3,
    D3DPT_TRIANGLELIST = 4,
    D3DPT_TRIANGLESTRIP = 5,
    D3DPT_TRIANGLEFAN = 6,
} D3DPRIMITIVETYPE;

/* D3D Format */
typedef enum _D3DFORMAT {
    D3DFMT_UNKNOWN = 0,
    D3DFMT_R8G8B8 = 20,
    D3DFMT_A8R8G8B8 = 21,
    D3DFMT_X8R8G8B8 = 22,
    D3DFMT_R5G6B5 = 23,
    D3DFMT_X1R5G5B5 = 24,
    D3DFMT_A1R5G5B5 = 25,
    D3DFMT_A4R4G4B4 = 26,
    D3DFMT_A8 = 28,
    D3DFMT_P8 = 41,
    D3DFMT_L8 = 50,
    D3DFMT_A8L8 = 51,
    D3DFMT_DXT1 = MAKEFOURCC('D','X','T','1'),
    D3DFMT_DXT2 = MAKEFOURCC('D','X','T','2'),
    D3DFMT_DXT3 = MAKEFOURCC('D','X','T','3'),
    D3DFMT_DXT4 = MAKEFOURCC('D','X','T','4'),
    D3DFMT_DXT5 = MAKEFOURCC('D','X','T','5'),
    D3DFMT_D16 = 80,
    D3DFMT_D32 = 71,
    D3DFMT_D24S8 = 75,
    D3DFMT_D24X8 = 77,
} D3DFORMAT;

/* Flexible Vertex Format flags */
#define D3DFVF_RESERVED0        0x001
#define D3DFVF_POSITION_MASK    0x400E
#define D3DFVF_XYZ              0x002
#define D3DFVF_XYZRHW           0x004
#define D3DFVF_XYZB1            0x006
#define D3DFVF_XYZB2            0x008
#define D3DFVF_XYZB3            0x00a
#define D3DFVF_XYZB4            0x00c
#define D3DFVF_XYZB5            0x00e
#define D3DFVF_XYZW             0x4002
#define D3DFVF_NORMAL           0x010
#define D3DFVF_PSIZE            0x020
#define D3DFVF_DIFFUSE          0x040
#define D3DFVF_SPECULAR         0x080
#define D3DFVF_TEXCOUNT_MASK    0xf00
#define D3DFVF_TEXCOUNT_SHIFT   8
#define D3DFVF_TEX0             0x000
#define D3DFVF_TEX1             0x100
#define D3DFVF_TEX2             0x200
#define D3DFVF_TEX3             0x300
#define D3DFVF_TEX4             0x400
#define D3DFVF_TEX5             0x500
#define D3DFVF_TEX6             0x600
#define D3DFVF_TEX7             0x700
#define D3DFVF_TEX8             0x800

/* Stub interfaces */
typedef void IDirect3D8;
typedef void IDirect3DDevice8;
typedef void IDirect3DTexture8;
typedef void IDirect3DSurface8;
typedef void IDirect3DVertexBuffer8;
typedef void IDirect3DIndexBuffer8;

typedef IDirect3D8* LPDIRECT3D8;
typedef IDirect3DDevice8* LPDIRECT3DDEVICE8;
typedef IDirect3DTexture8* LPDIRECT3DTEXTURE8;
typedef IDirect3DSurface8* LPDIRECT3DSURFACE8;
typedef IDirect3DVertexBuffer8* LPDIRECT3DVERTEXBUFFER8;
typedef IDirect3DIndexBuffer8* LPDIRECT3DINDEXBUFFER8;

/* Creation stub */
static inline IDirect3D8* Direct3DCreate8(UINT SDKVersion) {
    (void)SDKVersion;
    return NULL;
}

/* D3DX function stubs */
static inline HRESULT D3DXMatrixIdentity(D3DXMATRIX* pOut) {
    if (pOut) {
        pOut->_11 = 1; pOut->_12 = 0; pOut->_13 = 0; pOut->_14 = 0;
        pOut->_21 = 0; pOut->_22 = 1; pOut->_23 = 0; pOut->_24 = 0;
        pOut->_31 = 0; pOut->_32 = 0; pOut->_33 = 1; pOut->_34 = 0;
        pOut->_41 = 0; pOut->_42 = 0; pOut->_43 = 0; pOut->_44 = 1;
    }
    return S_OK;
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_D3DX_H */
