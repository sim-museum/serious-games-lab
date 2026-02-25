/*
 * FreeFalcon Linux Port - dinput.h compatibility
 *
 * DirectInput stub interface - will be replaced by SDL2
 */

#ifndef FF_COMPAT_DINPUT_H
#define FF_COMPAT_DINPUT_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * DirectInput Version
 * ============================================================ */

#define DIRECTINPUT_VERSION 0x0800

/* ============================================================
 * DirectInput Constants
 * ============================================================ */

/* Device types */
#define DI8DEVTYPE_DEVICE           0x11
#define DI8DEVTYPE_MOUSE            0x12
#define DI8DEVTYPE_KEYBOARD         0x13
#define DI8DEVTYPE_JOYSTICK         0x14
#define DI8DEVTYPE_GAMEPAD          0x15
#define DI8DEVTYPE_DRIVING          0x16
#define DI8DEVTYPE_FLIGHT           0x17
#define DI8DEVTYPE_1STPERSON        0x18
#define DI8DEVTYPE_DEVICECTRL       0x19
#define DI8DEVTYPE_SCREENPOINTER    0x1A
#define DI8DEVTYPE_REMOTE           0x1B
#define DI8DEVTYPE_SUPPLEMENTAL     0x1C

/* Device classes for EnumDevices */
#define DI8DEVCLASS_ALL             0
#define DI8DEVCLASS_DEVICE          1
#define DI8DEVCLASS_POINTER         2
#define DI8DEVCLASS_KEYBOARD        3
#define DI8DEVCLASS_GAMECTRL        4

/* Cooperative level flags */
#define DISCL_EXCLUSIVE             0x00000001
#define DISCL_NONEXCLUSIVE          0x00000002
#define DISCL_FOREGROUND            0x00000004
#define DISCL_BACKGROUND            0x00000008
#define DISCL_NOWINKEY              0x00000010

/* Enumeration flags */
#define DIEDFL_ALLDEVICES           0x00000000
#define DIEDFL_ATTACHEDONLY         0x00000001
#define DIEDFL_FORCEFEEDBACK        0x00000100
#define DIEDFL_INCLUDEALIASES       0x00010000
#define DIEDFL_INCLUDEPHANTOMS      0x00020000
#define DIEDFL_INCLUDEHIDDEN        0x00040000

/* Data format flags */
#define DIDFT_ALL                   0x00000000
#define DIDFT_RELAXIS               0x00000001
#define DIDFT_ABSAXIS               0x00000002
#define DIDFT_AXIS                  0x00000003
#define DIDFT_PSHBUTTON             0x00000004
#define DIDFT_TGLBUTTON             0x00000008
#define DIDFT_BUTTON                0x0000000C
#define DIDFT_POV                   0x00000010
#define DIDFT_COLLECTION            0x00000040
#define DIDFT_NODATA                0x00000080
#define DIDFT_ANYINSTANCE           0x00FFFF00
#define DIDFT_INSTANCEMASK          DIDFT_ANYINSTANCE
#define DIDFT_FFACTUATOR            0x01000000
#define DIDFT_FFEFFECTTRIGGER       0x02000000
#define DIDFT_OUTPUT                0x10000000
#define DIDFT_VENDORDEFINED         0x04000000
#define DIDFT_ALIAS                 0x08000000
#define DIDFT_OPTIONAL              0x80000000

#define DIDFT_MAKEINSTANCE(n)       ((WORD)(n) << 8)
#define DIDFT_GETTYPE(n)            LOBYTE(n)
#define DIDFT_GETINSTANCE(n)        LOWORD((n) >> 8)

/* Object data flags */
#define DIDF_ABSAXIS                0x00000001
#define DIDF_RELAXIS                0x00000002

/* Effect flags */
#define DIEFF_OBJECTIDS             0x00000001
#define DIEFF_OBJECTOFFSETS         0x00000002
#define DIEFF_CARTESIAN             0x00000010
#define DIEFF_POLAR                 0x00000020
#define DIEFF_SPHERICAL             0x00000040

/* Effect types */
#define DIEFT_ALL                   0x00000000
#define DIEFT_CONSTANTFORCE         0x00000001
#define DIEFT_RAMPFORCE             0x00000002
#define DIEFT_PERIODIC              0x00000003
#define DIEFT_CONDITION             0x00000004
#define DIEFT_CUSTOMFORCE           0x00000005
#define DIEFT_HARDWARE              0x000000FF
#define DIEFT_FFATTACK              0x00000200
#define DIEFT_FFFADE                0x00000400
#define DIEFT_SATURATION            0x00000800
#define DIEFT_POSNEGCOEFFICIENTS    0x00001000
#define DIEFT_POSNEGSATURATION      0x00002000
#define DIEFT_DEADBAND              0x00004000
#define DIEFT_STARTDELAY            0x00008000
#define DIEFT_GETTYPE(n)            LOBYTE(n)

/* Effect parameter flags */
#define DIEP_DURATION               0x00000001
#define DIEP_SAMPLEPERIOD           0x00000002
#define DIEP_GAIN                   0x00000004
#define DIEP_TRIGGERBUTTON          0x00000008
#define DIEP_TRIGGERREPEATINTERVAL  0x00000010
#define DIEP_AXES                   0x00000020
#define DIEP_DIRECTION              0x00000040
#define DIEP_ENVELOPE               0x00000080
#define DIEP_TYPESPECIFICPARAMS     0x00000100
#define DIEP_STARTDELAY             0x00000200
#define DIEP_ALLPARAMS_DX5          0x000001FF
#define DIEP_ALLPARAMS              0x000003FF
#define DIEP_START                  0x20000000
#define DIEP_NORESTART              0x40000000
#define DIEP_NODOWNLOAD             0x80000000

/* Keyboard scan codes for data format */
#define DIK_ESCAPE          0x01
#define DIK_1               0x02
#define DIK_2               0x03
#define DIK_3               0x04
#define DIK_4               0x05
#define DIK_5               0x06
#define DIK_6               0x07
#define DIK_7               0x08
#define DIK_8               0x09
#define DIK_9               0x0A
#define DIK_0               0x0B
#define DIK_MINUS           0x0C
#define DIK_EQUALS          0x0D
#define DIK_BACK            0x0E
#define DIK_TAB             0x0F
#define DIK_Q               0x10
#define DIK_W               0x11
#define DIK_E               0x12
#define DIK_R               0x13
#define DIK_T               0x14
#define DIK_Y               0x15
#define DIK_U               0x16
#define DIK_I               0x17
#define DIK_O               0x18
#define DIK_P               0x19
#define DIK_LBRACKET        0x1A
#define DIK_RBRACKET        0x1B
#define DIK_RETURN          0x1C
#define DIK_LCONTROL        0x1D
#define DIK_A               0x1E
#define DIK_S               0x1F
#define DIK_D               0x20
#define DIK_F               0x21
#define DIK_G               0x22
#define DIK_H               0x23
#define DIK_J               0x24
#define DIK_K               0x25
#define DIK_L               0x26
#define DIK_SEMICOLON       0x27
#define DIK_APOSTROPHE      0x28
#define DIK_GRAVE           0x29
#define DIK_LSHIFT          0x2A
#define DIK_BACKSLASH       0x2B
#define DIK_Z               0x2C
#define DIK_X               0x2D
#define DIK_C               0x2E
#define DIK_V               0x2F
#define DIK_B               0x30
#define DIK_N               0x31
#define DIK_M               0x32
#define DIK_COMMA           0x33
#define DIK_PERIOD          0x34
#define DIK_SLASH           0x35
#define DIK_RSHIFT          0x36
#define DIK_MULTIPLY        0x37
#define DIK_LMENU           0x38
#define DIK_SPACE           0x39
#define DIK_CAPITAL         0x3A
#define DIK_F1              0x3B
#define DIK_F2              0x3C
#define DIK_F3              0x3D
#define DIK_F4              0x3E
#define DIK_F5              0x3F
#define DIK_F6              0x40
#define DIK_F7              0x41
#define DIK_F8              0x42
#define DIK_F9              0x43
#define DIK_F10             0x44
#define DIK_NUMLOCK         0x45
#define DIK_SCROLL          0x46
#define DIK_SYSRQ           0xB7
#define DIK_NUMPAD7         0x47
#define DIK_NUMPAD8         0x48
#define DIK_NUMPAD9         0x49
#define DIK_SUBTRACT        0x4A
#define DIK_NUMPAD4         0x4B
#define DIK_NUMPAD5         0x4C
#define DIK_NUMPAD6         0x4D
#define DIK_ADD             0x4E
#define DIK_NUMPAD1         0x4F
#define DIK_NUMPAD2         0x50
#define DIK_NUMPAD3         0x51
#define DIK_NUMPAD0         0x52
#define DIK_DECIMAL         0x53
#define DIK_F11             0x57
#define DIK_F12             0x58
#define DIK_NUMPADENTER     0x9C
#define DIK_RCONTROL        0x9D
#define DIK_DIVIDE          0xB5
#define DIK_RMENU           0xB8
#define DIK_HOME            0xC7
#define DIK_UP              0xC8
#define DIK_PRIOR           0xC9
#define DIK_LEFT            0xCB
#define DIK_RIGHT           0xCD
#define DIK_END             0xCF
#define DIK_DOWN            0xD0
#define DIK_NEXT            0xD1
#define DIK_INSERT          0xD2
#define DIK_DELETE          0xD3
#define DIK_LWIN            0xDB
#define DIK_RWIN            0xDC
#define DIK_APPS            0xDD

/* Joystick offsets */
#define DIJOFS_X            0
#define DIJOFS_Y            4
#define DIJOFS_Z            8
#define DIJOFS_RX           12
#define DIJOFS_RY           16
#define DIJOFS_RZ           20
#define DIJOFS_SLIDER(n)    (24 + (n) * 4)
#define DIJOFS_POV(n)       (32 + (n) * 4)
#define DIJOFS_BUTTON(n)    (48 + (n))

/* Return values */
#define DI_OK                       S_OK
#define DI_NOTATTACHED              0x00000001
#define DI_BUFFEROVERFLOW           0x00000001
#define DI_PROPNOEFFECT             0x00000001
#define DI_NOEFFECT                 0x00000001
#define DI_POLLEDDEVICE             0x00000002
#define DI_DOWNLOADSKIPPED          0x00000003
#define DI_EFFECTRESTARTED          0x00000004
#define DI_TRUNCATED                0x00000008
#define DI_SETTINGSNOTSAVED         0x0000000B
#define DI_TRUNCATEDANDRESTARTED    0x0000000C
#define DI_WRITEPROTECT             0x00000013

#define DIERR_OLDDIRECTINPUTVERSION     0x8007047E
#define DIERR_BETADIRECTINPUTVERSION    0x80070481
#define DIERR_BADDRIVERVER              0x80070077
#define DIERR_DEVICENOTREG              REGDB_E_CLASSNOTREG
#define DIERR_NOTFOUND                  0x80070002
#define DIERR_OBJECTNOTFOUND            0x80070002
#define DIERR_INVALIDPARAM              E_INVALIDARG
#define DIERR_NOINTERFACE               E_NOINTERFACE
#define DIERR_GENERIC                   E_FAIL
#define DIERR_OUTOFMEMORY               E_OUTOFMEMORY
#define DIERR_UNSUPPORTED               E_NOTIMPL
#define DIERR_NOTINITIALIZED            0x80070015
#define DIERR_ALREADYINITIALIZED        0x800704DF
#define DIERR_NOAGGREGATION             CLASS_E_NOAGGREGATION
#define DIERR_OTHERAPPHASPRIO           E_ACCESSDENIED
#define DIERR_INPUTLOST                 0x8007001E
#define DIERR_ACQUIRED                  0x800700AA
#define DIERR_NOTACQUIRED               0x8007000C
#define DIERR_READONLY                  E_ACCESSDENIED
#define DIERR_HANDLEEXISTS              E_ACCESSDENIED
#define DIERR_INSUFFICIENTPRIVS         0x80040200
#define DIERR_DEVICEFULL                0x80040201
#define DIERR_MOREDATA                  0x80040202
#define DIERR_NOTDOWNLOADED             0x80040203
#define DIERR_HASEFFECTS                0x80040204
#define DIERR_NOTEXCLUSIVEACQUIRED      0x80040205
#define DIERR_INCOMPLETEEFFECT          0x80040206
#define DIERR_NOTBUFFERED               0x80040207
#define DIERR_EFFECTPLAYING             0x80040208
#define DIERR_UNPLUGGED                 0x80040209
#define DIERR_REPORTFULL                0x8004020A
#define DIERR_MAPFILEFAIL               0x8004020B

#define REGDB_E_CLASSNOTREG             0x80040154
#ifndef CLASS_E_NOAGGREGATION
#define CLASS_E_NOAGGREGATION           0x80040110
#endif

/* Enumeration return values */
#define DIENUM_STOP         0
#define DIENUM_CONTINUE     1

/* Mouse data format offsets */
#define DIMOFS_X            0
#define DIMOFS_Y            4
#define DIMOFS_Z            8
#define DIMOFS_BUTTON0      12
#define DIMOFS_BUTTON1      13
#define DIMOFS_BUTTON2      14
#define DIMOFS_BUTTON3      15
#define DIMOFS_BUTTON4      16
#define DIMOFS_BUTTON5      17
#define DIMOFS_BUTTON6      18
#define DIMOFS_BUTTON7      19

/* DirectInput version compatibility */
typedef struct IDirectInputDevice8A *LPDIRECTINPUTDEVICE2;
typedef struct IDirectInputDevice8A *LPDIRECTINPUTDEVICE2A;

/* ============================================================
 * DirectInput Structures
 * ============================================================ */

typedef struct DIDEVICEINSTANCEA {
    DWORD dwSize;
    GUID guidInstance;
    GUID guidProduct;
    DWORD dwDevType;
    CHAR tszInstanceName[260];
    CHAR tszProductName[260];
    GUID guidFFDriver;
    WORD wUsagePage;
    WORD wUsage;
} DIDEVICEINSTANCEA, *LPDIDEVICEINSTANCEA;

typedef const DIDEVICEINSTANCEA *LPCDIDEVICEINSTANCEA;
typedef DIDEVICEINSTANCEA DIDEVICEINSTANCE;
typedef LPDIDEVICEINSTANCEA LPDIDEVICEINSTANCE;
typedef LPCDIDEVICEINSTANCEA LPCDIDEVICEINSTANCE;

typedef struct DIDEVICEOBJECTINSTANCEA {
    DWORD dwSize;
    GUID guidType;
    DWORD dwOfs;
    DWORD dwType;
    DWORD dwFlags;
    CHAR tszName[260];
    DWORD dwFFMaxForce;
    DWORD dwFFForceResolution;
    WORD wCollectionNumber;
    WORD wDesignatorIndex;
    WORD wUsagePage;
    WORD wUsage;
    DWORD dwDimension;
    WORD wExponent;
    WORD wReportId;
} DIDEVICEOBJECTINSTANCEA, *LPDIDEVICEOBJECTINSTANCEA;

typedef const DIDEVICEOBJECTINSTANCEA *LPCDIDEVICEOBJECTINSTANCEA;
typedef DIDEVICEOBJECTINSTANCEA DIDEVICEOBJECTINSTANCE;
typedef LPDIDEVICEOBJECTINSTANCEA LPDIDEVICEOBJECTINSTANCE;
typedef LPCDIDEVICEOBJECTINSTANCEA LPCDIDEVICEOBJECTINSTANCE;

typedef struct DIDATAFORMAT {
    DWORD dwSize;
    DWORD dwObjSize;
    DWORD dwFlags;
    DWORD dwDataSize;
    DWORD dwNumObjs;
    LPVOID rgodf;  /* LPDIOBJECTDATAFORMAT */
} DIDATAFORMAT, *LPDIDATAFORMAT;

typedef const DIDATAFORMAT *LPCDIDATAFORMAT;

typedef struct DIOBJECTDATAFORMAT {
    const GUID *pguid;
    DWORD dwOfs;
    DWORD dwType;
    DWORD dwFlags;
} DIOBJECTDATAFORMAT, *LPDIOBJECTDATAFORMAT;

typedef struct DIJOYSTATE {
    LONG lX;
    LONG lY;
    LONG lZ;
    LONG lRx;
    LONG lRy;
    LONG lRz;
    LONG rglSlider[2];
    DWORD rgdwPOV[4];
    BYTE rgbButtons[32];
} DIJOYSTATE, *LPDIJOYSTATE;

typedef struct DIJOYSTATE2 {
    LONG lX;
    LONG lY;
    LONG lZ;
    LONG lRx;
    LONG lRy;
    LONG lRz;
    LONG rglSlider[2];
    DWORD rgdwPOV[4];
    BYTE rgbButtons[128];
    LONG lVX;
    LONG lVY;
    LONG lVZ;
    LONG lVRx;
    LONG lVRy;
    LONG lVRz;
    LONG rglVSlider[2];
    LONG lAX;
    LONG lAY;
    LONG lAZ;
    LONG lARx;
    LONG lARy;
    LONG lARz;
    LONG rglASlider[2];
    LONG lFX;
    LONG lFY;
    LONG lFZ;
    LONG lFRx;
    LONG lFRy;
    LONG lFRz;
    LONG rglFSlider[2];
} DIJOYSTATE2, *LPDIJOYSTATE2;

typedef struct DIMOUSESTATE {
    LONG lX;
    LONG lY;
    LONG lZ;
    BYTE rgbButtons[4];
} DIMOUSESTATE, *LPDIMOUSESTATE;

typedef struct DIMOUSESTATE2 {
    LONG lX;
    LONG lY;
    LONG lZ;
    BYTE rgbButtons[8];
} DIMOUSESTATE2, *LPDIMOUSESTATE2;

/* Effect structures */
typedef struct DIENVELOPE {
    DWORD dwSize;
    DWORD dwAttackLevel;
    DWORD dwAttackTime;
    DWORD dwFadeLevel;
    DWORD dwFadeTime;
} DIENVELOPE, *LPDIENVELOPE;

typedef const DIENVELOPE *LPCDIENVELOPE;

typedef struct DIEFFECT {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwDuration;
    DWORD dwSamplePeriod;
    DWORD dwGain;
    DWORD dwTriggerButton;
    DWORD dwTriggerRepeatInterval;
    DWORD cAxes;
    LPDWORD rgdwAxes;
    LPLONG rglDirection;
    LPDIENVELOPE lpEnvelope;
    DWORD cbTypeSpecificParams;
    LPVOID lpvTypeSpecificParams;
    DWORD dwStartDelay;
} DIEFFECT, *LPDIEFFECT;

typedef const DIEFFECT *LPCDIEFFECT;

typedef struct DICONSTANTFORCE {
    LONG lMagnitude;
} DICONSTANTFORCE, *LPDICONSTANTFORCE;

typedef struct DIRAMPFORCE {
    LONG lStart;
    LONG lEnd;
} DIRAMPFORCE, *LPDIRAMPFORCE;

typedef struct DIPERIODIC {
    DWORD dwMagnitude;
    LONG lOffset;
    DWORD dwPhase;
    DWORD dwPeriod;
} DIPERIODIC, *LPDIPERIODIC;

typedef struct DICONDITION {
    LONG lOffset;
    LONG lPositiveCoefficient;
    LONG lNegativeCoefficient;
    DWORD dwPositiveSaturation;
    DWORD dwNegativeSaturation;
    LONG lDeadBand;
} DICONDITION, *LPDICONDITION;

/* Property structures */
typedef struct DIPROPHEADER {
    DWORD dwSize;
    DWORD dwHeaderSize;
    DWORD dwObj;
    DWORD dwHow;
} DIPROPHEADER, *LPDIPROPHEADER;

typedef const DIPROPHEADER *LPCDIPROPHEADER;

typedef struct DIPROPDWORD {
    DIPROPHEADER diph;
    DWORD dwData;
} DIPROPDWORD, *LPDIPROPDWORD;

typedef const DIPROPDWORD *LPCDIPROPDWORD;

typedef struct DIPROPRANGE {
    DIPROPHEADER diph;
    LONG lMin;
    LONG lMax;
} DIPROPRANGE, *LPDIPROPRANGE;

typedef const DIPROPRANGE *LPCDIPROPRANGE;

/* Calibration structures */
#define MAXCPOINTSNUM 8

typedef struct CPOINT {
    LONG lP;    /* Point */
    DWORD dwLog; /* Log */
} CPOINT;

typedef struct DIPROPCPOINTS {
    DIPROPHEADER diph;
    DWORD dwCPointsNum;  /* Number of calibration points */
    CPOINT cp[MAXCPOINTSNUM];
} DIPROPCPOINTS, *LPDIPROPCPOINTS;

typedef const DIPROPCPOINTS *LPCDIPROPCPOINTS;

#define DIPROP_CPOINTS ((LPVOID)11)

/* Device capabilities */
typedef struct DIDEVCAPS {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwDevType;
    DWORD dwAxes;
    DWORD dwButtons;
    DWORD dwPOVs;
    DWORD dwFFSamplePeriod;
    DWORD dwFFMinTimeResolution;
    DWORD dwFirmwareRevision;
    DWORD dwHardwareRevision;
    DWORD dwFFDriverVersion;
} DIDEVCAPS, *LPDIDEVCAPS;

/* Device capability flags */
#define DIDC_ATTACHED           0x00000001
#define DIDC_POLLEDDEVICE       0x00000002
#define DIDC_EMULATED           0x00000004
#define DIDC_POLLEDDATAFORMAT   0x00000008
#define DIDC_FORCEFEEDBACK      0x00000100
#define DIDC_FFATTACK           0x00000200
#define DIDC_FFFADE             0x00000400
#define DIDC_SATURATION         0x00000800
#define DIDC_POSNEGCOEFFICIENTS 0x00001000
#define DIDC_POSNEGSATURATION   0x00002000
#define DIDC_DEADBAND           0x00004000
#define DIDC_STARTDELAY         0x00008000
#define DIDC_ALIAS              0x00010000
#define DIDC_PHANTOM            0x00020000
#define DIDC_HIDDEN             0x00040000

/* Property types */
#define DIPH_DEVICE     0
#define DIPH_BYOFFSET   1
#define DIPH_BYID       2
#define DIPH_BYUSAGE    3

/* Common property GUIDs (as integers for stub) */
#define DIPROP_BUFFERSIZE       ((LPVOID)1)
#define DIPROP_AXISMODE         ((LPVOID)2)
#define DIPROP_GRANULARITY      ((LPVOID)3)
#define DIPROP_RANGE            ((LPVOID)4)
#define DIPROP_DEADZONE         ((LPVOID)5)
#define DIPROP_SATURATION       ((LPVOID)6)
#define DIPROP_FFGAIN           ((LPVOID)7)
#define DIPROP_FFLOAD           ((LPVOID)8)
#define DIPROP_AUTOCENTER       ((LPVOID)9)
#define DIPROP_CALIBRATIONMODE  ((LPVOID)10)

#define DIPROPAXISMODE_ABS      0
#define DIPROPAXISMODE_REL      1

#define DIPROPAUTOCENTER_OFF    0
#define DIPROPAUTOCENTER_ON     1

/* Effect info structure */
typedef struct DIEFFECTINFOA {
    DWORD dwSize;
    GUID guid;
    DWORD dwEffType;
    DWORD dwStaticParams;
    DWORD dwDynamicParams;
    CHAR tszName[260];
} DIEFFECTINFOA, *LPDIEFFECTINFOA;

typedef const DIEFFECTINFOA *LPCDIEFFECTINFOA;
typedef DIEFFECTINFOA DIEFFECTINFO;
typedef LPDIEFFECTINFOA LPDIEFFECTINFO;
typedef LPCDIEFFECTINFOA LPCDIEFFECTINFO;

/* Custom force structure */
typedef struct DICUSTOMFORCE {
    DWORD cChannels;
    DWORD dwSamplePeriod;
    DWORD cSamples;
    LPLONG rglForceData;
} DICUSTOMFORCE, *LPDICUSTOMFORCE;

/* ============================================================
 * DirectInput Interface Declarations (stubs)
 * ============================================================ */

/* Device object data - used for GetDeviceData */
typedef struct DIDEVICEOBJECTDATA {
    DWORD dwOfs;
    DWORD dwData;
    DWORD dwTimeStamp;
    DWORD dwSequence;
    UINT_PTR uAppData;
} DIDEVICEOBJECTDATA, *LPDIDEVICEOBJECTDATA;

/* Flags for GetDeviceData */
#define DIGDD_PEEK          0x00000001

/* Forward declarations */
struct IDirectInput8A;
struct IDirectInputDevice8A;
struct IDirectInputEffect;

/* Pointer typedefs (needed before struct definitions that use them) */
typedef struct IDirectInput8A       *LPDIRECTINPUT8A;
typedef struct IDirectInput8A       *LPDIRECTINPUT8;
typedef struct IDirectInputDevice8A *LPDIRECTINPUTDEVICE8A;
typedef struct IDirectInputDevice8A *LPDIRECTINPUTDEVICE8;
typedef struct IDirectInputEffect   *LPDIRECTINPUTEFFECT;

/* Callback types */
typedef BOOL (*LPDIENUMDEVICESCALLBACKA)(LPCDIDEVICEINSTANCEA, LPVOID);
typedef BOOL (*LPDIENUMEFFECTSCALLBACKA)(LPCVOID, LPVOID);  /* LPCDIEFFECTINFOA */
typedef BOOL (*LPDIENUMDEVICEOBJECTSCALLBACKA)(LPCDIDEVICEOBJECTINSTANCEA, LPVOID);

/* IDirectInputEffect interface stub */
struct IDirectInputEffect {
    HRESULT Start(DWORD dwIterations, DWORD dwFlags) { (void)dwIterations; (void)dwFlags; return DIERR_NOTINITIALIZED; }
    HRESULT Stop() { return DIERR_NOTINITIALIZED; }
    HRESULT Download() { return DIERR_NOTINITIALIZED; }
    HRESULT Unload() { return DIERR_NOTINITIALIZED; }
    HRESULT SetParameters(LPCDIEFFECT lpeff, DWORD dwFlags) { (void)lpeff; (void)dwFlags; return DIERR_NOTINITIALIZED; }
    HRESULT GetParameters(LPDIEFFECT lpeff, DWORD dwFlags) { (void)lpeff; (void)dwFlags; return DIERR_NOTINITIALIZED; }
    ULONG Release() { return 0; }
    ULONG AddRef() { return 1; }
};

/* IDirectInputDevice8A interface stub */
struct IDirectInputDevice8A {
    HRESULT Acquire() { return DIERR_NOTINITIALIZED; }
    HRESULT Unacquire() { return DIERR_NOTINITIALIZED; }
    HRESULT GetDeviceState(DWORD cbData, LPVOID lpvData) { (void)cbData; (void)lpvData; return DIERR_NOTINITIALIZED; }
    HRESULT GetDeviceData(DWORD cbObjectData, LPDIDEVICEOBJECTDATA rgdod, LPDWORD pdwInOut, DWORD dwFlags) {
        (void)cbObjectData; (void)rgdod; (void)pdwInOut; (void)dwFlags;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT SetDataFormat(LPCDIDATAFORMAT lpdf) { (void)lpdf; return DIERR_NOTINITIALIZED; }
    HRESULT SetCooperativeLevel(HWND hwnd, DWORD dwFlags) { (void)hwnd; (void)dwFlags; return DIERR_NOTINITIALIZED; }
    HRESULT SetProperty(const void* rguidProp, LPCDIPROPHEADER pdiph) { (void)rguidProp; (void)pdiph; return DIERR_NOTINITIALIZED; }
    HRESULT GetProperty(const void* rguidProp, LPDIPROPHEADER pdiph) { (void)rguidProp; (void)pdiph; return DIERR_NOTINITIALIZED; }
    HRESULT EnumObjects(LPDIENUMDEVICEOBJECTSCALLBACKA lpCallback, LPVOID pvRef, DWORD dwFlags) {
        (void)lpCallback; (void)pvRef; (void)dwFlags;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT GetCapabilities(LPDIDEVCAPS lpDIDevCaps) { (void)lpDIDevCaps; return DIERR_NOTINITIALIZED; }
    HRESULT CreateEffect(REFGUID rguid, LPCDIEFFECT lpeff, LPDIRECTINPUTEFFECT *ppdeff, void* punkOuter) {
        (void)rguid; (void)lpeff; (void)ppdeff; (void)punkOuter;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT EnumEffects(LPDIENUMEFFECTSCALLBACKA lpCallback, LPVOID pvRef, DWORD dwEffType) {
        (void)lpCallback; (void)pvRef; (void)dwEffType;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT GetEffectInfo(void* pdei, REFGUID rguid) { (void)pdei; (void)rguid; return DIERR_NOTINITIALIZED; }
    HRESULT GetForceFeedbackState(LPDWORD pdwOut) { (void)pdwOut; return DIERR_NOTINITIALIZED; }
    HRESULT SendForceFeedbackCommand(DWORD dwFlags) { (void)dwFlags; return DIERR_NOTINITIALIZED; }
    HRESULT Poll() { return DIERR_NOTINITIALIZED; }
    HRESULT GetDeviceInfo(LPDIDEVICEINSTANCEA pdidi) { (void)pdidi; return DIERR_NOTINITIALIZED; }
    HRESULT SetEventNotification(HANDLE hEvent) { (void)hEvent; return DIERR_NOTINITIALIZED; }
    HRESULT GetObjectInfo(LPDIDEVICEOBJECTINSTANCEA pdidoi, DWORD dwObj, DWORD dwHow) {
        (void)pdidoi; (void)dwObj; (void)dwHow;
        return DIERR_NOTINITIALIZED;
    }
    ULONG Release() { return 0; }
    ULONG AddRef() { return 1; }
};

/* IDirectInput8A interface stub */
struct IDirectInput8A {
    HRESULT CreateDevice(REFGUID rguid, LPDIRECTINPUTDEVICE8A *lplpDirectInputDevice, void* pUnkOuter) {
        (void)rguid; (void)lplpDirectInputDevice; (void)pUnkOuter;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT EnumDevices(DWORD dwDevType, LPDIENUMDEVICESCALLBACKA lpCallback, LPVOID pvRef, DWORD dwFlags) {
        (void)dwDevType; (void)lpCallback; (void)pvRef; (void)dwFlags;
        return DIERR_NOTINITIALIZED;
    }
    HRESULT GetDeviceStatus(REFGUID rguidInstance) { (void)rguidInstance; return DIERR_NOTINITIALIZED; }
    HRESULT RunControlPanel(HWND hwndOwner, DWORD dwFlags) { (void)hwndOwner; (void)dwFlags; return DIERR_NOTINITIALIZED; }
    ULONG Release() { return 0; }
    ULONG AddRef() { return 1; }
};

#define LPDIENUMDEVICESCALLBACK LPDIENUMDEVICESCALLBACKA
#define LPDIENUMEFFECTSCALLBACK LPDIENUMEFFECTSCALLBACKA
#define LPDIENUMDEVICEOBJECTSCALLBACK LPDIENUMDEVICEOBJECTSCALLBACKA

/* Creation function - stub */
static inline HRESULT DirectInput8Create(
    HINSTANCE hinst,
    DWORD dwVersion,
    REFIID riidltf,
    LPVOID *ppvOut,
    LPVOID punkOuter)
{
    (void)hinst; (void)dwVersion; (void)riidltf; (void)ppvOut; (void)punkOuter;
    return DIERR_NOTINITIALIZED;
}

/* Predefined data formats */
extern const DIDATAFORMAT c_dfDIKeyboard;
extern const DIDATAFORMAT c_dfDIMouse;
extern const DIDATAFORMAT c_dfDIMouse2;
extern const DIDATAFORMAT c_dfDIJoystick;
extern const DIDATAFORMAT c_dfDIJoystick2;

/* IID definitions (stubs) */
static const GUID IID_IDirectInput8A = {0};
static const GUID IID_IDirectInput8W = {0};
#define IID_IDirectInput8 IID_IDirectInput8A

/* Object type GUIDs */
static const GUID GUID_XAxis = {0};
static const GUID GUID_YAxis = {0};
static const GUID GUID_ZAxis = {0};
static const GUID GUID_RxAxis = {0};
static const GUID GUID_RyAxis = {0};
static const GUID GUID_RzAxis = {0};
static const GUID GUID_Slider = {0};
static const GUID GUID_Button = {0};
static const GUID GUID_Key = {0};
static const GUID GUID_POV = {0};

/* Effect type GUIDs */
static const GUID GUID_ConstantForce = {0};
static const GUID GUID_RampForce = {0};
static const GUID GUID_Square = {0};
static const GUID GUID_Sine = {0};
static const GUID GUID_Triangle = {0};
static const GUID GUID_SawtoothUp = {0};
static const GUID GUID_SawtoothDown = {0};
static const GUID GUID_Spring = {0};
static const GUID GUID_Damper = {0};
static const GUID GUID_Inertia = {0};
static const GUID GUID_Friction = {0};
static const GUID GUID_CustomForce = {0};

/* Device GUIDs */
static const GUID GUID_SysMouse = {0};
static const GUID GUID_SysKeyboard = {0};
static const GUID GUID_Joystick = {0};

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DINPUT_H */
