/*
 * FreeFalcon Linux Port - dplay.h stub
 *
 * DirectPlay API compatibility stub - DirectPlay is not available on Linux.
 * This provides minimal type definitions to allow compilation.
 */

#ifndef FF_COMPAT_DPLAY_H
#define FF_COMPAT_DPLAY_H

#ifdef FF_LINUX

#include "windows.h"
#include "objbase.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declarations */
typedef struct IDirectPlay3 IDirectPlay3, *LPDIRECTPLAY3;
typedef struct IDirectPlay3A IDirectPlay3A, *LPDIRECTPLAY3A;
typedef struct IDirectPlayLobby2A IDirectPlayLobby2A, *LPDIRECTPLAYLOBBY2A;

/* DirectPlay result codes */
#define DP_OK                   S_OK
#define DPERR_GENERIC           E_FAIL
#define DPERR_INVALIDPARAMS     E_INVALIDARG
#define DPERR_OUTOFMEMORY       E_OUTOFMEMORY
#define DPERR_UNSUPPORTED       E_NOTIMPL
#define DPERR_NOTLOBBIED        0x80040300L
#define DPERR_CONNECTING        0x80040301L
#define DPERR_BUFFERTOOSMALL    0x80040302L
#define DPERR_NOMESSAGES        0x80040303L
#define DPERR_CONNECTIONLOST    0x80040304L
#define DPERR_NOCAPS            0x80040305L
#define DPERR_CANNOTCREATEGROUP 0x80040306L
#define DPERR_INVALIDPARAM      DPERR_INVALIDPARAMS

/* DirectPlay Player IDs */
typedef DWORD DPID;
#define DPID_SYSMSG             0x00000000
#define DPID_ALLPLAYERS         0x00000000
#define DPID_SERVERPLAYER       0x00000001
#define DPID_UNKNOWN            0xFFFFFFFF

/* DirectPlay flags */
#define DPOPEN_JOIN             0x00000001
#define DPOPEN_CREATE           0x00000002
#define DPLCONNECTION_CREATESESSION     0x00000002
#define DPLCONNECTION_JOINSESSION       0x00000001
#define DPSEND_GUARANTEED       0x00000001
#define DPRECEIVE_ALL           0x00000001
#define DPSESSION_MIGRATEHOST   0x00000004
#define DPSESSION_NODATAMESSAGES        0x00000080
#define DPSESSION_DIRECTPLAYPROTOCOL    0x00000800
#define DPSESSION_KEEPALIVE     0x00000200
#define DPENUMPLAYERS_ALL       0x00000000
#define DPENUMSESSIONS_AVAILABLE        0x00000001

/* Structures */
typedef struct DPNAME {
    DWORD dwSize;
    DWORD dwFlags;
    LPSTR lpszShortNameA;
    LPWSTR lpszShortName;
    LPSTR lpszLongNameA;
    LPWSTR lpszLongName;
} DPNAME, *LPDPNAME;

typedef const DPNAME *LPCDPNAME;

typedef struct DPSESSIONDESC2 {
    DWORD dwSize;
    DWORD dwFlags;
    GUID guidInstance;
    GUID guidApplication;
    DWORD dwMaxPlayers;
    DWORD dwCurrentPlayers;
    LPSTR lpszSessionNameA;
    LPWSTR lpszSessionName;
    LPSTR lpszPasswordA;
    LPWSTR lpszPassword;
    DWORD dwReserved1;
    DWORD dwReserved2;
    DWORD dwUser1;
    DWORD dwUser2;
    DWORD dwUser3;
    DWORD dwUser4;
} DPSESSIONDESC2, *LPDPSESSIONDESC2;

typedef const DPSESSIONDESC2 *LPCDPSESSIONDESC2;

typedef struct DPCAPS {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwMaxBufferSize;
    DWORD dwMaxQueueSize;
    DWORD dwMaxPlayers;
    DWORD dwHundredBaud;
    DWORD dwLatency;
    DWORD dwMaxLocalPlayers;
    DWORD dwHeaderLength;
    DWORD dwTimeout;
} DPCAPS, *LPDPCAPS;

typedef struct DPLCONNECTION {
    DWORD dwSize;
    DWORD dwFlags;
    LPDPSESSIONDESC2 lpSessionDesc;
    LPDPNAME lpPlayerName;
    GUID guidSP;
    LPVOID lpAddress;
    DWORD dwAddressSize;
} DPLCONNECTION, *LPDPLCONNECTION;

typedef struct _DPCOMPORTADDRESS {
    DWORD dwComPort;
    DWORD dwBaudRate;
    DWORD dwStopBits;
    DWORD dwParity;
    DWORD dwFlowControl;
} DPCOMPORTADDRESS, *LPDPCOMPORTADDRESS;

/* Message header */
typedef struct DPMSG_GENERIC {
    DWORD dwType;
} DPMSG_GENERIC, *LPDPMSG_GENERIC;

#define DPSYS_CREATEPLAYERORGROUP       0x0003
#define DPSYS_DESTROYPLAYERORGROUP      0x0005
#define DPSYS_ADDPLAYERTOGROUP          0x0007
#define DPSYS_DELETEPLAYERFROMGROUP     0x0021
#define DPSYS_SESSIONLOST               0x0031
#define DPSYS_HOST                      0x0101

typedef struct DPMSG_CREATEPLAYERORGROUP {
    DWORD dwType;
    DWORD dwPlayerType;
    DPID dpId;
    DWORD dwCurrentPlayers;
    LPVOID lpData;
    DWORD dwDataSize;
    DPNAME dpnName;
    DPID dpIdParent;
    DWORD dwFlags;
} DPMSG_CREATEPLAYERORGROUP, *LPDPMSG_CREATEPLAYERORGROUP;

typedef struct DPMSG_DESTROYPLAYERORGROUP {
    DWORD dwType;
    DWORD dwPlayerType;
    DPID dpId;
    LPVOID lpLocalData;
    DWORD dwLocalDataSize;
    LPVOID lpRemoteData;
    DWORD dwRemoteDataSize;
    DPNAME dpnName;
    DPID dpIdParent;
    DWORD dwFlags;
} DPMSG_DESTROYPLAYERORGROUP, *LPDPMSG_DESTROYPLAYERORGROUP;

typedef struct DPMSG_ADDPLAYERTOGROUP {
    DWORD dwType;
    DPID dpIdGroup;
    DPID dpIdPlayer;
} DPMSG_ADDPLAYERTOGROUP, *LPDPMSG_ADDPLAYERTOGROUP;

typedef struct DPMSG_DELETEPLAYERFROMGROUP {
    DWORD dwType;
    DPID dpIdGroup;
    DPID dpIdPlayer;
} DPMSG_DELETEPLAYERFROMGROUP, *LPDPMSG_DELETEPLAYERFROMGROUP;

/* Callback types */
typedef BOOL (FAR PASCAL *LPDPENUMDPCALLBACK)(LPGUID lpguidSP, LPTSTR lpSPName,
    DWORD dwMajorVersion, DWORD dwMinorVersion, LPVOID lpContext);

typedef BOOL (FAR PASCAL *LPDPENUMPLAYERSCALLBACK2)(DPID dpId, DWORD dwPlayerType,
    LPCDPNAME lpName, DWORD dwFlags, LPVOID lpContext);

typedef BOOL (FAR PASCAL *LPDPENUMSESSIONSCALLBACK2)(LPCDPSESSIONDESC2 lpThisSD,
    LPDWORD lpdwTimeOut, DWORD dwFlags, LPVOID lpContext);

/* DirectPlay enumeration function - stub */
static inline HRESULT DirectPlayEnumerateA(LPDPENUMDPCALLBACK lpEnumCallback, LPVOID lpContext) {
    (void)lpEnumCallback;
    (void)lpContext;
    return DPERR_UNSUPPORTED;
}
#define DirectPlayEnumerate DirectPlayEnumerateA

/* IDirectPlay3 interface vtable - stub */
typedef struct IDirectPlay3AVtbl {
    /* IUnknown methods */
    HRESULT (STDMETHODCALLTYPE *QueryInterface)(LPDIRECTPLAY3A This, REFIID riid, void **ppvObject);
    ULONG (STDMETHODCALLTYPE *AddRef)(LPDIRECTPLAY3A This);
    ULONG (STDMETHODCALLTYPE *Release)(LPDIRECTPLAY3A This);
    /* IDirectPlay3 methods - all stubbed */
    HRESULT (STDMETHODCALLTYPE *AddPlayerToGroup)(LPDIRECTPLAY3A This, DPID idGroup, DPID idPlayer);
    HRESULT (STDMETHODCALLTYPE *Close)(LPDIRECTPLAY3A This);
    HRESULT (STDMETHODCALLTYPE *CreateGroup)(LPDIRECTPLAY3A This, LPDPID lpidGroup, LPDPNAME lpGroupName, LPVOID lpData, DWORD dwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *CreatePlayer)(LPDIRECTPLAY3A This, LPDPID lpidPlayer, LPDPNAME lpPlayerName, HANDLE hEvent, LPVOID lpData, DWORD dwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *DeletePlayerFromGroup)(LPDIRECTPLAY3A This, DPID idGroup, DPID idPlayer);
    HRESULT (STDMETHODCALLTYPE *DestroyGroup)(LPDIRECTPLAY3A This, DPID idGroup);
    HRESULT (STDMETHODCALLTYPE *DestroyPlayer)(LPDIRECTPLAY3A This, DPID idPlayer);
    HRESULT (STDMETHODCALLTYPE *EnumGroupPlayers)(LPDIRECTPLAY3A This, DPID idGroup, LPGUID lpguidInstance, LPDPENUMPLAYERSCALLBACK2 lpEnumPlayersCallback2, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *EnumGroups)(LPDIRECTPLAY3A This, LPGUID lpguidInstance, LPDPENUMPLAYERSCALLBACK2 lpEnumPlayersCallback2, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *EnumPlayers)(LPDIRECTPLAY3A This, LPGUID lpguidInstance, LPDPENUMPLAYERSCALLBACK2 lpEnumPlayersCallback2, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *EnumSessions)(LPDIRECTPLAY3A This, LPDPSESSIONDESC2 lpsd, DWORD dwTimeout, LPDPENUMSESSIONSCALLBACK2 lpEnumSessionsCallback2, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetCaps)(LPDIRECTPLAY3A This, LPDPCAPS lpDPCaps, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetGroupData)(LPDIRECTPLAY3A This, DPID idGroup, LPVOID lpData, LPDWORD lpdwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetGroupName)(LPDIRECTPLAY3A This, DPID idGroup, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *GetMessageCount)(LPDIRECTPLAY3A This, DPID idPlayer, LPDWORD lpdwCount);
    HRESULT (STDMETHODCALLTYPE *GetPlayerAddress)(LPDIRECTPLAY3A This, DPID idPlayer, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *GetPlayerCaps)(LPDIRECTPLAY3A This, DPID idPlayer, LPDPCAPS lpPlayerCaps, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetPlayerData)(LPDIRECTPLAY3A This, DPID idPlayer, LPVOID lpData, LPDWORD lpdwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetPlayerName)(LPDIRECTPLAY3A This, DPID idPlayer, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *GetSessionDesc)(LPDIRECTPLAY3A This, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *Initialize)(LPDIRECTPLAY3A This, LPGUID lpGUID);
    HRESULT (STDMETHODCALLTYPE *Open)(LPDIRECTPLAY3A This, LPDPSESSIONDESC2 lpsd, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *Receive)(LPDIRECTPLAY3A This, LPDPID lpidFrom, LPDPID lpidTo, DWORD dwFlags, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *Send)(LPDIRECTPLAY3A This, DPID idFrom, DPID idTo, DWORD dwFlags, LPVOID lpData, DWORD dwDataSize);
    HRESULT (STDMETHODCALLTYPE *SetGroupData)(LPDIRECTPLAY3A This, DPID idGroup, LPVOID lpData, DWORD dwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *SetGroupName)(LPDIRECTPLAY3A This, DPID idGroup, LPDPNAME lpGroupName, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *SetPlayerData)(LPDIRECTPLAY3A This, DPID idPlayer, LPVOID lpData, DWORD dwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *SetPlayerName)(LPDIRECTPLAY3A This, DPID idPlayer, LPDPNAME lpPlayerName, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *SetSessionDesc)(LPDIRECTPLAY3A This, LPDPSESSIONDESC2 lpsd, DWORD dwFlags);
    /* IDirectPlay3 specific methods */
    HRESULT (STDMETHODCALLTYPE *AddGroupToGroup)(LPDIRECTPLAY3A This, DPID idParentGroup, DPID idGroup);
    HRESULT (STDMETHODCALLTYPE *CreateGroupInGroup)(LPDIRECTPLAY3A This, DPID idParentGroup, LPDPID lpidGroup, LPDPNAME lpGroupName, LPVOID lpData, DWORD dwDataSize, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *DeleteGroupFromGroup)(LPDIRECTPLAY3A This, DPID idParentGroup, DPID idGroup);
    HRESULT (STDMETHODCALLTYPE *EnumConnections)(LPDIRECTPLAY3A This, LPCGUID lpguidApplication, LPDPENUMDPCALLBACK lpEnumCallback, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *EnumGroupsInGroup)(LPDIRECTPLAY3A This, DPID idGroup, LPGUID lpguidInstance, LPDPENUMPLAYERSCALLBACK2 lpEnumPlayersCallback2, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetGroupConnectionSettings)(LPDIRECTPLAY3A This, DWORD dwFlags, DPID idGroup, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *InitializeConnection)(LPDIRECTPLAY3A This, LPVOID lpConnection, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *SecureOpen)(LPDIRECTPLAY3A This, LPCDPSESSIONDESC2 lpsd, DWORD dwFlags, LPVOID lpSecurity, LPVOID lpCredentials);
    HRESULT (STDMETHODCALLTYPE *SendChatMessage)(LPDIRECTPLAY3A This, DPID idFrom, DPID idTo, DWORD dwFlags, LPVOID lpData);
    HRESULT (STDMETHODCALLTYPE *SetGroupConnectionSettings)(LPDIRECTPLAY3A This, DWORD dwFlags, DPID idGroup, LPDPLCONNECTION lpConnection);
    HRESULT (STDMETHODCALLTYPE *StartSession)(LPDIRECTPLAY3A This, DWORD dwFlags, DPID idGroup);
    HRESULT (STDMETHODCALLTYPE *GetGroupFlags)(LPDIRECTPLAY3A This, DPID idGroup, LPDWORD lpdwFlags);
    HRESULT (STDMETHODCALLTYPE *GetGroupParent)(LPDIRECTPLAY3A This, DPID idGroup, LPDPID lpidParent);
    HRESULT (STDMETHODCALLTYPE *GetPlayerAccount)(LPDIRECTPLAY3A This, DPID idPlayer, DWORD dwFlags, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *GetPlayerFlags)(LPDIRECTPLAY3A This, DPID idPlayer, LPDWORD lpdwFlags);
} IDirectPlay3AVtbl;

struct IDirectPlay3A {
    IDirectPlay3AVtbl *lpVtbl;
};

/* IDirectPlay3 IID */
DEFINE_GUID(IID_IDirectPlay3A, 0x133efe40, 0x32dc, 0x11d0, 0x9c, 0xfb, 0x0, 0xa0, 0xc9, 0xa, 0x43, 0xcb);
#define IID_IDirectPlay3 IID_IDirectPlay3A

/* DirectPlayCreate - stub that always fails */
static inline HRESULT DirectPlayCreate(LPGUID lpGUID, LPDIRECTPLAY3A *lplpDP, LPUNKNOWN pUnk) {
    (void)lpGUID;
    (void)pUnk;
    if (lplpDP) *lplpDP = NULL;
    return DPERR_UNSUPPORTED;
}

/* CoCreateInstance for DirectPlay GUIDs - will fail */
DEFINE_GUID(CLSID_DirectPlay, 0xd1eb6d20, 0x8923, 0x11d0, 0x9d, 0x97, 0x0, 0xa0, 0xc9, 0xa, 0x43, 0xcb);

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DPLAY_H */
