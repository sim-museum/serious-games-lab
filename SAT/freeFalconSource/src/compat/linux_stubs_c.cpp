/*
 * FreeFalcon Linux Port - C-callable Stub implementations
 * These functions have C linkage so they can be called from C code.
 */

#ifdef FF_LINUX

#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>

extern "C" {

/* IsBad pointer checking functions - C versions with C linkage */
int F4IsBadReadPtrC(const void* lp, unsigned int ucb) {
    (void)lp; (void)ucb;
    return 0;
}

int F4IsBadCodePtrC(void* lpfn) {
    (void)lpfn;
    return 0;
}

int F4IsBadWritePtrC(void* lp, unsigned int ucb) {
    (void)lp; (void)ucb;
    return 0;
}

/* MonoPrint - Debug output */
void MonoPrint(const char* format, ...) {
#ifdef DEBUG
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
#else
    (void)format;
#endif
}

void MonoLocate(unsigned char x, unsigned char y) {
    (void)x; (void)y;
}

void MonoCls(void) {}

void MonoColor(unsigned char attribute) {
    (void)attribute;
}

/* SearchPath - Windows file search function */
unsigned long SearchPath(
    const char* lpPath,
    const char* lpFileName,
    const char* lpExtension,
    unsigned long nBufferLength,
    char* lpBuffer,
    char** lpFilePart
) {
    char fullPath[1024];
    (void)lpExtension;
    (void)lpFilePart;

    if (!lpFileName || !lpBuffer || nBufferLength == 0) {
        return 0;
    }

    if (lpPath && lpPath[0]) {
        snprintf(fullPath, sizeof(fullPath), "%s/%s", lpPath, lpFileName);
        if (access(fullPath, F_OK) == 0) {
            strncpy(lpBuffer, fullPath, nBufferLength - 1);
            lpBuffer[nBufferLength - 1] = '\0';
            return strlen(lpBuffer);
        }
    }

    if (access(lpFileName, F_OK) == 0) {
        strncpy(lpBuffer, lpFileName, nBufferLength - 1);
        lpBuffer[nBufferLength - 1] = '\0';
        return strlen(lpBuffer);
    }

    return 0;
}

/* LZSS compression/decompression - implemented in utils/lzss.cpp */
/* Stubs removed - using real implementation */

/* Radix sort stubs */
void RadixRelink(void* base, void* link, int count) {
    (void)base; (void)link; (void)count;
}

void RadixRRelink(void* base, void* link, int count) {
    (void)base; (void)link; (void)count;
}

/* Debug/spinner stubs */
void InitDebug(int level) { (void)level; }
int stoppingvoice = 0;

/* Movie system stubs */
int movieOpen(const char* filename) { (void)filename; return 0; }
void movieStart(void) {}
void movieClose(void) {}
int movieIsPlaying(void) { return 0; }
void movieInit(void) {}
void movieUnInit(void) {}

int gDumping = 0;

/* DirectPlay stubs */
void* g_pDPServer = 0;
void* g_pDPClient = 0;
char OVERRIDE_GUID[40] = {0};

/* DirectInput data format stubs */
typedef struct { int unused; } DIDATAFORMAT;
DIDATAFORMAT c_dfDIMouse = {0};
DIDATAFORMAT c_dfDIKeyboard = {0};
DIDATAFORMAT c_dfDIJoystick = {0};

} // extern "C"

#endif /* FF_LINUX */
