/*
 * FreeFalcon Linux Port - dplay8.h compatibility
 *
 * DirectPlay 8 header stub for networking.
 * Actual implementation will use POSIX sockets or similar.
 */

#ifndef FF_COMPAT_DPLAY8_H
#define FF_COMPAT_DPLAY8_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* DirectPlay error codes */
#define DPN_OK                      S_OK
#define DPNERR_GENERIC              E_FAIL
#define DPNERR_INVALIDPARAM         E_INVALIDARG
#define DPNERR_OUTOFMEMORY          E_OUTOFMEMORY
#define DPNERR_NOTHOST              ((HRESULT)0x80158530)
#define DPNERR_USERCANCEL           ((HRESULT)0x80158540)
#define DPNERR_SESSIONFULL          ((HRESULT)0x80158515)
#define DPNERR_CONNECTING           ((HRESULT)0x80158516)
#define DPNERR_HOSTREJECTEDCONNECTION ((HRESULT)0x80158517)
#define DPNERR_NOCONNECTION         ((HRESULT)0x80158520)
#define DPNERR_CONNECTIONLOST       ((HRESULT)0x80158521)
#define DPNERR_PLAYERLOST           ((HRESULT)0x80158530)
#define DPNERR_TIMEDOUT             ((HRESULT)0x80158532)
#define DPNERR_INVALIDHANDLE        ((HRESULT)0x80158533)

/* Player ID type */
typedef DWORD DPNID;
typedef DPNID *PDPNID;

/* Handle types */
typedef HANDLE DPNHANDLE;
typedef DPNHANDLE *PDPNHANDLE;

/* Message types */
#define DPN_MSGID_OFFSET                    0xA000
#define DPN_MSGID_CREATE_PLAYER             (DPN_MSGID_OFFSET | 0x0001)
#define DPN_MSGID_DESTROY_PLAYER            (DPN_MSGID_OFFSET | 0x0002)
#define DPN_MSGID_HOST_MIGRATE              (DPN_MSGID_OFFSET | 0x0003)
#define DPN_MSGID_INDICATE_CONNECT          (DPN_MSGID_OFFSET | 0x0004)
#define DPN_MSGID_INDICATED_CONNECT_ABORTED (DPN_MSGID_OFFSET | 0x0005)
#define DPN_MSGID_CONNECT_COMPLETE          (DPN_MSGID_OFFSET | 0x0006)
#define DPN_MSGID_RECEIVE                   (DPN_MSGID_OFFSET | 0x0007)
#define DPN_MSGID_SEND_COMPLETE             (DPN_MSGID_OFFSET | 0x0008)
#define DPN_MSGID_ASYNC_OP_COMPLETE         (DPN_MSGID_OFFSET | 0x0009)
#define DPN_MSGID_ENUM_HOSTS_QUERY          (DPN_MSGID_OFFSET | 0x000A)
#define DPN_MSGID_ENUM_HOSTS_RESPONSE       (DPN_MSGID_OFFSET | 0x000B)
#define DPN_MSGID_APPLICATION_DESC          (DPN_MSGID_OFFSET | 0x000C)
#define DPN_MSGID_TERMINATE_SESSION         (DPN_MSGID_OFFSET | 0x000D)

/* Send flags */
#define DPNSEND_SYNC                0x00000001
#define DPNSEND_NOCOPY              0x00000002
#define DPNSEND_NOCOMPLETE          0x00000004
#define DPNSEND_COMPLETEONPROCESS   0x00000008
#define DPNSEND_GUARANTEED          0x00000010
#define DPNSEND_NONSEQUENTIAL       0x00000020
#define DPNSEND_NOLOOPBACK          0x00000040
#define DPNSEND_PRIORITY_LOW        0x00000080
#define DPNSEND_PRIORITY_HIGH       0x00000100

/* Structures */
typedef struct _DPN_PLAYER_INFO {
    DWORD   dwSize;
    DWORD   dwInfoFlags;
    PWSTR   pwszName;
    PVOID   pvData;
    DWORD   dwDataSize;
    DWORD   dwPlayerFlags;
} DPN_PLAYER_INFO, *PDPN_PLAYER_INFO;

typedef struct _DPN_APPLICATION_DESC {
    DWORD   dwSize;
    DWORD   dwFlags;
    GUID    guidInstance;
    GUID    guidApplication;
    DWORD   dwMaxPlayers;
    DWORD   dwCurrentPlayers;
    PWSTR   pwszSessionName;
    PWSTR   pwszPassword;
    PVOID   pvReservedData;
    DWORD   dwReservedDataSize;
    PVOID   pvApplicationReservedData;
    DWORD   dwApplicationReservedDataSize;
} DPN_APPLICATION_DESC, *PDPN_APPLICATION_DESC;

typedef struct _DPN_BUFFER_DESC {
    DWORD   dwBufferSize;
    BYTE*   pBufferData;
} DPN_BUFFER_DESC, *PDPN_BUFFER_DESC;

/* Message structures */
typedef struct _DPNMSG_CREATE_PLAYER {
    DWORD   dwSize;
    DPNID   dpnidPlayer;
    PVOID   pvPlayerContext;
} DPNMSG_CREATE_PLAYER, *PDPNMSG_CREATE_PLAYER;

typedef struct _DPNMSG_DESTROY_PLAYER {
    DWORD   dwSize;
    DPNID   dpnidPlayer;
    PVOID   pvPlayerContext;
    DWORD   dwReason;
} DPNMSG_DESTROY_PLAYER, *PDPNMSG_DESTROY_PLAYER;

typedef struct _DPNMSG_RECEIVE {
    DWORD   dwSize;
    DPNID   dpnidSender;
    PVOID   pvPlayerContext;
    PBYTE   pReceiveData;
    DWORD   dwReceiveDataSize;
    DPNHANDLE hBufferHandle;
} DPNMSG_RECEIVE, *PDPNMSG_RECEIVE;

/* Service provider GUIDs */
static const GUID CLSID_DP8SP_TCPIP = {0xEBFE7BA0, 0x628D, 0x11D2, {0xAE, 0x0F, 0x00, 0x60, 0x97, 0xB0, 0x14, 0x11}};
static const GUID CLSID_DirectPlay8Client = {0x743F1DC6, 0x5ABA, 0x429F, {0x8B, 0xDF, 0xC5, 0x4D, 0x03, 0x25, 0x3D, 0xC2}};
static const GUID CLSID_DirectPlay8Server = {0xDA825E1B, 0x6830, 0x43D7, {0x83, 0x5D, 0x0B, 0x5A, 0xD8, 0x29, 0x56, 0xA2}};
static const GUID CLSID_DirectPlay8Peer = {0x286F484D, 0x375E, 0x4458, {0xA2, 0x72, 0xB1, 0x38, 0xE2, 0xF8, 0x0A, 0x6A}};
static const GUID CLSID_DirectPlay8Address = {0x934A9523, 0xA3CA, 0x4BC5, {0xAD, 0xA0, 0xD6, 0xD9, 0x5D, 0x97, 0x94, 0x21}};

/* Interface forward declarations - actual implementation will be different on Linux */
#ifdef __cplusplus
struct IDirectPlay8Client;
struct IDirectPlay8Server;
struct IDirectPlay8Peer;
struct IDirectPlay8Address;
#endif

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DPLAY8_H */
