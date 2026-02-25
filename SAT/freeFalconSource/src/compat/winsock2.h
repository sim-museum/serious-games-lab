/*
 * FreeFalcon Linux Port - winsock2.h compatibility
 *
 * Maps Windows Sockets to BSD sockets
 */

#ifndef FF_COMPAT_WINSOCK2_H
#define FF_COMPAT_WINSOCK2_H

#ifdef FF_LINUX

/* Include windows.h for full Windows API compatibility */
#include "windows.h"

/* If winsock.h was already included, just use its definitions */
#ifdef FF_COMPAT_WINSOCK_H
/* winsock.h already included - skip duplicate definitions */
#else

#include "compat_types.h"
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Socket type */
typedef int SOCKET;
#define INVALID_SOCKET  ((SOCKET)(~0))
#define SOCKET_ERROR    (-1)

/* Winsock startup/cleanup - no-op on Linux */
typedef struct WSAData {
    WORD wVersion;
    WORD wHighVersion;
    char szDescription[257];
    char szSystemStatus[129];
    unsigned short iMaxSockets;
    unsigned short iMaxUdpDg;
    char* lpVendorInfo;
} WSADATA, *LPWSADATA;

static inline int WSAStartup(WORD wVersionRequested, LPWSADATA lpWSAData) {
    (void)wVersionRequested;
    if (lpWSAData) {
        lpWSAData->wVersion = 0x0202;
        lpWSAData->wHighVersion = 0x0202;
        lpWSAData->szDescription[0] = '\0';
        lpWSAData->szSystemStatus[0] = '\0';
    }
    return 0;
}

static inline int WSACleanup(void) {
    return 0;
}

/* Error handling */
static inline int WSAGetLastError(void) {
    return errno;
}

static inline void WSASetLastError(int iError) {
    errno = iError;
}

/* Socket functions - map to POSIX */
#define closesocket         close
#define ioctlsocket         ioctl

/* Error codes */
#define WSAEINTR            EINTR
#define WSAEBADF            EBADF
#define WSAEACCES           EACCES
#define WSAEFAULT           EFAULT
#define WSAEINVAL           EINVAL
#define WSAEMFILE           EMFILE
#define WSAEWOULDBLOCK      EWOULDBLOCK
#define WSAEINPROGRESS      EINPROGRESS
#define WSAEALREADY         EALREADY
#define WSAENOTSOCK         ENOTSOCK
#define WSAEDESTADDRREQ     EDESTADDRREQ
#define WSAEMSGSIZE         EMSGSIZE
#define WSAEPROTOTYPE       EPROTOTYPE
#define WSAENOPROTOOPT      ENOPROTOOPT
#define WSAEPROTONOSUPPORT  EPROTONOSUPPORT
#define WSAESOCKTNOSUPPORT  ESOCKTNOSUPPORT
#define WSAEOPNOTSUPP       EOPNOTSUPP
#define WSAEPFNOSUPPORT     EPFNOSUPPORT
#define WSAEAFNOSUPPORT     EAFNOSUPPORT
#define WSAEADDRINUSE       EADDRINUSE
#define WSAEADDRNOTAVAIL    EADDRNOTAVAIL
#define WSAENETDOWN         ENETDOWN
#define WSAENETUNREACH      ENETUNREACH
#define WSAENETRESET        ENETRESET
#define WSAECONNABORTED     ECONNABORTED
#define WSAECONNRESET       ECONNRESET
#define WSAENOBUFS          ENOBUFS
#define WSAEISCONN          EISCONN
#define WSAENOTCONN         ENOTCONN
#define WSAESHUTDOWN        ESHUTDOWN
#define WSAETOOMANYREFS     ETOOMANYREFS
#define WSAETIMEDOUT        ETIMEDOUT
#define WSAECONNREFUSED     ECONNREFUSED
#define WSAELOOP            ELOOP
#define WSAENAMETOOLONG     ENAMETOOLONG
#define WSAEHOSTDOWN        EHOSTDOWN
#define WSAEHOSTUNREACH     EHOSTUNREACH
#define WSAENOTEMPTY        ENOTEMPTY
#define WSAEUSERS           EUSERS
#define WSAEDQUOT           EDQUOT
#define WSAESTALE           ESTALE
#define WSAEREMOTE          EREMOTE
#define WSANOTINITIALISED   10093

/* Address families */
#ifndef AF_INET
#define AF_INET             2
#endif
#ifndef AF_INET6
#define AF_INET6            10
#endif

/* Socket types */
#ifndef SOCK_STREAM
#define SOCK_STREAM         1
#define SOCK_DGRAM          2
#define SOCK_RAW            3
#endif

/* Protocol types */
#ifndef IPPROTO_TCP
#define IPPROTO_TCP         6
#define IPPROTO_UDP         17
#endif

/* Shutdown options */
#define SD_RECEIVE          0
#define SD_SEND             1
#define SD_BOTH             2

/* Socket options */
#ifndef SO_DEBUG
#define SO_DEBUG            1
#define SO_REUSEADDR        2
#define SO_TYPE             3
#define SO_ERROR            4
#define SO_DONTROUTE        5
#define SO_BROADCAST        6
#define SO_SNDBUF           7
#define SO_RCVBUF           8
#define SO_KEEPALIVE        9
#define SO_OOBINLINE        10
#define SO_LINGER           13
#define SO_RCVTIMEO         20
#define SO_SNDTIMEO         21
#endif

/* ioctlsocket commands */
#define FIONBIO             0x5421
#define FIONREAD            0x541B

/* WSAPROTOCOL_INFO - for protocol enumeration (stub) */
#define WSAPROTOCOL_LEN     255
#define MAX_PROTOCOL_CHAIN  7

typedef struct _WSAPROTOCOLCHAIN {
    int ChainLen;
    DWORD ChainEntries[MAX_PROTOCOL_CHAIN];
} WSAPROTOCOLCHAIN, *LPWSAPROTOCOLCHAIN;

typedef struct _WSAPROTOCOL_INFOA {
    DWORD dwServiceFlags1;
    DWORD dwServiceFlags2;
    DWORD dwServiceFlags3;
    DWORD dwServiceFlags4;
    DWORD dwProviderFlags;
    GUID ProviderId;
    DWORD dwCatalogEntryId;
    WSAPROTOCOLCHAIN ProtocolChain;
    int iVersion;
    int iAddressFamily;
    int iMaxSockAddr;
    int iMinSockAddr;
    int iSocketType;
    int iProtocol;
    int iProtocolMaxOffset;
    int iNetworkByteOrder;
    int iSecurityScheme;
    DWORD dwMessageSize;
    DWORD dwProviderReserved;
    char szProtocol[WSAPROTOCOL_LEN + 1];
} WSAPROTOCOL_INFOA, *LPWSAPROTOCOL_INFOA;

typedef WSAPROTOCOL_INFOA WSAPROTOCOL_INFO;
typedef LPWSAPROTOCOL_INFOA LPWSAPROTOCOL_INFO;

/* WSAEnumProtocols - stub that returns no protocols */
#define WSAENOBUFS          ENOBUFS

static inline int WSAEnumProtocols(int* lpiProtocols, LPWSAPROTOCOL_INFO lpProtocolBuffer, LPDWORD lpdwBufferLength) {
    (void)lpiProtocols;
    (void)lpProtocolBuffer;
    if (lpdwBufferLength) *lpdwBufferLength = 0;
    /* Return 0 protocols available */
    return 0;
}

#ifdef __cplusplus
}
#endif

#endif /* !FF_COMPAT_WINSOCK_H */

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINSOCK2_H */
