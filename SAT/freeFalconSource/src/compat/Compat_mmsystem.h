/*
 * FreeFalcon Linux Port - mmsystem.h compatibility
 *
 * Windows Multimedia System function stubs - will be replaced by SDL2/OpenAL
 */

#ifndef FF_COMPAT_MMSYSTEM_H
#define FF_COMPAT_MMSYSTEM_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Multimedia Types
 * ============================================================ */

typedef UINT        MMRESULT;
typedef UINT        MMVERSION;
typedef HANDLE      HWAVEOUT;
typedef HANDLE      HWAVEIN;
typedef HANDLE      HMIDI;
typedef HANDLE      HMIDIIN;
typedef HANDLE      HMIDIOUT;
typedef HANDLE      HMIDISTRM;
typedef HANDLE      HMIXER;
typedef HANDLE      HMIXEROBJ;

/* Wave format */
typedef struct tWAVEFORMATEX {
    WORD  wFormatTag;
    WORD  nChannels;
    DWORD nSamplesPerSec;
    DWORD nAvgBytesPerSec;
    WORD  nBlockAlign;
    WORD  wBitsPerSample;
    WORD  cbSize;
} WAVEFORMATEX, *PWAVEFORMATEX, *LPWAVEFORMATEX;

typedef const WAVEFORMATEX* LPCWAVEFORMATEX;

#define WAVE_FORMAT_PCM     1
#define WAVE_FORMAT_IEEE_FLOAT 3

/* Wave header */
typedef struct wavehdr_tag {
    LPSTR  lpData;
    DWORD  dwBufferLength;
    DWORD  dwBytesRecorded;
    DWORD_PTR dwUser;
    DWORD  dwFlags;
    DWORD  dwLoops;
    struct wavehdr_tag* lpNext;
    DWORD_PTR reserved;
} WAVEHDR, *PWAVEHDR, *LPWAVEHDR;

#define WHDR_DONE       0x00000001
#define WHDR_PREPARED   0x00000002
#define WHDR_BEGINLOOP  0x00000004
#define WHDR_ENDLOOP    0x00000008
#define WHDR_INQUEUE    0x00000010

/* ============================================================
 * Multimedia Constants
 * ============================================================ */

#define MMSYSERR_BASE           0
#define MMSYSERR_NOERROR        0
#define MMSYSERR_ERROR          (MMSYSERR_BASE + 1)
#define MMSYSERR_BADDEVICEID    (MMSYSERR_BASE + 2)
#define MMSYSERR_NOTENABLED     (MMSYSERR_BASE + 3)
#define MMSYSERR_ALLOCATED      (MMSYSERR_BASE + 4)
#define MMSYSERR_INVALHANDLE    (MMSYSERR_BASE + 5)
#define MMSYSERR_NODRIVER       (MMSYSERR_BASE + 6)
#define MMSYSERR_NOMEM          (MMSYSERR_BASE + 7)
#define MMSYSERR_NOTSUPPORTED   (MMSYSERR_BASE + 8)
#define MMSYSERR_BADERRNUM      (MMSYSERR_BASE + 9)
#define MMSYSERR_INVALFLAG      (MMSYSERR_BASE + 10)
#define MMSYSERR_INVALPARAM     (MMSYSERR_BASE + 11)
#define MMSYSERR_HANDLEBUSY     (MMSYSERR_BASE + 12)
#define MMSYSERR_INVALIDALIAS   (MMSYSERR_BASE + 13)
#define MMSYSERR_BADDB          (MMSYSERR_BASE + 14)
#define MMSYSERR_KEYNOTFOUND    (MMSYSERR_BASE + 15)
#define MMSYSERR_READERROR      (MMSYSERR_BASE + 16)
#define MMSYSERR_WRITEERROR     (MMSYSERR_BASE + 17)
#define MMSYSERR_DELETEERROR    (MMSYSERR_BASE + 18)
#define MMSYSERR_VALNOTFOUND    (MMSYSERR_BASE + 19)
#define MMSYSERR_NODRIVERCB     (MMSYSERR_BASE + 20)
#define MMSYSERR_LASTERROR      (MMSYSERR_BASE + 20)

#define TIMERR_BASE             96
#define TIMERR_NOERROR          (0)
#define TIMERR_NOCANDO          (TIMERR_BASE + 1)
#define TIMERR_STRUCT           (TIMERR_BASE + 33)

/* Wave callback messages */
#define MM_WOM_OPEN     0x3BB
#define MM_WOM_CLOSE    0x3BC
#define MM_WOM_DONE     0x3BD
#define MM_WIM_OPEN     0x3BE
#define MM_WIM_CLOSE    0x3BF
#define MM_WIM_DATA     0x3C0

#define CALLBACK_NULL       0x00000000
#define CALLBACK_WINDOW     0x00010000
#define CALLBACK_TASK       0x00020000
#define CALLBACK_FUNCTION   0x00030000
#define CALLBACK_THREAD     (CALLBACK_TASK)
#define CALLBACK_EVENT      0x00050000

#define WAVE_MAPPER         ((UINT)-1)

/* ============================================================
 * Timer Functions
 * ============================================================ */

typedef void (*LPTIMECALLBACK)(UINT uTimerID, UINT uMsg, DWORD_PTR dwUser, DWORD_PTR dw1, DWORD_PTR dw2);

typedef struct timecaps_tag {
    UINT wPeriodMin;
    UINT wPeriodMax;
} TIMECAPS, *PTIMECAPS, *LPTIMECAPS;

static inline DWORD timeGetTime(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (DWORD)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

static inline MMRESULT timeGetDevCaps(LPTIMECAPS ptc, UINT cbtc) {
    (void)cbtc;
    if (ptc) {
        ptc->wPeriodMin = 1;
        ptc->wPeriodMax = 1000000;
    }
    return TIMERR_NOERROR;
}

static inline MMRESULT timeBeginPeriod(UINT uPeriod) {
    (void)uPeriod;
    return TIMERR_NOERROR;
}

static inline MMRESULT timeEndPeriod(UINT uPeriod) {
    (void)uPeriod;
    return TIMERR_NOERROR;
}

static inline MMRESULT timeSetEvent(UINT uDelay, UINT uResolution, LPTIMECALLBACK fptc, DWORD_PTR dwUser, UINT fuEvent) {
    (void)uDelay; (void)uResolution; (void)fptc; (void)dwUser; (void)fuEvent;
    return 0; /* Stub - returns timer ID 0 (invalid) */
}

static inline MMRESULT timeKillEvent(UINT uTimerID) {
    (void)uTimerID;
    return TIMERR_NOERROR;
}

#define TIME_ONESHOT    0x0000
#define TIME_PERIODIC   0x0001
#define TIME_CALLBACK_FUNCTION      0x0000
#define TIME_CALLBACK_EVENT_SET     0x0010
#define TIME_CALLBACK_EVENT_PULSE   0x0020
#define TIME_KILL_SYNCHRONOUS       0x0100

/* ============================================================
 * Wave Output Functions (Stubs)
 * ============================================================ */

static inline UINT waveOutGetNumDevs(void) { return 0; }

static inline MMRESULT waveOutOpen(HWAVEOUT* phwo, UINT uDeviceID, LPCWAVEFORMATEX pwfx,
                                   DWORD_PTR dwCallback, DWORD_PTR dwInstance, DWORD fdwOpen) {
    (void)phwo; (void)uDeviceID; (void)pwfx; (void)dwCallback; (void)dwInstance; (void)fdwOpen;
    return MMSYSERR_NODRIVER;
}

static inline MMRESULT waveOutClose(HWAVEOUT hwo) { (void)hwo; return MMSYSERR_NOERROR; }
static inline MMRESULT waveOutPrepareHeader(HWAVEOUT hwo, LPWAVEHDR pwh, UINT cbwh) {
    (void)hwo; (void)pwh; (void)cbwh; return MMSYSERR_NOERROR;
}
static inline MMRESULT waveOutUnprepareHeader(HWAVEOUT hwo, LPWAVEHDR pwh, UINT cbwh) {
    (void)hwo; (void)pwh; (void)cbwh; return MMSYSERR_NOERROR;
}
static inline MMRESULT waveOutWrite(HWAVEOUT hwo, LPWAVEHDR pwh, UINT cbwh) {
    (void)hwo; (void)pwh; (void)cbwh; return MMSYSERR_NOERROR;
}
static inline MMRESULT waveOutReset(HWAVEOUT hwo) { (void)hwo; return MMSYSERR_NOERROR; }
static inline MMRESULT waveOutSetVolume(HWAVEOUT hwo, DWORD dwVolume) { (void)hwo; (void)dwVolume; return MMSYSERR_NOERROR; }
static inline MMRESULT waveOutGetVolume(HWAVEOUT hwo, LPDWORD pdwVolume) {
    (void)hwo; if (pdwVolume) *pdwVolume = 0xFFFFFFFF; return MMSYSERR_NOERROR;
}

/* ============================================================
 * Joystick Functions (Stubs - replaced by SDL2)
 * ============================================================ */

#define JOYSTICKID1     0
#define JOYSTICKID2     1

#define JOYERR_BASE         160
#define JOYERR_NOERROR      (0)
#define JOYERR_PARMS        (JOYERR_BASE+5)
#define JOYERR_NOCANDO      (JOYERR_BASE+6)
#define JOYERR_UNPLUGGED    (JOYERR_BASE+7)

typedef struct joyinfoex_tag {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwXpos;
    DWORD dwYpos;
    DWORD dwZpos;
    DWORD dwRpos;
    DWORD dwUpos;
    DWORD dwVpos;
    DWORD dwButtons;
    DWORD dwButtonNumber;
    DWORD dwPOV;
    DWORD dwReserved1;
    DWORD dwReserved2;
} JOYINFOEX, *PJOYINFOEX, *LPJOYINFOEX;

#define JOY_RETURNX         0x00000001
#define JOY_RETURNY         0x00000002
#define JOY_RETURNZ         0x00000004
#define JOY_RETURNR         0x00000008
#define JOY_RETURNU         0x00000010
#define JOY_RETURNV         0x00000020
#define JOY_RETURNPOV       0x00000040
#define JOY_RETURNBUTTONS   0x00000080
#define JOY_RETURNALL       (JOY_RETURNX | JOY_RETURNY | JOY_RETURNZ | JOY_RETURNR | JOY_RETURNU | JOY_RETURNV | JOY_RETURNPOV | JOY_RETURNBUTTONS)

#define JOY_POVCENTERED     ((DWORD)-1)
#define JOY_POVFORWARD      0
#define JOY_POVRIGHT        9000
#define JOY_POVBACKWARD     18000
#define JOY_POVLEFT         27000

static inline UINT joyGetNumDevs(void) { return 0; }
static inline MMRESULT joyGetPosEx(UINT uJoyID, LPJOYINFOEX pji) {
    (void)uJoyID; (void)pji;
    return JOYERR_UNPLUGGED;
}

/* ============================================================
 * MCI Functions (Stubs)
 * ============================================================ */

typedef UINT MCIERROR;
typedef UINT MCIDEVICEID;

static inline MCIERROR mciSendStringA(LPCSTR lpstrCommand, LPSTR lpstrReturnString, UINT uReturnLength, HWND hwndCallback) {
    (void)lpstrCommand; (void)lpstrReturnString; (void)uReturnLength; (void)hwndCallback;
    return MMSYSERR_NOTSUPPORTED;
}
#define mciSendString mciSendStringA

static inline BOOL mciGetErrorStringA(MCIERROR mcierr, LPSTR pszText, UINT cchText) {
    (void)mcierr;
    if (pszText && cchText > 0) {
        strncpy(pszText, "MCI not supported on Linux", cchText - 1);
        pszText[cchText - 1] = '\0';
    }
    return TRUE;
}
#define mciGetErrorString mciGetErrorStringA

/* ============================================================
 * PlaySound (Stub)
 * ============================================================ */

#define SND_SYNC            0x0000
#define SND_ASYNC           0x0001
#define SND_NODEFAULT       0x0002
#define SND_MEMORY          0x0004
#define SND_LOOP            0x0008
#define SND_NOSTOP          0x0010
#define SND_NOWAIT          0x00002000
#define SND_FILENAME        0x00020000
#define SND_RESOURCE        0x00040004

static inline BOOL PlaySoundA(LPCSTR pszSound, HMODULE hmod, DWORD fdwSound) {
    (void)pszSound; (void)hmod; (void)fdwSound;
    return FALSE;
}
#define PlaySound PlaySoundA

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_MMSYSTEM_H */
