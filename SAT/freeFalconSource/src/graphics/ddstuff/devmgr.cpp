/***************************************************************************\
    DevMgr.cpp
    Scott Randolph
    November 8, 1996

    This class provides management of the drawing devices in the system.
\***************************************************************************/
#include "stdafx.h"
#include "devmgr.h"
#include "falclib/include/playerop.h"

#include "falclib/include/dispopts.h" //JAM 04Oct03

#include <math.h>
#include "polylib.h"
#include "graphics/dxengine/dxengine.h"
extern bool g_bUse_DX_Engine;

typedef std::vector<DDPIXELFORMAT> PIXELFMT_ARRAY;

int HighResolutionHackFlag = FALSE; // Used in WinMain.CPP
extern bool g_bForceDXMultiThreadedCoopLevel;
extern char g_CardDetails[]; // JB 010215

#ifdef _MSC_VER
#define INT3 _asm {int 3}
#else
#define INT3
#endif

// Cobra - Hack to get VC6 to link
#if defined(_MSC_VER) && _MSC_VER < 1300

void __cdecl std::_Xlen()
{
}
void __cdecl std::_Xran()
{
}

#endif

// LPDIRECTDRAWCREATEEX is defined in ddraw.h
LPDIRECTDRAWENUMERATEEX pfnDirectDrawEnumerateEx = NULL;
LPDIRECTDRAWCREATEEX pfnDirectDrawCreateEx = NULL;

// Device GUIDs - MSVC-specific uuid attribute
#ifdef _MSC_VER
struct __declspec(uuid("D7B71CFA-4342-11CF-CE67-0120A6C2C935")) DEVGUID_3DFX_VOODOO2_a; // DX7 Beta Driver
struct __declspec(uuid("472BEA00-40DF-11D1-A9DF-006097C2EDB2")) DEVGUID_3DFX_VOODOO2_b; // DX7
#endif

void DeviceManager::Setup(int languageNum)
{
    try
    {
        CheckHR(D3DXInitialize());
        EnumDDDrivers(this);

        ready = TRUE;
    }

    catch (_com_error e)
    {
        MonoPrint("DeviceManager::Setup - Error 0x%X\n", e.Error());
    }
}


void DeviceManager::Cleanup(void)
{
    if (ready) D3DXUninitialize();

    ready = FALSE;
}


const char * DeviceManager::GetDriverName(int driverNum)
{
    if (driverNum < 0 or driverNum >= (int) m_arrDDDrivers.size())
        return NULL;

    return m_arrDDDrivers[driverNum].GetName();
}


const char * DeviceManager::GetDeviceName(int driverNum, int devNum)
{
    if (driverNum < 0 or driverNum >= (int) m_arrDDDrivers.size())
        return NULL;

    return m_arrDDDrivers[driverNum].GetDeviceName(devNum);
}

int DeviceManager::FindPrimaryDisplayDriver()
{
    for (int i = 0; i < (int) m_arrDDDrivers.size(); i++)
        if (IsEqualGUID(m_arrDDDrivers[i].m_guid, GUID_NULL)) return i;

    return -1;
}

const char *DeviceManager::GetModeName(int driverNum, int devNum, int modeNum)
{
    static char buffer[80];
    int i = 0;

    if (driverNum < 0 or driverNum >= (int) m_arrDDDrivers.size())
        return NULL;

    DDDriverInfo &DI = m_arrDDDrivers[driverNum];
    LPDDSURFACEDESC2 pddsd = NULL;

    // Find the nth (legal) display mode
    while (pddsd = DI.GetDisplayMode(i))
    {
        // For now we only allow 640x480, 800x600, 1280x960, 1600x1200
        // (MPR already does the 4:3 aspect ratio check for us)
        if (pddsd->ddpfPixelFormat.dwRGBBitCount >= 16 and (pddsd->dwWidth == 640 or pddsd->dwWidth == 800 or pddsd->dwWidth == 1024 or
                (pddsd->dwWidth == 1280 and pddsd->dwHeight == 960) or pddsd->dwWidth == 1600 or HighResolutionHackFlag))
        {
            if (modeNum == 0)
            {
                // This is the one we want.  Return it.
                // OW
                // sprintf( buffer, "%0dx%0d", pddsd->dwWidth, pddsd->dwHeight);
                sprintf(buffer, "%0dx%0d - %d Bit", pddsd->dwWidth, pddsd->dwHeight, pddsd->ddpfPixelFormat.dwRGBBitCount);
                return buffer;
            }

            else
            {
                // One down, more to go...
                modeNum--;
            }
        }

        i++;
    }

    return NULL;
}

bool DeviceManager::GetMode(int driverNum, int devNum, int modeNum, UINT *pWidth, UINT *pHeight, UINT *pDepth)
{
    static char buffer[80];
    int i = 0;

    if (driverNum < 0 or driverNum >= (int) m_arrDDDrivers.size())
        return false;

    DDDriverInfo &DI = m_arrDDDrivers[driverNum];
    LPDDSURFACEDESC2 pddsd = DI.GetDisplayMode(modeNum);

    if ( not pddsd) return false;

    *pWidth = pddsd->dwWidth;
    *pHeight = pddsd->dwHeight;
    *pDepth = pddsd->ddpfPixelFormat.dwRGBBitCount; // OW

    return true;
}

// Present the user with a dialog box listing the available devices and pick one
BOOL DeviceManager::ChooseDevice(int *usrDrvNum, int *usrDevNum, int *usrWidth)
{
    RECT rect;
    HWND listWin;
    DWORD listSlot;
    const char *devName;
    const char *drvName;
    const char *modeName;
    char name[MAX_PATH];
    unsigned devNum;
    unsigned drvNum;
    unsigned modeNum;
    unsigned width;
    unsigned height;
    unsigned packedNum;

    // Build a window for this application
    rect.top = rect.left = 0;
    rect.right = 200;
    rect.bottom = 400;
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);
    listWin = CreateWindow(
                  "LISTBOX", /* class */
                  "Choose Display Device",/* caption */
                  WS_OVERLAPPEDWINDOW, /* style */
                  CW_USEDEFAULT, /* init. x pos */
                  CW_USEDEFAULT, /* init. y pos */
                  rect.right - rect.left, /* init. x size */
                  rect.bottom - rect.top, /* init. y size */
                  NULL, /* parent window */
                  NULL, /* menu handle */
                  NULL, /* program handle */
                  NULL /* create parms */
              );

    if ( not listWin)
    {
        ShiError("Failed to construct list box window");
    }

    // Fill in the list box with the avaiable devices
    drvNum = 0;

    while (drvName = GetDriverName(drvNum))
    {

        devNum = 0;

        while (devName = GetDeviceName(drvNum, devNum))
        {

            modeNum = 0;

            while (modeName = GetModeName(drvNum, devNum, modeNum))
            {

                packedNum = (devNum << 24) bitor (drvNum << 8) bitor (modeNum);
                strcpy(name, drvName);
                strcat(name, ":  ");
                strcat(name, devName);

                strcat(name, "  ");
                strcat(name, modeName);

                listSlot = SendMessageA(listWin, LB_ADDSTRING, 0, (LPARAM)name);

                if (listSlot == LB_ERR)
                {
                    ShiError("Failed to add device to selection list.");
                }

                SendMessageA(listWin, LB_SETITEMDATA, listSlot, packedNum);

                modeNum++;
            }

            devNum++;
        }

        drvNum++;
    }

    // Mark the first entry as selected by default and show the window to the user
    SendMessageA(listWin, LB_SETCURSEL, 0, 0);
    ShowWindow(listWin, SW_SHOW);

    // Stop here until we get a choice from the user
    MessageBox(NULL, "Click OK when you've made your device choice", "", MB_OK);

    listSlot = SendMessageA(listWin, LB_GETCURSEL, 0, 0);
    ShiAssert(listSlot not_eq LB_ERR);
    packedNum = SendMessageA(listWin, LB_GETITEMDATA, listSlot, 0);
    devNum  = (packedNum >> 24) bitand 0xFF;
    drvNum  = (packedNum >> 8) bitand 0xFFFF;
    modeNum = (packedNum >> 0) bitand 0xFF;

    modeName = GetModeName(drvNum, devNum, modeNum);
    ShiAssert(modeName);
    sscanf(modeName, "%d x %d", &width, &height);
    ShiAssert(width * 3 / 4 == height);

    *usrDevNum  = devNum;
    *usrDrvNum  = drvNum;
    *usrWidth   = width;

    // Get rid of the list box now that we're done with it
    DestroyWindow(listWin);
    listWin = NULL;

    // return their choice
    return TRUE;
}

// OW

DXContext *DeviceManager::CreateContext(int driverNum, int devNum, int resNum, BOOL bFullscreen, HWND hWnd)
{
    fprintf(stderr, "  [CreateContext] driverNum=%d, devNum=%d, resNum=%d\n", driverNum, devNum, resNum); fflush(stderr);
    try
    {
        DDDriverInfo *pDDI = GetDriver(driverNum);
        fprintf(stderr, "  [CreateContext] GetDriver returned pDDI=%p\n", (void*)pDDI); fflush(stderr);

        if ( not pDDI) return NULL;

        fprintf(stderr, "  [CreateContext] D3D devices count: %zu\n", pDDI->m_arrD3DDevices.size()); fflush(stderr);
        fprintf(stderr, "  [CreateContext] Display modes count: %zu\n", pDDI->m_arrModes.size()); fflush(stderr);

        DDDriverInfo::D3DDeviceInfo *pD3DDI = pDDI->GetDevice(devNum);
        fprintf(stderr, "  [CreateContext] GetDevice returned pD3DDI=%p\n", (void*)pD3DDI); fflush(stderr);

        if ( not pD3DDI) return NULL;

        LPDDSURFACEDESC2 pddsd = pDDI->GetDisplayMode(resNum);
        fprintf(stderr, "  [CreateContext] GetDisplayMode returned pddsd=%p\n", (void*)pddsd); fflush(stderr);

        if ( not pddsd) return NULL;

        DXContext *pCtx = new DXContext;

        if (pCtx == NULL) return NULL;

        pCtx->m_guidDD = *pDDI->GetGuid();
        pCtx->m_guidD3D = *pD3DDI->GetGuid();

        MonoPrint("DeviceManager::CreateContext - %s\n", pD3DDI->GetName());

#ifdef _DEBUG

        if ( not bFullscreen) ShiAssert(pDDI->CanRenderWindowed());

#endif

        pCtx->Init(hWnd, pddsd->dwWidth, pddsd->dwHeight, pddsd->ddpfPixelFormat.dwRGBBitCount, bFullscreen ? true : false);

        return pCtx;
    }

    catch (_com_error e)
    {
        MonoPrint("DeviceManager::OpenDevice - Error 0x%X\n", e.Error());
        return NULL;
    }
}

void DeviceManager::EnumDDDrivers(DeviceManager *pThis)
{
#ifdef FF_LINUX
    // On Linux, we provide a single OpenGL-backed DirectDraw driver
    m_arrDDDrivers.clear();

    // Add our OpenGL driver as the primary (and only) display driver
    // Use GUID_NULL for the primary display device
    pThis->m_arrDDDrivers.push_back(DDDriverInfo(GUID_NULL, "OpenGL", "FreeFalcon OpenGL Driver"));
#else
    HINSTANCE h = LoadLibrary("ddraw.dll");

    if ( not h) return;

    m_arrDDDrivers.clear();

    // Note that you must know which version of the function to retrieve (see the following text). For this example, we use the ANSI version.
    LPDIRECTDRAWENUMERATEEX lpDDEnumEx;
    lpDDEnumEx = (LPDIRECTDRAWENUMERATEEX) GetProcAddress(h, "DirectDrawEnumerateExA");

    // If the function is there, call it to enumerate all display devices attached to the desktop, and any non-display DirectDraw devices.
    if (lpDDEnumEx) lpDDEnumEx(EnumDDCallbackEx, pThis, DDENUM_ATTACHEDSECONDARYDEVICES |
                                   DDENUM_NONDISPLAYDEVICES);
    else DirectDrawEnumerate(EnumDDCallback, pThis);

    FreeLibrary(h);
#endif
}

BOOL WINAPI DeviceManager::EnumDDCallback(GUID FAR *lpGUID, LPSTR lpDriverDescription,
        LPSTR lpDriverName, LPVOID lpContext)
{
    return EnumDDCallbackEx(lpGUID, lpDriverDescription, lpDriverName, lpContext, NULL);
}

BOOL WINAPI DeviceManager::EnumDDCallbackEx(GUID FAR *lpGUID, LPSTR lpDriverDescription,
        LPSTR lpDriverName, LPVOID lpContext, HMONITOR hm)
{
    DeviceManager *pThis = (DeviceManager *) lpContext;
    pThis->m_arrDDDrivers.push_back(DDDriverInfo(lpGUID ? *lpGUID : GUID_NULL, lpDriverName, lpDriverDescription));
    return TRUE;
}

DeviceManager::DDDriverInfo *DeviceManager::GetDriver(int driverNum)
{
    if (driverNum < 0 or driverNum >= (int) m_arrDDDrivers.size())
        return nullptr;

    return &m_arrDDDrivers[driverNum];
}

// DeviceManager::DDDriverInfo
/////////////////////////////////////////////////////////////////////////////

DeviceManager::DDDriverInfo::DDDriverInfo(GUID guid, LPCTSTR Name, LPCTSTR Description)
{
    m_guid = guid;
    m_strName = Name;
    m_strDescription = Description;

    EnumD3DDrivers();
}

void DeviceManager::DDDriverInfo::EnumD3DDrivers()
{
    fprintf(stderr, "  [EnumD3DDrivers] Starting...\n"); fflush(stderr);
    try
    {
        IDirectDraw7Ptr pDD7 = nullptr;
        IDirect3D7Ptr pD3D = nullptr;

        // Create DDRAW object
        CheckHR(DirectDrawCreateEx(&m_guid, (void **) &pDD7, IID_IDirectDraw7, NULL));
        fprintf(stderr, "  [EnumD3DDrivers] DirectDrawCreateEx returned pDD7=%p\n", (void*)pDD7); fflush(stderr);

        // Get IDirect3D7 interface via QueryInterface
        if (pDD7)
        {
            HRESULT hr = pDD7->QueryInterface(IID_IDirect3D7, (void**)&pD3D);
            fprintf(stderr, "  [EnumD3DDrivers] QueryInterface for D3D7: hr=0x%lx, pD3D=%p\n",
                    (unsigned long)hr, (void*)pD3D); fflush(stderr);
            pDD7->GetDeviceIdentifier(&devID, 0);
        }

        m_arrD3DDevices.clear();
        if (pD3D)
        {
            fprintf(stderr, "  [EnumD3DDrivers] Calling EnumDevices...\n"); fflush(stderr);
            pD3D->EnumDevices((void*)EnumD3DDriversCallback, this);
            fprintf(stderr, "  [EnumD3DDrivers] EnumDevices returned\n"); fflush(stderr);
        }
        else
        {
            fprintf(stderr, "  [EnumD3DDrivers] pD3D is NULL, skipping EnumDevices\n"); fflush(stderr);
        }

        if (pDD7)
            pDD7->EnumDisplayModes(0, NULL, this, EnumModesCallback);

        ZeroMemory(&m_caps, sizeof(m_caps));
        m_caps.dwSize = sizeof(m_caps);
        if (pDD7)
            pDD7->GetCaps(&m_caps, NULL);
    }

    catch (_com_error e)
    {
        MonoPrint("DeviceManager::DDDriverInfo::EnumD3DDrivers - Error 0x%X\n", e.Error());
    }
}

HRESULT CALLBACK DeviceManager::DDDriverInfo::EnumD3DDriversCallback(LPSTR lpDeviceDescription,
        LPSTR lpDeviceName, LPD3DDEVICEDESC7 lpD3DHWDeviceDesc, LPVOID lpContext)
{
    fprintf(stderr, "    [EnumD3DDriversCallback] name=%s, desc=%s\n",
            lpDeviceName ? lpDeviceName : "(null)",
            lpDeviceDescription ? lpDeviceDescription : "(null)"); fflush(stderr);

    DeviceManager::DDDriverInfo *pThis = (DeviceManager::DDDriverInfo *) lpContext;

    if (lpD3DHWDeviceDesc)
    {
        fprintf(stderr, "    [EnumD3DDriversCallback] dwDevCaps=0x%lx, required=0x%x\n",
                (unsigned long)lpD3DHWDeviceDesc->dwDevCaps, DisplayOptionsClass::GetDevCaps()); fflush(stderr);

        // COBRA - DX - Consider only Drivers making HW T&L
        // sfr: this causes notebooks to stop working
        //if (lpD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_HWTRANSFORMANDLIGHT ){
        if (lpD3DHWDeviceDesc->dwDevCaps bitand DisplayOptionsClass::GetDevCaps())
        {
            fprintf(stderr, "    [EnumD3DDriversCallback] Adding device to list\n"); fflush(stderr);
            pThis->m_arrD3DDevices.push_back(D3DDeviceInfo(*lpD3DHWDeviceDesc, lpDeviceName, lpDeviceDescription));
        }
        else
        {
            fprintf(stderr, "    [EnumD3DDriversCallback] Device caps don't match, not adding\n"); fflush(stderr);
        }
    }

    return D3DENUMRET_OK;
}

HRESULT WINAPI DeviceManager::DDDriverInfo::EnumModesCallback(LPDDSURFACEDESC2 lpDDSurfaceDesc, LPVOID lpContext)
{
    DeviceManager::DDDriverInfo *pThis = (DeviceManager::DDDriverInfo *) lpContext;
    pThis->m_arrModes.push_back(*lpDDSurfaceDesc);

    return DDENUMRET_OK;
}

const char *DeviceManager::DDDriverInfo::GetDeviceName(int n)
{
    if (n < 0 or n >= (int) m_arrD3DDevices.size())
        return NULL;

    return m_arrD3DDevices[n].GetName();
}

int DeviceManager::DDDriverInfo::FindDisplayMode(int nWidth, int nHeight, int nBPP)
{
    for (int i = 0; i < (int) m_arrModes.size(); i++)
    {
        if (m_arrModes[i].dwWidth == nWidth and m_arrModes[i].dwHeight == nHeight and 
            m_arrModes[i].ddpfPixelFormat.dwRGBBitCount == nBPP)
            return i;
    }

    return -1; // not found
}

LPDDSURFACEDESC2 DeviceManager::DDDriverInfo::GetDisplayMode(int n)
{
    if (n < 0 or n >= (int) m_arrModes.size())
        return NULL;

    return &m_arrModes[n];
}

bool DeviceManager::DDDriverInfo::CanRenderWindowed()
{
    return m_caps.dwCaps2 bitand DDCAPS2_CANRENDERWINDOWED ? true : false;
}

bool DeviceManager::DDDriverInfo::Is3dfx()
{
    return devID.dwVendorId == 4634;
}

bool DeviceManager::DDDriverInfo::SupportsSRT()
{
    if (devID.dwVendorId == 4634) // 3dfx
    {
        if (devID.dwDeviceId == 1 or devID.dwDeviceId == 2) // Voodoo 1 bitand 2
            return false;
    }

    return true; // assume SetRenderTarget works for all other cards
}

DeviceManager::DDDriverInfo::D3DDeviceInfo *DeviceManager::DDDriverInfo::GetDevice(int n)
{
    if (n < 0 or n >= (int) m_arrD3DDevices.size())
        return NULL;

    return &m_arrD3DDevices[n];
}

int DeviceManager::DDDriverInfo::FindRGBRenderer()
{
    for (int i = 0; i < (int) m_arrD3DDevices.size(); i++)
        if (IsEqualGUID(m_arrD3DDevices[i].m_devDesc.deviceGUID, IID_IDirect3DRGBDevice)) return i;

    return -1;
}

// DeviceManager::DDDriverInfo::D3DDeviceInfo
/////////////////////////////////////////////////////////////////////////////

DeviceManager::DDDriverInfo::D3DDeviceInfo::D3DDeviceInfo(D3DDEVICEDESC7 &devDesc, LPSTR lpDeviceName, LPSTR lpDeviceDescription)
{
    m_devDesc = devDesc;
    m_strName = lpDeviceName;
    m_strDescription = lpDeviceDescription;
}

bool DeviceManager::DDDriverInfo::D3DDeviceInfo::IsHardware()
{
    if (IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DRGBDevice) or IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DRefDevice) or
        IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DRampDevice) or IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DMMXDevice))
        return false;
    else if (IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DHALDevice))
        return true;
    else if (IsEqualIID(m_devDesc.deviceGUID, IID_IDirect3DTnLHalDevice))
        return true;
    else
    {
        ShiAssert(false); // check this
        return true;
    }
}

bool DeviceManager::DDDriverInfo::D3DDeviceInfo::CanFilterAnisotropic()
{
    bool bCanDoAnisotropic = (m_devDesc.dpcTriCaps.dwTextureFilterCaps bitand D3DPTFILTERCAPS_MAGFANISOTROPIC) and 
                             (m_devDesc.dpcTriCaps.dwTextureFilterCaps bitand D3DPTFILTERCAPS_MINFANISOTROPIC);
    return bCanDoAnisotropic;
}

// DXContext
/////////////////////////////////////////////////////////////////////////////

DXContext::DXContext()
{
    m_pDD = NULL;
    m_pD3D = NULL;
    m_pD3DD = NULL;
    m_bFullscreen = false;
    m_hWnd = NULL;
    m_nWidth = m_nHeight = 0;
    ZeroMemory(&m_guidDD, sizeof(m_guidDD));
    ZeroMemory(&m_guidD3D, sizeof(m_guidD3D));

    m_pcapsDD = new DDCAPS;
    m_pD3DHWDeviceDesc = new D3DDEVICEDESC7;
    m_pDevID = new DDDEVICEIDENTIFIER2;
    refcount = 1; // start with 1
}

DXContext::~DXContext()
{

    Shutdown();


    // sfr: why are these not being NULLed??
    if (m_pcapsDD) delete m_pcapsDD;

    if (m_pD3DHWDeviceDesc) delete m_pD3DHWDeviceDesc;

    if (m_pDevID) delete m_pDevID;
}

void DXContext::Shutdown()
{
    // MonoPrint("DXContext::Shutdown()\n");

    DWORD dwRefCnt;

    // release DX Engine stuff
    TheDXEngine.Release();

    if (m_pDD)
        CheckHR(m_pDD->SetCooperativeLevel(m_hWnd, DDSCL_NORMAL));

    if (m_pD3DD)
    {
        // free all textures
        m_pD3DD->SetTexture(0, NULL);
        m_pD3DD->SetTexture(1, NULL);
        m_pD3DD->SetTexture(3, NULL);

        // release
        dwRefCnt = m_pD3DD->Release();
        // ShiAssert(dwRefCnt == 0);
        m_pD3DD = NULL;
    }

    if (m_pD3D)
    {
        dwRefCnt = m_pD3D->Release();
        // ShiAssert(dwRefCnt == 0);
        m_pD3D = NULL;
    }

    if (m_pDD)
    {
        if (m_bFullscreen)
        {
            m_pDD->RestoreDisplayMode();
            m_pDD->FlipToGDISurface();
        }

        dwRefCnt = m_pDD->Release();
        // ShiAssert(dwRefCnt == 0);
        m_pDD = NULL;
    }

    m_bFullscreen = false;
    m_hWnd = NULL;
}

/*
DXContext& DXContext::operator=(DXContext &ref)
{
 m_pDD = ref.m_pDD;
 if(m_pDD) m_pDD->AddRef();

 m_pD3D = ref.m_pD3D;
 if(m_pD3D) m_pD3D->AddRef();

 m_pD3DD = ref.m_pD3DD;
 if(m_pD3DD) m_pD3DD->AddRef();

 return *this;
}
*/

bool DXContext::Init(HWND hWnd, int nWidth, int nHeight, int nDepth, bool bFullscreen)
{
    fprintf(stderr, "  [DXContext::Init] Starting with hWnd=%p, %dx%d@%d, fullscreen=%d\n", (void*)hWnd, nWidth, nHeight, nDepth, bFullscreen); fflush(stderr);
    MonoPrint("DXContext::Init(0x%X, %d, %d, %d, %d)\n", hWnd, nWidth, nHeight, nDepth, bFullscreen);

    try
    {
        fprintf(stderr, "  [DXContext::Init] Checking thread ID...\n"); fflush(stderr);
        ShiAssert(::GetCurrentThreadId() == GetWindowThreadProcessId(hWnd, NULL)); // Make sure this gets called by the main thread
        fprintf(stderr, "  [DXContext::Init] Thread ID check passed\n"); fflush(stderr);

        m_bFullscreen = bFullscreen;
        m_nWidth = nWidth;
        m_nHeight = nHeight;
        m_hWnd = hWnd;

        // Create DDRAW object
        fprintf(stderr, "  [DXContext::Init] Calling DirectDrawCreateEx...\n"); fflush(stderr);
        CheckHR(DirectDrawCreateEx(&m_guidDD, (void **) &m_pDD, IID_IDirectDraw7, NULL));
        fprintf(stderr, "  [DXContext::Init] DirectDrawCreateEx returned m_pDD=%p\n", (void*)m_pDD); fflush(stderr);

        fprintf(stderr, "  [DXContext::Init] Calling GetCaps... m_pcapsDD=%p\n", (void*)m_pcapsDD); fflush(stderr);
        m_pcapsDD->dwSize = sizeof(*m_pcapsDD);
        CheckHR(m_pDD->GetCaps(m_pcapsDD, NULL));
        fprintf(stderr, "  [DXContext::Init] GetCaps done\n"); fflush(stderr);

        fprintf(stderr, "  [DXContext::Init] Calling GetDeviceIdentifier... m_pDevID=%p\n", (void*)m_pDevID); fflush(stderr);
        CheckHR(m_pDD->GetDeviceIdentifier(m_pDevID, NULL));
        fprintf(stderr, "  [DXContext::Init] GetDeviceIdentifier done\n"); fflush(stderr);

        sprintf(g_CardDetails, "DXContext::Init - DriverInfo - \"%s\" - \"%s\", Vendor: %d, Device: %d, SubSys: %d, Rev: %d, Product: %d, Version: %d, SubVersion: %d, Build: %d\n",
                m_pDevID->szDriver, m_pDevID->szDescription,
                m_pDevID->dwVendorId, m_pDevID->dwDeviceId, m_pDevID->dwSubSysId, m_pDevID->dwRevision,
                HIWORD(m_pDevID->liDriverVersion.HighPart), LOWORD(m_pDevID->liDriverVersion.HighPart),
                HIWORD(m_pDevID->liDriverVersion.LowPart), LOWORD(m_pDevID->liDriverVersion.LowPart)); // JB 010215
        MonoPrint("%s", g_CardDetails);  // JB 010215
        fprintf(stderr, "  [DXContext::Init] %s", g_CardDetails); fflush(stderr);

        DWORD m_dwCoopFlags = NULL;
        m_dwCoopFlags or_eq DDSCL_FPUPRESERVE; // OW FIXME: check if this can be eliminated by eliminating ALL controlfp calls in all files

        if (g_bForceDXMultiThreadedCoopLevel) m_dwCoopFlags or_eq DDSCL_MULTITHREADED;

        if (bFullscreen) m_dwCoopFlags or_eq DDSCL_EXCLUSIVE bitor DDSCL_FULLSCREEN bitor DDSCL_ALLOWREBOOT;
        else m_dwCoopFlags or_eq DDSCL_NORMAL;

        fprintf(stderr, "  [DXContext::Init] Calling SetCooperativeLevel with flags=0x%x...\n", m_dwCoopFlags); fflush(stderr);
        CheckHR(m_pDD->SetCooperativeLevel(m_hWnd, m_dwCoopFlags));
        fprintf(stderr, "  [DXContext::Init] SetCooperativeLevel done\n"); fflush(stderr);

        if (bFullscreen) {
            fprintf(stderr, "  [DXContext::Init] Calling SetDisplayMode...\n"); fflush(stderr);
            CheckHR(m_pDD->SetDisplayMode(nWidth, nHeight, nDepth, 0, NULL));
            fprintf(stderr, "  [DXContext::Init] SetDisplayMode done\n"); fflush(stderr);
        }

        /*
         // Vendor specific workarounds
         if(IsEqualGUID(m_pDevID->guidDeviceIdentifier, __uuidof(DEVGUID_3DFX_VOODOO2)) and not bFlip)
         {
         // The V2 (Beta 1.0 DX Driver) cannot render to offscreen plain surfaces only to flipping primary surfaces
         m_guidD3D = IID_IDirect3DRGBDevice; // force software renderer
         }
        */

        //JAM 25Oct03 - Let's avoid user error and disable these.
        // if(IsEqualIID(m_guidD3D, IID_IDirect3DRGBDevice) or IsEqualIID(m_guidD3D, IID_IDirect3DRefDevice) or
        // IsEqualIID(m_guidD3D, IID_IDirect3DRampDevice) or IsEqualIID(m_guidD3D, IID_IDirect3DMMXDevice))
        // m_eDeviceCategory = D3DDeviceCategory_Software;
        // if(IsEqualIID(m_guidD3D, IID_IDirect3DHALDevice))
        m_eDeviceCategory = D3DDeviceCategory_Hardware;
        // else if(IsEqualIID(m_guidD3D, IID_IDirect3DTnLHalDevice))
        //FIXME: TnL
        // m_eDeviceCategory = D3DDeviceCategory_Hardware_TNL;
        // else
        // {
        // m_eDeviceCategory = D3DDeviceCategory_Software; // assume its software
        // ShiAssert(false); // check this
        // }
        //JAM

        fprintf(stderr, "  [DXContext::Init] Complete!\n"); fflush(stderr);
        return true;
    }

    catch (_com_error e)
    {
        fprintf(stderr, "  [DXContext::Init] Exception: 0x%X\n", e.Error()); fflush(stderr);
        MonoPrint("DXContext::DD_Init - Error 0x%X\n", e.Error());
        return false;
    }
}

extern bool bInBeginScene; // ASSO:

bool DXContext::SetRenderTarget(IDirectDrawSurface7 *pRenderTarget)
{
    // ASSO: may remove this try catch block from the loop
    try
    {
        if ( not m_pD3DD)
        {
#ifdef FF_LINUX
            // On Linux, validate pointers before use to avoid crashes from corrupt state
            if (!m_pDD || !pRenderTarget) {
                fprintf(stderr, "[SetRenderTarget] ERROR: m_pDD=%p pRenderTarget=%p (NULL or invalid)\n",
                        (void*)m_pDD, (void*)pRenderTarget);
                fflush(stderr);
                return false;
            }
#endif
            // Check the display mode, and
            DDSURFACEDESC2 ddsd_disp;
            ZeroMemory(&ddsd_disp, sizeof(ddsd_disp));
            ddsd_disp.dwSize = sizeof(ddsd_disp);
#ifdef FF_LINUX
            // On Linux, we know the display mode from SDL initialization - assume 32-bit
            // This avoids potential issues with the compat layer's GetDisplayMode
            ddsd_disp.ddpfPixelFormat.dwRGBBitCount = 32;
#else
            CheckHR(m_pDD->GetDisplayMode(&ddsd_disp));
#endif

            if (ddsd_disp.ddpfPixelFormat.dwRGBBitCount <= 8) // 8 Bit display unsupported
                throw _com_error(DDERR_INVALIDMODE);

#ifdef FF_LINUX
            // On Linux, the m_pDD pointer may be corrupt by the time SetRenderTarget is called
            // during sim mode entry (possibly due to threading or memory layout issues).
            // Use our compat layer's direct creation functions instead of going through m_pDD.
            fprintf(stderr, "[SetRenderTarget] Linux: Creating D3D7 interface directly\n"); fflush(stderr);
            m_pD3D = FF_CreateDirect3D7();
            if (!m_pD3D) {
                fprintf(stderr, "[SetRenderTarget] ERROR: FF_CreateDirect3D7 failed\n"); fflush(stderr);
                throw _com_error(DDERR_GENERIC);
            }
            fprintf(stderr, "[SetRenderTarget] Linux: m_pD3D=%p\n", (void*)m_pD3D); fflush(stderr);
#else
            CheckHR(m_pDD->QueryInterface(IID_IDirect3D7, (void **) &m_pD3D));
#endif


            // RV - RED - VISTA FIX, seems Vista is returning false to the check for zBuffer availability
            // we go enumerating them and eventually use them directly
            /* if(m_pcapsDD->dwCaps bitand DDSCAPS_ZBUFFER)
             {*/
            // Get the attached Z buffer surface
            IDirectDrawSurface7Ptr pDDSZB;
            DDSCAPS2 ddscaps;
            ZeroMemory(&ddscaps, sizeof(ddscaps));
            ddscaps.dwCaps = DDSCAPS_ZBUFFER;

#ifdef FF_LINUX
            // On Linux, we manage Z-buffers through OpenGL, not attached surfaces
            // Skip the GetAttachedSurface call and go directly to AttachDepthBuffer
            AttachDepthBuffer(pRenderTarget);
#else
            if (FAILED(pRenderTarget->GetAttachedSurface(&ddscaps, &pDDSZB)))
                AttachDepthBuffer(pRenderTarget);
#endif

            /* }

             else MonoPrint("DXContext::AttachDepthBuffer() - Warning: No Z-Buffer support \n");*/

#ifdef FF_LINUX
            // On Linux, use our compat layer to create the D3D device directly
            fprintf(stderr, "[SetRenderTarget] Linux: Creating D3D device directly, pRenderTarget=%p\n", (void*)pRenderTarget); fflush(stderr);
            m_pD3DD = FF_CreateDirect3DDevice7(m_pD3D, pRenderTarget);
            if (!m_pD3DD) {
                fprintf(stderr, "[SetRenderTarget] ERROR: FF_CreateDirect3DDevice7 failed\n"); fflush(stderr);
                throw _com_error(DDERR_GENERIC);
            }
            fprintf(stderr, "[SetRenderTarget] Linux: m_pD3DD=%p\n", (void*)m_pD3DD); fflush(stderr);

            // GetCaps and SetRenderState are handled by our compat layer's stub implementations
            if (m_pD3DD->GetCaps(m_pD3DHWDeviceDesc) != DD_OK) {
                fprintf(stderr, "[SetRenderTarget] Warning: GetCaps returned error (continuing anyway)\n"); fflush(stderr);
            }
#else
            CheckHR(m_pD3D->CreateDevice(m_guidD3D, pRenderTarget, &m_pD3DD));
            CheckHR(m_pD3DD->GetCaps(m_pD3DHWDeviceDesc));
#endif
            CheckHR(m_pD3DD->SetRenderState(D3DRENDERSTATE_ZENABLE, D3DZB_TRUE));

            CheckCaps();


            // COBRA - DX - DX ENGINE INTIALIZATION - use the right model initialization
            if (g_bUse_DX_Engine) TheDXEngine.Setup(m_pD3DD, m_pD3D, m_pDD);


            //JAM

            // CheckCaps();

            return true; // render target changed bitand succeeded
        }

        else
        {
            //JAM 17Dec03
            IDirectDrawSurface7Ptr pDDS;

#ifdef FF_LINUX
            // Re-get for the actual comparison below
            pDDS = nullptr;
#endif
            if (FAILED(m_pD3DD->GetRenderTarget(&pDDS)) or pDDS not_eq pRenderTarget)
            {
                IDirectDrawSurface7Ptr pRenderTargetOld;
                CheckHR(m_pD3DD->GetRenderTarget(&pRenderTargetOld));

                if (pRenderTargetOld)
                {
                    IDirectDrawSurface7Ptr pDDSZB;
                    DDSCAPS2 ddscaps = { DDSCAPS_ZBUFFER, 0, 0, 0 };
                    pRenderTargetOld->GetAttachedSurface(&ddscaps, &pDDSZB);

                    if (pDDSZB)
                    {
                        CheckHR(pRenderTargetOld->DeleteAttachedSurface(0, pDDSZB));

                        if (FAILED(pRenderTarget->AddAttachedSurface(pDDSZB)))
                            CheckHR(pRenderTargetOld->AddAttachedSurface(pDDSZB));
                    }
                }

                // DX - RED - U CAN CHANGE TARGET IN A SCENE...
                //if( bInBeginScene ) INT3; // ASSO: break if still in BeginScene
                //JAM

                // Now change the render target
                CheckHR(m_pD3DD->SetRenderTarget(pRenderTarget, NULL));

                return true; // render target changed
            }

            return false; // render target NOT changed
        }
    }

    catch (_com_error e)
    {
        MonoPrint("DXContext::SetRenderTarget - Error 0x%X\n", e.Error());
        return false;
    }
}

void DXContext::EnumZBufferFormats(void *parr)
{
    ((PIXELFMT_ARRAY *) parr)->clear();
    m_pD3D->EnumZBufferFormats(m_guidD3D, EnumZBufferFormatsCallback, parr);
}

HRESULT CALLBACK DXContext::EnumZBufferFormatsCallback(LPDDPIXELFORMAT lpDDPixFmt, LPVOID lpContext)
{
    if (lpDDPixFmt->dwFlags bitand DDPF_ZBUFFER)
    {
        PIXELFMT_ARRAY *pThis = (PIXELFMT_ARRAY *)lpContext;
        pThis->push_back(*lpDDPixFmt);
    }

    return D3DENUMRET_OK;
}

void DXContext::AttachDepthBuffer(IDirectDrawSurface7 *p)
{
    //JAM 25Jul03
    //return;

#ifdef FF_LINUX
    // On Linux with OpenGL, depth buffers are managed automatically by the GL context.
    // We don't need to create a DirectDraw Z-buffer surface - OpenGL handles this.
    // Skip the entire function to avoid using the corrupt m_pDD pointer.
    (void)p;  // Suppress unused parameter warning
    fprintf(stderr, "[AttachDepthBuffer] Linux: Skipping - OpenGL manages depth buffers\n"); fflush(stderr);
    return;
#endif

    // Check the display mode, and
    DDSURFACEDESC2 ddsd_disp;
    ZeroMemory(&ddsd_disp, sizeof(ddsd_disp));
    ddsd_disp.dwSize = sizeof(ddsd_disp);
    CheckHR(m_pDD->GetDisplayMode(&ddsd_disp));

    IDirectDrawSurface7Ptr pDDSZB;
    PIXELFMT_ARRAY arrZBFmts;

    EnumZBufferFormats(&arrZBFmts);

    if ( not arrZBFmts.empty())
    {
        // Match Z Buffer depth to the display depth
        DDPIXELFORMAT pixfmt;

        PIXELFMT_ARRAY::iterator it;

        for (it = arrZBFmts.begin(); it not_eq arrZBFmts.end(); it++)
        {
            // RV - RED - OK, Restored old original Code, seems the Stencil search causes a 25% FPS drop, dunno why
            // as we use the setncil on a surface not having it now
            // if(it->dwZBufferBitDepth >= ddsd_disp.ddpfPixelFormat.dwRGBBitCount and it->dwStencilBitDepth>=8)
            if (it->dwZBufferBitDepth == ddsd_disp.ddpfPixelFormat.dwRGBBitCount)
            {
                pixfmt = *it;
                break;
            }
        }

        DDSURFACEDESC2 ddsd;
        ZeroMemory(&ddsd, sizeof(ddsd));
        ddsd.dwSize = sizeof(ddsd);
        ddsd.dwFlags = DDSD_CAPS bitor DDSD_WIDTH bitor DDSD_HEIGHT bitor DDSD_PIXELFORMAT;
        ddsd.ddsCaps.dwCaps = DDSCAPS_ZBUFFER;
        ddsd.dwWidth = m_nWidth;
        ddsd.dwHeight = m_nHeight;
        ddsd.ddpfPixelFormat = pixfmt;

        // Software devices require system-memory depth buffers.
        if (m_eDeviceCategory == D3DDeviceCategory_Software)
            ddsd.ddsCaps.dwCaps or_eq DDSCAPS_SYSTEMMEMORY;

        CheckHR(m_pDD->CreateSurface(&ddsd, &pDDSZB, NULL));

        // Attach it to the render target
        CheckHR(p->AddAttachedSurface(pDDSZB));
    }

    else MonoPrint("DXContext::AttachDepthBuffer() - Warning: No Z-Buffer formats \n");
}

void DXContext::CheckCaps()
{
#ifdef _DEBUG
    MonoPrint("-- DXContext - Start of Caps report\n");

    if (m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_SEPARATETEXTUREMEMORIES)
        MonoPrint(" Device has separate texture memories per stage. \n");

    if (m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_TEXTURENONLOCALVIDMEM)
        MonoPrint(" Device supports AGP texturing\n");

    if ( not (m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_FLOATTLVERTEX))
        MonoPrint(" Device does not accepts floating point for post-transform vertex data. \n");

    if ( not (m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_TLVERTEXSYSTEMMEMORY))
        MonoPrint(" Device does not accept TL VBs in system memory.\n");

    if ( not (m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_TLVERTEXVIDEOMEMORY))
        MonoPrint(" Device does not accept TL VBs in video memory.\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwRasterCaps bitand D3DPRASTERCAPS_DITHER))
        MonoPrint(" No dithering\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwRasterCaps bitand D3DPRASTERCAPS_FOGRANGE))
        MonoPrint(" No range based fog\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwRasterCaps bitand D3DPRASTERCAPS_FOGVERTEX))
        MonoPrint(" No vertex fog\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwRasterCaps bitand D3DPRASTERCAPS_ZTEST))
        MonoPrint(" No Z Test support\n");

    if (m_pD3DHWDeviceDesc->dpcTriCaps.dwAlphaCmpCaps == D3DPCMPCAPS_ALWAYS or
        m_pD3DHWDeviceDesc->dpcTriCaps.dwAlphaCmpCaps == D3DPCMPCAPS_NEVER)
        MonoPrint(" No Alpha Test support\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwSrcBlendCaps bitand D3DPBLENDCAPS_SRCALPHA))
        MonoPrint(" SrcBlend SRCALPHA not supported\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwDestBlendCaps bitand D3DPBLENDCAPS_INVSRCALPHA))
        MonoPrint(" DestBlend INVSRCALPHA not supported\n");

    if ( not (m_pcapsDD->dwCaps bitand DDCAPS_COLORKEY and 
          m_pcapsDD->dwCKeyCaps bitand DDCKEYCAPS_DESTBLT and 
          m_pD3DHWDeviceDesc->dwDevCaps bitand D3DDEVCAPS_DRAWPRIMTLVERTEX))
        MonoPrint(" Insufficient color key support\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps bitand D3DPSHADECAPS_ALPHAFLATBLEND))
        MonoPrint(" No alpha blending with flat shading\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps bitand D3DPSHADECAPS_COLORGOURAUDRGB))
        MonoPrint(" No gouraud shading\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps bitand D3DPSHADECAPS_SPECULARFLATRGB))
        MonoPrint(" No specular flat shading\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps bitand D3DPSHADECAPS_SPECULARGOURAUDRGB))
        MonoPrint(" No specular gouraud shading\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwShadeCaps bitand D3DPSHADECAPS_FOGGOURAUD))
        MonoPrint(" No gouraud fog\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_ALPHA))
        MonoPrint(" No alpha textures\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_ALPHAPALETTE))
        MonoPrint(" No palettized alpha textures\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_COLORKEYBLEND))
        MonoPrint(" No color key blending support\n");

    if (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_POW2)
        MonoPrint(" Textures must be power of 2\n");

    if (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_SQUAREONLY)
        MonoPrint(" Textures must be square\n");

    if ( not (m_pD3DHWDeviceDesc->dpcTriCaps.dwTextureCaps bitand D3DPTEXTURECAPS_TRANSPARENCY))
        MonoPrint(" No texture transparency\n");

    if ( not (m_pD3DHWDeviceDesc->dwTextureOpCaps bitand D3DTEXOPCAPS_BLENDDIFFUSEALPHA)) // required for MPR_TF_ALPHA
        MonoPrint(" No D3DTOP_BLENDDIFFUSEALPHA (MPR_TF_ALPHA wont work ie. smoke trails)\n");

    MonoPrint("-- DXContext - End of Caps report\n");
#endif
}

bool DXContext::ValidateD3DDevice()
{
#ifdef _DEBUG
    DWORD dwPasses = 0;
    HRESULT hr = m_pD3DD->ValidateDevice(&dwPasses);

    if (FAILED(hr))
    {
        char *strError = "Unknown error";

        switch (hr)
        {
            case DDERR_INVALIDOBJECT:
                strError = "DDERR_INVALIDOBJECT";
                break;

            case DDERR_INVALIDPARAMS:
                strError = "DDERR_INVALIDPARAMS";
                break;

            case D3DERR_CONFLICTINGTEXTUREFILTER:
                strError = "D3DERR_CONFLICTINGTEXTUREFILTER";
                break;

            case D3DERR_CONFLICTINGTEXTUREPALETTE:
                strError = "D3DERR_CONFLICTINGTEXTUREPALETTE";
                break;

            case D3DERR_TOOMANYOPERATIONS:
                strError = "D3DERR_TOOMANYOPERATIONS";
                break;

            case D3DERR_UNSUPPORTEDALPHAARG:
                strError = "D3DERR_UNSUPPORTEDALPHAARG";
                break;

            case D3DERR_UNSUPPORTEDALPHAOPERATION:
                strError = "D3DERR_UNSUPPORTEDALPHAOPERATION";
                break;

            case D3DERR_UNSUPPORTEDCOLORARG:
                strError = "D3DERR_UNSUPPORTEDCOLORARG";
                break;

            case D3DERR_UNSUPPORTEDCOLOROPERATION:
                strError = "D3DERR_UNSUPPORTEDCOLOROPERATION";
                break;

            case D3DERR_UNSUPPORTEDFACTORVALUE:
                strError = "D3DERR_UNSUPPORTEDFACTORVALUE";
                break;

            case D3DERR_UNSUPPORTEDTEXTUREFILTER:
                strError = "D3DERR_UNSUPPORTEDTEXTUREFILTER";
                break;

            case D3DERR_WRONGTEXTUREFORMAT:
                strError = "D3DERR_WRONGTEXTUREFORMAT";
                break;
        }

        MonoPrint(">>> DXContext::ValidateD3DDevice: ValidateDevice failed with 0x%X (%s) - %d passes required\n",
                  hr, strError, dwPasses);
    }

    return SUCCEEDED(hr);
#else
    return true;
#endif
}

DWORD DXContext::TestCooperativeLevel()
{
    HRESULT hr = m_pDD->TestCooperativeLevel();

    if (hr not_eq DD_OK)
    {
        do
        {
            Sleep(100);
            hr = m_pDD->TestCooperativeLevel();
        }
        while (hr not_eq DD_OK);

        return S_FALSE; // surface were lost
    }

    return DD_OK; // no change
}
