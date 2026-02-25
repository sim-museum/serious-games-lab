/*
 * FreeFalcon Linux Port - exit.h compatibility
 *
 * Debug printing macros
 */

#ifndef FF_COMPAT_EXIT_H
#define FF_COMPAT_EXIT_H

#ifdef FF_LINUX

/* BOF_PRINT - debug print macro (disabled for release builds) */
#ifdef _DEBUG
#include <stdio.h>
#define BOF_PRINT(x) printf x
#else
#define BOF_PRINT(x)
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_EXIT_H */
