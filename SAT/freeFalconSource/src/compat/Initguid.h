/*
 * FreeFalcon Linux Port - initguid.h compatibility
 *
 * This header triggers GUID instantiation.
 * On Windows, including this before other headers causes GUID
 * variables to be defined rather than just declared.
 */

#ifndef FF_COMPAT_INITGUID_H
#define FF_COMPAT_INITGUID_H

#ifdef FF_LINUX

/* DEFINE_GUID macro - defines a GUID variable */
#ifdef DEFINE_GUID
#undef DEFINE_GUID
#endif

#ifdef INITGUID
#define DEFINE_GUID(name, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8) \
    const GUID name = { l, w1, w2, { b1, b2, b3, b4, b5, b6, b7, b8 } }
#else
#define DEFINE_GUID(name, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8) \
    extern const GUID name
#endif

/* Set flag to instantiate GUIDs */
#define INITGUID

#endif /* FF_LINUX */
#endif /* FF_COMPAT_INITGUID_H */
