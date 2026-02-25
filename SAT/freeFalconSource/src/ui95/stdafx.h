#if defined(_MSC_VER) && _MSC_VER < 1200
#error You need VC6 or higher
#endif // _MSC_VER < 1200

#pragma once

//sfr: added for mouse wheel
#define _WIN32_WINNT (0x0500)

#include "omni.h"

#ifdef _MSC_VER
// ATL
#include <atlbase.h>
//You may derive a class from CComModule and use it if you want to override
//something, but do not change the name of _Module
extern CComModule _Module;
#include <atlcom.h>

// Smart ptr stuff
#include <comdef.h>
#endif

// DirectX
#define D3D_OVERLOADS

#include <ddraw.h>
#ifdef _MSC_VER
#include <d3d.h>
#include <d3dxcore.h>
#include <d3dxmath.h>
#endif

// STL
#include <vector>
#include <string>
#include <map>

// Misc
#ifdef _MSC_VER
#include <io.h>
#endif
#include <math.h>
#include <stdio.h>

#include "graphics/include/smart.h"
