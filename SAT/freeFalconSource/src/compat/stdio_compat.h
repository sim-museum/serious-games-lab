/*
 * FreeFalcon Linux Port - STDIO compatibility
 *
 * Windows-specific FILE structure member access compatibility.
 * NOTE: These are stubs - the actual functionality needs reimplementation.
 */

#ifndef FF_COMPAT_STDIO_H
#define FF_COMPAT_STDIO_H

#ifdef FF_LINUX

#include <stdio.h>

/* Windows FILE structure flags */
#define _IOREAD         0x0001
#define _IOWRT          0x0002
#define _IOMYBUF        0x0008
#define _IOEOF          0x0010
#define _IOERR          0x0020
#define _IOSTRG         0x0040
#define _IORW           0x0080

/* Custom flags for resource manager */
#define _IOARCHIVE      0x0100
#define _IOLOOSE        0x0200

/*
 * On Linux/glibc, we can't directly access FILE internals.
 * These macros provide compatibility but may not work correctly.
 * The resource manager will need proper reimplementation.
 */

/* MSVC internal lock functions - stubs */
#define _freebuf(f)         ((void)0)
#define _fseek_lk(f,o,w)    fseek(f,o,w)
#define _lseek_lk(fd,o,w)   lseek(fd,o,w)
#define _read_lk(fd,b,n)    read(fd,b,n)

#ifdef __cplusplus
extern "C" {
#endif

/* Case-insensitive file operations for Linux */
FILE* fopen_nocase(const char* filepath, const char* mode);
int open_nocase(const char* filepath, int flags, int mode);

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_STDIO_H */
