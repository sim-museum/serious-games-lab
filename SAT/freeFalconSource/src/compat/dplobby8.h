/*
 * FreeFalcon Linux Port - dplobby8.h compatibility
 *
 * DirectPlay Lobby 8 header stub.
 * Actual implementation will use different networking.
 */

#ifndef FF_COMPAT_DPLOBBY8_H
#define FF_COMPAT_DPLOBBY8_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "dplay8.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Lobby error codes */
#define DPNLOBBY_OK                     S_OK
#define DPNLOBBYERR_GENERIC             E_FAIL
#define DPNLOBBYERR_NOTAVAILABLE        ((HRESULT)0x80040112)

/* Lobby message types */
#define DPL_MSGID_OFFSET                0xB000
#define DPL_MSGID_DISCONNECT            (DPL_MSGID_OFFSET | 0x0001)
#define DPL_MSGID_RECEIVE               (DPL_MSGID_OFFSET | 0x0002)
#define DPL_MSGID_SESSION_STATUS        (DPL_MSGID_OFFSET | 0x0003)
#define DPL_MSGID_CONNECTION_SETTINGS   (DPL_MSGID_OFFSET | 0x0004)

/* Session status values */
#define DPLSESSION_CONNECTED            0x0001
#define DPLSESSION_DISCONNECTED         0x0002
#define DPLSESSION_TERMINATED           0x0003
#define DPLSESSION_HOSTMIGRATED         0x0004

/* Connection settings flags */
#define DPLCONNECTSETTINGS_HOST         0x0001

/* Structures */
typedef struct _DPL_APPLICATION_INFO {
    GUID    guidApplication;
    PWSTR   pwszApplicationName;
    DWORD   dwNumRunning;
    DWORD   dwNumWaiting;
    DWORD   dwFlags;
} DPL_APPLICATION_INFO, *PDPL_APPLICATION_INFO;

typedef struct _DPL_CONNECTION_SETTINGS {
    DWORD                   dwSize;
    DWORD                   dwFlags;
    DPN_APPLICATION_DESC    dpnAppDesc;
    void*                   pdp8HostAddress;
    void**                  ppdp8DeviceAddresses;
    DWORD                   cNumDeviceAddresses;
    PWSTR                   pwszPlayerName;
} DPL_CONNECTION_SETTINGS, *PDPL_CONNECTION_SETTINGS;

/* Message structures */
typedef struct _DPL_MESSAGE_DISCONNECT {
    DWORD   dwSize;
    DPNHANDLE hDisconnectId;
    HRESULT hrReason;
} DPL_MESSAGE_DISCONNECT, *PDPL_MESSAGE_DISCONNECT;

typedef struct _DPL_MESSAGE_RECEIVE {
    DWORD   dwSize;
    DPNHANDLE hSender;
    BYTE*   pBuffer;
    DWORD   dwBufferSize;
} DPL_MESSAGE_RECEIVE, *PDPL_MESSAGE_RECEIVE;

typedef struct _DPL_MESSAGE_SESSION_STATUS {
    DWORD   dwSize;
    DPNHANDLE hSender;
    DWORD   dwStatus;
} DPL_MESSAGE_SESSION_STATUS, *PDPL_MESSAGE_SESSION_STATUS;

typedef struct _DPL_MESSAGE_CONNECTION_SETTINGS {
    DWORD   dwSize;
    DPNHANDLE hSender;
    PDPL_CONNECTION_SETTINGS pdplConnectionSettings;
} DPL_MESSAGE_CONNECTION_SETTINGS, *PDPL_MESSAGE_CONNECTION_SETTINGS;

/* Service provider GUIDs */
static const GUID CLSID_DirectPlay8LobbiedApplication = {0x667955AD, 0x6B3B, 0x43CA, {0xB9, 0x49, 0xBC, 0x69, 0xB5, 0xBA, 0xFF, 0x7F}};
static const GUID CLSID_DirectPlay8LobbyClient = {0x3B2B6775, 0x70B6, 0x45AF, {0x8D, 0xEA, 0xA2, 0x09, 0xC6, 0x95, 0x59, 0xF3}};

/* Interface forward declarations */
#ifdef __cplusplus
struct IDirectPlay8LobbiedApplication;
struct IDirectPlay8LobbyClient;
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DPLOBBY8_H */
