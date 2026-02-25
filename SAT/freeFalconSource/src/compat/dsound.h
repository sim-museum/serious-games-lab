/*
 * FreeFalcon Linux Port - dsound.h compatibility
 *
 * DirectSound interface - implemented via OpenAL
 */

#ifndef FF_COMPAT_DSOUND_H
#define FF_COMPAT_DSOUND_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "compat_mmsystem.h"

// Use OpenAL-backed implementation
#define FF_USE_OPENAL_DSOUND 1

/* C constants and structures are declared in extern "C" block */
#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * DirectSound Constants
 * ============================================================ */

/* Capability flags */
#define DSCAPS_PRIMARYMONO          0x00000001
#define DSCAPS_PRIMARYSTEREO        0x00000002
#define DSCAPS_PRIMARY8BIT          0x00000004
#define DSCAPS_PRIMARY16BIT         0x00000008
#define DSCAPS_CONTINUOUSRATE       0x00000010
#define DSCAPS_EMULDRIVER           0x00000020
#define DSCAPS_CERTIFIED            0x00000040
#define DSCAPS_SECONDARYMONO        0x00000100
#define DSCAPS_SECONDARYSTEREO      0x00000200
#define DSCAPS_SECONDARY8BIT        0x00000400
#define DSCAPS_SECONDARY16BIT       0x00000800

/* Buffer capability flags */
#define DSBCAPS_PRIMARYBUFFER       0x00000001
#define DSBCAPS_STATIC              0x00000002
#define DSBCAPS_LOCHARDWARE         0x00000004
#define DSBCAPS_LOCSOFTWARE         0x00000008
#define DSBCAPS_CTRL3D              0x00000010
#define DSBCAPS_CTRLFREQUENCY       0x00000020
#define DSBCAPS_CTRLPAN             0x00000040
#define DSBCAPS_CTRLVOLUME          0x00000080
#define DSBCAPS_CTRLPOSITIONNOTIFY  0x00000100
#define DSBCAPS_CTRLFX              0x00000200
#define DSBCAPS_STICKYFOCUS         0x00004000
#define DSBCAPS_GLOBALFOCUS         0x00008000
#define DSBCAPS_GETCURRENTPOSITION2 0x00010000
#define DSBCAPS_MUTE3DATMAXDISTANCE 0x00020000
#define DSBCAPS_LOCDEFER            0x00040000

/* Lock flags */
#define DSBLOCK_FROMWRITECURSOR     0x00000001
#define DSBLOCK_ENTIREBUFFER        0x00000002

/* Play flags */
#define DSBPLAY_LOOPING             0x00000001
#define DSBPLAY_LOCHARDWARE         0x00000002
#define DSBPLAY_LOCSOFTWARE         0x00000004
#define DSBPLAY_TERMINATEBY_TIME    0x00000008
#define DSBPLAY_TERMINATEBY_DISTANCE 0x00000010
#define DSBPLAY_TERMINATEBY_PRIORITY 0x00000020

/* Buffer status flags */
#define DSBSTATUS_PLAYING           0x00000001
#define DSBSTATUS_BUFFERLOST        0x00000002
#define DSBSTATUS_LOOPING           0x00000004
#define DSBSTATUS_LOCHARDWARE       0x00000008
#define DSBSTATUS_LOCSOFTWARE       0x00000010
#define DSBSTATUS_TERMINATED        0x00000020

/* 3D processing modes */
#define DS3DMODE_NORMAL             0x00000000
#define DS3DMODE_HEADRELATIVE       0x00000001
#define DS3DMODE_DISABLE            0x00000002

/* 3D apply flags */
#define DS3D_IMMEDIATE              0x00000000
#define DS3D_DEFERRED               0x00000001

/* SetCooperativeLevel flags */
#define DSSCL_NORMAL                0x00000001
#define DSSCL_PRIORITY              0x00000002
#define DSSCL_EXCLUSIVE             0x00000003
#define DSSCL_WRITEPRIMARY          0x00000004

/* Return values */
#define DS_OK                       S_OK
#define DS_NO_VIRTUALIZATION        0x0878000A
#define DSERR_ALLOCATED             0x8878000A
#define DSERR_CONTROLUNAVAIL        0x8878001E
#define DSERR_INVALIDPARAM          E_INVALIDARG
#define DSERR_INVALIDCALL           0x88780032
#define DSERR_GENERIC               E_FAIL
#define DSERR_PRIOLEVELNEEDED       0x88780046
#define DSERR_OUTOFMEMORY           E_OUTOFMEMORY
#define DSERR_BADFORMAT             0x88780064
#define DSERR_UNSUPPORTED           E_NOTIMPL
#define DSERR_NODRIVER              0x88780078
#define DSERR_ALREADYINITIALIZED    0x88780082
#define DSERR_NOAGGREGATION         CLASS_E_NOAGGREGATION
#define DSERR_BUFFERLOST            0x88780096
#define DSERR_OTHERAPPHASPRIO       0x887800A0
#define DSERR_UNINITIALIZED         0x887800AA
#define DSERR_NOINTERFACE           E_NOINTERFACE

#define CLASS_E_NOAGGREGATION       0x80040110

/* ============================================================
 * DirectSound Structures
 * ============================================================ */

typedef struct _DSBUFFERDESC {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwBufferBytes;
    DWORD dwReserved;
    LPWAVEFORMATEX lpwfxFormat;
    GUID guid3DAlgorithm;
} DSBUFFERDESC, *LPDSBUFFERDESC;

typedef const DSBUFFERDESC *LPCDSBUFFERDESC;

typedef struct _DSCAPS {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwMinSecondarySampleRate;
    DWORD dwMaxSecondarySampleRate;
    DWORD dwPrimaryBuffers;
    DWORD dwMaxHwMixingAllBuffers;
    DWORD dwMaxHwMixingStaticBuffers;
    DWORD dwMaxHwMixingStreamingBuffers;
    DWORD dwFreeHwMixingAllBuffers;
    DWORD dwFreeHwMixingStaticBuffers;
    DWORD dwFreeHwMixingStreamingBuffers;
    DWORD dwMaxHw3DAllBuffers;
    DWORD dwMaxHw3DStaticBuffers;
    DWORD dwMaxHw3DStreamingBuffers;
    DWORD dwFreeHw3DAllBuffers;
    DWORD dwFreeHw3DStaticBuffers;
    DWORD dwFreeHw3DStreamingBuffers;
    DWORD dwTotalHwMemBytes;
    DWORD dwFreeHwMemBytes;
    DWORD dwMaxContigFreeHwMemBytes;
    DWORD dwUnlockTransferRateHwBuffers;
    DWORD dwPlayCpuOverheadSwBuffers;
    DWORD dwReserved1;
    DWORD dwReserved2;
} DSCAPS, *LPDSCAPS;

typedef const DSCAPS *LPCDSCAPS;

typedef struct _DSBCAPS {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwBufferBytes;
    DWORD dwUnlockTransferRate;
    DWORD dwPlayCpuOverhead;
} DSBCAPS, *LPDSBCAPS;

typedef const DSBCAPS *LPCDSBCAPS;

/* 3D structures - use D3D's definition if available */
#ifndef _D3DVECTOR_DEFINED
typedef struct _D3DVECTOR {
    float x;
    float y;
    float z;
} D3DVECTOR, *LPD3DVECTOR;
#define _D3DVECTOR_DEFINED
#endif

typedef struct _DS3DBUFFER {
    DWORD dwSize;
    D3DVECTOR vPosition;
    D3DVECTOR vVelocity;
    DWORD dwInsideConeAngle;
    DWORD dwOutsideConeAngle;
    D3DVECTOR vConeOrientation;
    LONG lConeOutsideVolume;
    float flMinDistance;
    float flMaxDistance;
    DWORD dwMode;
} DS3DBUFFER, *LPDS3DBUFFER;

typedef const DS3DBUFFER *LPCDS3DBUFFER;

typedef struct _DS3DLISTENER {
    DWORD dwSize;
    D3DVECTOR vPosition;
    D3DVECTOR vVelocity;
    D3DVECTOR vOrientFront;
    D3DVECTOR vOrientTop;
    float flDistanceFactor;
    float flRolloffFactor;
    float flDopplerFactor;
} DS3DLISTENER, *LPDS3DLISTENER;

typedef const DS3DLISTENER *LPCDS3DLISTENER;

/* Notification position - must be before interfaces */
typedef struct _DSBPOSITIONNOTIFY {
    DWORD dwOffset;
    HANDLE hEventNotify;
} DSBPOSITIONNOTIFY, *LPDSBPOSITIONNOTIFY;

typedef const DSBPOSITIONNOTIFY *LPCDSBPOSITIONNOTIFY;

#define DSBPN_OFFSETSTOP            0xFFFFFFFF

/* Close the extern "C" block before C++ class definitions */
#ifdef __cplusplus
}
#endif

/* ============================================================
 * DirectSound Interface Declarations (C++ classes)
 * ============================================================ */

#ifndef _DIRECTSOUND_INTERFACES_DEFINED
#define _DIRECTSOUND_INTERFACES_DEFINED

#ifdef __cplusplus

#ifdef FF_USE_OPENAL_DSOUND
/* Use OpenAL-backed implementations */
#include "openal_dsound.h"

#else /* Stub implementations for when OpenAL is not available */

/* Forward declarations for all interfaces */
class IDirectSound;
class IDirectSoundBuffer;
class IDirectSound3DListener;
class IDirectSound3DBuffer;
class IDirectSoundNotify;
class IDirectSoundCapture;
class IDirectSoundCaptureBuffer;

/* Typedef pointer types early */
typedef IDirectSound           *LPDIRECTSOUND;
typedef IDirectSoundBuffer     *LPDIRECTSOUNDBUFFER;
typedef IDirectSound3DListener *LPDIRECTSOUND3DLISTENER;
typedef IDirectSound3DBuffer   *LPDIRECTSOUND3DBUFFER;
typedef IDirectSoundNotify     *LPDIRECTSOUNDNOTIFY;
typedef IDirectSoundCapture    *LPDIRECTSOUNDCAPTURE;
typedef IDirectSoundCaptureBuffer *LPDIRECTSOUNDCAPTUREBUFFER;

/* IDirectSoundBuffer interface stub */
class IDirectSoundBuffer {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT GetCaps(LPDSBCAPS pDSBufferCaps) { (void)pDSBufferCaps; return DSERR_GENERIC; }
    virtual HRESULT GetCurrentPosition(LPDWORD pdwCurrentPlayCursor, LPDWORD pdwCurrentWriteCursor) {
        (void)pdwCurrentPlayCursor; (void)pdwCurrentWriteCursor; return DSERR_GENERIC;
    }
    virtual HRESULT GetFormat(LPWAVEFORMATEX pwfxFormat, DWORD dwSizeAllocated, LPDWORD pdwSizeWritten) {
        (void)pwfxFormat; (void)dwSizeAllocated; (void)pdwSizeWritten; return DSERR_GENERIC;
    }
    virtual HRESULT GetVolume(LPLONG plVolume) { (void)plVolume; return DSERR_GENERIC; }
    virtual HRESULT GetPan(LPLONG plPan) { (void)plPan; return DSERR_GENERIC; }
    virtual HRESULT GetFrequency(LPDWORD pdwFrequency) { (void)pdwFrequency; return DSERR_GENERIC; }
    virtual HRESULT GetStatus(LPDWORD pdwStatus) { (void)pdwStatus; return DSERR_GENERIC; }
    virtual HRESULT Initialize(LPDIRECTSOUND pDirectSound, LPCDSBUFFERDESC pcDSBufferDesc) {
        (void)pDirectSound; (void)pcDSBufferDesc; return DSERR_GENERIC;
    }
    virtual HRESULT Lock(DWORD dwOffset, DWORD dwBytes, LPVOID *ppvAudioPtr1, LPDWORD pdwAudioBytes1,
                         LPVOID *ppvAudioPtr2, LPDWORD pdwAudioBytes2, DWORD dwFlags) {
        (void)dwOffset; (void)dwBytes; (void)ppvAudioPtr1; (void)pdwAudioBytes1;
        (void)ppvAudioPtr2; (void)pdwAudioBytes2; (void)dwFlags; return DSERR_GENERIC;
    }
    virtual HRESULT Play(DWORD dwReserved1, DWORD dwPriority, DWORD dwFlags) {
        (void)dwReserved1; (void)dwPriority; (void)dwFlags; return DS_OK;
    }
    virtual HRESULT SetCurrentPosition(DWORD dwNewPosition) { (void)dwNewPosition; return DS_OK; }
    virtual HRESULT SetFormat(LPCWAVEFORMATEX pcfxFormat) { (void)pcfxFormat; return DS_OK; }
    virtual HRESULT SetVolume(LONG lVolume) { (void)lVolume; return DS_OK; }
    virtual HRESULT SetPan(LONG lPan) { (void)lPan; return DS_OK; }
    virtual HRESULT SetFrequency(DWORD dwFrequency) { (void)dwFrequency; return DS_OK; }
    virtual HRESULT Stop(void) { return DS_OK; }
    virtual HRESULT Unlock(LPVOID pvAudioPtr1, DWORD dwAudioBytes1, LPVOID pvAudioPtr2, DWORD dwAudioBytes2) {
        (void)pvAudioPtr1; (void)dwAudioBytes1; (void)pvAudioPtr2; (void)dwAudioBytes2; return DS_OK;
    }
    virtual HRESULT Restore(void) { return DS_OK; }
};

/* IDirectSound8, IDirectSoundBuffer8 are same as base versions for our purposes */
typedef IDirectSound IDirectSound8;
typedef IDirectSoundBuffer IDirectSoundBuffer8;
typedef IDirectSound8 *LPDIRECTSOUND8;
typedef IDirectSoundBuffer8 *LPDIRECTSOUNDBUFFER8;

/* IDirectSound interface stub */
class IDirectSound {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT CreateSoundBuffer(LPCDSBUFFERDESC pcDSBufferDesc, LPDIRECTSOUNDBUFFER *ppDSBuffer, void* pUnkOuter) {
        (void)pcDSBufferDesc; (void)ppDSBuffer; (void)pUnkOuter; return DSERR_GENERIC;
    }
    virtual HRESULT GetCaps(LPDSCAPS pDSCaps) { (void)pDSCaps; return DSERR_GENERIC; }
    virtual HRESULT DuplicateSoundBuffer(LPDIRECTSOUNDBUFFER pDSBufferOriginal, LPDIRECTSOUNDBUFFER *ppDSBufferDuplicate) {
        (void)pDSBufferOriginal; (void)ppDSBufferDuplicate; return DSERR_GENERIC;
    }
    virtual HRESULT SetCooperativeLevel(HWND hwnd, DWORD dwLevel) { (void)hwnd; (void)dwLevel; return DS_OK; }
    virtual HRESULT Compact(void) { return DS_OK; }
    virtual HRESULT GetSpeakerConfig(LPDWORD pdwSpeakerConfig) { (void)pdwSpeakerConfig; return DSERR_GENERIC; }
    virtual HRESULT SetSpeakerConfig(DWORD dwSpeakerConfig) { (void)dwSpeakerConfig; return DS_OK; }
    virtual HRESULT Initialize(LPCGUID pcGuidDevice) { (void)pcGuidDevice; return DS_OK; }
};

/* IDirectSound8 is same as IDirectSound for our purposes */
typedef IDirectSound IDirectSound8;

/* IDirectSoundBuffer8 is same as IDirectSoundBuffer for our purposes */
typedef IDirectSoundBuffer IDirectSoundBuffer8;

/* IDirectSound3DListener interface stub */
class IDirectSound3DListener {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT GetAllParameters(LPDS3DLISTENER pListener) { (void)pListener; return DSERR_GENERIC; }
    virtual HRESULT GetDistanceFactor(float *pflDistanceFactor) { (void)pflDistanceFactor; return DSERR_GENERIC; }
    virtual HRESULT GetDopplerFactor(float *pflDopplerFactor) { (void)pflDopplerFactor; return DSERR_GENERIC; }
    virtual HRESULT GetOrientation(D3DVECTOR *pvOrientFront, D3DVECTOR *pvOrientTop) {
        (void)pvOrientFront; (void)pvOrientTop; return DSERR_GENERIC;
    }
    virtual HRESULT GetPosition(D3DVECTOR *pvPosition) { (void)pvPosition; return DSERR_GENERIC; }
    virtual HRESULT GetRolloffFactor(float *pflRolloffFactor) { (void)pflRolloffFactor; return DSERR_GENERIC; }
    virtual HRESULT GetVelocity(D3DVECTOR *pvVelocity) { (void)pvVelocity; return DSERR_GENERIC; }
    virtual HRESULT SetAllParameters(LPCDS3DLISTENER pcListener, DWORD dwApply) {
        (void)pcListener; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetDistanceFactor(float flDistanceFactor, DWORD dwApply) {
        (void)flDistanceFactor; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetDopplerFactor(float flDopplerFactor, DWORD dwApply) {
        (void)flDopplerFactor; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetOrientation(float xFront, float yFront, float zFront,
                                   float xTop, float yTop, float zTop, DWORD dwApply) {
        (void)xFront; (void)yFront; (void)zFront; (void)xTop; (void)yTop; (void)zTop; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetPosition(float x, float y, float z, DWORD dwApply) {
        (void)x; (void)y; (void)z; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetRolloffFactor(float flRolloffFactor, DWORD dwApply) {
        (void)flRolloffFactor; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetVelocity(float x, float y, float z, DWORD dwApply) {
        (void)x; (void)y; (void)z; (void)dwApply; return DS_OK;
    }
    virtual HRESULT CommitDeferredSettings(void) { return DS_OK; }
};

/* IDirectSound3DBuffer interface stub */
class IDirectSound3DBuffer {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT GetAllParameters(LPDS3DBUFFER pDs3dBuffer) { (void)pDs3dBuffer; return DSERR_GENERIC; }
    virtual HRESULT GetConeAngles(LPDWORD pdwInsideConeAngle, LPDWORD pdwOutsideConeAngle) {
        (void)pdwInsideConeAngle; (void)pdwOutsideConeAngle; return DSERR_GENERIC;
    }
    virtual HRESULT GetConeOrientation(D3DVECTOR *pvOrientation) { (void)pvOrientation; return DSERR_GENERIC; }
    virtual HRESULT GetConeOutsideVolume(LPLONG plConeOutsideVolume) { (void)plConeOutsideVolume; return DSERR_GENERIC; }
    virtual HRESULT GetMaxDistance(float *pflMaxDistance) { (void)pflMaxDistance; return DSERR_GENERIC; }
    virtual HRESULT GetMinDistance(float *pflMinDistance) { (void)pflMinDistance; return DSERR_GENERIC; }
    virtual HRESULT GetMode(LPDWORD pdwMode) { (void)pdwMode; return DSERR_GENERIC; }
    virtual HRESULT GetPosition(D3DVECTOR *pvPosition) { (void)pvPosition; return DSERR_GENERIC; }
    virtual HRESULT GetVelocity(D3DVECTOR *pvVelocity) { (void)pvVelocity; return DSERR_GENERIC; }
    virtual HRESULT SetAllParameters(LPCDS3DBUFFER pcDs3dBuffer, DWORD dwApply) {
        (void)pcDs3dBuffer; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetConeAngles(DWORD dwInsideConeAngle, DWORD dwOutsideConeAngle, DWORD dwApply) {
        (void)dwInsideConeAngle; (void)dwOutsideConeAngle; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetConeOrientation(float x, float y, float z, DWORD dwApply) {
        (void)x; (void)y; (void)z; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetConeOutsideVolume(LONG lConeOutsideVolume, DWORD dwApply) {
        (void)lConeOutsideVolume; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetMaxDistance(float flMaxDistance, DWORD dwApply) {
        (void)flMaxDistance; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetMinDistance(float flMinDistance, DWORD dwApply) {
        (void)flMinDistance; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetMode(DWORD dwMode, DWORD dwApply) { (void)dwMode; (void)dwApply; return DS_OK; }
    virtual HRESULT SetPosition(float x, float y, float z, DWORD dwApply) {
        (void)x; (void)y; (void)z; (void)dwApply; return DS_OK;
    }
    virtual HRESULT SetVelocity(float x, float y, float z, DWORD dwApply) {
        (void)x; (void)y; (void)z; (void)dwApply; return DS_OK;
    }
};

/* IDirectSoundNotify interface stub */
class IDirectSoundNotify {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT SetNotificationPositions(DWORD dwPositionNotifies, LPCDSBPOSITIONNOTIFY pcPositionNotifies) {
        (void)dwPositionNotifies; (void)pcPositionNotifies; return DS_OK;
    }
};

/* IDirectSoundCapture interface stub */
class IDirectSoundCapture {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT CreateCaptureBuffer(void* pcDSCBufferDesc, void** ppDSCBuffer, void* pUnkOuter) {
        (void)pcDSCBufferDesc; (void)ppDSCBuffer; (void)pUnkOuter; return DSERR_GENERIC;
    }
    virtual HRESULT GetCaps(void* pDSCCaps) { (void)pDSCCaps; return DSERR_GENERIC; }
    virtual HRESULT Initialize(LPCGUID pcGuidDevice) { (void)pcGuidDevice; return DS_OK; }
};

/* IDirectSoundCaptureBuffer interface stub */
class IDirectSoundCaptureBuffer {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef(void) { return 1; }
    virtual ULONG   Release(void) { return 0; }
    virtual HRESULT GetCaps(void* pDSCBCaps) { (void)pDSCBCaps; return DSERR_GENERIC; }
    virtual HRESULT GetCurrentPosition(LPDWORD pdwCapturePosition, LPDWORD pdwReadPosition) {
        (void)pdwCapturePosition; (void)pdwReadPosition; return DSERR_GENERIC;
    }
    virtual HRESULT GetFormat(LPWAVEFORMATEX pwfxFormat, DWORD dwSizeAllocated, LPDWORD pdwSizeWritten) {
        (void)pwfxFormat; (void)dwSizeAllocated; (void)pdwSizeWritten; return DSERR_GENERIC;
    }
    virtual HRESULT GetStatus(LPDWORD pdwStatus) { (void)pdwStatus; return DSERR_GENERIC; }
    virtual HRESULT Initialize(void* pDirectSoundCapture, void* pcDSCBufferDesc) {
        (void)pDirectSoundCapture; (void)pcDSCBufferDesc; return DS_OK;
    }
    virtual HRESULT Lock(DWORD dwOffset, DWORD dwBytes, LPVOID *ppvAudioPtr1, LPDWORD pdwAudioBytes1,
                         LPVOID *ppvAudioPtr2, LPDWORD pdwAudioBytes2, DWORD dwFlags) {
        (void)dwOffset; (void)dwBytes; (void)ppvAudioPtr1; (void)pdwAudioBytes1;
        (void)ppvAudioPtr2; (void)pdwAudioBytes2; (void)dwFlags; return DSERR_GENERIC;
    }
    virtual HRESULT Start(DWORD dwFlags) { (void)dwFlags; return DS_OK; }
    virtual HRESULT Stop(void) { return DS_OK; }
    virtual HRESULT Unlock(LPVOID pvAudioPtr1, DWORD dwAudioBytes1, LPVOID pvAudioPtr2, DWORD dwAudioBytes2) {
        (void)pvAudioPtr1; (void)dwAudioBytes1; (void)pvAudioPtr2; (void)dwAudioBytes2; return DS_OK;
    }
};

#endif /* FF_USE_OPENAL_DSOUND - end of stub implementations */

#else /* C compatibility - use void pointers */

typedef void IDirectSound;
typedef void IDirectSound8;
typedef void IDirectSoundBuffer;
typedef void IDirectSoundBuffer8;
typedef void IDirectSound3DListener;
typedef void IDirectSound3DBuffer;
typedef void IDirectSoundNotify;
typedef void IDirectSoundCapture;
typedef void IDirectSoundCaptureBuffer;

typedef IDirectSound        *LPDIRECTSOUND;
typedef IDirectSound8       *LPDIRECTSOUND8;
typedef IDirectSoundBuffer  *LPDIRECTSOUNDBUFFER;
typedef IDirectSoundBuffer8 *LPDIRECTSOUNDBUFFER8;
typedef IDirectSound3DListener *LPDIRECTSOUND3DLISTENER;
typedef IDirectSound3DBuffer   *LPDIRECTSOUND3DBUFFER;
typedef IDirectSoundNotify     *LPDIRECTSOUNDNOTIFY;
typedef IDirectSoundCapture    *LPDIRECTSOUNDCAPTURE;
typedef IDirectSoundCaptureBuffer *LPDIRECTSOUNDCAPTUREBUFFER;

#endif /* __cplusplus */

#endif /* _DIRECTSOUND_INTERFACES_DEFINED */

#ifndef FF_USE_OPENAL_DSOUND
/* Creation functions - stubs that return failure (when OpenAL not available) */
static inline HRESULT DirectSoundCreate(LPCGUID pcGuidDevice, LPDIRECTSOUND *ppDS, void* pUnkOuter) {
    (void)pcGuidDevice; (void)ppDS; (void)pUnkOuter;
    return DSERR_NODRIVER;
}

static inline HRESULT DirectSoundCreate8(LPCGUID pcGuidDevice, LPDIRECTSOUND8 *ppDS8, void* pUnkOuter) {
    (void)pcGuidDevice; (void)ppDS8; (void)pUnkOuter;
    return DSERR_NODRIVER;
}
#endif /* !FF_USE_OPENAL_DSOUND */

/* GUIDs */
#define DSDEVID_DefaultPlayback     NULL
#define DSDEVID_DefaultCapture      NULL
#define DSDEVID_DefaultVoicePlayback NULL
#define DSDEVID_DefaultVoiceCapture NULL

/* DS3D algorithm GUIDs */
static const GUID DS3DALG_DEFAULT = {0};
static const GUID DS3DALG_NO_VIRTUALIZATION = {0};
static const GUID DS3DALG_HRTF_FULL = {0};
static const GUID DS3DALG_HRTF_LIGHT = {0};

/* Interface IIDs for QueryInterface */
static const GUID IID_IDirectSound = {0x279AFA83, 0x4981, 0x11CE, {0xA5, 0x21, 0x00, 0x20, 0xAF, 0x0B, 0xE5, 0x60}};
static const GUID IID_IDirectSound8 = {0xC50A7E93, 0xF395, 0x4834, {0x9E, 0xF6, 0x7F, 0xA9, 0x9D, 0xE5, 0x09, 0x66}};
static const GUID IID_IDirectSoundBuffer = {0x279AFA85, 0x4981, 0x11CE, {0xA5, 0x21, 0x00, 0x20, 0xAF, 0x0B, 0xE5, 0x60}};
static const GUID IID_IDirectSoundBuffer8 = {0x6825A449, 0x7524, 0x4D82, {0x92, 0x0F, 0x50, 0xE3, 0x6A, 0xB3, 0xAB, 0x1E}};
static const GUID IID_IDirectSound3DListener = {0x279AFA84, 0x4981, 0x11CE, {0xA5, 0x21, 0x00, 0x20, 0xAF, 0x0B, 0xE5, 0x60}};
static const GUID IID_IDirectSound3DBuffer = {0x279AFA86, 0x4981, 0x11CE, {0xA5, 0x21, 0x00, 0x20, 0xAF, 0x0B, 0xE5, 0x60}};
static const GUID IID_IDirectSoundNotify = {0xB0210783, 0x89CD, 0x11D0, {0xAF, 0x08, 0x00, 0xA0, 0xC9, 0x25, 0xCD, 0x16}};
static const GUID IID_IDirectSoundCapture = {0xB0210781, 0x89CD, 0x11D0, {0xAF, 0x08, 0x00, 0xA0, 0xC9, 0x25, 0xCD, 0x16}};
static const GUID IID_IDirectSoundCaptureBuffer = {0xB0210782, 0x89CD, 0x11D0, {0xAF, 0x08, 0x00, 0xA0, 0xC9, 0x25, 0xCD, 0x16}};

/* Volume constants */
#define DSBVOLUME_MIN               -10000
#define DSBVOLUME_MAX               0

/* Pan constants */
#define DSBPAN_LEFT                 -10000
#define DSBPAN_CENTER               0
#define DSBPAN_RIGHT                10000

/* Frequency constants */
#define DSBFREQUENCY_MIN            100
#define DSBFREQUENCY_MAX            200000
#define DSBFREQUENCY_ORIGINAL       0

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DSOUND_H */
