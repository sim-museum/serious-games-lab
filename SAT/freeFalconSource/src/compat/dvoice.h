/*
 * FreeFalcon Linux Port - dvoice.h compatibility
 *
 * DirectPlay Voice header stub.
 * Actual implementation will use different audio/voice systems.
 */

#ifndef FF_COMPAT_DVOICE_H
#define FF_COMPAT_DVOICE_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "dplay8.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Voice error codes */
#define DV_OK                           S_OK
#define DV_FULLDUPLEX                   ((HRESULT)0x00000001)
#define DV_HALFDUPLEX                   ((HRESULT)0x00000002)

#define DVERR_GENERIC                   E_FAIL
#define DVERR_BUFFERTOOSMALL            ((HRESULT)0x8015001E)
#define DVERR_EXCEPTION                 ((HRESULT)0x8015001F)
#define DVERR_INVALIDFLAGS              ((HRESULT)0x80150020)
#define DVERR_INVALIDOBJECT             ((HRESULT)0x80150021)
#define DVERR_INVALIDPARAM              E_INVALIDARG
#define DVERR_INVALIDPLAYER             ((HRESULT)0x80150023)
#define DVERR_INVALIDGROUP              ((HRESULT)0x80150024)
#define DVERR_INVALIDHANDLE             ((HRESULT)0x80150025)
#define DVERR_NOTINITIALIZED            ((HRESULT)0x80150037)
#define DVERR_OUTOFMEMORY               E_OUTOFMEMORY
#define DVERR_PENDING                   ((HRESULT)0x80150049)
#define DVERR_NOVOICESESSION            ((HRESULT)0x8015004A)
#define DVERR_CONNECTIONLOST            ((HRESULT)0x80150050)

/* Message types */
#define DVMSGID_OFFSET                  0xC000
#define DVMSGID_CREATEVOICEPLAYER       (DVMSGID_OFFSET | 0x0001)
#define DVMSGID_DELETEVOICEPLAYER       (DVMSGID_OFFSET | 0x0002)
#define DVMSGID_SESSIONLOST             (DVMSGID_OFFSET | 0x0003)
#define DVMSGID_PLAYERVOICESTART        (DVMSGID_OFFSET | 0x0004)
#define DVMSGID_PLAYERVOICESTOP         (DVMSGID_OFFSET | 0x0005)
#define DVMSGID_RECORDSTART             (DVMSGID_OFFSET | 0x0006)
#define DVMSGID_RECORDSTOP              (DVMSGID_OFFSET | 0x0007)
#define DVMSGID_CONNECTRESULT           (DVMSGID_OFFSET | 0x0008)
#define DVMSGID_DISCONNECTRESULT        (DVMSGID_OFFSET | 0x0009)
#define DVMSGID_INPUTLEVEL              (DVMSGID_OFFSET | 0x000A)
#define DVMSGID_OUTPUTLEVEL             (DVMSGID_OFFSET | 0x000B)
#define DVMSGID_HOSTMIGRATED            (DVMSGID_OFFSET | 0x000C)
#define DVMSGID_SETTARGETS              (DVMSGID_OFFSET | 0x000D)

/* Session types */
#define DVSESSIONTYPE_PEER              0x00000001
#define DVSESSIONTYPE_MIXING            0x00000002
#define DVSESSIONTYPE_FORWARDING        0x00000003
#define DVSESSIONTYPE_ECHO              0x00000004

/* Flags */
#define DVPLAYERCAPS_HALFDUPLEX         0x00000001
#define DVPLAYERCAPS_LOCAL              0x00000002

#define DVCLIENTCONFIG_AUTORECORDVOLUME 0x00000001
#define DVCLIENTCONFIG_AUTOVOICEACTIVATED 0x00000002
#define DVCLIENTCONFIG_MUTEGLOBAL       0x00000004
#define DVCLIENTCONFIG_PLAYBACKMUTE     0x00000008
#define DVCLIENTCONFIG_RECORDMUTE       0x00000010

#define DVFLAGS_SYNC                    0x00000001
#define DVFLAGS_NOHOSTMIGRATE           0x00000008

/* Structures */
typedef struct _DVCAPS {
    DWORD   dwSize;
    DWORD   dwFlags;
} DVCAPS, *PDVCAPS;

typedef struct _DVSOUNDDEVICECONFIG {
    DWORD   dwSize;
    DWORD   dwFlags;
    GUID    guidPlaybackDevice;
    GUID    guidCaptureDevice;
    HWND    hwndAppWindow;
    void*   lpdsPlaybackDevice;
    void*   lpdsCaptureDevice;
    DWORD   dwMainBufferFlags;
    DWORD   dwMainBufferPriority;
} DVSOUNDDEVICECONFIG, *PDVSOUNDDEVICECONFIG;

typedef struct _DVCLIENTCONFIG {
    DWORD   dwSize;
    DWORD   dwFlags;
    LONG    lRecordVolume;
    LONG    lPlaybackVolume;
    DWORD   dwThreshold;
    DWORD   dwBufferQuality;
    DWORD   dwBufferAggressiveness;
    DWORD   dwNotifyPeriod;
} DVCLIENTCONFIG, *PDVCLIENTCONFIG;

typedef struct _DVSESSIONDESC {
    DWORD   dwSize;
    DWORD   dwFlags;
    DWORD   dwSessionType;
    GUID    guidCT;
    DWORD   dwBufferQuality;
    DWORD   dwBufferAggressiveness;
} DVSESSIONDESC, *PDVSESSIONDESC;

/* Message structures */
typedef struct _DVMSG_CREATEVOICEPLAYER {
    DWORD   dwSize;
    DPNID   dvidPlayer;
    DWORD   dwFlags;
    PVOID   pvPlayerContext;
} DVMSG_CREATEVOICEPLAYER, *PDVMSG_CREATEVOICEPLAYER;

typedef struct _DVMSG_DELETEVOICEPLAYER {
    DWORD   dwSize;
    DPNID   dvidPlayer;
    PVOID   pvPlayerContext;
} DVMSG_DELETEVOICEPLAYER, *PDVMSG_DELETEVOICEPLAYER;

typedef struct _DVMSG_SESSIONLOST {
    DWORD   dwSize;
    HRESULT hrResult;
} DVMSG_SESSIONLOST, *PDVMSG_SESSIONLOST;

typedef struct _DVMSG_PLAYERVOICESTART {
    DWORD   dwSize;
    DPNID   dvidSourcePlayerID;
    PVOID   pvPlayerContext;
} DVMSG_PLAYERVOICESTART, *PDVMSG_PLAYERVOICESTART;

typedef struct _DVMSG_PLAYERVOICESTOP {
    DWORD   dwSize;
    DPNID   dvidSourcePlayerID;
    PVOID   pvPlayerContext;
} DVMSG_PLAYERVOICESTOP, *PDVMSG_PLAYERVOICESTOP;

typedef struct _DVMSG_CONNECTRESULT {
    DWORD   dwSize;
    HRESULT hrResult;
} DVMSG_CONNECTRESULT, *PDVMSG_CONNECTRESULT;

/* Service provider GUIDs */
static const GUID CLSID_DirectPlayVoiceClient = {0xB9F3EB85, 0xB781, 0x4AC1, {0x8D, 0x90, 0x93, 0xA0, 0x5E, 0xE3, 0x7D, 0x7D}};
static const GUID CLSID_DirectPlayVoiceServer = {0xD3F5B8E6, 0x9B78, 0x4A4C, {0x94, 0xEA, 0xCA, 0x23, 0x97, 0xB6, 0x63, 0xD3}};

/* Interface forward declarations */
#ifdef __cplusplus
struct IDirectPlayVoiceClient;
struct IDirectPlayVoiceServer;
struct IDirectPlayVoiceTest;
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DVOICE_H */
