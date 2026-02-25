/*
 * FreeFalcon Linux Port - OpenAL-backed DirectSound Header
 *
 * This file declares the OpenAL-backed DirectSound implementation classes.
 */

#ifndef FF_OPENAL_DSOUND_H
#define FF_OPENAL_DSOUND_H

#ifdef FF_LINUX

#include <AL/al.h>
#include <AL/alc.h>
#include <vector>
#include <atomic>

// Include the base DirectSound definitions (without the stub implementations)
#include "compat_types.h"
#include "compat_mmsystem.h"

/* Forward declarations */
class OpenALDirectSound;
class OpenALSoundBuffer;
class OpenAL3DBuffer;
class OpenAL3DListener;

/* ============================================================
 * DirectSound Constants (duplicated for standalone compilation)
 * ============================================================ */

#ifndef DSBCAPS_PRIMARYBUFFER
#define DSBCAPS_PRIMARYBUFFER       0x00000001
#define DSBCAPS_STATIC              0x00000002
#define DSBCAPS_CTRL3D              0x00000010
#define DSBCAPS_CTRLVOLUME          0x00000080
#define DSBCAPS_CTRLPAN             0x00000040
#define DSBCAPS_MUTE3DATMAXDISTANCE 0x00020000
#endif

#ifndef DSBPLAY_LOOPING
#define DSBPLAY_LOOPING             0x00000001
#endif

#ifndef DSBSTATUS_PLAYING
#define DSBSTATUS_PLAYING           0x00000001
#define DSBSTATUS_LOOPING           0x00000004
#endif

#ifndef DS3DMODE_NORMAL
#define DS3DMODE_NORMAL             0x00000000
#define DS3DMODE_HEADRELATIVE       0x00000001
#define DS3DMODE_DISABLE            0x00000002
#endif

#ifndef DS3D_IMMEDIATE
#define DS3D_IMMEDIATE              0x00000000
#define DS3D_DEFERRED               0x00000001
#endif

#ifndef DSBVOLUME_MIN
#define DSBVOLUME_MIN               -10000
#define DSBVOLUME_MAX               0
#endif

#ifndef DSBPAN_LEFT
#define DSBPAN_LEFT                 -10000
#define DSBPAN_CENTER               0
#define DSBPAN_RIGHT                10000
#endif

#ifndef DS_OK
#define DS_OK                       0
#define DSERR_GENERIC               0x80004005
#define DSERR_INVALIDPARAM          0x80070057
#define DSERR_NODRIVER              0x88780078
#endif

/* ============================================================
 * DirectSound Structures
 *
 * NOTE: When included from dsound.h, all structures (DSBUFFERDESC,
 * DSCAPS, DSBCAPS, D3DVECTOR, DS3DBUFFER, DS3DLISTENER, etc.)
 * are already defined before this header is included.
 * ============================================================ */

/* ============================================================
 * OpenAL-backed DirectSound Buffer
 * ============================================================ */

class OpenALSoundBuffer {
public:
    OpenALSoundBuffer();
    virtual ~OpenALSoundBuffer();

    bool Initialize(const DSBUFFERDESC* desc, OpenALDirectSound* parent);

    // IUnknown
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject);
    virtual ULONG   AddRef();
    virtual ULONG   Release();

    // IDirectSoundBuffer
    virtual HRESULT GetCaps(LPDSBCAPS pDSBufferCaps);
    virtual HRESULT GetCurrentPosition(LPDWORD pdwCurrentPlayCursor, LPDWORD pdwCurrentWriteCursor);
    virtual HRESULT GetFormat(LPWAVEFORMATEX pwfxFormat, DWORD dwSizeAllocated, LPDWORD pdwSizeWritten);
    virtual HRESULT GetVolume(LPLONG plVolume);
    virtual HRESULT GetPan(LPLONG plPan);
    virtual HRESULT GetFrequency(LPDWORD pdwFrequency);
    virtual HRESULT GetStatus(LPDWORD pdwStatus);
    virtual HRESULT Initialize(OpenALDirectSound* pDirectSound, LPCDSBUFFERDESC pcDSBufferDesc);
    virtual HRESULT Lock(DWORD dwOffset, DWORD dwBytes, LPVOID *ppvAudioPtr1, LPDWORD pdwAudioBytes1,
                         LPVOID *ppvAudioPtr2, LPDWORD pdwAudioBytes2, DWORD dwFlags);
    virtual HRESULT Play(DWORD dwReserved1, DWORD dwPriority, DWORD dwFlags);
    virtual HRESULT SetCurrentPosition(DWORD dwNewPosition);
    virtual HRESULT SetFormat(LPCWAVEFORMATEX pcfxFormat);
    virtual HRESULT SetVolume(LONG lVolume);
    virtual HRESULT SetPan(LONG lPan);
    virtual HRESULT SetFrequency(DWORD dwFrequency);
    virtual HRESULT Stop();
    virtual HRESULT Unlock(LPVOID pvAudioPtr1, DWORD dwAudioBytes1, LPVOID pvAudioPtr2, DWORD dwAudioBytes2);
    virtual HRESULT Restore();

    // OpenAL data
    ALuint m_alBuffer;
    ALuint m_alSource;
    BYTE* m_audioData;
    DWORD m_audioDataSize;
    bool m_isPrimary;
    bool m_is3D;
    OpenAL3DBuffer* m_3dBuffer;

private:
    std::atomic<ULONG> m_refCount;
    WAVEFORMATEX m_format;
    LONG m_volume;
    LONG m_pan;
    DWORD m_frequency;
    DWORD m_flags;
};

/* ============================================================
 * OpenAL-backed 3D Sound Buffer
 * ============================================================ */

class OpenAL3DBuffer {
public:
    OpenAL3DBuffer(OpenALSoundBuffer* owner);
    virtual ~OpenAL3DBuffer();

    // IUnknown
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject);
    virtual ULONG   AddRef();
    virtual ULONG   Release();

    // IDirectSound3DBuffer
    virtual HRESULT GetAllParameters(LPDS3DBUFFER pDs3dBuffer);
    virtual HRESULT GetConeAngles(LPDWORD pdwInsideConeAngle, LPDWORD pdwOutsideConeAngle);
    virtual HRESULT GetConeOrientation(D3DVECTOR *pvOrientation);
    virtual HRESULT GetConeOutsideVolume(LPLONG plConeOutsideVolume);
    virtual HRESULT GetMaxDistance(float *pflMaxDistance);
    virtual HRESULT GetMinDistance(float *pflMinDistance);
    virtual HRESULT GetMode(LPDWORD pdwMode);
    virtual HRESULT GetPosition(D3DVECTOR *pvPosition);
    virtual HRESULT GetVelocity(D3DVECTOR *pvVelocity);
    virtual HRESULT SetAllParameters(LPCDS3DBUFFER pcDs3dBuffer, DWORD dwApply);
    virtual HRESULT SetConeAngles(DWORD dwInsideConeAngle, DWORD dwOutsideConeAngle, DWORD dwApply);
    virtual HRESULT SetConeOrientation(float x, float y, float z, DWORD dwApply);
    virtual HRESULT SetConeOutsideVolume(LONG lConeOutsideVolume, DWORD dwApply);
    virtual HRESULT SetMaxDistance(float flMaxDistance, DWORD dwApply);
    virtual HRESULT SetMinDistance(float flMinDistance, DWORD dwApply);
    virtual HRESULT SetMode(DWORD dwMode, DWORD dwApply);
    virtual HRESULT SetPosition(float x, float y, float z, DWORD dwApply);
    virtual HRESULT SetVelocity(float x, float y, float z, DWORD dwApply);

private:
    void ApplyToSource();
    void ApplyConeToSource();

    std::atomic<ULONG> m_refCount;
    OpenALSoundBuffer* m_owner;
    DS3DBUFFER m_params;
    DWORD m_mode;
};

/* ============================================================
 * OpenAL-backed 3D Listener
 * ============================================================ */

class OpenAL3DListener {
public:
    OpenAL3DListener();
    virtual ~OpenAL3DListener();

    // IUnknown
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject);
    virtual ULONG   AddRef();
    virtual ULONG   Release();

    // IDirectSound3DListener
    virtual HRESULT GetAllParameters(LPDS3DLISTENER pListener);
    virtual HRESULT GetDistanceFactor(float *pflDistanceFactor);
    virtual HRESULT GetDopplerFactor(float *pflDopplerFactor);
    virtual HRESULT GetOrientation(D3DVECTOR *pvOrientFront, D3DVECTOR *pvOrientTop);
    virtual HRESULT GetPosition(D3DVECTOR *pvPosition);
    virtual HRESULT GetRolloffFactor(float *pflRolloffFactor);
    virtual HRESULT GetVelocity(D3DVECTOR *pvVelocity);
    virtual HRESULT SetAllParameters(LPCDS3DLISTENER pcListener, DWORD dwApply);
    virtual HRESULT SetDistanceFactor(float flDistanceFactor, DWORD dwApply);
    virtual HRESULT SetDopplerFactor(float flDopplerFactor, DWORD dwApply);
    virtual HRESULT SetOrientation(float xFront, float yFront, float zFront,
                                   float xTop, float yTop, float zTop, DWORD dwApply);
    virtual HRESULT SetPosition(float x, float y, float z, DWORD dwApply);
    virtual HRESULT SetRolloffFactor(float flRolloffFactor, DWORD dwApply);
    virtual HRESULT SetVelocity(float x, float y, float z, DWORD dwApply);
    virtual HRESULT CommitDeferredSettings();

private:
    void ApplyToListener();

    std::atomic<ULONG> m_refCount;
    DS3DLISTENER m_params;
};

/* ============================================================
 * OpenAL-backed DirectSound
 * ============================================================ */

class OpenALDirectSound {
public:
    OpenALDirectSound();
    virtual ~OpenALDirectSound();

    // IUnknown
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject);
    virtual ULONG   AddRef();
    virtual ULONG   Release();

    // IDirectSound
    virtual HRESULT CreateSoundBuffer(LPCDSBUFFERDESC pcDSBufferDesc, OpenALSoundBuffer **ppDSBuffer, void* pUnkOuter);
    virtual HRESULT GetCaps(LPDSCAPS pDSCaps);
    virtual HRESULT DuplicateSoundBuffer(OpenALSoundBuffer *pDSBufferOriginal, OpenALSoundBuffer **ppDSBufferDuplicate);
    virtual HRESULT SetCooperativeLevel(HWND hwnd, DWORD dwLevel);
    virtual HRESULT Compact();
    virtual HRESULT GetSpeakerConfig(LPDWORD pdwSpeakerConfig);
    virtual HRESULT SetSpeakerConfig(DWORD dwSpeakerConfig);
    virtual HRESULT Initialize(LPCGUID pcGuidDevice);

    // Internal
    OpenALSoundBuffer* m_primaryBuffer;
    OpenAL3DListener* m_listener;
    std::vector<OpenALSoundBuffer*> m_buffers;

private:
    std::atomic<ULONG> m_refCount;
};

/* ============================================================
 * DirectSound Creation Functions
 * ============================================================ */

#ifdef __cplusplus
extern "C" {
#endif

HRESULT OpenAL_DirectSoundCreate(LPCGUID pcGuidDevice, OpenALDirectSound **ppDS, void* pUnkOuter);
HRESULT OpenAL_DirectSoundCreate8(LPCGUID pcGuidDevice, OpenALDirectSound **ppDS8, void* pUnkOuter);

#ifdef __cplusplus
}
#endif

/* ============================================================
 * Stub classes for interfaces not yet fully implemented
 * ============================================================ */

/* IDirectSoundNotify - notification stub */
class OpenALSoundNotify {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef() { return ++m_refCount; }
    virtual ULONG   Release() { if (--m_refCount == 0) { delete this; return 0; } return m_refCount; }
    virtual HRESULT SetNotificationPositions(DWORD dwPositionNotifies, LPCDSBPOSITIONNOTIFY pcPositionNotifies) {
        (void)dwPositionNotifies; (void)pcPositionNotifies; return DS_OK;
    }
private:
    std::atomic<ULONG> m_refCount{1};
};

/* IDirectSoundCapture - capture stub */
class OpenALSoundCapture {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef() { return ++m_refCount; }
    virtual ULONG   Release() { if (--m_refCount == 0) { delete this; return 0; } return m_refCount; }
    virtual HRESULT CreateCaptureBuffer(void* pcDSCBufferDesc, void** ppDSCBuffer, void* pUnkOuter) {
        (void)pcDSCBufferDesc; (void)ppDSCBuffer; (void)pUnkOuter; return DSERR_GENERIC;
    }
    virtual HRESULT GetCaps(void* pDSCCaps) { (void)pDSCCaps; return DSERR_GENERIC; }
    virtual HRESULT Initialize(LPCGUID pcGuidDevice) { (void)pcGuidDevice; return DS_OK; }
private:
    std::atomic<ULONG> m_refCount{1};
};

/* IDirectSoundCaptureBuffer - capture buffer stub */
class OpenALSoundCaptureBuffer {
public:
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) { (void)riid; (void)ppvObject; return E_NOTIMPL; }
    virtual ULONG   AddRef() { return ++m_refCount; }
    virtual ULONG   Release() { if (--m_refCount == 0) { delete this; return 0; } return m_refCount; }
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
    virtual HRESULT Stop() { return DS_OK; }
    virtual HRESULT Unlock(LPVOID pvAudioPtr1, DWORD dwAudioBytes1, LPVOID pvAudioPtr2, DWORD dwAudioBytes2) {
        (void)pvAudioPtr1; (void)dwAudioBytes1; (void)pvAudioPtr2; (void)dwAudioBytes2; return DS_OK;
    }
private:
    std::atomic<ULONG> m_refCount{1};
};

/* Typedefs for compatibility */
typedef OpenALSoundBuffer IDirectSoundBuffer;
typedef OpenALSoundBuffer IDirectSoundBuffer8;
typedef OpenALDirectSound IDirectSound;
typedef OpenALDirectSound IDirectSound8;
typedef OpenAL3DListener  IDirectSound3DListener;
typedef OpenAL3DBuffer    IDirectSound3DBuffer;
typedef OpenALSoundNotify IDirectSoundNotify;
typedef OpenALSoundCapture IDirectSoundCapture;
typedef OpenALSoundCaptureBuffer IDirectSoundCaptureBuffer;

typedef IDirectSound           *LPDIRECTSOUND;
typedef IDirectSound8          *LPDIRECTSOUND8;
typedef IDirectSoundBuffer     *LPDIRECTSOUNDBUFFER;
typedef IDirectSoundBuffer8    *LPDIRECTSOUNDBUFFER8;
typedef IDirectSound3DListener *LPDIRECTSOUND3DLISTENER;
typedef IDirectSound3DBuffer   *LPDIRECTSOUND3DBUFFER;
typedef IDirectSoundNotify     *LPDIRECTSOUNDNOTIFY;
typedef IDirectSoundCapture    *LPDIRECTSOUNDCAPTURE;
typedef IDirectSoundCaptureBuffer *LPDIRECTSOUNDCAPTUREBUFFER;

/* Redirect creation functions */
#define DirectSoundCreate   OpenAL_DirectSoundCreate
#define DirectSoundCreate8  OpenAL_DirectSoundCreate8

#endif // FF_LINUX
#endif // FF_OPENAL_DSOUND_H
