/*
 * FreeFalcon Linux Port - cguid.h compatibility
 *
 * Windows GUID constant definitions stub.
 */

#ifndef FF_COMPAT_CGUID_H
#define FF_COMPAT_CGUID_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* GUID_NULL is defined in compat_types.h */

/* IID_IUnknown */
static const IID IID_IUnknown = {0x00000000, 0x0000, 0x0000, {0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};

/* IID_IClassFactory */
static const IID IID_IClassFactory = {0x00000001, 0x0000, 0x0000, {0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_CGUID_H */
