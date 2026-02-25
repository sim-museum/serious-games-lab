/*
 * FreeFalcon Linux Port - Direct3D stub
 *
 * Direct3D interfaces will be replaced by OpenGL
 */

#ifndef FF_COMPAT_D3D_H
#define FF_COMPAT_D3D_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "ddraw.h"
#include "d3dtypes.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Direct3D Device GUIDs
 * ============================================================ */

/* RGB software rasterizer */
static const GUID IID_IDirect3DRGBDevice =
    {0xa4665c60, 0x2673, 0x11cf, {0xa3, 0x1a, 0x00, 0xaa, 0x00, 0xb9, 0x33, 0x56}};

/* HAL (Hardware Abstraction Layer) device */
static const GUID IID_IDirect3DHALDevice =
    {0x84e63de0, 0x46aa, 0x11cf, {0x81, 0x6f, 0x00, 0x00, 0xc0, 0x20, 0x15, 0x6e}};

/* MMX software rasterizer */
static const GUID IID_IDirect3DMMXDevice =
    {0x881949a1, 0xd6f3, 0x11d0, {0x89, 0xab, 0x00, 0xa0, 0xc9, 0x05, 0x41, 0x29}};

/* Reference (REF) device - software reference rasterizer */
static const GUID IID_IDirect3DRefDevice =
    {0x50936643, 0x13e9, 0x11d1, {0x89, 0xaa, 0x00, 0xa0, 0xc9, 0x05, 0x41, 0x29}};

/* Null device */
static const GUID IID_IDirect3DNullDevice =
    {0x8767df22, 0xbacc, 0x11d1, {0x89, 0x69, 0x00, 0xa0, 0xc9, 0x06, 0x29, 0xa8}};

/* TnL (Transform and Lighting) HAL device - hardware T&L support */
static const GUID IID_IDirect3DTnLHalDevice =
    {0xf5049e78, 0x4861, 0x11d2, {0xa4, 0x07, 0x00, 0xa0, 0xc9, 0x06, 0x29, 0xa8}};

/* Ramp software rasterizer (legacy) */
static const GUID IID_IDirect3DRampDevice =
    {0xf2086b20, 0x259f, 0x11cf, {0xa3, 0x1a, 0x00, 0xaa, 0x00, 0xb9, 0x33, 0x56}};

/* D3DVAL macro */
#ifndef D3DVAL
#define D3DVAL(val) ((D3DVALUE)(val))
#endif

/* Material color source values (D3DMCS_*) */
typedef enum _D3DMATERIALCOLORSOURCE {
    D3DMCS_MATERIAL = 0,
    D3DMCS_COLOR1 = 1,
    D3DMCS_COLOR2 = 2,
} D3DMATERIALCOLORSOURCE;

/* State block types (D3DSBT_*) */
typedef enum _D3DSTATEBLOCKTYPE {
    D3DSBT_ALL = 1,
    D3DSBT_PIXELSTATE = 2,
    D3DSBT_VERTEXSTATE = 3,
} D3DSTATEBLOCKTYPE;

/* D3D status flags */
#define D3DSTATUS_DEFAULT           0x00000000
#define D3DSTATUS_CLIPUNIONLEFT     0x00000001
#define D3DSTATUS_CLIPUNIONRIGHT    0x00000002
#define D3DSTATUS_CLIPUNIONTOP      0x00000004
#define D3DSTATUS_CLIPUNIONBOTTOM   0x00000008
#define D3DSTATUS_CLIPUNIONFRONT    0x00000010
#define D3DSTATUS_CLIPUNIONBACK     0x00000020
#define D3DSTATUS_CLIPUNIONGEN0     0x00000040
#define D3DSTATUS_CLIPUNIONGEN1     0x00000080
#define D3DSTATUS_CLIPUNIONGEN2     0x00000100
#define D3DSTATUS_CLIPUNIONGEN3     0x00000200
#define D3DSTATUS_CLIPUNIONGEN4     0x00000400
#define D3DSTATUS_CLIPUNIONGEN5     0x00000800
#define D3DSTATUS_CLIPUNIONALL      0x00000fff

/* Vertex buffer capability flags */
#define D3DVBCAPS_SYSTEMMEMORY          0x00000800
#define D3DVBCAPS_WRITEONLY             0x00010000
#define D3DVBCAPS_OPTIMIZED             0x80000000
#define D3DVBCAPS_DONOTCLIP             0x00000001

/* D3DVERTEXBUFFERDESC - Vertex buffer descriptor */
typedef struct _D3DVERTEXBUFFERDESC {
    DWORD dwSize;
    DWORD dwCaps;
    DWORD dwFVF;
    DWORD dwNumVertices;
} D3DVERTEXBUFFERDESC, *LPD3DVERTEXBUFFERDESC;

/* D3D error codes */
#define D3D_OK                          S_OK
#define D3DERR_BADMAJORVERSION          0x88760000
#define D3DERR_BADMINORVERSION          0x88760001
#define D3DERR_INVALID_DEVICE           0x88760002
#define D3DERR_INITFAILED               0x88760003
#define D3DERR_DEVICEAGGREGATED         0x88760004
#define D3DERR_EXECUTE_CREATE_FAILED    0x88760005
#define D3DERR_EXECUTE_DESTROY_FAILED   0x88760006
#define D3DERR_EXECUTE_LOCK_FAILED      0x88760007
#define D3DERR_EXECUTE_UNLOCK_FAILED    0x88760008
#define D3DERR_EXECUTE_LOCKED           0x88760009
#define D3DERR_EXECUTE_NOT_LOCKED       0x8876000a
#define D3DERR_EXECUTE_FAILED           0x8876000b
#define D3DERR_EXECUTE_CLIPPED_FAILED   0x8876000c
#define D3DERR_TEXTURE_NO_SUPPORT       0x8876000d
#define D3DERR_TEXTURE_CREATE_FAILED    0x8876000e
#define D3DERR_TEXTURE_DESTROY_FAILED   0x8876000f
#define D3DERR_TEXTURE_LOCK_FAILED      0x88760010
#define D3DERR_TEXTURE_UNLOCK_FAILED    0x88760011
#define D3DERR_TEXTURE_LOAD_FAILED      0x88760012
#define D3DERR_TEXTURE_SWAP_FAILED      0x88760013
#define D3DERR_TEXTURE_LOCKED           0x88760014
#define D3DERR_TEXTURE_NOT_LOCKED       0x88760015
#define D3DERR_TEXTURE_GETSURF_FAILED   0x88760016
#define D3DERR_MATRIX_CREATE_FAILED     0x88760017
#define D3DERR_MATRIX_DESTROY_FAILED    0x88760018
#define D3DERR_MATRIX_SETDATA_FAILED    0x88760019
#define D3DERR_MATRIX_GETDATA_FAILED    0x8876001a
#define D3DERR_SETVIEWPORTDATA_FAILED   0x8876001b
#define D3DERR_INVALIDCURRENTVIEWPORT   0x8876001c
#define D3DERR_INVALIDPRIMITIVETYPE     0x8876001d
#define D3DERR_INVALIDVERTEXTYPE        0x8876001e
#define D3DERR_TEXTURE_BADSIZE          0x8876001f
#define D3DERR_INVALIDRAMPTEXTURE       0x88760020
#define D3DERR_MATERIAL_CREATE_FAILED   0x88760021
#define D3DERR_MATERIAL_DESTROY_FAILED  0x88760022
#define D3DERR_MATERIAL_SETDATA_FAILED  0x88760023
#define D3DERR_MATERIAL_GETDATA_FAILED  0x88760024
#define D3DERR_INVALIDPALETTE           0x88760025
#define D3DERR_ZBUFF_NEEDS_SYSTEMMEMORY 0x88760026
#define D3DERR_ZBUFF_NEEDS_VIDEOMEMORY  0x88760027
#define D3DERR_SURFACENOTINVIDMEM       0x88760028
#define D3DERR_LIGHT_SET_FAILED         0x88760029
#define D3DERR_LIGHTHASVIEWPORT         0x8876002a
#define D3DERR_LIGHTNOTINTHISVIEWPORT   0x8876002b
#define D3DERR_SCENE_IN_SCENE           0x8876002c
#define D3DERR_SCENE_NOT_IN_SCENE       0x8876002d
#define D3DERR_SCENE_BEGIN_FAILED       0x8876002e
#define D3DERR_SCENE_END_FAILED         0x8876002f
#define D3DERR_INBEGIN                  0x88760030
#define D3DERR_NOTINBEGIN               0x88760031
#define D3DERR_NOVIEWPORTS              0x88760032
#define D3DERR_VIEWPORTDATANOTSET       0x88760033
#define D3DERR_VIEWPORTHASNODEVICE      0x88760034
#define D3DERR_NOCURRENTVIEWPORT        0x88760035
#define D3DERR_INVALIDVERTEXFORMAT      0x88760036
#define D3DERR_COLORKEYATTACHED         0x88760037
#define D3DERR_VERTEXBUFFEROPTIMIZED    0x88760038
#define D3DERR_VBUF_CREATE_FAILED       0x88760039
#define D3DERR_VERTEXBUFFERLOCKED       0x8876003a
#define D3DERR_VERTEXBUFFERUNLOCKFAILED 0x8876003b
#define D3DERR_ZBUFFER_NOTPRESENT       0x8876003c
#define D3DERR_STENCILBUFFER_NOTPRESENT 0x8876003d

#define D3DERR_WRONGTEXTUREFORMAT       0x88760100
#define D3DERR_UNSUPPORTEDCOLOROPERATION 0x88760101
#define D3DERR_UNSUPPORTEDCOLORARG      0x88760102
#define D3DERR_UNSUPPORTEDALPHAOPERATION 0x88760103
#define D3DERR_UNSUPPORTEDALPHAARG      0x88760104
#define D3DERR_TOOMANYOPERATIONS        0x88760105
#define D3DERR_CONFLICTINGTEXTUREFILTER 0x88760106
#define D3DERR_UNSUPPORTEDFACTORVALUE   0x88760107
#define D3DERR_CONFLICTINGRENDERSTATE   0x88760108
#define D3DERR_UNSUPPORTEDTEXTUREFILTER 0x88760109
#define D3DERR_CONFLICTINGTEXTUREPALETTE 0x8876010a
#define D3DERR_DRIVERINTERNALERROR      0x8876010b

/* Forward declarations */
struct IDirect3D7;
struct IDirect3DDevice7;
struct IDirect3DVertexBuffer7;
struct IDirect3DTexture2;

typedef struct IDirect3D7 *LPDIRECT3D7;
typedef struct IDirect3DDevice7 *LPDIRECT3DDEVICE7;
typedef struct IDirect3DVertexBuffer7 *LPDIRECT3DVERTEXBUFFER7;
typedef struct IDirect3DTexture2 *LPDIRECT3DTEXTURE2;

/* ============================================================
 * IDirect3DDevice7 interface stub
 * This is a minimal stub - will be replaced by OpenGL renderer
 * ============================================================ */
typedef struct IDirect3DDevice7Vtbl {
    /* IUnknown methods */
    HRESULT (*QueryInterface)(struct IDirect3DDevice7 *This, REFIID riid, void **ppvObject);
    ULONG (*AddRef)(struct IDirect3DDevice7 *This);
    ULONG (*Release)(struct IDirect3DDevice7 *This);

    /* IDirect3DDevice7 methods */
    HRESULT (*GetCaps)(struct IDirect3DDevice7 *This, LPD3DDEVICEDESC7 lpD3DDevDesc);
    HRESULT (*EnumTextureFormats)(struct IDirect3DDevice7 *This, void *lpd3dEnumPixelProc, LPVOID lpArg);
    HRESULT (*BeginScene)(struct IDirect3DDevice7 *This);
    HRESULT (*EndScene)(struct IDirect3DDevice7 *This);
    HRESULT (*GetDirect3D)(struct IDirect3DDevice7 *This, LPDIRECT3D7 *lplpD3D);
    HRESULT (*SetRenderTarget)(struct IDirect3DDevice7 *This, LPDIRECTDRAWSURFACE7 lpNewRenderTarget, DWORD dwFlags);
    HRESULT (*GetRenderTarget)(struct IDirect3DDevice7 *This, LPDIRECTDRAWSURFACE7 *lplpRenderTarget);
    HRESULT (*Clear)(struct IDirect3DDevice7 *This, DWORD dwCount, LPD3DRECT lpRects, DWORD dwFlags, D3DCOLOR dwColor, D3DVALUE dvZ, DWORD dwStencil);
    HRESULT (*SetTransform)(struct IDirect3DDevice7 *This, D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix);
    HRESULT (*GetTransform)(struct IDirect3DDevice7 *This, D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix);
    HRESULT (*SetViewport)(struct IDirect3DDevice7 *This, LPD3DVIEWPORT7 lpViewport);
    HRESULT (*MultiplyTransform)(struct IDirect3DDevice7 *This, D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix);
    HRESULT (*GetViewport)(struct IDirect3DDevice7 *This, LPD3DVIEWPORT7 lpViewport);
    HRESULT (*SetMaterial)(struct IDirect3DDevice7 *This, LPD3DMATERIAL7 lpMaterial);
    HRESULT (*GetMaterial)(struct IDirect3DDevice7 *This, LPD3DMATERIAL7 lpMaterial);
    HRESULT (*SetLight)(struct IDirect3DDevice7 *This, DWORD dwLightIndex, LPD3DLIGHT7 lpLight);
    HRESULT (*GetLight)(struct IDirect3DDevice7 *This, DWORD dwLightIndex, LPD3DLIGHT7 lpLight);
    HRESULT (*SetRenderState)(struct IDirect3DDevice7 *This, D3DRENDERSTATETYPE dwRenderStateType, DWORD dwRenderState);
    HRESULT (*GetRenderState)(struct IDirect3DDevice7 *This, D3DRENDERSTATETYPE dwRenderStateType, LPDWORD lpdwRenderState);
    HRESULT (*BeginStateBlock)(struct IDirect3DDevice7 *This);
    HRESULT (*EndStateBlock)(struct IDirect3DDevice7 *This, LPDWORD lpdwBlockHandle);
    HRESULT (*PreLoad)(struct IDirect3DDevice7 *This, LPDIRECTDRAWSURFACE7 lpddsTexture);
    HRESULT (*DrawPrimitive)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, DWORD dwFlags);
    HRESULT (*DrawIndexedPrimitive)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags);
    HRESULT (*SetClipStatus)(struct IDirect3DDevice7 *This, void *lpD3DClipStatus);
    HRESULT (*GetClipStatus)(struct IDirect3DDevice7 *This, void *lpD3DClipStatus);
    HRESULT (*DrawPrimitiveStrided)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, void *lpVertexArray, DWORD dwVertexCount, DWORD dwFlags);
    HRESULT (*DrawIndexedPrimitiveStrided)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, void *lpVertexArray, DWORD dwVertexCount, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags);
    HRESULT (*DrawPrimitiveVB)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, DWORD dwFlags);
    HRESULT (*DrawIndexedPrimitiveVB)(struct IDirect3DDevice7 *This, D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags);
    HRESULT (*ComputeSphereVisibility)(struct IDirect3DDevice7 *This, LPD3DVECTOR lpCenters, LPD3DVALUE lpRadii, DWORD dwNumSpheres, DWORD dwFlags, LPDWORD lpdwReturnValues);
    HRESULT (*GetTexture)(struct IDirect3DDevice7 *This, DWORD dwStage, LPDIRECTDRAWSURFACE7 *lplpTexture);
    HRESULT (*SetTexture)(struct IDirect3DDevice7 *This, DWORD dwStage, LPDIRECTDRAWSURFACE7 lpTexture);
    HRESULT (*GetTextureStageState)(struct IDirect3DDevice7 *This, DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, LPDWORD lpdwState);
    HRESULT (*SetTextureStageState)(struct IDirect3DDevice7 *This, DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, DWORD dwState);
    HRESULT (*ValidateDevice)(struct IDirect3DDevice7 *This, LPDWORD lpdwPasses);
    HRESULT (*ApplyStateBlock)(struct IDirect3DDevice7 *This, DWORD dwBlockHandle);
    HRESULT (*CaptureStateBlock)(struct IDirect3DDevice7 *This, DWORD dwBlockHandle);
    HRESULT (*DeleteStateBlock)(struct IDirect3DDevice7 *This, DWORD dwBlockHandle);
    HRESULT (*CreateStateBlock)(struct IDirect3DDevice7 *This, DWORD d3dsbType, LPDWORD lpdwBlockHandle);
    HRESULT (*Load)(struct IDirect3DDevice7 *This, LPDIRECTDRAWSURFACE7 lpDestTex, LPPOINT lpDestPoint, LPDIRECTDRAWSURFACE7 lpSrcTex, LPRECT lprcSrcRect, DWORD dwFlags);
    HRESULT (*LightEnable)(struct IDirect3DDevice7 *This, DWORD dwLightIndex, BOOL bEnable);
    HRESULT (*GetLightEnable)(struct IDirect3DDevice7 *This, DWORD dwLightIndex, BOOL *pbEnable);
    HRESULT (*SetClipPlane)(struct IDirect3DDevice7 *This, DWORD dwIndex, D3DVALUE *pPlaneEquation);
    HRESULT (*GetClipPlane)(struct IDirect3DDevice7 *This, DWORD dwIndex, D3DVALUE *pPlaneEquation);
    HRESULT (*GetInfo)(struct IDirect3DDevice7 *This, DWORD dwDevInfoID, LPVOID pDevInfoStruct, DWORD dwSize);
} IDirect3DDevice7Vtbl;

struct IDirect3DDevice7 {
    const IDirect3DDevice7Vtbl *lpVtbl;

#ifdef __cplusplus
    /* C++ helper methods that forward to vtbl */
    HRESULT QueryInterface(REFIID riid, void **ppvObject) { return lpVtbl->QueryInterface(this, riid, ppvObject); }
    ULONG AddRef() { return lpVtbl->AddRef(this); }
    ULONG Release() { return lpVtbl->Release(this); }
    HRESULT GetCaps(LPD3DDEVICEDESC7 lpD3DDevDesc) { return lpVtbl->GetCaps(this, lpD3DDevDesc); }
    HRESULT BeginScene() { return lpVtbl->BeginScene(this); }
    HRESULT EndScene() { return lpVtbl->EndScene(this); }
    HRESULT GetDirect3D(LPDIRECT3D7 *lplpD3D) { return lpVtbl->GetDirect3D(this, lplpD3D); }
    HRESULT SetRenderTarget(LPDIRECTDRAWSURFACE7 lpNewRenderTarget, DWORD dwFlags) { return lpVtbl->SetRenderTarget(this, lpNewRenderTarget, dwFlags); }
    HRESULT GetRenderTarget(LPDIRECTDRAWSURFACE7 *lplpRenderTarget) { return lpVtbl->GetRenderTarget(this, lplpRenderTarget); }
    HRESULT Clear(DWORD dwCount, LPD3DRECT lpRects, DWORD dwFlags, D3DCOLOR dwColor, D3DVALUE dvZ, DWORD dwStencil) { return lpVtbl->Clear(this, dwCount, lpRects, dwFlags, dwColor, dvZ, dwStencil); }
    HRESULT SetTransform(D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix) { return lpVtbl->SetTransform(this, dtstTransformStateType, lpD3DMatrix); }
    HRESULT GetTransform(D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix) { return lpVtbl->GetTransform(this, dtstTransformStateType, lpD3DMatrix); }
    HRESULT SetViewport(LPD3DVIEWPORT7 lpViewport) { return lpVtbl->SetViewport(this, lpViewport); }
    HRESULT MultiplyTransform(D3DTRANSFORMSTATETYPE dtstTransformStateType, LPD3DMATRIX lpD3DMatrix) { return lpVtbl->MultiplyTransform(this, dtstTransformStateType, lpD3DMatrix); }
    HRESULT GetViewport(LPD3DVIEWPORT7 lpViewport) { return lpVtbl->GetViewport(this, lpViewport); }
    HRESULT SetMaterial(LPD3DMATERIAL7 lpMaterial) { return lpVtbl->SetMaterial(this, lpMaterial); }
    HRESULT GetMaterial(LPD3DMATERIAL7 lpMaterial) { return lpVtbl->GetMaterial(this, lpMaterial); }
    HRESULT SetLight(DWORD dwLightIndex, LPD3DLIGHT7 lpLight) { return lpVtbl->SetLight(this, dwLightIndex, lpLight); }
    HRESULT GetLight(DWORD dwLightIndex, LPD3DLIGHT7 lpLight) { return lpVtbl->GetLight(this, dwLightIndex, lpLight); }
    HRESULT SetRenderState(D3DRENDERSTATETYPE dwRenderStateType, DWORD dwRenderState) { return lpVtbl->SetRenderState(this, dwRenderStateType, dwRenderState); }
    HRESULT GetRenderState(D3DRENDERSTATETYPE dwRenderStateType, LPDWORD lpdwRenderState) { return lpVtbl->GetRenderState(this, dwRenderStateType, lpdwRenderState); }
    HRESULT BeginStateBlock() { return lpVtbl->BeginStateBlock(this); }
    HRESULT EndStateBlock(LPDWORD lpdwBlockHandle) { return lpVtbl->EndStateBlock(this, lpdwBlockHandle); }
    HRESULT PreLoad(LPDIRECTDRAWSURFACE7 lpddsTexture) { return lpVtbl->PreLoad(this, lpddsTexture); }
    HRESULT DrawPrimitive(D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, DWORD dwFlags) { return lpVtbl->DrawPrimitive(this, dptPrimitiveType, dwVertexTypeDesc, lpvVertices, dwVertexCount, dwFlags); }
    HRESULT DrawIndexedPrimitive(D3DPRIMITIVETYPE dptPrimitiveType, DWORD dwVertexTypeDesc, LPVOID lpvVertices, DWORD dwVertexCount, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags) { return lpVtbl->DrawIndexedPrimitive(this, dptPrimitiveType, dwVertexTypeDesc, lpvVertices, dwVertexCount, lpwIndices, dwIndexCount, dwFlags); }
    HRESULT DrawPrimitiveVB(D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, DWORD dwFlags) { return lpVtbl->DrawPrimitiveVB(this, dptPrimitiveType, lpd3dVertexBuffer, dwStartVertex, dwNumVertices, dwFlags); }
    HRESULT DrawIndexedPrimitiveVB(D3DPRIMITIVETYPE dptPrimitiveType, LPDIRECT3DVERTEXBUFFER7 lpd3dVertexBuffer, DWORD dwStartVertex, DWORD dwNumVertices, LPWORD lpwIndices, DWORD dwIndexCount, DWORD dwFlags) { return lpVtbl->DrawIndexedPrimitiveVB(this, dptPrimitiveType, lpd3dVertexBuffer, dwStartVertex, dwNumVertices, lpwIndices, dwIndexCount, dwFlags); }
    HRESULT ComputeSphereVisibility(LPD3DVECTOR lpCenters, LPD3DVALUE lpRadii, DWORD dwNumSpheres, DWORD dwFlags, LPDWORD lpdwReturnValues) { return lpVtbl->ComputeSphereVisibility(this, lpCenters, lpRadii, dwNumSpheres, dwFlags, lpdwReturnValues); }
    HRESULT GetTexture(DWORD dwStage, LPDIRECTDRAWSURFACE7 *lplpTexture) { return lpVtbl->GetTexture(this, dwStage, lplpTexture); }
    HRESULT SetTexture(DWORD dwStage, LPDIRECTDRAWSURFACE7 lpTexture) { return lpVtbl->SetTexture(this, dwStage, lpTexture); }
    HRESULT GetTextureStageState(DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, LPDWORD lpdwState) { return lpVtbl->GetTextureStageState(this, dwStage, d3dTexStageStateType, lpdwState); }
    HRESULT SetTextureStageState(DWORD dwStage, D3DTEXTURESTAGESTATETYPE d3dTexStageStateType, DWORD dwState) { return lpVtbl->SetTextureStageState(this, dwStage, d3dTexStageStateType, dwState); }
    HRESULT ValidateDevice(LPDWORD lpdwPasses) { return lpVtbl->ValidateDevice(this, lpdwPasses); }
    HRESULT ApplyStateBlock(DWORD dwBlockHandle) { return lpVtbl->ApplyStateBlock(this, dwBlockHandle); }
    HRESULT CaptureStateBlock(DWORD dwBlockHandle) { return lpVtbl->CaptureStateBlock(this, dwBlockHandle); }
    HRESULT DeleteStateBlock(DWORD dwBlockHandle) { return lpVtbl->DeleteStateBlock(this, dwBlockHandle); }
    HRESULT CreateStateBlock(DWORD d3dsbType, LPDWORD lpdwBlockHandle) { return lpVtbl->CreateStateBlock(this, d3dsbType, lpdwBlockHandle); }
    HRESULT Load(LPDIRECTDRAWSURFACE7 lpDestTex, LPPOINT lpDestPoint, LPDIRECTDRAWSURFACE7 lpSrcTex, LPRECT lprcSrcRect, DWORD dwFlags) { return lpVtbl->Load(this, lpDestTex, lpDestPoint, lpSrcTex, lprcSrcRect, dwFlags); }
    HRESULT LightEnable(DWORD dwLightIndex, BOOL bEnable) { return lpVtbl->LightEnable(this, dwLightIndex, bEnable); }
    HRESULT GetLightEnable(DWORD dwLightIndex, BOOL *pbEnable) { return lpVtbl->GetLightEnable(this, dwLightIndex, pbEnable); }
    HRESULT SetClipPlane(DWORD dwIndex, D3DVALUE *pPlaneEquation) { return lpVtbl->SetClipPlane(this, dwIndex, pPlaneEquation); }
    HRESULT GetClipPlane(DWORD dwIndex, D3DVALUE *pPlaneEquation) { return lpVtbl->GetClipPlane(this, dwIndex, pPlaneEquation); }
    HRESULT GetInfo(DWORD dwDevInfoID, LPVOID pDevInfoStruct, DWORD dwSize) { return lpVtbl->GetInfo(this, dwDevInfoID, pDevInfoStruct, dwSize); }
#endif
};

/* C++ style method macros */
#ifdef __cplusplus
#define IDirect3DDevice7_QueryInterface(p,a,b) (p)->lpVtbl->QueryInterface(p,a,b)
#define IDirect3DDevice7_AddRef(p) (p)->lpVtbl->AddRef(p)
#define IDirect3DDevice7_Release(p) (p)->lpVtbl->Release(p)
#define IDirect3DDevice7_GetCaps(p,a) (p)->lpVtbl->GetCaps(p,a)
#define IDirect3DDevice7_EnumTextureFormats(p,a,b) (p)->lpVtbl->EnumTextureFormats(p,a,b)
#define IDirect3DDevice7_BeginScene(p) (p)->lpVtbl->BeginScene(p)
#define IDirect3DDevice7_EndScene(p) (p)->lpVtbl->EndScene(p)
#define IDirect3DDevice7_GetDirect3D(p,a) (p)->lpVtbl->GetDirect3D(p,a)
#define IDirect3DDevice7_SetRenderTarget(p,a,b) (p)->lpVtbl->SetRenderTarget(p,a,b)
#define IDirect3DDevice7_GetRenderTarget(p,a) (p)->lpVtbl->GetRenderTarget(p,a)
#define IDirect3DDevice7_Clear(p,a,b,c,d,e,f) (p)->lpVtbl->Clear(p,a,b,c,d,e,f)
#define IDirect3DDevice7_SetTransform(p,a,b) (p)->lpVtbl->SetTransform(p,a,b)
#define IDirect3DDevice7_GetTransform(p,a,b) (p)->lpVtbl->GetTransform(p,a,b)
#define IDirect3DDevice7_SetViewport(p,a) (p)->lpVtbl->SetViewport(p,a)
#define IDirect3DDevice7_MultiplyTransform(p,a,b) (p)->lpVtbl->MultiplyTransform(p,a,b)
#define IDirect3DDevice7_GetViewport(p,a) (p)->lpVtbl->GetViewport(p,a)
#define IDirect3DDevice7_SetMaterial(p,a) (p)->lpVtbl->SetMaterial(p,a)
#define IDirect3DDevice7_GetMaterial(p,a) (p)->lpVtbl->GetMaterial(p,a)
#define IDirect3DDevice7_SetLight(p,a,b) (p)->lpVtbl->SetLight(p,a,b)
#define IDirect3DDevice7_GetLight(p,a,b) (p)->lpVtbl->GetLight(p,a,b)
#define IDirect3DDevice7_SetRenderState(p,a,b) (p)->lpVtbl->SetRenderState(p,a,b)
#define IDirect3DDevice7_GetRenderState(p,a,b) (p)->lpVtbl->GetRenderState(p,a,b)
#define IDirect3DDevice7_BeginStateBlock(p) (p)->lpVtbl->BeginStateBlock(p)
#define IDirect3DDevice7_EndStateBlock(p,a) (p)->lpVtbl->EndStateBlock(p,a)
#define IDirect3DDevice7_PreLoad(p,a) (p)->lpVtbl->PreLoad(p,a)
#define IDirect3DDevice7_DrawPrimitive(p,a,b,c,d,e) (p)->lpVtbl->DrawPrimitive(p,a,b,c,d,e)
#define IDirect3DDevice7_DrawIndexedPrimitive(p,a,b,c,d,e,f,g) (p)->lpVtbl->DrawIndexedPrimitive(p,a,b,c,d,e,f,g)
#define IDirect3DDevice7_SetClipStatus(p,a) (p)->lpVtbl->SetClipStatus(p,a)
#define IDirect3DDevice7_GetClipStatus(p,a) (p)->lpVtbl->GetClipStatus(p,a)
#define IDirect3DDevice7_DrawPrimitiveStrided(p,a,b,c,d,e) (p)->lpVtbl->DrawPrimitiveStrided(p,a,b,c,d,e)
#define IDirect3DDevice7_DrawIndexedPrimitiveStrided(p,a,b,c,d,e,f,g) (p)->lpVtbl->DrawIndexedPrimitiveStrided(p,a,b,c,d,e,f,g)
#define IDirect3DDevice7_DrawPrimitiveVB(p,a,b,c,d,e) (p)->lpVtbl->DrawPrimitiveVB(p,a,b,c,d,e)
#define IDirect3DDevice7_DrawIndexedPrimitiveVB(p,a,b,c,d,e,f,g) (p)->lpVtbl->DrawIndexedPrimitiveVB(p,a,b,c,d,e,f,g)
#define IDirect3DDevice7_ComputeSphereVisibility(p,a,b,c,d,e) (p)->lpVtbl->ComputeSphereVisibility(p,a,b,c,d,e)
#define IDirect3DDevice7_GetTexture(p,a,b) (p)->lpVtbl->GetTexture(p,a,b)
#define IDirect3DDevice7_SetTexture(p,a,b) (p)->lpVtbl->SetTexture(p,a,b)
#define IDirect3DDevice7_GetTextureStageState(p,a,b,c) (p)->lpVtbl->GetTextureStageState(p,a,b,c)
#define IDirect3DDevice7_SetTextureStageState(p,a,b,c) (p)->lpVtbl->SetTextureStageState(p,a,b,c)
#define IDirect3DDevice7_ValidateDevice(p,a) (p)->lpVtbl->ValidateDevice(p,a)
#define IDirect3DDevice7_ApplyStateBlock(p,a) (p)->lpVtbl->ApplyStateBlock(p,a)
#define IDirect3DDevice7_CaptureStateBlock(p,a) (p)->lpVtbl->CaptureStateBlock(p,a)
#define IDirect3DDevice7_DeleteStateBlock(p,a) (p)->lpVtbl->DeleteStateBlock(p,a)
#define IDirect3DDevice7_CreateStateBlock(p,a,b) (p)->lpVtbl->CreateStateBlock(p,a,b)
#define IDirect3DDevice7_Load(p,a,b,c,d,e) (p)->lpVtbl->Load(p,a,b,c,d,e)
#define IDirect3DDevice7_LightEnable(p,a,b) (p)->lpVtbl->LightEnable(p,a,b)
#define IDirect3DDevice7_GetLightEnable(p,a,b) (p)->lpVtbl->GetLightEnable(p,a,b)
#define IDirect3DDevice7_SetClipPlane(p,a,b) (p)->lpVtbl->SetClipPlane(p,a,b)
#define IDirect3DDevice7_GetClipPlane(p,a,b) (p)->lpVtbl->GetClipPlane(p,a,b)
#define IDirect3DDevice7_GetInfo(p,a,b,c) (p)->lpVtbl->GetInfo(p,a,b,c)
#endif

/* ============================================================
 * IDirect3DVertexBuffer7 interface stub
 * ============================================================ */
typedef struct IDirect3DVertexBuffer7Vtbl {
    /* IUnknown methods */
    HRESULT (*QueryInterface)(struct IDirect3DVertexBuffer7 *This, REFIID riid, void **ppvObject);
    ULONG (*AddRef)(struct IDirect3DVertexBuffer7 *This);
    ULONG (*Release)(struct IDirect3DVertexBuffer7 *This);

    /* IDirect3DVertexBuffer7 methods */
    HRESULT (*Lock)(struct IDirect3DVertexBuffer7 *This, DWORD dwFlags, LPVOID *lplpData, LPDWORD lpdwSize);
    HRESULT (*Unlock)(struct IDirect3DVertexBuffer7 *This);
    HRESULT (*ProcessVertices)(struct IDirect3DVertexBuffer7 *This, DWORD dwVertexOp, DWORD dwDestIndex, DWORD dwCount, struct IDirect3DVertexBuffer7 *lpSrcBuffer, DWORD dwSrcIndex, struct IDirect3DDevice7 *lpD3DDevice, DWORD dwFlags);
    HRESULT (*GetVertexBufferDesc)(struct IDirect3DVertexBuffer7 *This, LPD3DVERTEXBUFFERDESC lpVBDesc);
    HRESULT (*Optimize)(struct IDirect3DVertexBuffer7 *This, struct IDirect3DDevice7 *lpD3DDevice, DWORD dwFlags);
    HRESULT (*ProcessVerticesStrided)(struct IDirect3DVertexBuffer7 *This, DWORD dwVertexOp, DWORD dwDestIndex, DWORD dwCount, void *lpVertexArray, DWORD dwSrcIndex, struct IDirect3DDevice7 *lpD3DDevice, DWORD dwFlags);
} IDirect3DVertexBuffer7Vtbl;

struct IDirect3DVertexBuffer7 {
    const IDirect3DVertexBuffer7Vtbl *lpVtbl;

#ifdef __cplusplus
    HRESULT QueryInterface(REFIID riid, void **ppvObject) { return lpVtbl->QueryInterface(this, riid, ppvObject); }
    ULONG AddRef() { return lpVtbl->AddRef(this); }
    ULONG Release() { return lpVtbl->Release(this); }
    HRESULT Lock(DWORD dwFlags, LPVOID *lplpData, LPDWORD lpdwSize) { return lpVtbl->Lock(this, dwFlags, lplpData, lpdwSize); }
    HRESULT Unlock() { return lpVtbl->Unlock(this); }
    HRESULT GetVertexBufferDesc(LPD3DVERTEXBUFFERDESC lpVBDesc) { return lpVtbl->GetVertexBufferDesc(this, lpVBDesc); }
    HRESULT Optimize(struct IDirect3DDevice7 *lpD3DDevice, DWORD dwFlags) { return lpVtbl->Optimize(this, lpD3DDevice, dwFlags); }
#endif
};

/* ============================================================
 * IDirect3D7 interface stub
 * ============================================================ */
typedef struct IDirect3D7Vtbl {
    /* IUnknown methods */
    HRESULT (*QueryInterface)(struct IDirect3D7 *This, REFIID riid, void **ppvObject);
    ULONG (*AddRef)(struct IDirect3D7 *This);
    ULONG (*Release)(struct IDirect3D7 *This);

    /* IDirect3D7 methods */
    HRESULT (*EnumDevices)(struct IDirect3D7 *This, void *lpEnumDevicesCallback, LPVOID lpUserArg);
    HRESULT (*CreateDevice)(struct IDirect3D7 *This, REFCLSID rclsid, LPDIRECTDRAWSURFACE7 lpDDS, LPDIRECT3DDEVICE7 *lplpD3DDevice);
    HRESULT (*CreateVertexBuffer)(struct IDirect3D7 *This, LPD3DVERTEXBUFFERDESC lpVBDesc, LPDIRECT3DVERTEXBUFFER7 *lplpD3DVertexBuffer, DWORD dwFlags);
    HRESULT (*EnumZBufferFormats)(struct IDirect3D7 *This, REFCLSID riidDevice, void *lpEnumCallback, LPVOID lpContext);
    HRESULT (*EvictManagedTextures)(struct IDirect3D7 *This);
} IDirect3D7Vtbl;

struct IDirect3D7 {
    const IDirect3D7Vtbl *lpVtbl;

#ifdef __cplusplus
    HRESULT QueryInterface(REFIID riid, void **ppvObject) { return lpVtbl->QueryInterface(this, riid, ppvObject); }
    ULONG AddRef() { return lpVtbl->AddRef(this); }
    ULONG Release() { return lpVtbl->Release(this); }
    HRESULT EnumDevices(void *cb, LPVOID arg) { return lpVtbl->EnumDevices(this, cb, arg); }
    HRESULT CreateDevice(REFCLSID rclsid, LPDIRECTDRAWSURFACE7 lpDDS, LPDIRECT3DDEVICE7 *lplpD3DDevice) { return lpVtbl->CreateDevice(this, rclsid, lpDDS, lplpD3DDevice); }
    HRESULT CreateVertexBuffer(LPD3DVERTEXBUFFERDESC lpVBDesc, LPDIRECT3DVERTEXBUFFER7 *lplpD3DVertexBuffer, DWORD dwFlags) { return lpVtbl->CreateVertexBuffer(this, lpVBDesc, lplpD3DVertexBuffer, dwFlags); }
    HRESULT EnumZBufferFormats(REFCLSID riidDevice, void *cb, LPVOID ctx) { return lpVtbl->EnumZBufferFormats(this, riidDevice, cb, ctx); }
    HRESULT EvictManagedTextures() { return lpVtbl->EvictManagedTextures(this); }
#endif
};

/* ============================================================
 * IDirect3DTexture2 interface stub
 * ============================================================ */
typedef struct IDirect3DTexture2Vtbl {
    /* IUnknown methods */
    HRESULT (*QueryInterface)(struct IDirect3DTexture2 *This, REFIID riid, void **ppvObject);
    ULONG (*AddRef)(struct IDirect3DTexture2 *This);
    ULONG (*Release)(struct IDirect3DTexture2 *This);

    /* IDirect3DTexture2 methods */
    HRESULT (*GetHandle)(struct IDirect3DTexture2 *This, struct IDirect3DDevice7 *lpD3DDevice, LPDWORD lpHandle);
    HRESULT (*PaletteChanged)(struct IDirect3DTexture2 *This, DWORD dwStart, DWORD dwCount);
    HRESULT (*Load)(struct IDirect3DTexture2 *This, struct IDirect3DTexture2 *lpD3DTexture2);
} IDirect3DTexture2Vtbl;

struct IDirect3DTexture2 {
    const IDirect3DTexture2Vtbl *lpVtbl;
};

/* D3D creation */
/* Note: DirectDrawCreateEx is now implemented as a real function in ddraw.h */
#define Direct3DCreate7() FF_CreateDirect3D7()

/* IID definitions for DirectX 7 */
#ifndef IID_IDirect3D7
static const IID IID_IDirect3D7 = {0xf5049e77, 0x4861, 0x11d2, {0xa4, 0x07, 0x00, 0xa0, 0xc9, 0x06, 0x29, 0xa8}};
#endif
#ifndef IID_IDirect3DDevice7
static const IID IID_IDirect3DDevice7 = {0xf5049e79, 0x4861, 0x11d2, {0xa4, 0x07, 0x00, 0xa0, 0xc9, 0x06, 0x29, 0xa8}};
#endif
#ifndef IID_IDirect3DVertexBuffer7
static const IID IID_IDirect3DVertexBuffer7 = {0xf5049e7d, 0x4861, 0x11d2, {0xa4, 0x07, 0x00, 0xa0, 0xc9, 0x06, 0x29, 0xa8}};
#endif
#ifndef IID_IDirect3DTexture2
static const IID IID_IDirect3DTexture2 = {0x93281502, 0x8cf8, 0x11d0, {0x89, 0xab, 0x00, 0xa0, 0xc9, 0x05, 0x41, 0x29}};
#endif
#ifndef IID_IDirectDraw7
static const IID IID_IDirectDraw7 = {0x15e65ec0, 0x3b9c, 0x11d2, {0xb9, 0x2f, 0x00, 0x60, 0x97, 0x97, 0xea, 0x5b}};
#endif
#ifndef IID_IDirectDrawSurface7
static const IID IID_IDirectDrawSurface7 = {0x06675a80, 0x3b9b, 0x11d2, {0xb9, 0x2f, 0x00, 0x60, 0x97, 0x97, 0xea, 0x5b}};
#endif

/* ============================================================
 * D3DX Utility Functions - stubs
 * ============================================================ */
static inline HRESULT D3DXInitialize(void) {
    return S_OK;
}

static inline HRESULT D3DXUninitialize(void) {
    return S_OK;
}

/* D3DXVECTOR3 - same as D3DVECTOR for our stub purposes */
#ifndef D3DXVECTOR3_DEFINED
typedef D3DVECTOR D3DXVECTOR3;
typedef D3DVECTOR *LPD3DXVECTOR3;
#define D3DXVECTOR3_DEFINED
#endif

/* D3DX Matrix/Vector math stubs */
#ifdef __cplusplus
#ifndef D3DXVec3TransformCoord_DEFINED
static inline D3DXVECTOR3* D3DXVec3TransformCoord(D3DXVECTOR3 *pOut, const D3DXVECTOR3 *pV, const D3DXMATRIX *pM) {
    if (!pOut || !pV || !pM) return NULL;
    float x = pV->x * pM->_11 + pV->y * pM->_21 + pV->z * pM->_31 + pM->_41;
    float y = pV->x * pM->_12 + pV->y * pM->_22 + pV->z * pM->_32 + pM->_42;
    float z = pV->x * pM->_13 + pV->y * pM->_23 + pV->z * pM->_33 + pM->_43;
    float w = pV->x * pM->_14 + pV->y * pM->_24 + pV->z * pM->_34 + pM->_44;
    if (w != 0.0f) {
        pOut->x = x / w;
        pOut->y = y / w;
        pOut->z = z / w;
    } else {
        pOut->x = x;
        pOut->y = y;
        pOut->z = z;
    }
    return pOut;
}
#define D3DXVec3TransformCoord_DEFINED
#endif
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_D3D_H */
