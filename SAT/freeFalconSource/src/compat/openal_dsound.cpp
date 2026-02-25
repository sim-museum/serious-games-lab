/*
 * FreeFalcon Linux Port - OpenAL-backed DirectSound Implementation
 *
 * This file implements DirectSound interfaces using OpenAL as the backend.
 * It provides a compatibility layer to allow the Windows DirectSound code
 * to work on Linux without major modifications.
 */

#ifdef FF_LINUX

#include <AL/al.h>
#include <AL/alc.h>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <vector>
#include <mutex>

#include "compat_types.h"
#include "compat_mmsystem.h"

// Include dsound.h which includes openal_dsound.h and provides all struct definitions
#include "dsound.h"

// Global OpenAL context - initialized in main_linux.cpp
extern ALCdevice* g_alDevice;
extern ALCcontext* g_alContext;

// Debug output control
#define DSOUND_DEBUG 1
#if DSOUND_DEBUG
#define DS_LOG(fmt, ...) fprintf(stderr, "[OpenAL-DS] " fmt "\n", ##__VA_ARGS__)
#else
#define DS_LOG(fmt, ...) ((void)0)
#endif

/* ============================================================
 * Volume Conversion Utilities
 *
 * DirectSound uses centibels: -10000 (silent) to 0 (full volume)
 * OpenAL uses linear gain: 0.0 (silent) to 1.0 (full volume)
 * ============================================================ */

static float DSVolumeToALGain(LONG dsVolume) {
    // DirectSound: -10000 = -100dB (silent), 0 = 0dB (full)
    // Convert centibels to linear gain
    if (dsVolume <= DSBVOLUME_MIN) {
        return 0.0f;
    }
    if (dsVolume >= DSBVOLUME_MAX) {
        return 1.0f;
    }
    // Convert from centibels (hundredths of dB) to linear
    // gain = 10^(dB/20) where dB = centibels/100
    return powf(10.0f, (float)dsVolume / 2000.0f);
}

static LONG ALGainToDSVolume(float gain) {
    if (gain <= 0.0f) {
        return DSBVOLUME_MIN;
    }
    if (gain >= 1.0f) {
        return DSBVOLUME_MAX;
    }
    // Convert linear to centibels
    return (LONG)(2000.0f * log10f(gain));
}

/* ============================================================
 * Pan Conversion Utilities
 *
 * DirectSound: -10000 (left) to 10000 (right), 0 = center
 * OpenAL: Uses 3D position, we'll position source on X axis
 * ============================================================ */

static void DSPanToALPosition(LONG dsPan, float* x, float* y, float* z) {
    // Map pan to X position: -1.0 (left) to 1.0 (right)
    *x = (float)dsPan / 10000.0f;
    *y = 0.0f;
    *z = 0.0f;
}

/* ============================================================
 * OpenAL Format Conversion
 * ============================================================ */

static ALenum GetALFormat(const WAVEFORMATEX* wfx) {
    if (!wfx) return AL_FORMAT_STEREO16;

    if (wfx->nChannels == 1) {
        if (wfx->wBitsPerSample == 8) {
            return AL_FORMAT_MONO8;
        } else if (wfx->wBitsPerSample == 16) {
            return AL_FORMAT_MONO16;
        }
    } else if (wfx->nChannels == 2) {
        if (wfx->wBitsPerSample == 8) {
            return AL_FORMAT_STEREO8;
        } else if (wfx->wBitsPerSample == 16) {
            return AL_FORMAT_STEREO16;
        }
    }

    DS_LOG("Unsupported format: channels=%d, bits=%d",
           wfx->nChannels, wfx->wBitsPerSample);
    return AL_FORMAT_STEREO16;  // Default fallback
}

/* ============================================================
 * OpenALSoundBuffer Implementation
 * ============================================================ */

OpenALSoundBuffer::OpenALSoundBuffer()
    : m_refCount(1)
    , m_alBuffer(0)
    , m_alSource(0)
    , m_audioData(nullptr)
    , m_audioDataSize(0)
    , m_isPrimary(false)
    , m_volume(DSBVOLUME_MAX)
    , m_pan(DSBPAN_CENTER)
    , m_frequency(0)
    , m_flags(0)
    , m_is3D(false)
    , m_3dBuffer(nullptr)
{
    memset(&m_format, 0, sizeof(m_format));
}

OpenALSoundBuffer::~OpenALSoundBuffer() {
    DS_LOG("Destroying buffer, source=%u, buffer=%u", m_alSource, m_alBuffer);

    if (m_3dBuffer) {
        delete m_3dBuffer;
        m_3dBuffer = nullptr;
    }

    if (m_alSource) {
        alSourceStop(m_alSource);
        alDeleteSources(1, &m_alSource);
        m_alSource = 0;
    }

    if (m_alBuffer) {
        alDeleteBuffers(1, &m_alBuffer);
        m_alBuffer = 0;
    }

    if (m_audioData) {
        free(m_audioData);
        m_audioData = nullptr;
    }
}

bool OpenALSoundBuffer::Initialize(const DSBUFFERDESC* desc, OpenALDirectSound* parent) {
    if (!desc) return false;

    m_flags = desc->dwFlags;
    m_isPrimary = (desc->dwFlags & DSBCAPS_PRIMARYBUFFER) != 0;
    m_is3D = (desc->dwFlags & DSBCAPS_CTRL3D) != 0;

    DS_LOG("Initialize: primary=%d, 3d=%d, size=%u",
           m_isPrimary, m_is3D, desc->dwBufferBytes);

    // Primary buffers are special - they represent the listener
    if (m_isPrimary) {
        // No OpenAL buffer/source needed for primary
        // But we may need to set up the listener
        return true;
    }

    // Copy format if provided
    if (desc->lpwfxFormat) {
        memcpy(&m_format, desc->lpwfxFormat, sizeof(WAVEFORMATEX));
        m_frequency = m_format.nSamplesPerSec;
    }

    // Allocate audio data buffer for Lock/Unlock
    m_audioDataSize = desc->dwBufferBytes;
    if (m_audioDataSize > 0) {
        m_audioData = (BYTE*)malloc(m_audioDataSize);
        if (!m_audioData) {
            DS_LOG("Failed to allocate audio buffer of %u bytes", m_audioDataSize);
            return false;
        }
        memset(m_audioData, 0, m_audioDataSize);
    }

    // Generate OpenAL buffer and source
    alGenBuffers(1, &m_alBuffer);
    ALenum err = alGetError();
    if (err != AL_NO_ERROR) {
        DS_LOG("alGenBuffers failed: 0x%x", err);
        return false;
    }

    alGenSources(1, &m_alSource);
    err = alGetError();
    if (err != AL_NO_ERROR) {
        DS_LOG("alGenSources failed: 0x%x", err);
        alDeleteBuffers(1, &m_alBuffer);
        m_alBuffer = 0;
        return false;
    }

    DS_LOG("Created buffer=%u, source=%u", m_alBuffer, m_alSource);

    // Set up 3D buffer interface if needed
    if (m_is3D) {
        m_3dBuffer = new OpenAL3DBuffer(this);
    }

    return true;
}

HRESULT OpenALSoundBuffer::QueryInterface(REFIID riid, void** ppvObject) {
    if (!ppvObject) return E_POINTER;

    // Check for 3D buffer interface
    if (m_is3D && m_3dBuffer) {
        // For now, return our 3D buffer for any query
        // In a full implementation, we'd check the riid
        *ppvObject = m_3dBuffer;
        m_3dBuffer->AddRef();
        return S_OK;
    }

    *ppvObject = nullptr;
    return E_NOINTERFACE;
}

ULONG OpenALSoundBuffer::AddRef() {
    return ++m_refCount;
}

ULONG OpenALSoundBuffer::Release() {
    ULONG count = --m_refCount;
    if (count == 0) {
        delete this;
    }
    return count;
}

HRESULT OpenALSoundBuffer::GetCaps(LPDSBCAPS pDSBufferCaps) {
    if (!pDSBufferCaps) return DSERR_INVALIDPARAM;

    pDSBufferCaps->dwSize = sizeof(DSBCAPS);
    pDSBufferCaps->dwFlags = m_flags;
    pDSBufferCaps->dwBufferBytes = m_audioDataSize;
    pDSBufferCaps->dwUnlockTransferRate = 0;
    pDSBufferCaps->dwPlayCpuOverhead = 0;

    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetCurrentPosition(LPDWORD pdwCurrentPlayCursor, LPDWORD pdwCurrentWriteCursor) {
    if (!m_alSource) {
        if (pdwCurrentPlayCursor) *pdwCurrentPlayCursor = 0;
        if (pdwCurrentWriteCursor) *pdwCurrentWriteCursor = 0;
        return DS_OK;
    }

    ALint offset = 0;
    alGetSourcei(m_alSource, AL_BYTE_OFFSET, &offset);

    if (pdwCurrentPlayCursor) *pdwCurrentPlayCursor = (DWORD)offset;
    if (pdwCurrentWriteCursor) *pdwCurrentWriteCursor = (DWORD)offset;

    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetFormat(LPWAVEFORMATEX pwfxFormat, DWORD dwSizeAllocated, LPDWORD pdwSizeWritten) {
    if (pdwSizeWritten) *pdwSizeWritten = sizeof(WAVEFORMATEX);

    if (pwfxFormat && dwSizeAllocated >= sizeof(WAVEFORMATEX)) {
        memcpy(pwfxFormat, &m_format, sizeof(WAVEFORMATEX));
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetVolume(LPLONG plVolume) {
    if (!plVolume) return DSERR_INVALIDPARAM;
    *plVolume = m_volume;
    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetPan(LPLONG plPan) {
    if (!plPan) return DSERR_INVALIDPARAM;
    *plPan = m_pan;
    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetFrequency(LPDWORD pdwFrequency) {
    if (!pdwFrequency) return DSERR_INVALIDPARAM;
    *pdwFrequency = m_frequency;
    return DS_OK;
}

HRESULT OpenALSoundBuffer::GetStatus(LPDWORD pdwStatus) {
    if (!pdwStatus) return DSERR_INVALIDPARAM;

    *pdwStatus = 0;

    if (m_alSource) {
        ALint state;
        alGetSourcei(m_alSource, AL_SOURCE_STATE, &state);

        if (state == AL_PLAYING) {
            *pdwStatus |= DSBSTATUS_PLAYING;

            ALint looping;
            alGetSourcei(m_alSource, AL_LOOPING, &looping);
            if (looping) {
                *pdwStatus |= DSBSTATUS_LOOPING;
            }
        }
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::Initialize(OpenALDirectSound* pDirectSound, LPCDSBUFFERDESC pcDSBufferDesc) {
    // Already initialized in constructor
    (void)pDirectSound;
    (void)pcDSBufferDesc;
    return DS_OK;
}

HRESULT OpenALSoundBuffer::Lock(DWORD dwOffset, DWORD dwBytes, LPVOID *ppvAudioPtr1, LPDWORD pdwAudioBytes1,
                                LPVOID *ppvAudioPtr2, LPDWORD pdwAudioBytes2, DWORD dwFlags) {
    if (!m_audioData || !ppvAudioPtr1 || !pdwAudioBytes1) {
        return DSERR_INVALIDPARAM;
    }

    // Handle DSBLOCK_ENTIREBUFFER flag
    if (dwFlags & DSBLOCK_ENTIREBUFFER) {
        dwOffset = 0;
        dwBytes = m_audioDataSize;
    }

    DS_LOG("Lock: offset=%u, bytes=%u, totalSize=%u", dwOffset, dwBytes, m_audioDataSize);

    // Simple case: no wrap-around needed
    if (dwOffset + dwBytes <= m_audioDataSize) {
        *ppvAudioPtr1 = m_audioData + dwOffset;
        *pdwAudioBytes1 = dwBytes;
        if (ppvAudioPtr2) *ppvAudioPtr2 = nullptr;
        if (pdwAudioBytes2) *pdwAudioBytes2 = 0;
    } else {
        // Wrap-around case
        DWORD firstPart = m_audioDataSize - dwOffset;
        DWORD secondPart = dwBytes - firstPart;

        *ppvAudioPtr1 = m_audioData + dwOffset;
        *pdwAudioBytes1 = firstPart;

        if (ppvAudioPtr2 && pdwAudioBytes2) {
            *ppvAudioPtr2 = m_audioData;
            *pdwAudioBytes2 = secondPart;
        }
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::Unlock(LPVOID pvAudioPtr1, DWORD dwAudioBytes1,
                                   LPVOID pvAudioPtr2, DWORD dwAudioBytes2) {
    (void)pvAudioPtr1;
    (void)pvAudioPtr2;

    if (!m_alBuffer || !m_audioData) {
        return DS_OK;
    }

    DS_LOG("Unlock: bytes1=%u, bytes2=%u", dwAudioBytes1, dwAudioBytes2);

    // Upload the audio data to OpenAL
    ALenum format = GetALFormat(&m_format);
    ALsizei freq = m_format.nSamplesPerSec ? m_format.nSamplesPerSec : 22050;

    // Stop the source before updating the buffer
    if (m_alSource) {
        alSourceStop(m_alSource);
        alSourcei(m_alSource, AL_BUFFER, 0);  // Detach buffer
    }

    alBufferData(m_alBuffer, format, m_audioData, m_audioDataSize, freq);
    ALenum err = alGetError();
    if (err != AL_NO_ERROR) {
        DS_LOG("alBufferData failed: 0x%x", err);
        return DSERR_GENERIC;
    }

    // Reattach buffer to source
    if (m_alSource) {
        alSourcei(m_alSource, AL_BUFFER, m_alBuffer);
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::Play(DWORD dwReserved1, DWORD dwPriority, DWORD dwFlags) {
    (void)dwReserved1;
    (void)dwPriority;

    if (m_isPrimary) {
        // Primary buffer doesn't play - it represents the output device
        return DS_OK;
    }

    if (!m_alSource) {
        return DSERR_GENERIC;
    }

    DS_LOG("Play: source=%u, flags=0x%x", m_alSource, dwFlags);

    // Set looping
    ALint looping = (dwFlags & DSBPLAY_LOOPING) ? AL_TRUE : AL_FALSE;
    alSourcei(m_alSource, AL_LOOPING, looping);

    // Apply current volume
    float gain = DSVolumeToALGain(m_volume);
    alSourcef(m_alSource, AL_GAIN, gain);

    // Apply pan (for non-3D sources)
    if (!m_is3D) {
        float x, y, z;
        DSPanToALPosition(m_pan, &x, &y, &z);
        alSource3f(m_alSource, AL_POSITION, x, y, z);
    }

    alSourcePlay(m_alSource);

    return DS_OK;
}

HRESULT OpenALSoundBuffer::SetCurrentPosition(DWORD dwNewPosition) {
    if (!m_alSource) return DS_OK;

    alSourcei(m_alSource, AL_BYTE_OFFSET, (ALint)dwNewPosition);
    return DS_OK;
}

HRESULT OpenALSoundBuffer::SetFormat(LPCWAVEFORMATEX pcfxFormat) {
    if (!pcfxFormat) return DSERR_INVALIDPARAM;

    memcpy(&m_format, pcfxFormat, sizeof(WAVEFORMATEX));
    m_frequency = m_format.nSamplesPerSec;

    return DS_OK;
}

HRESULT OpenALSoundBuffer::SetVolume(LONG lVolume) {
    m_volume = lVolume;

    if (m_alSource) {
        float gain = DSVolumeToALGain(lVolume);
        alSourcef(m_alSource, AL_GAIN, gain);
        DS_LOG("SetVolume: ds=%ld -> al=%.3f", lVolume, gain);
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::SetPan(LONG lPan) {
    m_pan = lPan;

    if (m_alSource && !m_is3D) {
        float x, y, z;
        DSPanToALPosition(lPan, &x, &y, &z);
        alSource3f(m_alSource, AL_POSITION, x, y, z);
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::SetFrequency(DWORD dwFrequency) {
    m_frequency = dwFrequency;

    if (m_alSource && dwFrequency > 0) {
        // OpenAL uses pitch multiplier, not absolute frequency
        float pitch = (float)dwFrequency / (float)m_format.nSamplesPerSec;
        alSourcef(m_alSource, AL_PITCH, pitch);
    }

    return DS_OK;
}

HRESULT OpenALSoundBuffer::Stop() {
    if (m_alSource) {
        alSourceStop(m_alSource);
        DS_LOG("Stop: source=%u", m_alSource);
    }
    return DS_OK;
}

HRESULT OpenALSoundBuffer::Restore() {
    // OpenAL doesn't have a "lost" state like DirectSound
    return DS_OK;
}

/* ============================================================
 * OpenAL3DBuffer Implementation
 * ============================================================ */

OpenAL3DBuffer::OpenAL3DBuffer(OpenALSoundBuffer* owner)
    : m_refCount(1)
    , m_owner(owner)
    , m_mode(DS3DMODE_NORMAL)
{
    memset(&m_params, 0, sizeof(m_params));
    m_params.dwSize = sizeof(DS3DBUFFER);
    m_params.flMinDistance = 1.0f;
    m_params.flMaxDistance = 1000000000.0f;  // DS3D_DEFAULTMAXDISTANCE
    m_params.dwInsideConeAngle = 360;
    m_params.dwOutsideConeAngle = 360;
    m_params.lConeOutsideVolume = DSBVOLUME_MAX;
}

OpenAL3DBuffer::~OpenAL3DBuffer() {
}

HRESULT OpenAL3DBuffer::QueryInterface(REFIID riid, void** ppvObject) {
    (void)riid;
    *ppvObject = nullptr;
    return E_NOINTERFACE;
}

ULONG OpenAL3DBuffer::AddRef() {
    return ++m_refCount;
}

ULONG OpenAL3DBuffer::Release() {
    ULONG count = --m_refCount;
    if (count == 0) {
        delete this;
    }
    return count;
}

HRESULT OpenAL3DBuffer::GetAllParameters(LPDS3DBUFFER pDs3dBuffer) {
    if (!pDs3dBuffer) return DSERR_INVALIDPARAM;
    memcpy(pDs3dBuffer, &m_params, sizeof(DS3DBUFFER));
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetConeAngles(LPDWORD pdwInsideConeAngle, LPDWORD pdwOutsideConeAngle) {
    if (pdwInsideConeAngle) *pdwInsideConeAngle = m_params.dwInsideConeAngle;
    if (pdwOutsideConeAngle) *pdwOutsideConeAngle = m_params.dwOutsideConeAngle;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetConeOrientation(D3DVECTOR *pvOrientation) {
    if (!pvOrientation) return DSERR_INVALIDPARAM;
    *pvOrientation = m_params.vConeOrientation;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetConeOutsideVolume(LPLONG plConeOutsideVolume) {
    if (!plConeOutsideVolume) return DSERR_INVALIDPARAM;
    *plConeOutsideVolume = m_params.lConeOutsideVolume;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetMaxDistance(float *pflMaxDistance) {
    if (!pflMaxDistance) return DSERR_INVALIDPARAM;
    *pflMaxDistance = m_params.flMaxDistance;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetMinDistance(float *pflMinDistance) {
    if (!pflMinDistance) return DSERR_INVALIDPARAM;
    *pflMinDistance = m_params.flMinDistance;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetMode(LPDWORD pdwMode) {
    if (!pdwMode) return DSERR_INVALIDPARAM;
    *pdwMode = m_mode;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetPosition(D3DVECTOR *pvPosition) {
    if (!pvPosition) return DSERR_INVALIDPARAM;
    *pvPosition = m_params.vPosition;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::GetVelocity(D3DVECTOR *pvVelocity) {
    if (!pvVelocity) return DSERR_INVALIDPARAM;
    *pvVelocity = m_params.vVelocity;
    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetAllParameters(LPCDS3DBUFFER pcDs3dBuffer, DWORD dwApply) {
    if (!pcDs3dBuffer) return DSERR_INVALIDPARAM;

    memcpy(&m_params, pcDs3dBuffer, sizeof(DS3DBUFFER));

    if (dwApply == DS3D_IMMEDIATE) {
        ApplyToSource();
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetConeAngles(DWORD dwInsideConeAngle, DWORD dwOutsideConeAngle, DWORD dwApply) {
    m_params.dwInsideConeAngle = dwInsideConeAngle;
    m_params.dwOutsideConeAngle = dwOutsideConeAngle;

    if (dwApply == DS3D_IMMEDIATE) {
        ApplyConeToSource();
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetConeOrientation(float x, float y, float z, DWORD dwApply) {
    m_params.vConeOrientation.x = x;
    m_params.vConeOrientation.y = y;
    m_params.vConeOrientation.z = z;

    if (dwApply == DS3D_IMMEDIATE) {
        ApplyConeToSource();
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetConeOutsideVolume(LONG lConeOutsideVolume, DWORD dwApply) {
    m_params.lConeOutsideVolume = lConeOutsideVolume;

    if (dwApply == DS3D_IMMEDIATE) {
        ApplyConeToSource();
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetMaxDistance(float flMaxDistance, DWORD dwApply) {
    m_params.flMaxDistance = flMaxDistance;

    if (dwApply == DS3D_IMMEDIATE && m_owner && m_owner->m_alSource) {
        alSourcef(m_owner->m_alSource, AL_MAX_DISTANCE, flMaxDistance);
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetMinDistance(float flMinDistance, DWORD dwApply) {
    m_params.flMinDistance = flMinDistance;

    if (dwApply == DS3D_IMMEDIATE && m_owner && m_owner->m_alSource) {
        alSourcef(m_owner->m_alSource, AL_REFERENCE_DISTANCE, flMinDistance);
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetMode(DWORD dwMode, DWORD dwApply) {
    m_mode = dwMode;

    if (dwApply == DS3D_IMMEDIATE && m_owner && m_owner->m_alSource) {
        if (dwMode == DS3DMODE_DISABLE) {
            // Disable 3D processing - make relative to listener at origin
            alSourcei(m_owner->m_alSource, AL_SOURCE_RELATIVE, AL_TRUE);
            alSource3f(m_owner->m_alSource, AL_POSITION, 0, 0, 0);
        } else if (dwMode == DS3DMODE_HEADRELATIVE) {
            alSourcei(m_owner->m_alSource, AL_SOURCE_RELATIVE, AL_TRUE);
        } else {
            alSourcei(m_owner->m_alSource, AL_SOURCE_RELATIVE, AL_FALSE);
        }
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetPosition(float x, float y, float z, DWORD dwApply) {
    m_params.vPosition.x = x;
    m_params.vPosition.y = y;
    m_params.vPosition.z = z;

    if (dwApply == DS3D_IMMEDIATE && m_owner && m_owner->m_alSource) {
        // Note: DirectSound uses left-handed coordinates, OpenAL uses right-handed
        // Negate Z to convert
        alSource3f(m_owner->m_alSource, AL_POSITION, x, y, -z);
    }

    return DS_OK;
}

HRESULT OpenAL3DBuffer::SetVelocity(float x, float y, float z, DWORD dwApply) {
    m_params.vVelocity.x = x;
    m_params.vVelocity.y = y;
    m_params.vVelocity.z = z;

    if (dwApply == DS3D_IMMEDIATE && m_owner && m_owner->m_alSource) {
        alSource3f(m_owner->m_alSource, AL_VELOCITY, x, y, -z);
    }

    return DS_OK;
}

void OpenAL3DBuffer::ApplyToSource() {
    if (!m_owner || !m_owner->m_alSource) return;

    ALuint source = m_owner->m_alSource;

    alSource3f(source, AL_POSITION, m_params.vPosition.x, m_params.vPosition.y, -m_params.vPosition.z);
    alSource3f(source, AL_VELOCITY, m_params.vVelocity.x, m_params.vVelocity.y, -m_params.vVelocity.z);
    alSourcef(source, AL_REFERENCE_DISTANCE, m_params.flMinDistance);
    alSourcef(source, AL_MAX_DISTANCE, m_params.flMaxDistance);

    ApplyConeToSource();
}

void OpenAL3DBuffer::ApplyConeToSource() {
    if (!m_owner || !m_owner->m_alSource) return;

    ALuint source = m_owner->m_alSource;

    alSourcef(source, AL_CONE_INNER_ANGLE, (float)m_params.dwInsideConeAngle);
    alSourcef(source, AL_CONE_OUTER_ANGLE, (float)m_params.dwOutsideConeAngle);
    alSourcef(source, AL_CONE_OUTER_GAIN, DSVolumeToALGain(m_params.lConeOutsideVolume));
    alSource3f(source, AL_DIRECTION,
               m_params.vConeOrientation.x,
               m_params.vConeOrientation.y,
               -m_params.vConeOrientation.z);
}

/* ============================================================
 * OpenAL3DListener Implementation
 * ============================================================ */

OpenAL3DListener::OpenAL3DListener()
    : m_refCount(1)
{
    memset(&m_params, 0, sizeof(m_params));
    m_params.dwSize = sizeof(DS3DLISTENER);
    m_params.flDistanceFactor = 1.0f;
    m_params.flDopplerFactor = 1.0f;
    m_params.flRolloffFactor = 1.0f;
    m_params.vOrientFront.z = 1.0f;  // Forward is +Z
    m_params.vOrientTop.y = 1.0f;    // Up is +Y
}

OpenAL3DListener::~OpenAL3DListener() {
}

HRESULT OpenAL3DListener::QueryInterface(REFIID riid, void** ppvObject) {
    (void)riid;
    *ppvObject = nullptr;
    return E_NOINTERFACE;
}

ULONG OpenAL3DListener::AddRef() {
    return ++m_refCount;
}

ULONG OpenAL3DListener::Release() {
    ULONG count = --m_refCount;
    if (count == 0) {
        delete this;
    }
    return count;
}

HRESULT OpenAL3DListener::GetAllParameters(LPDS3DLISTENER pListener) {
    if (!pListener) return DSERR_INVALIDPARAM;
    memcpy(pListener, &m_params, sizeof(DS3DLISTENER));
    return DS_OK;
}

HRESULT OpenAL3DListener::GetDistanceFactor(float *pflDistanceFactor) {
    if (!pflDistanceFactor) return DSERR_INVALIDPARAM;
    *pflDistanceFactor = m_params.flDistanceFactor;
    return DS_OK;
}

HRESULT OpenAL3DListener::GetDopplerFactor(float *pflDopplerFactor) {
    if (!pflDopplerFactor) return DSERR_INVALIDPARAM;
    *pflDopplerFactor = m_params.flDopplerFactor;
    return DS_OK;
}

HRESULT OpenAL3DListener::GetOrientation(D3DVECTOR *pvOrientFront, D3DVECTOR *pvOrientTop) {
    if (pvOrientFront) *pvOrientFront = m_params.vOrientFront;
    if (pvOrientTop) *pvOrientTop = m_params.vOrientTop;
    return DS_OK;
}

HRESULT OpenAL3DListener::GetPosition(D3DVECTOR *pvPosition) {
    if (!pvPosition) return DSERR_INVALIDPARAM;
    *pvPosition = m_params.vPosition;
    return DS_OK;
}

HRESULT OpenAL3DListener::GetRolloffFactor(float *pflRolloffFactor) {
    if (!pflRolloffFactor) return DSERR_INVALIDPARAM;
    *pflRolloffFactor = m_params.flRolloffFactor;
    return DS_OK;
}

HRESULT OpenAL3DListener::GetVelocity(D3DVECTOR *pvVelocity) {
    if (!pvVelocity) return DSERR_INVALIDPARAM;
    *pvVelocity = m_params.vVelocity;
    return DS_OK;
}

HRESULT OpenAL3DListener::SetAllParameters(LPCDS3DLISTENER pcListener, DWORD dwApply) {
    if (!pcListener) return DSERR_INVALIDPARAM;

    memcpy(&m_params, pcListener, sizeof(DS3DLISTENER));

    if (dwApply == DS3D_IMMEDIATE) {
        ApplyToListener();
    }

    return DS_OK;
}

HRESULT OpenAL3DListener::SetDistanceFactor(float flDistanceFactor, DWORD dwApply) {
    m_params.flDistanceFactor = flDistanceFactor;

    // OpenAL doesn't have a direct distance factor - it affects how we interpret positions
    // We'll store it and apply when positions are set
    (void)dwApply;

    return DS_OK;
}

HRESULT OpenAL3DListener::SetDopplerFactor(float flDopplerFactor, DWORD dwApply) {
    m_params.flDopplerFactor = flDopplerFactor;

    if (dwApply == DS3D_IMMEDIATE) {
        alDopplerFactor(flDopplerFactor);
    }

    return DS_OK;
}

HRESULT OpenAL3DListener::SetOrientation(float xFront, float yFront, float zFront,
                                          float xTop, float yTop, float zTop, DWORD dwApply) {
    m_params.vOrientFront.x = xFront;
    m_params.vOrientFront.y = yFront;
    m_params.vOrientFront.z = zFront;
    m_params.vOrientTop.x = xTop;
    m_params.vOrientTop.y = yTop;
    m_params.vOrientTop.z = zTop;

    if (dwApply == DS3D_IMMEDIATE) {
        // OpenAL orientation: forward vector followed by up vector
        // Negate Z for coordinate system conversion
        ALfloat orientation[6] = {
            xFront, yFront, -zFront,
            xTop, yTop, -zTop
        };
        alListenerfv(AL_ORIENTATION, orientation);
    }

    return DS_OK;
}

HRESULT OpenAL3DListener::SetPosition(float x, float y, float z, DWORD dwApply) {
    m_params.vPosition.x = x;
    m_params.vPosition.y = y;
    m_params.vPosition.z = z;

    if (dwApply == DS3D_IMMEDIATE) {
        // Apply distance factor and coordinate conversion
        float scale = m_params.flDistanceFactor;
        alListener3f(AL_POSITION, x * scale, y * scale, -z * scale);
    }

    return DS_OK;
}

HRESULT OpenAL3DListener::SetRolloffFactor(float flRolloffFactor, DWORD dwApply) {
    m_params.flRolloffFactor = flRolloffFactor;

    // OpenAL rolloff is per-source, not global
    // We store it here for when sources are created
    (void)dwApply;

    return DS_OK;
}

HRESULT OpenAL3DListener::SetVelocity(float x, float y, float z, DWORD dwApply) {
    m_params.vVelocity.x = x;
    m_params.vVelocity.y = y;
    m_params.vVelocity.z = z;

    if (dwApply == DS3D_IMMEDIATE) {
        alListener3f(AL_VELOCITY, x, y, -z);
    }

    return DS_OK;
}

HRESULT OpenAL3DListener::CommitDeferredSettings() {
    ApplyToListener();
    return DS_OK;
}

void OpenAL3DListener::ApplyToListener() {
    float scale = m_params.flDistanceFactor;

    alListener3f(AL_POSITION,
                 m_params.vPosition.x * scale,
                 m_params.vPosition.y * scale,
                 -m_params.vPosition.z * scale);

    alListener3f(AL_VELOCITY,
                 m_params.vVelocity.x,
                 m_params.vVelocity.y,
                 -m_params.vVelocity.z);

    ALfloat orientation[6] = {
        m_params.vOrientFront.x, m_params.vOrientFront.y, -m_params.vOrientFront.z,
        m_params.vOrientTop.x, m_params.vOrientTop.y, -m_params.vOrientTop.z
    };
    alListenerfv(AL_ORIENTATION, orientation);

    alDopplerFactor(m_params.flDopplerFactor);
}

/* ============================================================
 * OpenALDirectSound Implementation
 * ============================================================ */

OpenALDirectSound::OpenALDirectSound()
    : m_refCount(1)
    , m_primaryBuffer(nullptr)
    , m_listener(nullptr)
{
    DS_LOG("OpenALDirectSound created");
}

OpenALDirectSound::~OpenALDirectSound() {
    DS_LOG("OpenALDirectSound destroyed");

    // Release all buffers
    for (auto* buf : m_buffers) {
        delete buf;
    }
    m_buffers.clear();

    if (m_listener) {
        delete m_listener;
        m_listener = nullptr;
    }
}

HRESULT OpenALDirectSound::QueryInterface(REFIID riid, void** ppvObject) {
    (void)riid;
    *ppvObject = nullptr;
    return E_NOINTERFACE;
}

ULONG OpenALDirectSound::AddRef() {
    return ++m_refCount;
}

ULONG OpenALDirectSound::Release() {
    ULONG count = --m_refCount;
    if (count == 0) {
        delete this;
    }
    return count;
}

HRESULT OpenALDirectSound::CreateSoundBuffer(LPCDSBUFFERDESC pcDSBufferDesc,
                                              OpenALSoundBuffer **ppDSBuffer,
                                              void* pUnkOuter) {
    (void)pUnkOuter;

    if (!pcDSBufferDesc || !ppDSBuffer) {
        return DSERR_INVALIDPARAM;
    }

    OpenALSoundBuffer* buffer = new OpenALSoundBuffer();
    if (!buffer->Initialize(pcDSBufferDesc, this)) {
        delete buffer;
        return DSERR_GENERIC;
    }

    // Track primary buffer specially
    if (pcDSBufferDesc->dwFlags & DSBCAPS_PRIMARYBUFFER) {
        m_primaryBuffer = buffer;

        // Create listener for 3D audio
        if (pcDSBufferDesc->dwFlags & DSBCAPS_CTRL3D) {
            m_listener = new OpenAL3DListener();
        }
    }

    m_buffers.push_back(buffer);
    *ppDSBuffer = buffer;

    DS_LOG("Created buffer: %p (primary=%d)", buffer,
           (pcDSBufferDesc->dwFlags & DSBCAPS_PRIMARYBUFFER) ? 1 : 0);

    return DS_OK;
}

HRESULT OpenALDirectSound::GetCaps(LPDSCAPS pDSCaps) {
    if (!pDSCaps) return DSERR_INVALIDPARAM;

    memset(pDSCaps, 0, sizeof(DSCAPS));
    pDSCaps->dwSize = sizeof(DSCAPS);
    pDSCaps->dwFlags = DSCAPS_PRIMARYSTEREO | DSCAPS_PRIMARY16BIT |
                       DSCAPS_SECONDARYSTEREO | DSCAPS_SECONDARY16BIT |
                       DSCAPS_CONTINUOUSRATE;
    pDSCaps->dwMinSecondarySampleRate = 100;
    pDSCaps->dwMaxSecondarySampleRate = 200000;
    pDSCaps->dwPrimaryBuffers = 1;
    pDSCaps->dwMaxHwMixingAllBuffers = 256;
    pDSCaps->dwMaxHwMixingStaticBuffers = 256;
    pDSCaps->dwMaxHwMixingStreamingBuffers = 256;
    pDSCaps->dwFreeHwMixingAllBuffers = 256;
    pDSCaps->dwFreeHwMixingStaticBuffers = 256;
    pDSCaps->dwFreeHwMixingStreamingBuffers = 256;

    return DS_OK;
}

HRESULT OpenALDirectSound::DuplicateSoundBuffer(OpenALSoundBuffer *pDSBufferOriginal,
                                                 OpenALSoundBuffer **ppDSBufferDuplicate) {
    // For now, just create a new buffer
    // A proper implementation would share the audio data
    (void)pDSBufferOriginal;
    (void)ppDSBufferDuplicate;
    return DSERR_GENERIC;
}

HRESULT OpenALDirectSound::SetCooperativeLevel(HWND hwnd, DWORD dwLevel) {
    (void)hwnd;
    (void)dwLevel;
    // OpenAL doesn't have cooperative levels
    return DS_OK;
}

HRESULT OpenALDirectSound::Compact() {
    return DS_OK;
}

HRESULT OpenALDirectSound::GetSpeakerConfig(LPDWORD pdwSpeakerConfig) {
    if (pdwSpeakerConfig) {
        *pdwSpeakerConfig = 0;  // DSSPEAKER_STEREO
    }
    return DS_OK;
}

HRESULT OpenALDirectSound::SetSpeakerConfig(DWORD dwSpeakerConfig) {
    (void)dwSpeakerConfig;
    return DS_OK;
}

HRESULT OpenALDirectSound::Initialize(LPCGUID pcGuidDevice) {
    (void)pcGuidDevice;
    return DS_OK;
}

/* ============================================================
 * DirectSound Creation Functions
 * ============================================================ */

// Global instance - we only need one
static OpenALDirectSound* g_dsoundInstance = nullptr;

HRESULT OpenAL_DirectSoundCreate(LPCGUID pcGuidDevice, OpenALDirectSound **ppDS, void* pUnkOuter) {
    (void)pcGuidDevice;
    (void)pUnkOuter;

    if (!ppDS) {
        return DSERR_INVALIDPARAM;
    }

    // Check if OpenAL is available
    if (!g_alDevice || !g_alContext) {
        fprintf(stderr, "[OpenAL-DS] OpenAL not initialized!\n");
        return DSERR_NODRIVER;
    }

    // Create a new DirectSound instance
    if (!g_dsoundInstance) {
        g_dsoundInstance = new OpenALDirectSound();
    } else {
        g_dsoundInstance->AddRef();
    }

    *ppDS = g_dsoundInstance;

    DS_LOG("DirectSoundCreate succeeded, instance=%p", g_dsoundInstance);
    return DS_OK;
}

HRESULT OpenAL_DirectSoundCreate8(LPCGUID pcGuidDevice, OpenALDirectSound **ppDS8, void* pUnkOuter) {
    return OpenAL_DirectSoundCreate(pcGuidDevice, ppDS8, pUnkOuter);
}

// Primary buffer QueryInterface for getting 3D listener
HRESULT OpenALSoundBuffer_QueryInterface_Listener(OpenALSoundBuffer* buffer, void** ppvObject) {
    if (!buffer || !ppvObject) return E_INVALIDARG;

    // Find the parent DirectSound and get its listener
    if (buffer->m_isPrimary && g_dsoundInstance && g_dsoundInstance->m_listener) {
        *ppvObject = g_dsoundInstance->m_listener;
        g_dsoundInstance->m_listener->AddRef();
        return S_OK;
    }

    // For non-primary 3D buffers, return the 3D buffer interface
    if (buffer->m_3dBuffer) {
        *ppvObject = buffer->m_3dBuffer;
        buffer->m_3dBuffer->AddRef();
        return S_OK;
    }

    return E_NOINTERFACE;
}

#endif // FF_LINUX
