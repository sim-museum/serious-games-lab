// smart.h : Smart pointer definitions

#pragma once

#ifdef _WIN32
// #define USE_ATL_SMART_POINTERS

#ifndef USE_ATL_SMART_POINTERS
#define COM_SMARTPTR_TYPEDEF _COM_SMARTPTR_TYPEDEF
#else
// Emulates VC smart pointers
#define COM_SMARTPTR_TYPEDEF(a, b) typedef CComQIPtr<a, &b> a##Ptr
#endif // USE_ATL_SMART_POINTERS

COM_SMARTPTR_TYPEDEF(IDirectDraw, IID_IDirectDraw);
COM_SMARTPTR_TYPEDEF(IDirectDrawPalette, IID_IDirectDrawPalette);
COM_SMARTPTR_TYPEDEF(IDirectDraw7, IID_IDirectDraw7);
COM_SMARTPTR_TYPEDEF(IDirect3D, IID_IDirect3D);
COM_SMARTPTR_TYPEDEF(IDirect3D7, IID_IDirect3D7);
COM_SMARTPTR_TYPEDEF(IDirectDrawSurface7, IID_IDirectDraw7);
COM_SMARTPTR_TYPEDEF(IDirectDrawClipper, IID_IDirectDrawClipper);
COM_SMARTPTR_TYPEDEF(IDirect3DDevice7, IID_IDirect3DDevice7);
COM_SMARTPTR_TYPEDEF(IDirect3DVertexBuffer7, IID_IDirect3DVertexBuffer7);
COM_SMARTPTR_TYPEDEF(IDirectDrawGammaControl, IID_IDirectDrawGammaControl);

// Helper stuff
inline void CheckHR(HRESULT hr)
{
    if (FAILED(hr))
    {
        IErrorInfo *pEI = NULL;
        ::GetErrorInfo(NULL, &pEI);
        throw _com_error(hr, pEI);
    }
}

#else  /* Linux/non-Windows */

// On Linux, we use the interface types from our compat headers
// Forward declarations (full definitions in compat/ddraw.h and compat/d3d.h)
struct IDirectDraw;
struct IDirectDrawPalette;
struct IDirectDraw7;
struct IDirect3D;
struct IDirect3D7;
struct IDirectDrawSurface7;
struct IDirectDrawClipper;
struct IDirect3DDevice7;
struct IDirect3DVertexBuffer7;
struct IDirectDrawGammaControl;

typedef IDirectDraw* IDirectDrawPtr;
typedef IDirectDrawPalette* IDirectDrawPalettePtr;
typedef IDirectDraw7* IDirectDraw7Ptr;
typedef IDirect3D* IDirect3DPtr;
typedef IDirect3D7* IDirect3D7Ptr;
typedef IDirectDrawSurface7* IDirectDrawSurface7Ptr;
typedef IDirectDrawClipper* IDirectDrawClipperPtr;
typedef IDirect3DDevice7* IDirect3DDevice7Ptr;
typedef IDirect3DVertexBuffer7* IDirect3DVertexBuffer7Ptr;
typedef IDirectDrawGammaControl* IDirectDrawGammaControlPtr;

inline void CheckHR(HRESULT hr)
{
    (void)hr;
    // No-op on Linux - will be replaced with proper error handling
}

#endif /* _WIN32 */
