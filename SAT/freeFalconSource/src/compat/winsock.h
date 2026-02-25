/*
 * FreeFalcon Linux Port - winsock.h compatibility
 *
 * Windows Sockets API compatibility for Linux
 * Note: If winsock2.h was already included, we just use its definitions
 */

#ifndef FF_COMPAT_WINSOCK_H
#define FF_COMPAT_WINSOCK_H

#ifdef FF_LINUX

/* Include windows.h for full Windows API compatibility (GetTickCount, Sleep, etc) */
#include "windows.h"

/* If winsock2.h was already included, just use its definitions */
#ifdef FF_COMPAT_WINSOCK2_H
/* winsock2.h already included, nothing more to do */
#else
/* winsock2.h not included, provide winsock1 compatibility */

#include "compat_types.h"
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
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * WinSock Types
 * ============================================================ */

typedef int SOCKET;
#define INVALID_SOCKET  ((SOCKET)(~0))
#define SOCKET_ERROR    (-1)

/* WinSock address family - same as POSIX */
#ifndef AF_INET
#define AF_INET         2
#endif

/* WinSock socket types - same as POSIX */
#ifndef SOCK_STREAM
#define SOCK_STREAM     1
#define SOCK_DGRAM      2
#define SOCK_RAW        3
#endif

/* WinSock protocols */
#ifndef IPPROTO_TCP
#define IPPROTO_TCP     6
#define IPPROTO_UDP     17
#endif

/* WinSock send/recv flags */
#ifndef MSG_OOB
#define MSG_OOB         0x1
#define MSG_PEEK        0x2
#define MSG_DONTROUTE   0x4
#endif

/* ============================================================
 * WinSock Structures (same as POSIX but may need aliases)
 * ============================================================ */

/* sockaddr_in is the same on Windows and POSIX */
/* in_addr is the same on Windows and POSIX */

/* WSADATA structure for WSAStartup */
typedef struct WSAData {
    WORD    wVersion;
    WORD    wHighVersion;
    char    szDescription[257];
    char    szSystemStatus[129];
    unsigned short iMaxSockets;
    unsigned short iMaxUdpDg;
    char*   lpVendorInfo;
} WSADATA, *LPWSADATA;

/* ============================================================
 * WinSock Error Codes
 * ============================================================ */

#define WSABASEERR              10000
#define WSAEINTR                (WSABASEERR + 4)
#define WSAEBADF                (WSABASEERR + 9)
#define WSAEACCES               (WSABASEERR + 13)
#define WSAEFAULT               (WSABASEERR + 14)
#define WSAEINVAL               (WSABASEERR + 22)
#define WSAEMFILE               (WSABASEERR + 24)
#define WSAEWOULDBLOCK          (WSABASEERR + 35)
#define WSAEINPROGRESS          (WSABASEERR + 36)
#define WSAEALREADY             (WSABASEERR + 37)
#define WSAENOTSOCK             (WSABASEERR + 38)
#define WSAEDESTADDRREQ         (WSABASEERR + 39)
#define WSAEMSGSIZE             (WSABASEERR + 40)
#define WSAEPROTOTYPE           (WSABASEERR + 41)
#define WSAENOPROTOOPT          (WSABASEERR + 42)
#define WSAEPROTONOSUPPORT      (WSABASEERR + 43)
#define WSAESOCKTNOSUPPORT      (WSABASEERR + 44)
#define WSAEOPNOTSUPP           (WSABASEERR + 45)
#define WSAEPFNOSUPPORT         (WSABASEERR + 46)
#define WSAEAFNOSUPPORT         (WSABASEERR + 47)
#define WSAEADDRINUSE           (WSABASEERR + 48)
#define WSAEADDRNOTAVAIL        (WSABASEERR + 49)
#define WSAENETDOWN             (WSABASEERR + 50)
#define WSAENETUNREACH          (WSABASEERR + 51)
#define WSAENETRESET            (WSABASEERR + 52)
#define WSAECONNABORTED         (WSABASEERR + 53)
#define WSAECONNRESET           (WSABASEERR + 54)
#define WSAENOBUFS              (WSABASEERR + 55)
#define WSAEISCONN              (WSABASEERR + 56)
#define WSAENOTCONN             (WSABASEERR + 57)
#define WSAESHUTDOWN            (WSABASEERR + 58)
#define WSAETOOMANYREFS         (WSABASEERR + 59)
#define WSAETIMEDOUT            (WSABASEERR + 60)
#define WSAECONNREFUSED         (WSABASEERR + 61)
#define WSAELOOP                (WSABASEERR + 62)
#define WSAENAMETOOLONG         (WSABASEERR + 63)
#define WSAEHOSTDOWN            (WSABASEERR + 64)
#define WSAEHOSTUNREACH         (WSABASEERR + 65)
#define WSAENOTEMPTY            (WSABASEERR + 66)
#define WSAEPROCLIM             (WSABASEERR + 67)
#define WSAEUSERS               (WSABASEERR + 68)
#define WSAEDQUOT               (WSABASEERR + 69)
#define WSAESTALE               (WSABASEERR + 70)
#define WSAEREMOTE              (WSABASEERR + 71)
#define WSANOTINITIALISED       (WSABASEERR + 93)

/* ============================================================
 * WinSock Functions
 * ============================================================ */

/* WSAStartup/WSACleanup - no-op on Linux (sockets always available) */
static inline int WSAStartup(WORD wVersionRequested, LPWSADATA lpWSAData) {
    if (lpWSAData) {
        lpWSAData->wVersion = wVersionRequested;
        lpWSAData->wHighVersion = 0x0202; /* 2.2 */
        strcpy(lpWSAData->szDescription, "Linux WinSock Emulation");
        lpWSAData->szSystemStatus[0] = '\0';
        lpWSAData->iMaxSockets = 1024;
        lpWSAData->iMaxUdpDg = 65507;
        lpWSAData->lpVendorInfo = NULL;
    }
    return 0;
}

static inline int WSACleanup(void) {
    return 0;
}

/* WSAGetLastError - map to errno */
static inline int WSAGetLastError(void) {
    switch (errno) {
        case EINTR:         return WSAEINTR;
        case EBADF:         return WSAEBADF;
        case EACCES:        return WSAEACCES;
        case EFAULT:        return WSAEFAULT;
        case EINVAL:        return WSAEINVAL;
        case EMFILE:        return WSAEMFILE;
        case EWOULDBLOCK:   return WSAEWOULDBLOCK;
        case EINPROGRESS:   return WSAEINPROGRESS;
        case EALREADY:      return WSAEALREADY;
        case ENOTSOCK:      return WSAENOTSOCK;
        case EDESTADDRREQ:  return WSAEDESTADDRREQ;
        case EMSGSIZE:      return WSAEMSGSIZE;
        case EPROTOTYPE:    return WSAEPROTOTYPE;
        case ENOPROTOOPT:   return WSAENOPROTOOPT;
        case EPROTONOSUPPORT: return WSAEPROTONOSUPPORT;
#ifdef ESOCKTNOSUPPORT
        case ESOCKTNOSUPPORT: return WSAESOCKTNOSUPPORT;
#endif
        case EOPNOTSUPP:    return WSAEOPNOTSUPP;
#ifdef EPFNOSUPPORT
        case EPFNOSUPPORT:  return WSAEPFNOSUPPORT;
#endif
        case EAFNOSUPPORT:  return WSAEAFNOSUPPORT;
        case EADDRINUSE:    return WSAEADDRINUSE;
        case EADDRNOTAVAIL: return WSAEADDRNOTAVAIL;
        case ENETDOWN:      return WSAENETDOWN;
        case ENETUNREACH:   return WSAENETUNREACH;
        case ENETRESET:     return WSAENETRESET;
        case ECONNABORTED:  return WSAECONNABORTED;
        case ECONNRESET:    return WSAECONNRESET;
        case ENOBUFS:       return WSAENOBUFS;
        case EISCONN:       return WSAEISCONN;
        case ENOTCONN:      return WSAENOTCONN;
#ifdef ESHUTDOWN
        case ESHUTDOWN:     return WSAESHUTDOWN;
#endif
#ifdef ETOOMANYREFS
        case ETOOMANYREFS:  return WSAETOOMANYREFS;
#endif
        case ETIMEDOUT:     return WSAETIMEDOUT;
        case ECONNREFUSED:  return WSAECONNREFUSED;
        case ELOOP:         return WSAELOOP;
        case ENAMETOOLONG:  return WSAENAMETOOLONG;
#ifdef EHOSTDOWN
        case EHOSTDOWN:     return WSAEHOSTDOWN;
#endif
        case EHOSTUNREACH:  return WSAEHOSTUNREACH;
        case ENOTEMPTY:     return WSAENOTEMPTY;
        default:            return WSABASEERR + errno;
    }
}

static inline void WSASetLastError(int iError) {
    (void)iError;
    /* No direct mapping back to errno */
}

/* closesocket - Windows uses closesocket, Linux uses close */
static inline int closesocket(SOCKET s) {
    return close(s);
}

/* ioctlsocket - map to fcntl for non-blocking mode */
/* Use Linux values for FIONBIO/FIONREAD if not already defined */
#ifndef FIONBIO
#define FIONBIO     0x5421
#endif
#ifndef FIONREAD
#define FIONREAD    0x541B
#endif

static inline int ioctlsocket(SOCKET s, long cmd, unsigned long* argp) {
    if (cmd == FIONBIO) {
        int flags = fcntl(s, F_GETFL, 0);
        if (flags < 0) return SOCKET_ERROR;
        if (*argp) {
            flags |= O_NONBLOCK;
        } else {
            flags &= ~O_NONBLOCK;
        }
        return fcntl(s, F_SETFL, flags) < 0 ? SOCKET_ERROR : 0;
    } else if (cmd == FIONREAD) {
        int bytes;
        if (ioctl(s, FIONREAD, &bytes) < 0) return SOCKET_ERROR;
        *argp = bytes;
        return 0;
    }
    return SOCKET_ERROR;
}

/* MAKEWORD macro for WSAStartup version */
#ifndef MAKEWORD
#define MAKEWORD(a, b)  ((WORD)(((BYTE)(a)) | ((WORD)((BYTE)(b))) << 8))
#endif

/* Socket option levels and options */
#ifndef SOL_SOCKET
#define SOL_SOCKET      1
#endif

#ifndef SO_REUSEADDR
#define SO_REUSEADDR    2
#define SO_KEEPALIVE    9
#define SO_BROADCAST    6
#define SO_LINGER       13
#define SO_RCVBUF       8
#define SO_SNDBUF       7
#define SO_RCVTIMEO     20
#define SO_SNDTIMEO     21
#endif

/* TCP options */
#ifndef TCP_NODELAY
#define TCP_NODELAY     1
#endif

/* hostent structure is the same on Windows and Linux */
/* gethostbyname, gethostbyaddr work the same way */

/* FD_SETSIZE and fd_set may differ */
#ifndef FD_SETSIZE
#define FD_SETSIZE      64
#endif

#ifdef __cplusplus
}
#endif

#endif /* !FF_COMPAT_WINSOCK2_H */

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINSOCK_H */
