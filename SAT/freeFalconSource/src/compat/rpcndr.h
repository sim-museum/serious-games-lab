/*
 * FreeFalcon Linux Port - rpcndr.h compatibility stub
 *
 * Windows RPC NDR (Network Data Representation) headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_RPCNDR_H
#define FF_COMPAT_RPCNDR_H

#ifdef FF_LINUX

#include <windows.h>

/* NDR version - set to current */
#define __RPCNDR_H_VERSION__ 500

/* Hyper (64-bit int) type */
typedef long long hyper;
typedef unsigned long long uhyper;

/* Wire types */
typedef unsigned char byte;
typedef byte cs_byte;

/* Handle types */
typedef void* RPC_BINDING_HANDLE;
typedef RPC_BINDING_HANDLE handle_t;

/* NDR context handle */
typedef void* NDR_CCONTEXT;

/* Error status type */
typedef unsigned long error_status_t;

/* Basic NDR types - used by MIDL compiler output */
typedef unsigned char boolean;

/* MIDL memory functions */
static inline void* MIDL_user_allocate(size_t size) { return malloc(size); }
static inline void MIDL_user_free(void* ptr) { free(ptr); }

/* NDR helper macros */
#define __RPC_FAR
#define __RPC_UNIQUE

/* Stub descriptor types */
typedef struct _MIDL_STUB_MESSAGE MIDL_STUB_MESSAGE;
typedef struct _MIDL_STUB_DESC MIDL_STUB_DESC;

/* Format string types */
typedef unsigned char PFORMAT_STRING;

/* Pointer types */
#ifndef __RPCNDR_H__
#define __RPCNDR_H__
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_RPCNDR_H */
