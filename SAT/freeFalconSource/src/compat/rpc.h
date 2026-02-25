/*
 * FreeFalcon Linux Port - rpc.h compatibility stub
 *
 * Windows RPC (Remote Procedure Call) headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_RPC_H
#define FF_COMPAT_RPC_H

#ifdef FF_LINUX

#include <windows.h>

/* RPC calling conventions */
#define __RPC_FAR
#define __RPC_API
#define __RPC_USER
#define __RPC_STUB

#define RPC_IF_HANDLE void*
#define RPC_BINDING_HANDLE void*

/* MIDL version */
#define __MIDL_PASS

/* RPC status codes */
typedef long RPC_STATUS;
#define RPC_S_OK 0

/* Stub helpers */
#define DECLSPEC_UUID(x)
#define MIDL_INTERFACE(x) struct

/* Interface keyword for C++ */
#ifndef interface
#define interface struct
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_RPC_H */
