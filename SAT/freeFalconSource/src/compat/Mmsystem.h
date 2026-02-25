/*
 * FreeFalcon Linux Port - mmsystem.h compatibility
 *
 * Windows Multimedia System API stub for Linux.
 */

#ifndef FF_COMPAT_MMSYSTEM_H
#define FF_COMPAT_MMSYSTEM_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Multimedia result codes */
typedef UINT MMRESULT;
typedef MMRESULT MCIERROR;

#define MMSYSERR_NOERROR        0
#define MMSYSERR_ERROR          1
#define MMSYSERR_BADDEVICEID    2
#define MMSYSERR_NOTENABLED     3
#define MMSYSERR_ALLOCATED      4
#define MMSYSERR_INVALHANDLE    5
#define MMSYSERR_NODRIVER       6
#define MMSYSERR_NOMEM          7
#define MMSYSERR_NOTSUPPORTED   8
#define MMSYSERR_BADERRNUM      9
#define MMSYSERR_INVALFLAG      10
#define MMSYSERR_INVALPARAM     11
#define MMSYSERR_HANDLEBUSY     12
#define MMSYSERR_INVALIDALIAS   13
#define MMSYSERR_BADDB          14
#define MMSYSERR_KEYNOTFOUND    15
#define MMSYSERR_READERROR      16
#define MMSYSERR_WRITEERROR     17
#define MMSYSERR_DELETEERROR    18
#define MMSYSERR_VALNOTFOUND    19
#define MMSYSERR_NODRIVERCB     20
#define MMSYSERR_LASTERROR      20

/* Wave error codes */
#define WAVERR_BASE             32
#define WAVERR_BADFORMAT        (WAVERR_BASE + 0)
#define WAVERR_STILLPLAYING     (WAVERR_BASE + 1)
#define WAVERR_UNPREPARED       (WAVERR_BASE + 2)
#define WAVERR_SYNC             (WAVERR_BASE + 3)
#define WAVERR_LASTERROR        (WAVERR_BASE + 3)

/* Callback types */
#define CALLBACK_NULL           0x00000000
#define CALLBACK_WINDOW         0x00010000
#define CALLBACK_TASK           0x00020000
#define CALLBACK_FUNCTION       0x00030000
#define CALLBACK_THREAD         CALLBACK_TASK
#define CALLBACK_EVENT          0x00050000
#define CALLBACK_TYPEMASK       0x00070000

/* Wave handles */
typedef HANDLE HWAVEOUT;
typedef HANDLE HWAVEIN;
typedef HWAVEOUT* LPHWAVEOUT;
typedef HWAVEIN* LPHWAVEIN;

/* Wave format */
#define WAVE_FORMAT_PCM         1

typedef struct tWAVEFORMATEX {
    WORD wFormatTag;
    WORD nChannels;
    DWORD nSamplesPerSec;
    DWORD nAvgBytesPerSec;
    WORD nBlockAlign;
    WORD wBitsPerSample;
    WORD cbSize;
} WAVEFORMATEX, *PWAVEFORMATEX, *LPWAVEFORMATEX;

typedef const WAVEFORMATEX *LPCWAVEFORMATEX;

/* Wave header */
typedef struct wavehdr_tag {
    LPSTR lpData;
    DWORD dwBufferLength;
    DWORD dwBytesRecorded;
    DWORD_PTR dwUser;
    DWORD dwFlags;
    DWORD dwLoops;
    struct wavehdr_tag *lpNext;
    DWORD_PTR reserved;
} WAVEHDR, *PWAVEHDR, *LPWAVEHDR;

/* Wave header flags */
#define WHDR_DONE           0x00000001
#define WHDR_PREPARED       0x00000002
#define WHDR_BEGINLOOP      0x00000004
#define WHDR_ENDLOOP        0x00000008
#define WHDR_INQUEUE        0x00000010

/* Wave out caps */
typedef struct tagWAVEOUTCAPSA {
    WORD wMid;
    WORD wPid;
    UINT vDriverVersion;
    CHAR szPname[32];
    DWORD dwFormats;
    WORD wChannels;
    WORD wReserved1;
    DWORD dwSupport;
} WAVEOUTCAPSA, *PWAVEOUTCAPSA, *LPWAVEOUTCAPSA;

typedef WAVEOUTCAPSA WAVEOUTCAPS;
typedef LPWAVEOUTCAPSA LPWAVEOUTCAPS;

/* Wave messages */
#define MM_WOM_OPEN             0x3BB
#define MM_WOM_CLOSE            0x3BC
#define MM_WOM_DONE             0x3BD
#define MM_WIM_OPEN             0x3BE
#define MM_WIM_CLOSE            0x3BF
#define MM_WIM_DATA             0x3C0

/* Wave device IDs */
#define WAVE_MAPPER             ((UINT)-1)

/* Timer */
typedef UINT MMVERSION;
typedef struct timecaps_tag {
    UINT wPeriodMin;
    UINT wPeriodMax;
} TIMECAPS, *PTIMECAPS, *LPTIMECAPS;

#define TIMERR_NOERROR          0
#define TIMERR_NOCANDO          (TIMERR_NOERROR + 1)
#define TIMERR_STRUCT           (TIMERR_NOERROR + 33)

/* Timer callbacks */
typedef void (CALLBACK *LPTIMECALLBACK)(UINT uTimerID, UINT uMsg, DWORD_PTR dwUser, DWORD_PTR dw1, DWORD_PTR dw2);

/* Timer flags */
#define TIME_ONESHOT            0x0000
#define TIME_PERIODIC           0x0001
#define TIME_CALLBACK_FUNCTION  0x0000
#define TIME_CALLBACK_EVENT_SET 0x0010
#define TIME_CALLBACK_EVENT_PULSE 0x0020
#define TIME_KILL_SYNCHRONOUS   0x0100

/* MCI */
typedef UINT MCIDEVICEID;

/* Joystick */
typedef UINT MMVERSION;

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

#define JOYSTICKID1             0
#define JOYSTICKID2             1

#define JOY_RETURNX             0x00000001
#define JOY_RETURNY             0x00000002
#define JOY_RETURNZ             0x00000004
#define JOY_RETURNR             0x00000008
#define JOY_RETURNU             0x00000010
#define JOY_RETURNV             0x00000020
#define JOY_RETURNPOV           0x00000040
#define JOY_RETURNBUTTONS       0x00000080
#define JOY_RETURNRAWDATA       0x00000100
#define JOY_RETURNPOVCTS        0x00000200
#define JOY_RETURNCENTERED      0x00000400
#define JOY_USEDEADZONE         0x00000800
#define JOY_RETURNALL           (JOY_RETURNX | JOY_RETURNY | JOY_RETURNZ | JOY_RETURNR | JOY_RETURNU | JOY_RETURNV | JOY_RETURNPOV | JOY_RETURNBUTTONS)

#define JOYERR_NOERROR          0
#define JOYERR_PARMS            (JOYERR_NOERROR + 5)
#define JOYERR_NOCANDO          (JOYERR_NOERROR + 6)
#define JOYERR_UNPLUGGED        (JOYERR_NOERROR + 7)

/* FOURCC type and macros */
#ifndef _FOURCC_DEFINED
typedef DWORD FOURCC;
#define _FOURCC_DEFINED
#endif

#ifndef mmioFOURCC
#define mmioFOURCC(ch0, ch1, ch2, ch3) \
    ((DWORD)(BYTE)(ch0) | ((DWORD)(BYTE)(ch1) << 8) | \
     ((DWORD)(BYTE)(ch2) << 16) | ((DWORD)(BYTE)(ch3) << 24))
#endif

/* Stub functions */
static inline MMRESULT waveOutOpen(LPHWAVEOUT phwo, UINT uDeviceID, LPCWAVEFORMATEX pwfx,
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
    (void)hwo; (void)pwh; (void)cbwh; return MMSYSERR_NODRIVER;
}
static inline MMRESULT waveOutReset(HWAVEOUT hwo) { (void)hwo; return MMSYSERR_NOERROR; }
static inline MMRESULT waveOutGetVolume(HWAVEOUT hwo, LPDWORD pdwVolume) {
    (void)hwo; if (pdwVolume) *pdwVolume = 0xFFFFFFFF; return MMSYSERR_NOERROR;
}
static inline MMRESULT waveOutSetVolume(HWAVEOUT hwo, DWORD dwVolume) {
    (void)hwo; (void)dwVolume; return MMSYSERR_NOERROR;
}
static inline UINT waveOutGetNumDevs(void) { return 0; }
static inline MMRESULT waveOutGetDevCapsA(UINT uDeviceID, LPWAVEOUTCAPSA pwoc, UINT cbwoc) {
    (void)uDeviceID; (void)pwoc; (void)cbwoc; return MMSYSERR_BADDEVICEID;
}
#define waveOutGetDevCaps waveOutGetDevCapsA

/* Timer stubs */
static inline MMRESULT timeGetDevCaps(LPTIMECAPS ptc, UINT cbtc) {
    (void)cbtc;
    if (ptc) { ptc->wPeriodMin = 1; ptc->wPeriodMax = 1000000; }
    return TIMERR_NOERROR;
}
static inline MMRESULT timeBeginPeriod(UINT uPeriod) { (void)uPeriod; return TIMERR_NOERROR; }
static inline MMRESULT timeEndPeriod(UINT uPeriod) { (void)uPeriod; return TIMERR_NOERROR; }
static inline DWORD timeGetTime(void) { return 0; /* Use GetTickCount instead */ }
static inline MMRESULT timeSetEvent(UINT uDelay, UINT uResolution, LPTIMECALLBACK fptc,
                                    DWORD_PTR dwUser, UINT fuEvent) {
    (void)uDelay; (void)uResolution; (void)fptc; (void)dwUser; (void)fuEvent;
    return 0;
}
static inline MMRESULT timeKillEvent(UINT uTimerID) { (void)uTimerID; return TIMERR_NOERROR; }

/* Joystick stubs */
static inline UINT joyGetNumDevs(void) { return 0; }
static inline MMRESULT joyGetPosEx(UINT uJoyID, LPJOYINFOEX pji) {
    (void)uJoyID; (void)pji; return JOYERR_UNPLUGGED;
}

/* PlaySound flags */
#define SND_SYNC            0x0000
#define SND_ASYNC           0x0001
#define SND_NODEFAULT       0x0002
#define SND_MEMORY          0x0004
#define SND_LOOP            0x0008
#define SND_NOSTOP          0x0010
#define SND_NOWAIT          0x00002000
#define SND_ALIAS           0x00010000
#define SND_ALIAS_ID        0x00110000
#define SND_FILENAME        0x00020000
#define SND_RESOURCE        0x00040004
#define SND_PURGE           0x0040
#define SND_APPLICATION     0x0080

static inline BOOL PlaySoundA(LPCSTR pszSound, HMODULE hmod, DWORD fdwSound) {
    (void)pszSound; (void)hmod; (void)fdwSound; return FALSE;
}
#define PlaySound PlaySoundA

static inline BOOL sndPlaySoundA(LPCSTR pszSound, UINT fuSound) {
    (void)pszSound; (void)fuSound; return FALSE;
}
#define sndPlaySound sndPlaySoundA

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_MMSYSTEM_H */
