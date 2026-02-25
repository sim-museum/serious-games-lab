/*
 * FreeFalcon Linux Port - direct.h compatibility
 *
 * Windows directory operations replacement
 */

#ifndef FF_COMPAT_DIRECT_H
#define FF_COMPAT_DIRECT_H

#ifdef FF_LINUX

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Directory operations */
#define _mkdir(path)        mkdir(path, 0755)
#define _rmdir(path)        rmdir(path)
#define _chdir(path)        chdir(path)
#define _getcwd(buf, size)  getcwd(buf, size)

/* _getdrive - returns current drive (1=A, 2=B, etc.) - always 3 (C:) on Linux */
static inline int _getdrive(void) {
    return 3;
}

/* _chdrive - change drive - no-op on Linux */
static inline int _chdrive(int drive) {
    (void)drive;
    return 0;
}

/* _getdcwd - get current directory on specified drive */
static inline char* _getdcwd(int drive, char* buffer, int maxlen) {
    (void)drive;
    return getcwd(buffer, maxlen);
}

/* _splitpath / _makepath for path manipulation */
static inline void _splitpath(const char* path, char* drive, char* dir, char* fname, char* ext) {
    if (drive) drive[0] = '\0';
    if (dir) dir[0] = '\0';
    if (fname) fname[0] = '\0';
    if (ext) ext[0] = '\0';

    if (!path) return;

    const char* lastSlash = strrchr(path, '/');
    const char* lastDot = strrchr(path, '.');

    if (dir && lastSlash) {
        size_t len = lastSlash - path + 1;
        strncpy(dir, path, len);
        dir[len] = '\0';
    }

    const char* filename = lastSlash ? lastSlash + 1 : path;

    if (lastDot && lastDot > filename) {
        if (fname) {
            size_t len = lastDot - filename;
            strncpy(fname, filename, len);
            fname[len] = '\0';
        }
        if (ext) {
            strcpy(ext, lastDot);
        }
    } else {
        if (fname) strcpy(fname, filename);
    }
}

static inline void _makepath(char* path, const char* drive, const char* dir, const char* fname, const char* ext) {
    path[0] = '\0';
    (void)drive; /* Ignored on Linux */

    if (dir && dir[0]) {
        strcat(path, dir);
        size_t len = strlen(path);
        if (len > 0 && path[len-1] != '/') {
            strcat(path, "/");
        }
    }

    if (fname) strcat(path, fname);
    if (ext && ext[0]) {
        if (ext[0] != '.') strcat(path, ".");
        strcat(path, ext);
    }
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DIRECT_H */
