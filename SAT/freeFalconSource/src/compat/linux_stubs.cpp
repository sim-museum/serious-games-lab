/*
 * FreeFalcon Linux Port - C++ Stub implementations
 */

#ifdef FF_LINUX

#include <cstdio>
#include <cstddef>
#include <fcntl.h>
#include <unistd.h>

/* Forward declarations */
class C_Base;

/* ============================================================
 * IsBad pointer checking - C++ versions
 * ============================================================ */

int F4IsBadReadPtr(const void* lp, unsigned int ucb) {
    (void)lp; (void)ucb;
    return 0;
}

int F4IsBadWritePtr(void* lp, unsigned int ucb) {
    (void)lp; (void)ucb;
    return 0;
}

int F4IsBadCodePtr(void* lpfn) {
    (void)lpfn;
    return 0;
}

/* ============================================================
 * Message system - TheEventStrings, FalconMsgIdStr etc. are defined
 * in falclib/mesgstr.cpp - do NOT define stubs here
 * ============================================================ */

/* ============================================================
 * Font tool stubs - these are UI callbacks that only exist in
 * Windows tool builds
 * ============================================================ */

void InitFontTool() {}

void ChooseFontCB(long, short, C_Base*) {}
void CreateFontCB(long, short, C_Base*) {}
void CreateTheFontCB(long, short, C_Base*) {}
void SaveFontCB(long, short, C_Base*) {}
void IncreaseLead(long, short, C_Base*) {}
void DecreaseLead(long, short, C_Base*) {}
void IncreaseTrail(long, short, C_Base*) {}
void DecreaseTrail(long, short, C_Base*) {}
void IncreaseWidth(long, short, C_Base*) {}
void DecreaseWidth(long, short, C_Base*) {}
void IncreaseKern(long, short, C_Base*) {}
void DecreaseKern(long, short, C_Base*) {}

/* ============================================================
 * Transmit function - for radio communication
 * ============================================================ */

void Transmit(int code) {
    (void)code;
}

/* ============================================================
 * Voice system stubs - C++ linkage
 * ============================================================ */

void StopVoice() {}
void startupvoice(char* name) { (void)name; }
void RefreshVoiceFreqs() {}
void DirectVoiceSetVolume(int vol) { (void)vol; }

/* ============================================================
 * Campaign dialog stubs - these are Windows file dialog wrappers
 * from src/campaign/camptool/dialog.cpp (not included on Linux)
 * Note: These are DIFFERENT from the FILE* OpenCampFile() function
 * in campaign.cpp which handles actual file I/O
 * ============================================================ */

// Need HWND type from Windows compat header
typedef void* HWND;
typedef int BOOL;

BOOL OpenCampFile(HWND hWnd) { (void)hWnd; return 0; }
BOOL SaveCampFile(HWND hWnd, int mode) { (void)hWnd; (void)mode; return 0; }
BOOL SaveAsCampFile(HWND hWnd, int mode) { (void)hWnd; (void)mode; return 0; }

/* ============================================================
 * Cheat/debug stubs - C++ linkage
 * ============================================================ */

void FistOfGod(void* hwnd, unsigned int msg, unsigned long wp, long lp) {
    (void)hwnd; (void)msg; (void)wp; (void)lp;
}
void CheatTool(void* hwnd, unsigned int msg, unsigned long wp, long lp) {
    (void)hwnd; (void)msg; (void)wp; (void)lp;
}
int CheckForCheatFlight(unsigned long flight) { (void)flight; return 0; }

/* ============================================================
 * Debug/spinner stubs - C++ linkage
 * ============================================================ */

void set_spinner1(int value) { (void)value; }
void set_spinner3(int value) { (void)value; }

/* ============================================================
 * Case-insensitive file opening for Linux
 * Windows games use mixed case filenames which don't work on
 * case-sensitive Linux filesystems.
 * ============================================================ */

#include <cstring>
#include <cctype>
#include <dirent.h>
#include <sys/stat.h>

// Convert backslashes to forward slashes in place
static void normalize_path(char* path) {
    for (char* p = path; *p; p++) {
        if (*p == '\\') *p = '/';
    }
}

// Helper: Find a directory entry case-insensitively
// Returns true if found and copies the actual name to result
static bool find_entry_nocase(const char* dirPath, const char* name, char* result, size_t resultSize) {
    DIR* dir = opendir(dirPath[0] ? dirPath : ".");
    if (!dir) return false;

    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        if (strcasecmp(entry->d_name, name) == 0) {
            strncpy(result, entry->d_name, resultSize - 1);
            result[resultSize - 1] = '\0';
            closedir(dir);
            return true;
        }
    }
    closedir(dir);
    return false;
}

// Case-insensitive file open that handles the full path
extern "C" FILE* fopen_nocase(const char* filepath, const char* mode) {
    if (!filepath || !mode) return nullptr;

    // Make a mutable copy and normalize slashes
    char path[1024];
    strncpy(path, filepath, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
    normalize_path(path);

    // Try exact path first
    FILE* fp = fopen(path, mode);
    if (fp) return fp;

    // Build the path component by component with case-insensitive matching
    char resolvedPath[1024] = "";
    char* pathCopy = path;

    // Handle absolute paths
    if (path[0] == '/') {
        resolvedPath[0] = '/';
        resolvedPath[1] = '\0';
        pathCopy++;
    }

    char* component = strtok(pathCopy, "/");
    while (component) {
        char actualName[256];

        if (find_entry_nocase(resolvedPath[0] ? resolvedPath : ".", component, actualName, sizeof(actualName))) {
            // Found case-insensitive match
            if (resolvedPath[0] && resolvedPath[strlen(resolvedPath)-1] != '/') {
                strcat(resolvedPath, "/");
            }
            strcat(resolvedPath, actualName);
        } else {
            // Not found - try appending as-is (might fail at open)
            if (resolvedPath[0] && resolvedPath[strlen(resolvedPath)-1] != '/') {
                strcat(resolvedPath, "/");
            }
            strcat(resolvedPath, component);
        }

        component = strtok(nullptr, "/");
    }

    // Try to open the resolved path
    fp = fopen(resolvedPath, mode);
    return fp;
}

// Case-insensitive file open that returns a file descriptor (for CreateFile)
extern "C" int open_nocase(const char* filepath, int flags, int mode) {
    if (!filepath) return -1;

    // Make a mutable copy and normalize slashes
    char path[1024];
    strncpy(path, filepath, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
    normalize_path(path);

    // fprintf(stderr, "[open_nocase] Trying: %s\n", path);

    // Try exact path first
    int fd = open(path, flags, mode);
    if (fd != -1) {
        // fprintf(stderr, "[open_nocase] Exact match succeeded: fd=%d\n", fd);
        return fd;
    }

    // Build the path component by component with case-insensitive matching
    char resolvedPath[1024] = "";
    char* pathCopy = path;

    // Handle absolute paths
    if (path[0] == '/') {
        resolvedPath[0] = '/';
        resolvedPath[1] = '\0';
        pathCopy++;
    }

    // strtok modifies the string, so we need to work on a copy
    char* component = strtok(pathCopy, "/");
    while (component) {
        char actualName[256];

        if (find_entry_nocase(resolvedPath[0] ? resolvedPath : ".", component, actualName, sizeof(actualName))) {
            // Found case-insensitive match
            if (resolvedPath[0] && resolvedPath[strlen(resolvedPath)-1] != '/') {
                strcat(resolvedPath, "/");
            }
            strcat(resolvedPath, actualName);
        } else {
            // Not found - try appending as-is (might fail at open)
            if (resolvedPath[0] && resolvedPath[strlen(resolvedPath)-1] != '/') {
                strcat(resolvedPath, "/");
            }
            strcat(resolvedPath, component);
        }

        component = strtok(nullptr, "/");
    }

    // Try to open the resolved path
    // fprintf(stderr, "[open_nocase] Trying resolved: %s\n", resolvedPath);
    fd = open(resolvedPath, flags, mode);
    if (fd == -1) {
        // fprintf(stderr, "[open_nocase] FAILED both paths for: %s\n", filepath);
    } else {
        // fprintf(stderr, "[open_nocase] Resolved match succeeded: fd=%d\n", fd);
    }
    return fd;
}

#endif /* FF_LINUX */
