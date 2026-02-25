/*
 * FreeFalcon Linux Port - io.h compatibility
 *
 * Windows low-level I/O functions replacement
 */

#ifndef FF_COMPAT_IO_H
#define FF_COMPAT_IO_H

#ifdef FF_LINUX

#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>

#ifdef __cplusplus
extern "C" {
#endif

/* File access modes */
#ifndef _A_NORMAL
#define _A_NORMAL   0x00
#define _A_RDONLY   0x01
#define _A_HIDDEN   0x02
#define _A_SYSTEM   0x04
#define _A_SUBDIR   0x10
#define _A_ARCH     0x20
#endif

/* File open modes */
#ifndef _O_RDONLY
#define _O_RDONLY   O_RDONLY
#define _O_WRONLY   O_WRONLY
#define _O_RDWR     O_RDWR
#define _O_APPEND   O_APPEND
#define _O_CREAT    O_CREAT
#define _O_TRUNC    O_TRUNC
#define _O_EXCL     O_EXCL
#define _O_BINARY   0           /* No binary mode on Linux */
#define _O_TEXT     0           /* No text mode on Linux */
#define _O_SEQUENTIAL 0         /* Sequential access hint (no-op on Linux) */
#define _O_RANDOM   0           /* Random access hint (no-op on Linux) */
#endif

/* Seek origins */
#ifndef SEEK_SET
#define SEEK_SET    0
#define SEEK_CUR    1
#define SEEK_END    2
#endif

/* Function mappings */
#define _open       open
#define _close      close
#define _read       read
#define _write      write
#define _lseek      lseek
#define _tell(fd)   lseek(fd, 0, SEEK_CUR)
#define tell(fd)    lseek(fd, 0, SEEK_CUR)
#define _filelength(fd) ({ \
    off_t cur = lseek(fd, 0, SEEK_CUR); \
    off_t end = lseek(fd, 0, SEEK_END); \
    lseek(fd, cur, SEEK_SET); \
    end; \
})
#define filelength  _filelength
#define _access     access
#define _chmod      chmod
#define _unlink     unlink
#define _dup        dup
#define _dup2       dup2
#define _isatty     isatty
#define _fileno     fileno
#define _setmode(fd, mode)  (0)  /* No-op on Linux */

/* eof() function - checks if at end of file */
static inline int eof(int fd) {
    off_t cur = lseek(fd, 0, SEEK_CUR);
    off_t end = lseek(fd, 0, SEEK_END);
    lseek(fd, cur, SEEK_SET);
    return (cur >= end) ? 1 : 0;
}
#define _eof        eof

/* File find structures (simplified) */
struct _finddata_t {
    unsigned attrib;
    time_t time_create;
    time_t time_access;
    time_t time_write;
    unsigned long size;
    char name[260];
};

typedef long intptr_t_find;

/* File find functions - stub implementations */
static inline intptr_t_find _findfirst(const char *filespec, struct _finddata_t *fileinfo) {
    (void)filespec; (void)fileinfo;
    return -1; /* Not implemented - use dirent.h for directory operations */
}

static inline int _findnext(intptr_t_find handle, struct _finddata_t *fileinfo) {
    (void)handle; (void)fileinfo;
    return -1;
}

static inline int _findclose(intptr_t_find handle) {
    (void)handle;
    return 0;
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_IO_H */
