/*
 * FreeFalcon Linux Port - dplobby.h stub
 *
 * DirectPlay Lobby API compatibility stub - DirectPlay is not available on Linux.
 * This provides minimal type definitions to allow compilation.
 */

#ifndef FF_COMPAT_DPLOBBY_H
#define FF_COMPAT_DPLOBBY_H

#ifdef FF_LINUX

#include "dplay.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declarations */
typedef struct IDirectPlayLobby IDirectPlayLobby, *LPDIRECTPLAYLOBBY;
typedef struct IDirectPlayLobbyA IDirectPlayLobbyA, *LPDIRECTPLAYLOBBYA;
typedef struct IDirectPlayLobby2 IDirectPlayLobby2, *LPDIRECTPLAYLOBBY2;
typedef struct IDirectPlayLobby2A IDirectPlayLobby2A;

/* Lobby result codes */
#define DPERR_NOTREGISTERED     0x80040308L
#define DPERR_CANTLOADCAPI      0x80040309L
#define DPERR_NOTCONNECTED      0x80040310L
#define DPERR_APPNOTSTARTED     0x80040311L

/* Lobby flags */
#define DPLMSG_STANDARD         0x00000001
#define DPLMSG_RELIABLE         0x00000002
#define DPCONNECT_RETURNSTATUS  0x00000080

/* Address types */
typedef struct DPADDRESS {
    GUID guidDataType;
    DWORD dwDataSize;
} DPADDRESS, *LPDPADDRESS;

typedef struct DPCOMPOUNDADDRESSELEMENT {
    GUID guidDataType;
    DWORD dwDataSize;
    LPVOID lpData;
} DPCOMPOUNDADDRESSELEMENT, *LPDPCOMPOUNDADDRESSELEMENT;

/* Well-known GUIDs for address data */
DEFINE_GUID(DPAID_TotalSize, 0x1318f560, 0x912c, 0x11d0, 0x9d, 0xaa, 0x0, 0xa0, 0xc9, 0xa, 0x43, 0xcb);
DEFINE_GUID(DPAID_ServiceProvider, 0x7d916c0, 0x912c, 0x11d0, 0x9d, 0xaa, 0x0, 0xa0, 0xc9, 0xa, 0x43, 0xcb);
DEFINE_GUID(DPAID_LobbyProvider, 0x59b95640, 0x9667, 0x11d0, 0xa7, 0x7d, 0x0, 0x0, 0xf8, 0x3, 0xab, 0xfc);
DEFINE_GUID(DPAID_Phone, 0x78ec89a0, 0xe0e4, 0x11cf, 0x9c, 0x4e, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_PhoneW, 0xba5a7a70, 0x9dbf, 0x11d0, 0x9c, 0xc1, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_Modem, 0xf6dcc200, 0xa2fe, 0x11d0, 0x9c, 0x4f, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_ModemW, 0x1fd92e0, 0xa2ff, 0x11d0, 0x9c, 0x4f, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_INet, 0xc4a54da0, 0xe0af, 0x11cf, 0x9c, 0x4e, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_INetW, 0xe63232a0, 0x9dbf, 0x11d0, 0x9c, 0xc1, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(DPAID_INetPort, 0xe4524541, 0x8ea5, 0x11d1, 0x8a, 0x96, 0x0, 0x60, 0x97, 0xb0, 0x14, 0x11);
DEFINE_GUID(DPAID_ComPort, 0xf2f0ce00, 0xe0af, 0x11cf, 0x9c, 0x4e, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);

/* Callback types */
typedef BOOL (FAR PASCAL *LPDPENUMADDRESSCALLBACK)(REFGUID guidDataType,
    DWORD dwDataSize, LPCVOID lpData, LPVOID lpContext);

typedef BOOL (FAR PASCAL *LPDPLENUMADDRESSTYPESCALLBACK)(REFGUID guidDataType,
    LPVOID lpContext, DWORD dwFlags);

typedef BOOL (FAR PASCAL *LPDPLENUMLOCALAPPLICATIONSCALLBACK)(LPCDPLAPPINFO lpAppInfo,
    LPVOID lpContext, DWORD dwFlags);

/* Application info struct */
typedef struct DPLAPPINFO {
    DWORD dwSize;
    GUID guidApplication;
    union {
        LPSTR lpszAppNameA;
        LPWSTR lpszAppName;
    };
} DPLAPPINFO, *LPDPLAPPINFO;

typedef const DPLAPPINFO *LPCDPLAPPINFO;

/* IDirectPlayLobby2A interface vtable - stub */
typedef struct IDirectPlayLobby2AVtbl {
    /* IUnknown methods */
    HRESULT (STDMETHODCALLTYPE *QueryInterface)(LPDIRECTPLAYLOBBY2A This, REFIID riid, void **ppvObject);
    ULONG (STDMETHODCALLTYPE *AddRef)(LPDIRECTPLAYLOBBY2A This);
    ULONG (STDMETHODCALLTYPE *Release)(LPDIRECTPLAYLOBBY2A This);
    /* IDirectPlayLobby methods */
    HRESULT (STDMETHODCALLTYPE *Connect)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, LPDIRECTPLAY3A *lplpDP, LPUNKNOWN lpUnk);
    HRESULT (STDMETHODCALLTYPE *CreateAddress)(LPDIRECTPLAYLOBBY2A This, REFGUID guidSP, REFGUID guidDataType, LPCVOID lpData, DWORD dwDataSize, LPVOID lpAddress, LPDWORD lpdwAddressSize);
    HRESULT (STDMETHODCALLTYPE *CreateCompoundAddress)(LPDIRECTPLAYLOBBY2A This, LPDPCOMPOUNDADDRESSELEMENT lpElements, DWORD dwElementCount, LPVOID lpAddress, LPDWORD lpdwAddressSize);
    HRESULT (STDMETHODCALLTYPE *EnumAddress)(LPDIRECTPLAYLOBBY2A This, LPDPENUMADDRESSCALLBACK lpEnumAddressCallback, LPCVOID lpAddress, DWORD dwAddressSize, LPVOID lpContext);
    HRESULT (STDMETHODCALLTYPE *EnumAddressTypes)(LPDIRECTPLAYLOBBY2A This, LPDPLENUMADDRESSTYPESCALLBACK lpEnumAddressTypeCallback, REFGUID guidSP, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *EnumLocalApplications)(LPDIRECTPLAYLOBBY2A This, LPDPLENUMLOCALAPPLICATIONSCALLBACK lpEnumLocalAppCallback, LPVOID lpContext, DWORD dwFlags);
    HRESULT (STDMETHODCALLTYPE *GetConnectionSettings)(LPDIRECTPLAYLOBBY2A This, DWORD dwAppID, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *ReceiveLobbyMessage)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, DWORD dwAppID, LPDWORD lpdwMessageFlags, LPVOID lpData, LPDWORD lpdwDataSize);
    HRESULT (STDMETHODCALLTYPE *RunApplication)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, LPDWORD lpdwAppID, LPDPLCONNECTION lpConn, HANDLE hReceiveEvent);
    HRESULT (STDMETHODCALLTYPE *SendLobbyMessage)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, DWORD dwAppID, LPVOID lpData, DWORD dwDataSize);
    HRESULT (STDMETHODCALLTYPE *SetConnectionSettings)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, DWORD dwAppID, LPDPLCONNECTION lpConn);
    HRESULT (STDMETHODCALLTYPE *SetLobbyMessageEvent)(LPDIRECTPLAYLOBBY2A This, DWORD dwFlags, DWORD dwAppID, HANDLE hReceiveEvent);
    /* IDirectPlayLobby2 methods */
    HRESULT (STDMETHODCALLTYPE *CreateCompoundAddress2)(LPDIRECTPLAYLOBBY2A This, LPDPCOMPOUNDADDRESSELEMENT lpOriginalElements, DWORD dwOriginalCount, LPDPCOMPOUNDADDRESSELEMENT lpNewElement, LPVOID lpAddress, LPDWORD lpdwAddressSize, REFGUID guidSP);
} IDirectPlayLobby2AVtbl;

struct IDirectPlayLobby2A {
    IDirectPlayLobby2AVtbl *lpVtbl;
};

/* GUIDs */
DEFINE_GUID(IID_IDirectPlayLobby, 0xaf465c71, 0x9588, 0x11cf, 0xa0, 0x20, 0x0, 0xaa, 0x0, 0x61, 0x57, 0xac);
DEFINE_GUID(IID_IDirectPlayLobbyA, 0x26c66a70, 0xb367, 0x11cf, 0xa0, 0x24, 0x0, 0xaa, 0x0, 0x61, 0x57, 0xac);
DEFINE_GUID(IID_IDirectPlayLobby2, 0x194c220, 0xa303, 0x11d0, 0x9c, 0x4f, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);
DEFINE_GUID(IID_IDirectPlayLobby2A, 0x1bb4af80, 0xa303, 0x11d0, 0x9c, 0x4f, 0x0, 0xa0, 0xc9, 0x5, 0x42, 0x5e);

DEFINE_GUID(CLSID_DirectPlayLobby, 0x2fe8f810, 0xb2a5, 0x11d0, 0xa7, 0x87, 0x0, 0x0, 0xf8, 0x3, 0xab, 0xfc);

/* DirectPlayLobbyCreate - stub that always fails */
static inline HRESULT DirectPlayLobbyCreateA(LPGUID lpGuid, LPDIRECTPLAYLOBBY2A *lplpDPL, LPUNKNOWN pUnk, LPVOID lpData, DWORD dwDataSize) {
    (void)lpGuid;
    (void)pUnk;
    (void)lpData;
    (void)dwDataSize;
    if (lplpDPL) *lplpDPL = NULL;
    return DPERR_UNSUPPORTED;
}
#define DirectPlayLobbyCreate DirectPlayLobbyCreateA

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DPLOBBY_H */
