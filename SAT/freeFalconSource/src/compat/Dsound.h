/*
 * FreeFalcon Linux Port - dsound.h compatibility
 *
 * DirectSound stub interface - will be replaced by OpenAL
 */

#ifndef FF_COMPAT_DSOUND_H
#define FF_COMPAT_DSOUND_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "compat_mmsystem.h"

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

/* ============================================================
 * DirectSound Interface Declarations (stubs)
 * ============================================================ */

/* DirectSound interface stubs - use opaque void pointers */
#ifndef _DIRECTSOUND_INTERFACES_DEFINED
#define _DIRECTSOUND_INTERFACES_DEFINED
typedef void IDirectSound;
typedef void IDirectSound8;
typedef void IDirectSoundBuffer;
typedef void IDirectSoundBuffer8;
typedef void IDirectSound3DListener;
typedef void IDirectSound3DBuffer;
typedef void IDirectSoundNotify;

typedef IDirectSound        *LPDIRECTSOUND;
typedef IDirectSound8       *LPDIRECTSOUND8;
typedef IDirectSoundBuffer  *LPDIRECTSOUNDBUFFER;
typedef IDirectSoundBuffer8 *LPDIRECTSOUNDBUFFER8;
typedef IDirectSound3DListener *LPDIRECTSOUND3DLISTENER;
typedef IDirectSound3DBuffer   *LPDIRECTSOUND3DBUFFER;
typedef IDirectSoundNotify     *LPDIRECTSOUNDNOTIFY;
#endif

/* Notification position */
typedef struct _DSBPOSITIONNOTIFY {
    DWORD dwOffset;
    HANDLE hEventNotify;
} DSBPOSITIONNOTIFY, *LPDSBPOSITIONNOTIFY;

typedef const DSBPOSITIONNOTIFY *LPCDSBPOSITIONNOTIFY;

#define DSBPN_OFFSETSTOP            0xFFFFFFFF

/* Creation functions - stubs that return failure */
static inline HRESULT DirectSoundCreate(LPCGUID pcGuidDevice, LPDIRECTSOUND *ppDS, void* pUnkOuter) {
    (void)pcGuidDevice; (void)ppDS; (void)pUnkOuter;
    return DSERR_NODRIVER;
}

static inline HRESULT DirectSoundCreate8(LPCGUID pcGuidDevice, LPDIRECTSOUND8 *ppDS8, void* pUnkOuter) {
    (void)pcGuidDevice; (void)ppDS8; (void)pUnkOuter;
    return DSERR_NODRIVER;
}

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

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DSOUND_H */
