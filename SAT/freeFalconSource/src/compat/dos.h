/*
 * FreeFalcon Linux Port - dos.h compatibility
 *
 * MS-DOS header stub. Most DOS functions are not applicable on Linux.
 */

#ifndef FF_COMPAT_DOS_H
#define FF_COMPAT_DOS_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* DOS-specific defines - mostly no-ops on Linux */

/* DOS memory allocation limits - not applicable */
#define _MAX_PATH   260
#define _MAX_DRIVE  3
#define _MAX_DIR    256
#define _MAX_FNAME  256
#define _MAX_EXT    256

/* DOS date/time structures */
struct _dosdate_t {
    unsigned char day;
    unsigned char month;
    unsigned int year;
    unsigned char dayofweek;
};

struct _dostime_t {
    unsigned char hour;
    unsigned char minute;
    unsigned char second;
    unsigned char hsecond;
};

/* DOS path splitting functions - use our implementations */
static inline void _splitpath(
    const char* path,
    char* drive,
    char* dir,
    char* fname,
    char* ext)
{
    if (drive) drive[0] = '\0';  /* No drive letters on Linux */

    if (!path) {
        if (dir) dir[0] = '\0';
        if (fname) fname[0] = '\0';
        if (ext) ext[0] = '\0';
        return;
    }

    const char* lastslash = strrchr(path, '/');
    const char* lastdot;

    /* Extract directory */
    if (dir) {
        if (lastslash) {
            size_t len = lastslash - path + 1;
            strncpy(dir, path, len);
            dir[len] = '\0';
        } else {
            dir[0] = '\0';
        }
    }

    /* Get filename start */
    const char* fnamestart = lastslash ? lastslash + 1 : path;

    /* Find extension */
    lastdot = strrchr(fnamestart, '.');

    /* Extract filename */
    if (fname) {
        if (lastdot) {
            size_t len = lastdot - fnamestart;
            strncpy(fname, fnamestart, len);
            fname[len] = '\0';
        } else {
            strcpy(fname, fnamestart);
        }
    }

    /* Extract extension */
    if (ext) {
        if (lastdot) {
            strcpy(ext, lastdot);
        } else {
            ext[0] = '\0';
        }
    }
}

static inline void _makepath(
    char* path,
    const char* drive,
    const char* dir,
    const char* fname,
    const char* ext)
{
    (void)drive;  /* No drive letters on Linux */

    path[0] = '\0';
    if (dir && dir[0]) {
        strcpy(path, dir);
    }
    if (fname && fname[0]) {
        strcat(path, fname);
    }
    if (ext && ext[0]) {
        if (ext[0] != '.') strcat(path, ".");
        strcat(path, ext);
    }
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DOS_H */
