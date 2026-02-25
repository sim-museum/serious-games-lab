/*
 * FreeFalcon Linux Port - d3dtypes.h compatibility
 *
 * Direct3D type definitions stub for Linux.
 * This is a legacy DirectX header with basic D3D types.
 */

#ifndef FF_COMPAT_D3DTYPES_H
#define FF_COMPAT_D3DTYPES_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "ddraw.h"

#ifdef __cplusplus
extern "C" {
#endif

/* D3D value types */
typedef float D3DVALUE;
typedef float *LPD3DVALUE;
typedef long D3DFIXED;
typedef DWORD D3DCOLOR;

/* Primitive types */
typedef enum _D3DPRIMITIVETYPE {
    D3DPT_POINTLIST = 1,
    D3DPT_LINELIST = 2,
    D3DPT_LINESTRIP = 3,
    D3DPT_TRIANGLELIST = 4,
    D3DPT_TRIANGLESTRIP = 5,
    D3DPT_TRIANGLEFAN = 6,
} D3DPRIMITIVETYPE;

/* Vertex types */
typedef enum _D3DVERTEXTYPE {
    D3DVT_VERTEX = 1,
    D3DVT_LVERTEX = 2,
    D3DVT_TLVERTEX = 3,
} D3DVERTEXTYPE;

/* Transform state types */
typedef enum _D3DTRANSFORMSTATETYPE {
    D3DTRANSFORMSTATE_WORLD = 1,
    D3DTRANSFORMSTATE_VIEW = 2,
    D3DTRANSFORMSTATE_PROJECTION = 3,
    D3DTRANSFORMSTATE_WORLD1 = 4,
    D3DTRANSFORMSTATE_WORLD2 = 5,
    D3DTRANSFORMSTATE_WORLD3 = 6,
    D3DTRANSFORMSTATE_TEXTURE0 = 16,
    D3DTRANSFORMSTATE_TEXTURE1 = 17,
    D3DTRANSFORMSTATE_TEXTURE2 = 18,
    D3DTRANSFORMSTATE_TEXTURE3 = 19,
    D3DTRANSFORMSTATE_TEXTURE4 = 20,
    D3DTRANSFORMSTATE_TEXTURE5 = 21,
    D3DTRANSFORMSTATE_TEXTURE6 = 22,
    D3DTRANSFORMSTATE_TEXTURE7 = 23,
} D3DTRANSFORMSTATETYPE;

/* Light type */
typedef enum _D3DLIGHTTYPE {
    D3DLIGHT_POINT = 1,
    D3DLIGHT_SPOT = 2,
    D3DLIGHT_DIRECTIONAL = 3,
} D3DLIGHTTYPE;

/* D3DVECTOR - 3D vector */
#ifndef _D3DVECTOR_DEFINED
typedef struct _D3DVECTOR {
    union {
        float x;
        float dvX;
    };
    union {
        float y;
        float dvY;
    };
    union {
        float z;
        float dvZ;
    };
#ifdef __cplusplus
    _D3DVECTOR() : x(0), y(0), z(0) {}
    _D3DVECTOR(float _x, float _y, float _z) : x(_x), y(_y), z(_z) {}
#endif
} D3DVECTOR, *LPD3DVECTOR;
#define _D3DVECTOR_DEFINED
#endif

#ifdef __cplusplus
} // end extern "C" - operators must have C++ linkage

/* D3DVECTOR operators for C++ */
inline D3DVECTOR operator-(const D3DVECTOR& a, const D3DVECTOR& b) {
    D3DVECTOR result;
    result.x = a.x - b.x;
    result.y = a.y - b.y;
    result.z = a.z - b.z;
    return result;
}

inline D3DVECTOR operator+(const D3DVECTOR& a, const D3DVECTOR& b) {
    D3DVECTOR result;
    result.x = a.x + b.x;
    result.y = a.y + b.y;
    result.z = a.z + b.z;
    return result;
}

inline D3DVECTOR operator*(const D3DVECTOR& a, float s) {
    D3DVECTOR result;
    result.x = a.x * s;
    result.y = a.y * s;
    result.z = a.z * s;
    return result;
}

inline D3DVECTOR operator-(const D3DVECTOR& a) {
    D3DVECTOR result;
    result.x = -a.x;
    result.y = -a.y;
    result.z = -a.z;
    return result;
}

extern "C" { // reopen extern "C"
#endif

/* D3DCOLORVALUE - RGBA color */
typedef struct _D3DCOLORVALUE {
    union {
        float r;
        float dvR;
    };
    union {
        float g;
        float dvG;
    };
    union {
        float b;
        float dvB;
    };
    union {
        float a;
        float dvA;
    };
} D3DCOLORVALUE, *LPD3DCOLORVALUE;

/* D3DMATRIX - 4x4 matrix
 * Note: The m[4][4] member name conflicts with macros in matrixdefs.h that
 * define m11, m12 etc as m[0][0], m[0][1] etc. We use 'mat' as the array name.
 */
typedef struct _D3DMATRIX {
    union {
        struct {
            float _11, _12, _13, _14;
            float _21, _22, _23, _24;
            float _31, _32, _33, _34;
            float _41, _42, _43, _44;
        };
        float mat[4][4];
    };
#ifdef __cplusplus
    /* Accessor for mat[][] style using operator[] */
    float* operator[](int i) { return mat[i]; }
    const float* operator[](int i) const { return mat[i]; }
#endif
} D3DMATRIX, *LPD3DMATRIX;

/* Provide 'm' as an alias when matrixdefs macros aren't in effect */
#ifndef m11
#define D3DMATRIX_HAS_M_ALIAS 1
#endif

/* D3DXMATRIX - same as D3DMATRIX for our stub purposes */
typedef D3DMATRIX D3DXMATRIX;
typedef D3DMATRIX *LPD3DXMATRIX;

/* D3DMATRIX comparison operators for C++ */
#ifdef __cplusplus
inline bool operator==(const D3DMATRIX& a, const D3DMATRIX& b) {
    return a._11 == b._11 && a._12 == b._12 && a._13 == b._13 && a._14 == b._14 &&
           a._21 == b._21 && a._22 == b._22 && a._23 == b._23 && a._24 == b._24 &&
           a._31 == b._31 && a._32 == b._32 && a._33 == b._33 && a._34 == b._34 &&
           a._41 == b._41 && a._42 == b._42 && a._43 == b._43 && a._44 == b._44;
}
inline bool operator!=(const D3DMATRIX& a, const D3DMATRIX& b) {
    return !(a == b);
}
#endif

/* D3DVERTEX - untransformed lit vertex */
typedef struct _D3DVERTEX {
    float x, y, z;
    float nx, ny, nz;
    float tu, tv;
} D3DVERTEX, *LPD3DVERTEX;

/* D3DLVERTEX - untransformed unlit vertex */
typedef struct _D3DLVERTEX {
    float x, y, z;
    DWORD dwReserved;
    D3DCOLOR color;
    D3DCOLOR specular;
    float tu, tv;
} D3DLVERTEX, *LPD3DLVERTEX;

/* D3DTLVERTEX - transformed lit vertex */
typedef struct _D3DTLVERTEX {
    float sx, sy, sz, rhw;
    D3DCOLOR color;
    D3DCOLOR specular;
    float tu, tv;
} D3DTLVERTEX, *LPD3DTLVERTEX;

/* D3DRECT - rectangle */
typedef struct _D3DRECT {
    union {
        long x1;
        long lX1;
    };
    union {
        long y1;
        long lY1;
    };
    union {
        long x2;
        long lX2;
    };
    union {
        long y2;
        long lY2;
    };
} D3DRECT, *LPD3DRECT;

/* D3DLIGHT - light definition */
typedef struct _D3DLIGHT {
    DWORD dwSize;
    D3DLIGHTTYPE dltType;
    D3DCOLORVALUE dcvDiffuse;
    D3DCOLORVALUE dcvSpecular;
    D3DCOLORVALUE dcvAmbient;
    D3DVECTOR dvPosition;
    D3DVECTOR dvDirection;
    float dvRange;
    float dvFalloff;
    float dvAttenuation0;
    float dvAttenuation1;
    float dvAttenuation2;
    float dvTheta;
    float dvPhi;
} D3DLIGHT, *LPD3DLIGHT;

typedef D3DLIGHT D3DLIGHT7;
typedef D3DLIGHT *LPD3DLIGHT7;

/* D3DMATERIAL - material definition */
typedef struct _D3DMATERIAL {
    DWORD dwSize;
    union {
        D3DCOLORVALUE dcvDiffuse;
        D3DCOLORVALUE diffuse;
    };
    union {
        D3DCOLORVALUE dcvAmbient;
        D3DCOLORVALUE ambient;
    };
    union {
        D3DCOLORVALUE dcvSpecular;
        D3DCOLORVALUE specular;
    };
    union {
        D3DCOLORVALUE dcvEmissive;
        D3DCOLORVALUE emissive;
    };
    union {
        float dvPower;
        float power;
    };
    DWORD dwRampSize;
    DWORD hTexture;
} D3DMATERIAL, *LPD3DMATERIAL;

typedef D3DMATERIAL D3DMATERIAL7;
typedef D3DMATERIAL *LPD3DMATERIAL7;

/* D3DVIEWPORT - viewport definition */
typedef struct _D3DVIEWPORT {
    DWORD dwSize;
    DWORD dwX;
    DWORD dwY;
    DWORD dwWidth;
    DWORD dwHeight;
    float dvScaleX;
    float dvScaleY;
    float dvMaxX;
    float dvMaxY;
    float dvMinZ;
    float dvMaxZ;
} D3DVIEWPORT, *LPD3DVIEWPORT;

typedef struct _D3DVIEWPORT7 {
    DWORD dwX;
    DWORD dwY;
    DWORD dwWidth;
    DWORD dwHeight;
    float dvMinZ;
    float dvMaxZ;
} D3DVIEWPORT7, *LPD3DVIEWPORT7;

/* Render states */
typedef enum _D3DRENDERSTATETYPE {
    D3DRENDERSTATE_TEXTUREHANDLE = 1,
    D3DRENDERSTATE_ANTIALIAS = 2,
    D3DRENDERSTATE_TEXTUREADDRESS = 3,
    D3DRENDERSTATE_TEXTUREPERSPECTIVE = 4,
    D3DRENDERSTATE_WRAPU = 5,
    D3DRENDERSTATE_WRAPV = 6,
    D3DRENDERSTATE_ZENABLE = 7,
    D3DRENDERSTATE_FILLMODE = 8,
    D3DRENDERSTATE_SHADEMODE = 9,
    D3DRENDERSTATE_LINEPATTERN = 10,
    D3DRENDERSTATE_MONOENABLE = 11,
    D3DRENDERSTATE_ROP2 = 12,
    D3DRENDERSTATE_PLANEMASK = 13,
    D3DRENDERSTATE_ZWRITEENABLE = 14,
    D3DRENDERSTATE_ALPHATESTENABLE = 15,
    D3DRENDERSTATE_LASTPIXEL = 16,
    D3DRENDERSTATE_TEXTUREMAG = 17,
    D3DRENDERSTATE_TEXTUREMIN = 18,
    D3DRENDERSTATE_SRCBLEND = 19,
    D3DRENDERSTATE_DESTBLEND = 20,
    D3DRENDERSTATE_TEXTUREMAPBLEND = 21,
    D3DRENDERSTATE_CULLMODE = 22,
    D3DRENDERSTATE_ZFUNC = 23,
    D3DRENDERSTATE_ALPHAREF = 24,
    D3DRENDERSTATE_ALPHAFUNC = 25,
    D3DRENDERSTATE_DITHERENABLE = 26,
    D3DRENDERSTATE_ALPHABLENDENABLE = 27,
    D3DRENDERSTATE_FOGENABLE = 28,
    D3DRENDERSTATE_SPECULARENABLE = 29,
    D3DRENDERSTATE_ZVISIBLE = 30,
    D3DRENDERSTATE_SUBPIXEL = 31,
    D3DRENDERSTATE_SUBPIXELX = 32,
    D3DRENDERSTATE_STIPPLEDALPHA = 33,
    D3DRENDERSTATE_FOGCOLOR = 34,
    D3DRENDERSTATE_FOGTABLEMODE = 35,
    D3DRENDERSTATE_FOGTABLESTART = 36,
    D3DRENDERSTATE_FOGTABLEEND = 37,
    D3DRENDERSTATE_FOGTABLEDENSITY = 38,
    D3DRENDERSTATE_STIPPLEENABLE = 39,
    D3DRENDERSTATE_COLORKEYENABLE = 41,
    D3DRENDERSTATE_BORDERCOLOR = 43,
    D3DRENDERSTATE_TEXTUREADDRESSU = 44,
    D3DRENDERSTATE_TEXTUREADDRESSV = 45,
    D3DRENDERSTATE_MIPMAPLODBIAS = 46,
    D3DRENDERSTATE_ZBIAS = 47,
    D3DRENDERSTATE_RANGEFOGENABLE = 48,
    D3DRENDERSTATE_ANISOTROPY = 49,
    D3DRENDERSTATE_FLUSHBATCH = 50,
    D3DRENDERSTATE_TRANSLUCENTSORTINDEPENDENT = 51,
    D3DRENDERSTATE_STENCILENABLE = 52,
    D3DRENDERSTATE_STENCILFAIL = 53,
    D3DRENDERSTATE_STENCILZFAIL = 54,
    D3DRENDERSTATE_STENCILPASS = 55,
    D3DRENDERSTATE_STENCILFUNC = 56,
    D3DRENDERSTATE_STENCILREF = 57,
    D3DRENDERSTATE_STENCILMASK = 58,
    D3DRENDERSTATE_STENCILWRITEMASK = 59,
    D3DRENDERSTATE_TEXTUREFACTOR = 60,
    D3DRENDERSTATE_STIPPLEPATTERN00 = 64,
    D3DRENDERSTATE_STIPPLEPATTERN01 = 65,
    D3DRENDERSTATE_STIPPLEPATTERN02 = 66,
    D3DRENDERSTATE_STIPPLEPATTERN03 = 67,
    D3DRENDERSTATE_STIPPLEPATTERN04 = 68,
    D3DRENDERSTATE_STIPPLEPATTERN05 = 69,
    D3DRENDERSTATE_STIPPLEPATTERN06 = 70,
    D3DRENDERSTATE_STIPPLEPATTERN07 = 71,
    D3DRENDERSTATE_STIPPLEPATTERN08 = 72,
    D3DRENDERSTATE_STIPPLEPATTERN09 = 73,
    D3DRENDERSTATE_STIPPLEPATTERN10 = 74,
    D3DRENDERSTATE_STIPPLEPATTERN11 = 75,
    D3DRENDERSTATE_STIPPLEPATTERN12 = 76,
    D3DRENDERSTATE_STIPPLEPATTERN13 = 77,
    D3DRENDERSTATE_STIPPLEPATTERN14 = 78,
    D3DRENDERSTATE_STIPPLEPATTERN15 = 79,
    D3DRENDERSTATE_STIPPLEPATTERN16 = 80,
    D3DRENDERSTATE_STIPPLEPATTERN17 = 81,
    D3DRENDERSTATE_STIPPLEPATTERN18 = 82,
    D3DRENDERSTATE_STIPPLEPATTERN19 = 83,
    D3DRENDERSTATE_STIPPLEPATTERN20 = 84,
    D3DRENDERSTATE_STIPPLEPATTERN21 = 85,
    D3DRENDERSTATE_STIPPLEPATTERN22 = 86,
    D3DRENDERSTATE_STIPPLEPATTERN23 = 87,
    D3DRENDERSTATE_STIPPLEPATTERN24 = 88,
    D3DRENDERSTATE_STIPPLEPATTERN25 = 89,
    D3DRENDERSTATE_STIPPLEPATTERN26 = 90,
    D3DRENDERSTATE_STIPPLEPATTERN27 = 91,
    D3DRENDERSTATE_STIPPLEPATTERN28 = 92,
    D3DRENDERSTATE_STIPPLEPATTERN29 = 93,
    D3DRENDERSTATE_STIPPLEPATTERN30 = 94,
    D3DRENDERSTATE_STIPPLEPATTERN31 = 95,
    D3DRENDERSTATE_WRAP0 = 128,
    D3DRENDERSTATE_WRAP1 = 129,
    D3DRENDERSTATE_WRAP2 = 130,
    D3DRENDERSTATE_WRAP3 = 131,
    D3DRENDERSTATE_WRAP4 = 132,
    D3DRENDERSTATE_WRAP5 = 133,
    D3DRENDERSTATE_WRAP6 = 134,
    D3DRENDERSTATE_WRAP7 = 135,
    D3DRENDERSTATE_CLIPPING = 136,
    D3DRENDERSTATE_LIGHTING = 137,
    D3DRENDERSTATE_EXTENTS = 138,
    D3DRENDERSTATE_AMBIENT = 139,
    D3DRENDERSTATE_FOGVERTEXMODE = 140,
    D3DRENDERSTATE_COLORVERTEX = 141,
    D3DRENDERSTATE_LOCALVIEWER = 142,
    D3DRENDERSTATE_NORMALIZENORMALS = 143,
    D3DRENDERSTATE_COLORKEYBLENDENABLE = 144,
    D3DRENDERSTATE_DIFFUSEMATERIALSOURCE = 145,
    D3DRENDERSTATE_SPECULARMATERIALSOURCE = 146,
    D3DRENDERSTATE_AMBIENTMATERIALSOURCE = 147,
    D3DRENDERSTATE_EMISSIVEMATERIALSOURCE = 148,
    D3DRENDERSTATE_VERTEXBLEND = 151,
    D3DRENDERSTATE_CLIPPLANEENABLE = 152,
} D3DRENDERSTATETYPE;

/* Legacy fog state names (aliased to table versions) */
#define D3DRENDERSTATE_FOGSTART D3DRENDERSTATE_FOGTABLESTART
#define D3DRENDERSTATE_FOGEND D3DRENDERSTATE_FOGTABLEEND
#define D3DRENDERSTATE_FOGDENSITY D3DRENDERSTATE_FOGTABLEDENSITY

/* Texture stage states */
typedef enum _D3DTEXTURESTAGESTATETYPE {
    D3DTSS_COLOROP = 1,
    D3DTSS_COLORARG1 = 2,
    D3DTSS_COLORARG2 = 3,
    D3DTSS_ALPHAOP = 4,
    D3DTSS_ALPHAARG1 = 5,
    D3DTSS_ALPHAARG2 = 6,
    D3DTSS_BUMPENVMAT00 = 7,
    D3DTSS_BUMPENVMAT01 = 8,
    D3DTSS_BUMPENVMAT10 = 9,
    D3DTSS_BUMPENVMAT11 = 10,
    D3DTSS_TEXCOORDINDEX = 11,
    D3DTSS_ADDRESS = 12,
    D3DTSS_ADDRESSU = 13,
    D3DTSS_ADDRESSV = 14,
    D3DTSS_BORDERCOLOR = 15,
    D3DTSS_MAGFILTER = 16,
    D3DTSS_MINFILTER = 17,
    D3DTSS_MIPFILTER = 18,
    D3DTSS_MIPMAPLODBIAS = 19,
    D3DTSS_MAXMIPLEVEL = 20,
    D3DTSS_MAXANISOTROPY = 21,
    D3DTSS_BUMPENVLSCALE = 22,
    D3DTSS_BUMPENVLOFFSET = 23,
    D3DTSS_TEXTURETRANSFORMFLAGS = 24,
} D3DTEXTURESTAGESTATETYPE;

/* Texture filter types */
typedef enum _D3DTEXTUREFILTERTYPE {
    D3DTFN_POINT = 1,
    D3DTFN_LINEAR = 2,
    D3DTFN_ANISOTROPIC = 3,
    D3DTFG_POINT = 1,
    D3DTFG_LINEAR = 2,
    D3DTFG_FLATCUBIC = 3,
    D3DTFG_GAUSSIANCUBIC = 4,
    D3DTFG_ANISOTROPIC = 5,
    D3DTFP_NONE = 1,
    D3DTFP_POINT = 2,
    D3DTFP_LINEAR = 3,
} D3DTEXTUREFILTERTYPE;

/* Texture address modes */
typedef enum _D3DTEXTUREADDRESS {
    D3DTADDRESS_WRAP = 1,
    D3DTADDRESS_MIRROR = 2,
    D3DTADDRESS_CLAMP = 3,
    D3DTADDRESS_BORDER = 4,
    D3DTADDRESS_MIRRORONCE = 5,
} D3DTEXTUREADDRESS;

/* Blend modes */
typedef enum _D3DBLEND {
    D3DBLEND_ZERO = 1,
    D3DBLEND_ONE = 2,
    D3DBLEND_SRCCOLOR = 3,
    D3DBLEND_INVSRCCOLOR = 4,
    D3DBLEND_SRCALPHA = 5,
    D3DBLEND_INVSRCALPHA = 6,
    D3DBLEND_DESTALPHA = 7,
    D3DBLEND_INVDESTALPHA = 8,
    D3DBLEND_DESTCOLOR = 9,
    D3DBLEND_INVDESTCOLOR = 10,
    D3DBLEND_SRCALPHASAT = 11,
    D3DBLEND_BOTHSRCALPHA = 12,
    D3DBLEND_BOTHINVSRCALPHA = 13,
} D3DBLEND;

/* Compare functions */
typedef enum _D3DCMPFUNC {
    D3DCMP_NEVER = 1,
    D3DCMP_LESS = 2,
    D3DCMP_EQUAL = 3,
    D3DCMP_LESSEQUAL = 4,
    D3DCMP_GREATER = 5,
    D3DCMP_NOTEQUAL = 6,
    D3DCMP_GREATEREQUAL = 7,
    D3DCMP_ALWAYS = 8,
} D3DCMPFUNC;

/* Stencil operations */
typedef enum _D3DSTENCILOP {
    D3DSTENCILOP_KEEP = 1,
    D3DSTENCILOP_ZERO = 2,
    D3DSTENCILOP_REPLACE = 3,
    D3DSTENCILOP_INCRSAT = 4,
    D3DSTENCILOP_DECRSAT = 5,
    D3DSTENCILOP_INVERT = 6,
    D3DSTENCILOP_INCR = 7,
    D3DSTENCILOP_DECR = 8,
} D3DSTENCILOP;

/* Shade modes */
typedef enum _D3DSHADEMODE {
    D3DSHADE_FLAT = 1,
    D3DSHADE_GOURAUD = 2,
    D3DSHADE_PHONG = 3,
} D3DSHADEMODE;

/* Fill modes */
typedef enum _D3DFILLMODE {
    D3DFILL_POINT = 1,
    D3DFILL_WIREFRAME = 2,
    D3DFILL_SOLID = 3,
} D3DFILLMODE;

/* Cull modes */
typedef enum _D3DCULL {
    D3DCULL_NONE = 1,
    D3DCULL_CW = 2,
    D3DCULL_CCW = 3,
} D3DCULL;

/* Fog modes */
typedef enum _D3DFOGMODE {
    D3DFOG_NONE = 0,
    D3DFOG_EXP = 1,
    D3DFOG_EXP2 = 2,
    D3DFOG_LINEAR = 3,
} D3DFOGMODE;

/* Texture operations */
typedef enum _D3DTEXTUREOP {
    D3DTOP_DISABLE = 1,
    D3DTOP_SELECTARG1 = 2,
    D3DTOP_SELECTARG2 = 3,
    D3DTOP_MODULATE = 4,
    D3DTOP_MODULATE2X = 5,
    D3DTOP_MODULATE4X = 6,
    D3DTOP_ADD = 7,
    D3DTOP_ADDSIGNED = 8,
    D3DTOP_ADDSIGNED2X = 9,
    D3DTOP_SUBTRACT = 10,
    D3DTOP_ADDSMOOTH = 11,
    D3DTOP_BLENDDIFFUSEALPHA = 12,
    D3DTOP_BLENDTEXTUREALPHA = 13,
    D3DTOP_BLENDFACTORALPHA = 14,
    D3DTOP_BLENDTEXTUREALPHAPM = 15,
    D3DTOP_BLENDCURRENTALPHA = 16,
    D3DTOP_PREMODULATE = 17,
    D3DTOP_MODULATEALPHA_ADDCOLOR = 18,
    D3DTOP_MODULATECOLOR_ADDALPHA = 19,
    D3DTOP_MODULATEINVALPHA_ADDCOLOR = 20,
    D3DTOP_MODULATEINVCOLOR_ADDALPHA = 21,
    D3DTOP_BUMPENVMAP = 22,
    D3DTOP_BUMPENVMAPLUMINANCE = 23,
    D3DTOP_DOTPRODUCT3 = 24,
} D3DTEXTUREOP;

/* Texture argument flags */
#define D3DTA_SELECTMASK        0x0000000f
#define D3DTA_DIFFUSE           0x00000000
#define D3DTA_CURRENT           0x00000001
#define D3DTA_TEXTURE           0x00000002
#define D3DTA_TFACTOR           0x00000003
#define D3DTA_SPECULAR          0x00000004
#define D3DTA_COMPLEMENT        0x00000010
#define D3DTA_ALPHAREPLICATE    0x00000020

/* Clear flags */
#define D3DCLEAR_TARGET         0x00000001
#define D3DCLEAR_ZBUFFER        0x00000002
#define D3DCLEAR_STENCIL        0x00000004

/* Flexible vertex format flags */
#define D3DFVF_RESERVED0        0x0001
#define D3DFVF_POSITION_MASK    0x000E
#define D3DFVF_XYZ              0x0002
#define D3DFVF_XYZRHW           0x0004
#define D3DFVF_XYZB1            0x0006
#define D3DFVF_XYZB2            0x0008
#define D3DFVF_XYZB3            0x000a
#define D3DFVF_XYZB4            0x000c
#define D3DFVF_XYZB5            0x000e
#define D3DFVF_NORMAL           0x0010
#define D3DFVF_RESERVED1        0x0020
#define D3DFVF_DIFFUSE          0x0040
#define D3DFVF_SPECULAR         0x0080
#define D3DFVF_TEXCOUNT_MASK    0x0f00
#define D3DFVF_TEXCOUNT_SHIFT   8
#define D3DFVF_TEX0             0x0000
#define D3DFVF_TEX1             0x0100
#define D3DFVF_TEX2             0x0200
#define D3DFVF_TEX3             0x0300
#define D3DFVF_TEX4             0x0400
#define D3DFVF_TEX5             0x0500
#define D3DFVF_TEX6             0x0600
#define D3DFVF_TEX7             0x0700
#define D3DFVF_TEX8             0x0800
#define D3DFVF_RESERVED2        0xf000

#define D3DFVF_VERTEX           (D3DFVF_XYZ | D3DFVF_NORMAL | D3DFVF_TEX1)
#define D3DFVF_LVERTEX          (D3DFVF_XYZ | D3DFVF_RESERVED1 | D3DFVF_DIFFUSE | D3DFVF_SPECULAR | D3DFVF_TEX1)
#define D3DFVF_TLVERTEX         (D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_SPECULAR | D3DFVF_TEX1)

/* D3D color macros */
#define RGBA_MAKE(r, g, b, a)   ((D3DCOLOR) (((a) << 24) | ((r) << 16) | ((g) << 8) | (b)))
#define D3DRGBA(r, g, b, a)     RGBA_MAKE((DWORD)((r)*255.0f), (DWORD)((g)*255.0f), (DWORD)((b)*255.0f), (DWORD)((a)*255.0f))
#define D3DRGB(r, g, b)         D3DRGBA(r, g, b, 1.0f)

#define RGB_MAKE(r, g, b)       ((D3DCOLOR) (((r) << 16) | ((g) << 8) | (b)))
#define RGBA_TORGB(rgba)        ((D3DCOLOR) ((rgba) & 0xffffff))
#define RGB_GETRED(rgb)         (((rgb) >> 16) & 0xff)
#define RGB_GETGREEN(rgb)       (((rgb) >> 8) & 0xff)
#define RGB_GETBLUE(rgb)        ((rgb) & 0xff)
#define RGBA_GETRED(rgba)       (((rgba) >> 16) & 0xff)
#define RGBA_GETGREEN(rgba)     (((rgba) >> 8) & 0xff)
#define RGBA_GETBLUE(rgba)      ((rgba) & 0xff)
#define RGBA_GETALPHA(rgba)     (((rgba) >> 24) & 0xff)

/* Device capability flags (D3DDEVCAPS) */
#define D3DDEVCAPS_EXECUTESYSTEMMEMORY      0x00000010
#define D3DDEVCAPS_EXECUTEVIDEOMEMORY       0x00000020
#define D3DDEVCAPS_TLVERTEXSYSTEMMEMORY     0x00000040
#define D3DDEVCAPS_TLVERTEXVIDEOMEMORY      0x00000080
#define D3DDEVCAPS_TEXTURESYSTEMMEMORY      0x00000100
#define D3DDEVCAPS_TEXTUREVIDEOMEMORY       0x00000200
#define D3DDEVCAPS_DRAWPRIMTLVERTEX         0x00000400
#define D3DDEVCAPS_CANRENDERAFTERFLIP       0x00000800
#define D3DDEVCAPS_TEXTURENONLOCALVIDMEM    0x00001000
#define D3DDEVCAPS_DRAWPRIMITIVES2          0x00002000
#define D3DDEVCAPS_SEPARATETEXTUREMEMORIES  0x00004000
#define D3DDEVCAPS_DRAWPRIMITIVES2EX        0x00008000
#define D3DDEVCAPS_HWTRANSFORMANDLIGHT      0x00010000
#define D3DDEVCAPS_CANBLTSYSTONONLOCAL      0x00020000
#define D3DDEVCAPS_HWRASTERIZATION          0x00080000
#define D3DDEVCAPS_PUREDEVICE               0x00100000
#define D3DDEVCAPS_QUINTICRTPATCHES         0x00200000
#define D3DDEVCAPS_RTPATCHES                0x00400000
#define D3DDEVCAPS_RTPATCHHANDLEZERO        0x00800000
#define D3DDEVCAPS_NPATCHES                 0x01000000
#define D3DDEVCAPS_FLOATTLVERTEX            0x00000001

/* Primitive caps comparison flags */
#define D3DPCMPCAPS_NEVER           0x00000001
#define D3DPCMPCAPS_LESS            0x00000002
#define D3DPCMPCAPS_EQUAL           0x00000004
#define D3DPCMPCAPS_LESSEQUAL       0x00000008
#define D3DPCMPCAPS_GREATER         0x00000010
#define D3DPCMPCAPS_NOTEQUAL        0x00000020
#define D3DPCMPCAPS_GREATEREQUAL    0x00000040
#define D3DPCMPCAPS_ALWAYS          0x00000080

/* Raster caps */
#define D3DPRASTERCAPS_DITHER               0x00000001
#define D3DPRASTERCAPS_ROP2                 0x00000002
#define D3DPRASTERCAPS_XOR                  0x00000004
#define D3DPRASTERCAPS_PAT                  0x00000008
#define D3DPRASTERCAPS_ZTEST                0x00000010
#define D3DPRASTERCAPS_SUBPIXEL             0x00000020
#define D3DPRASTERCAPS_SUBPIXELX            0x00000040
#define D3DPRASTERCAPS_FOGVERTEX            0x00000080
#define D3DPRASTERCAPS_FOGTABLE             0x00000100
#define D3DPRASTERCAPS_STIPPLE              0x00000200
#define D3DPRASTERCAPS_ANTIALIASSORTDEPENDENT   0x00000400
#define D3DPRASTERCAPS_ANTIALIASSORTINDEPENDENT 0x00000800
#define D3DPRASTERCAPS_ANTIALIASEDGES       0x00001000
#define D3DPRASTERCAPS_MIPMAPLODBIAS        0x00002000
#define D3DPRASTERCAPS_ZBIAS                0x00004000
#define D3DPRASTERCAPS_ZBUFFERLESSHSR       0x00008000
#define D3DPRASTERCAPS_FOGRANGE             0x00010000
#define D3DPRASTERCAPS_ANISOTROPY           0x00020000
#define D3DPRASTERCAPS_WBUFFER              0x00040000
#define D3DPRASTERCAPS_TRANSLUCENTSORTINDEPENDENT 0x00080000
#define D3DPRASTERCAPS_WFOG                 0x00100000
#define D3DPRASTERCAPS_ZFOG                 0x00200000

/* Shade caps */
#define D3DPSHADECAPS_COLORFLATMONO         0x00000001
#define D3DPSHADECAPS_COLORFLATRGB          0x00000002
#define D3DPSHADECAPS_COLORGOURAUDMONO      0x00000004
#define D3DPSHADECAPS_COLORGOURAUDRGB       0x00000008
#define D3DPSHADECAPS_COLORPHONGMONO        0x00000010
#define D3DPSHADECAPS_COLORPHONGRGB         0x00000020
#define D3DPSHADECAPS_SPECULARFLATMONO      0x00000040
#define D3DPSHADECAPS_SPECULARFLATRGB       0x00000080
#define D3DPSHADECAPS_SPECULARGOURAUDMONO   0x00000100
#define D3DPSHADECAPS_SPECULARGOURAUDRGB    0x00000200
#define D3DPSHADECAPS_SPECULARPHONGMONO     0x00000400
#define D3DPSHADECAPS_SPECULARPHONGRGB      0x00000800
#define D3DPSHADECAPS_ALPHAFLATBLEND        0x00001000
#define D3DPSHADECAPS_ALPHAFLATSTIPPLED     0x00002000
#define D3DPSHADECAPS_ALPHAGOURAUDBLEND     0x00004000
#define D3DPSHADECAPS_ALPHAGOURAUDSTIPPLED  0x00008000
#define D3DPSHADECAPS_ALPHAPHONGBLEND       0x00010000
#define D3DPSHADECAPS_ALPHAPHONGSTIPPLED    0x00020000
#define D3DPSHADECAPS_FOGFLAT               0x00040000
#define D3DPSHADECAPS_FOGGOURAUD            0x00080000
#define D3DPSHADECAPS_FOGPHONG              0x00100000

/* Blend caps */
#define D3DPBLENDCAPS_ZERO                  0x00000001
#define D3DPBLENDCAPS_ONE                   0x00000002
#define D3DPBLENDCAPS_SRCCOLOR              0x00000004
#define D3DPBLENDCAPS_INVSRCCOLOR           0x00000008
#define D3DPBLENDCAPS_SRCALPHA              0x00000010
#define D3DPBLENDCAPS_INVSRCALPHA           0x00000020
#define D3DPBLENDCAPS_DESTALPHA             0x00000040
#define D3DPBLENDCAPS_INVDESTALPHA          0x00000080
#define D3DPBLENDCAPS_DESTCOLOR             0x00000100
#define D3DPBLENDCAPS_INVDESTCOLOR          0x00000200
#define D3DPBLENDCAPS_SRCALPHASAT           0x00000400
#define D3DPBLENDCAPS_BOTHSRCALPHA          0x00000800
#define D3DPBLENDCAPS_BOTHINVSRCALPHA       0x00001000

/* Texture filter caps */
#define D3DPTFILTERCAPS_NEAREST             0x00000001
#define D3DPTFILTERCAPS_LINEAR              0x00000002
#define D3DPTFILTERCAPS_MIPNEAREST          0x00000004
#define D3DPTFILTERCAPS_MIPLINEAR           0x00000008
#define D3DPTFILTERCAPS_LINEARMIPNEAREST    0x00000010
#define D3DPTFILTERCAPS_LINEARMIPLINEAR     0x00000020
#define D3DPTFILTERCAPS_MINFPOINT           0x00000100
#define D3DPTFILTERCAPS_MINFLINEAR          0x00000200
#define D3DPTFILTERCAPS_MINFANISOTROPIC     0x00000400
#define D3DPTFILTERCAPS_MIPFPOINT           0x00010000
#define D3DPTFILTERCAPS_MIPFLINEAR          0x00020000
#define D3DPTFILTERCAPS_MAGFPOINT           0x01000000
#define D3DPTFILTERCAPS_MAGFLINEAR          0x02000000
#define D3DPTFILTERCAPS_MAGFANISOTROPIC     0x04000000
#define D3DPTFILTERCAPS_MAGFAFLATCUBIC      0x08000000
#define D3DPTFILTERCAPS_MAGFGAUSSIANCUBIC   0x10000000

/* Texture caps */
#define D3DPTEXTURECAPS_PERSPECTIVE         0x00000001
#define D3DPTEXTURECAPS_POW2                0x00000002
#define D3DPTEXTURECAPS_ALPHA               0x00000004
#define D3DPTEXTURECAPS_TRANSPARENCY        0x00000008
#define D3DPTEXTURECAPS_BORDER              0x00000010
#define D3DPTEXTURECAPS_SQUAREONLY          0x00000020
#define D3DPTEXTURECAPS_TEXREPEATNOTSCALEDBYSIZE 0x00000040
#define D3DPTEXTURECAPS_ALPHAPALETTE        0x00000080
#define D3DPTEXTURECAPS_NONPOW2CONDITIONAL  0x00000100
#define D3DPTEXTURECAPS_PROJECTED           0x00000400
#define D3DPTEXTURECAPS_CUBEMAP             0x00000800
#define D3DPTEXTURECAPS_COLORKEYBLEND       0x00001000

/* Texture operation caps */
#define D3DTEXOPCAPS_DISABLE                0x00000001
#define D3DTEXOPCAPS_SELECTARG1             0x00000002
#define D3DTEXOPCAPS_SELECTARG2             0x00000004
#define D3DTEXOPCAPS_MODULATE               0x00000008
#define D3DTEXOPCAPS_MODULATE2X             0x00000010
#define D3DTEXOPCAPS_MODULATE4X             0x00000020
#define D3DTEXOPCAPS_ADD                    0x00000040
#define D3DTEXOPCAPS_ADDSIGNED              0x00000080
#define D3DTEXOPCAPS_ADDSIGNED2X            0x00000100
#define D3DTEXOPCAPS_SUBTRACT               0x00000200
#define D3DTEXOPCAPS_ADDSMOOTH              0x00000400
#define D3DTEXOPCAPS_BLENDDIFFUSEALPHA      0x00000800
#define D3DTEXOPCAPS_BLENDTEXTUREALPHA      0x00001000
#define D3DTEXOPCAPS_BLENDFACTORALPHA       0x00002000
#define D3DTEXOPCAPS_BLENDTEXTUREALPHAPM    0x00004000
#define D3DTEXOPCAPS_BLENDCURRENTALPHA      0x00008000
#define D3DTEXOPCAPS_PREMODULATE            0x00010000
#define D3DTEXOPCAPS_MODULATEALPHA_ADDCOLOR 0x00020000
#define D3DTEXOPCAPS_MODULATECOLOR_ADDALPHA 0x00040000
#define D3DTEXOPCAPS_MODULATEINVALPHA_ADDCOLOR 0x00080000
#define D3DTEXOPCAPS_MODULATEINVCOLOR_ADDALPHA 0x00100000
#define D3DTEXOPCAPS_BUMPENVMAP             0x00200000
#define D3DTEXOPCAPS_BUMPENVMAPLUMINANCE    0x00400000
#define D3DTEXOPCAPS_DOTPRODUCT3            0x00800000

/* Z-buffer types */
typedef enum _D3DZBUFFERTYPE {
    D3DZB_FALSE = 0,
    D3DZB_TRUE = 1,
    D3DZB_USEW = 2,
} D3DZBUFFERTYPE;

/* D3D enumeration return values */
#define D3DENUMRET_CANCEL                   DDENUMRET_CANCEL
#define D3DENUMRET_OK                       DDENUMRET_OK

/* D3DPRIMCAPS - Primitive capabilities */
typedef struct _D3DPRIMCAPS {
    DWORD dwSize;
    DWORD dwMiscCaps;
    DWORD dwRasterCaps;
    DWORD dwZCmpCaps;
    DWORD dwSrcBlendCaps;
    DWORD dwDestBlendCaps;
    DWORD dwAlphaCmpCaps;
    DWORD dwShadeCaps;
    DWORD dwTextureCaps;
    DWORD dwTextureFilterCaps;
    DWORD dwTextureBlendCaps;
    DWORD dwTextureAddressCaps;
    DWORD dwStippleWidth;
    DWORD dwStippleHeight;
} D3DPRIMCAPS, *LPD3DPRIMCAPS;

/* D3DTRANSFORMCAPS */
typedef struct _D3DTRANSFORMCAPS {
    DWORD dwSize;
    DWORD dwCaps;
} D3DTRANSFORMCAPS, *LPD3DTRANSFORMCAPS;

/* D3DLIGHTINGCAPS */
typedef struct _D3DLIGHTINGCAPS {
    DWORD dwSize;
    DWORD dwCaps;
    DWORD dwLightingModel;
    DWORD dwNumLights;
} D3DLIGHTINGCAPS, *LPD3DLIGHTINGCAPS;

/* Device description (DirectX 7) */
typedef struct _D3DDeviceDesc7 {
    DWORD dwDevCaps;
    D3DPRIMCAPS dpcLineCaps;
    D3DPRIMCAPS dpcTriCaps;
    DWORD dwDeviceRenderBitDepth;
    DWORD dwDeviceZBufferBitDepth;
    DWORD dwMinTextureWidth, dwMinTextureHeight;
    DWORD dwMaxTextureWidth, dwMaxTextureHeight;
    DWORD dwMaxTextureRepeat;
    DWORD dwMaxTextureAspectRatio;
    DWORD dwMaxAnisotropy;
    float dvGuardBandLeft;
    float dvGuardBandTop;
    float dvGuardBandRight;
    float dvGuardBandBottom;
    float dvExtentsAdjust;
    DWORD dwStencilCaps;
    DWORD dwFVFCaps;
    DWORD dwTextureOpCaps;
    WORD wMaxTextureBlendStages;
    WORD wMaxSimultaneousTextures;
    DWORD dwMaxActiveLights;
    float dvMaxVertexW;
    GUID deviceGUID;
    WORD wMaxUserClipPlanes;
    WORD wMaxVertexBlendMatrices;
    DWORD dwVertexProcessingCaps;
    DWORD dwReserved1;
    DWORD dwReserved2;
    DWORD dwReserved3;
    DWORD dwReserved4;
} D3DDEVICEDESC7, *LPD3DDEVICEDESC7;

/* Legacy D3DDEVICEDESC for older code */
typedef struct _D3DDeviceDesc {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dcmColorModel;
    DWORD dwDevCaps;
    D3DTRANSFORMCAPS dtcTransformCaps;
    BOOL bClipping;
    D3DLIGHTINGCAPS dlcLightingCaps;
    D3DPRIMCAPS dpcLineCaps;
    D3DPRIMCAPS dpcTriCaps;
    DWORD dwDeviceRenderBitDepth;
    DWORD dwDeviceZBufferBitDepth;
    DWORD dwMaxBufferSize;
    DWORD dwMaxVertexCount;
} D3DDEVICEDESC, *LPD3DDEVICEDESC;

/* D3DX Surface format enumeration */
typedef enum _D3DX_SURFACEFORMAT {
    D3DX_SF_UNKNOWN = 0,
    D3DX_SF_R8G8B8 = 1,
    D3DX_SF_A8R8G8B8 = 2,
    D3DX_SF_X8R8G8B8 = 3,
    D3DX_SF_R5G6B5 = 4,
    D3DX_SF_R5G5B5 = 5,
    D3DX_SF_PALETTE8 = 6,
    D3DX_SF_PALETTE4 = 7,
    D3DX_SF_A1R5G5B5 = 8,
    D3DX_SF_X1R5G5B5 = 9,
    D3DX_SF_A4R4G4B4 = 10,
    D3DX_SF_X4R4G4B4 = 11,
    D3DX_SF_A8 = 12,
    D3DX_SF_L8 = 13,
    D3DX_SF_A8L8 = 14,
    D3DX_SF_A4L4 = 15,
    D3DX_SF_DXT1 = 16,
    D3DX_SF_DXT2 = 17,
    D3DX_SF_DXT3 = 18,
    D3DX_SF_DXT4 = 19,
    D3DX_SF_DXT5 = 20,
    D3DX_SF_FORCE_DWORD = 0x7fffffff
} D3DX_SURFACEFORMAT;

/* Backward compatibility - same enum but different name */
typedef D3DX_SURFACEFORMAT _D3DX_SURFACEFORMAT;

/* D3DXMakeSurfaceFormat - convert pixel format to D3DX surface format */
static inline D3DX_SURFACEFORMAT D3DXMakeSurfaceFormat(LPDDPIXELFORMAT lpddpf) {
    if (!lpddpf) return D3DX_SF_UNKNOWN;

    if (lpddpf->dwFlags & DDPF_FOURCC) {
        switch (lpddpf->dwFourCC) {
            case MAKEFOURCC('D','X','T','1'): return D3DX_SF_DXT1;
            case MAKEFOURCC('D','X','T','2'): return D3DX_SF_DXT2;
            case MAKEFOURCC('D','X','T','3'): return D3DX_SF_DXT3;
            case MAKEFOURCC('D','X','T','4'): return D3DX_SF_DXT4;
            case MAKEFOURCC('D','X','T','5'): return D3DX_SF_DXT5;
            default: return D3DX_SF_UNKNOWN;
        }
    }

    if (lpddpf->dwFlags & DDPF_RGB) {
        switch (lpddpf->dwRGBBitCount) {
            case 32: return (lpddpf->dwFlags & DDPF_ALPHAPIXELS) ? D3DX_SF_A8R8G8B8 : D3DX_SF_X8R8G8B8;
            case 24: return D3DX_SF_R8G8B8;
            case 16:
                if (lpddpf->dwGBitMask == 0x07E0) return D3DX_SF_R5G6B5;
                if (lpddpf->dwFlags & DDPF_ALPHAPIXELS) {
                    if (lpddpf->dwRGBAlphaBitMask == 0x8000) return D3DX_SF_A1R5G5B5;
                    if (lpddpf->dwRGBAlphaBitMask == 0xF000) return D3DX_SF_A4R4G4B4;
                    return D3DX_SF_X1R5G5B5;
                }
                return D3DX_SF_R5G5B5;
            default: return D3DX_SF_UNKNOWN;
        }
    }

    if (lpddpf->dwFlags & DDPF_LUMINANCE) {
        if (lpddpf->dwFlags & DDPF_ALPHAPIXELS) return D3DX_SF_A8L8;
        return D3DX_SF_L8;
    }

    if (lpddpf->dwFlags & DDPF_ALPHA) return D3DX_SF_A8;

    if (lpddpf->dwFlags & DDPF_PALETTEINDEXED8) return D3DX_SF_PALETTE8;
    if (lpddpf->dwFlags & DDPF_PALETTEINDEXED4) return D3DX_SF_PALETTE4;

    return D3DX_SF_UNKNOWN;
}

/* D3DX constants */
#define D3DX_TEXTURE_NOMIPMAP       0
#define D3DX_FT_LINEAR              0x00000002

/* D3D Device Info structures */
typedef struct _D3DDEVINFO_TEXTUREMANAGER {
    BOOL bThrashing;
    DWORD dwApproxBytesDownloaded;
    DWORD dwNumEvicts;
    DWORD dwNumVidCreates;
    DWORD dwNumTexturesUsed;
    DWORD dwNumUsedTexInVid;
    DWORD dwWorkingSet;
    DWORD dwWorkingSetBytes;
    DWORD dwTotalManaged;
    DWORD dwTotalBytes;
    DWORD dwLastPri;
} D3DDEVINFO_TEXTUREMANAGER, *LPD3DDEVINFO_TEXTUREMANAGER;

typedef struct _D3DDEVINFO_TEXTURING {
    DWORD dwNumLoads;
    DWORD dwApproxBytesLoaded;
    DWORD dwNumPreLoads;
    DWORD dwNumSet;
    DWORD dwNumCreates;
    DWORD dwNumDestroys;
    DWORD dwNumSetPriorities;
    DWORD dwNumSetLODs;
    DWORD dwNumLocks;
    DWORD dwNumGetDCs;
} D3DDEVINFO_TEXTURING, *LPD3DDEVINFO_TEXTURING;

#define D3DDEVINFOID_TEXTUREMANAGER     1
#define D3DDEVINFOID_TEXTURING          3

/* D3DX function stubs */
#ifdef __cplusplus
extern "C++" {
struct IDirectDrawSurface7;  /* Forward declaration */

/* D3DXCreateTexture stub - returns failure */
static inline HRESULT D3DXCreateTexture(
    void* pDevice,
    DWORD* pFlags,
    DWORD* pWidth,
    DWORD* pHeight,
    D3DX_SURFACEFORMAT* pFormat,
    void* pDDPalette,
    IDirectDrawSurface7** ppDDSurface,
    DWORD* pNumMips
) {
    (void)pDevice; (void)pFlags; (void)pWidth; (void)pHeight;
    (void)pFormat; (void)pDDPalette; (void)ppDDSurface; (void)pNumMips;
    if (ppDDSurface) *ppDDSurface = NULL;
    return E_NOTIMPL;
}

/* D3DXLoadTextureFromMemory stub - returns failure
 * Parameters: pDevice, pSurface, mipLevel, pSrcData, pSrcRect, srcFormat, srcPitch, pDestRect, dwFilter
 */
static inline HRESULT D3DXLoadTextureFromMemory(
    void* pDevice,
    IDirectDrawSurface7* pDDSurface,
    DWORD dwMipLevel,
    LPCVOID pSrcData,
    void* pSrcRect,
    D3DX_SURFACEFORMAT srcFormat,
    DWORD cbSrcPitch,
    void* pDestRect,
    DWORD dwFilter
) {
    (void)pDevice; (void)pDDSurface; (void)dwMipLevel;
    (void)pSrcData; (void)pSrcRect; (void)srcFormat; (void)cbSrcPitch; (void)pDestRect; (void)dwFilter;
    return E_NOTIMPL;
}
} /* extern "C++" */
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_D3DTYPES_H */
