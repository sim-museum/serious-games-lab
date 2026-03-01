// FFViper Linux main entry point
// Creates SDL2 window, OpenGL context, and initializes the game

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <time.h>
#include <fenv.h>
#include <signal.h>
#include <execinfo.h>
#include <mutex>
#include <queue>
#include <vector>

// Linux port debug configuration
#include "ff_linux_debug.h"

// SDL2
#include <SDL2/SDL.h>

// OpenGL
#include <GL/glew.h>
#include <GL/gl.h>

// OpenAL
#include <AL/al.h>
#include <AL/alc.h>

// FreeFalcon core headers - minimal set for initial startup
#include "falclib.h"
#include "f4find.h"
#include "f4vu.h"
#include "classtbl.h"
#include "camplib.h"
#include "threadmgr.h"
#include "sim/include/simloop.h"
#include "codelib/resources/reslib/src/resmgr.h"
#include "theaterdef.h"
#include "campaign.h"
#include "campaign/include/cmpclass.h"  // For TheCampaign
#include "falcsess.h"                     // For FalconLocalSession
#include "dispcfg.h"
#include "playerop.h"
#include "falclib/include/dispopts.h"
#include "rules.h"
#include "fsound.h"
#include "simdrive.h"
#include "graphics/include/drawparticlesys.h"
#include "graphics/include/timemgr.h"
#include "graphics/include/setup.h"
#include "graphics/include/renderow.h"
#include "graphics/include/drawbsp.h"
#include "sim/include/otwdrive.h"

// D3D/OpenGL rendering
#include "d3d.h"
#include "ddraw.h"
#include "graphics/dxengine/dxengine.h"
#include "graphics/include/tex.h"
#include "graphics/include/context.h"
#include "graphics/include/device.h"

// UI system (for gMainHandler)
#include "ui95/chandler.h"
#include "ui/include/falcuser.h"
#include "ui/include/uicomms.h"  // FF_LINUX: For gCommsMgr

// Simulation input (for IO structure and joystick data)
#include "sim/include/simio.h"
#include "sim/include/sinput.h"
#include "sim/include/inpfunc.h"  // FF_LINUX: For LoadFunctionTables()

// Campaign / instant action headers
#include "campaign/include/iaction.h"
#include "campaign/include/dogfight.h"
#include "campaign/include/weather.h"  // FF_LINUX: For WeatherClass / realWeather

// External initialization functions
extern void LoadTheaterList();
extern void FF_PresentPrimarySurface();  // Present DirectDraw primary surface via OpenGL
extern void LoadTrails();
extern int UI_Startup();
extern void UI_Cleanup();

// External globals from the UI/game systems
extern C_Handler *gMainHandler;
extern int doUI;
extern void ReadCampAIInputs(char* name);
extern int LoadTactics(char *name);
extern void InitVU();
extern void BuildAscii();

// Campaign/mission lifecycle externs
extern void EndUI(void);
extern void CampaignJoinSuccess(void);
extern void CampaignJoinFail(void);
extern void ShutdownCampaign(void);
extern void CampaignPreloadSuccess(int remote);
extern void CampaignAutoSave(FalconGameType type);
extern char gUI_CampaignFile[];
extern void UI_CommsErrorMessage(WORD error);
extern int gameCompressionRatio;
extern DogfightClass SimDogfight;
extern void StartCampaignGame(int local, int game_type);
extern void tactical_restart_mission(void);

// Communications initialization (needed for CAPI function pointers)
typedef struct WSAData {
    unsigned short wVersion;
    unsigned short wHighVersion;
    char szDescription[257];
    char szSystemStatus[129];
} WSADATA;
extern "C" int initialize_windows_sockets(WSADATA *wsaData);

// Default data directory - can be overridden with -d flag or FF_DATA_DIR env var
// Use -d <path> to point at your FreeFalcon6 game data directory
#define DEFAULT_DATA_DIR nullptr

// Window settings - must match UI resolution (1024x768 for HiRes UI)
#define WINDOW_WIDTH 1024
#define WINDOW_HEIGHT 768
int g_nWindowWidth = WINDOW_WIDTH;
int g_nWindowHeight = WINDOW_HEIGHT;
#define WINDOW_TITLE "Free Falcon 6 Linux Port"

// External globals from falclib
extern char FalconDataDirectory[];
extern char FalconCampaignSaveDirectory[];
extern char FalconCampUserSaveDirectory[];
extern char FalconTerrainDataDir[];
extern char FalconMiscTexDataDir[];
extern char FalconPictureDirectory[];
extern char FalconObjectDataDir[];
extern char Falcon3DDataDir[];

// Sound-related directories (defined in winmain.cpp, we just reference them)
extern char FalconSoundThrDirectory[];
extern char FalconUISoundDirectory[];
extern char FalconCockpitThrDirectory[];
extern char FalconZipsThrDirectory[];
extern char FalconTacrefThrDirectory[];
extern char FalconSplashThrDirectory[];
extern char FalconMovieDirectory[];
extern char FalconMovieMode[];
extern char FalconUIArtDirectory[];
extern char FalconUIArtThrDirectory[];

// Global SDL objects - these replace Windows HWND etc.
SDL_Window* g_SDLWindow = nullptr;
SDL_GLContext g_GLContext = nullptr;

// FF_LINUX: ShiAssert control globals
// winmain.cpp defines these under #ifdef DEBUG, but CMake only defines _DEBUG (with underscore)
// So we always need to define them here for Linux builds
// shiHardCrashOn MUST be 0 to prevent crash on assertions
int shiAssertsOn = 1;
int shiWarningsOn = 1;
int shiHardCrashOn = 0;

// OpenGL context transfer for multi-threaded rendering
// The sim thread needs the GL context for OTWDriver.Cycle(), but the main thread
// owns it during UI mode. These functions transfer ownership.
static std::mutex g_glContextMutex;
bool g_simOwnsGLContext = false;  // Non-static: accessed from simloop.cpp via extern

// Release GL context from current thread (call before another thread acquires it)
void FF_ReleaseGLContext() {
    std::lock_guard<std::mutex> lock(g_glContextMutex);
    if (g_SDLWindow) {
        SDL_GL_MakeCurrent(g_SDLWindow, NULL);
    }
}

// Acquire GL context on current thread
void FF_AcquireGLContext() {
    std::lock_guard<std::mutex> lock(g_glContextMutex);
    if (g_SDLWindow && g_GLContext) {
        SDL_GL_MakeCurrent(g_SDLWindow, g_GLContext);
    }
}

// Called by sim thread before it starts rendering
void FF_SimThreadAcquireGL() {
    fprintf(stderr, "[GL] FF_SimThreadAcquireGL() ENTER\n");
    fflush(stderr);
    FF_AcquireGLContext();
    g_simOwnsGLContext = true;
    fprintf(stderr, "[GL] Sim thread acquired GL context, g_simOwnsGLContext=true\n");
    fflush(stderr);
}

// Called by sim thread when it's done rendering
void FF_SimThreadReleaseGL() {
    fprintf(stderr, "[GL] FF_SimThreadReleaseGL() ENTER\n");
    fflush(stderr);
    g_simOwnsGLContext = false;
    FF_ReleaseGLContext();
    fprintf(stderr, "[GL] Sim thread released GL context, g_simOwnsGLContext=false\n");
    fflush(stderr);
}

// Swap buffers - callable from any thread that owns the GL context
void FF_SwapBuffers() {
    static int swapCount = 0;
    swapCount++;

    if (g_SDLWindow && g_GLContext) {
        // Make sure the GL context is current on this thread before swapping
        SDL_GLContext current = SDL_GL_GetCurrentContext();
        if (current != g_GLContext) {
            SDL_GL_MakeCurrent(g_SDLWindow, g_GLContext);
        }

        // FF_LINUX: Ensure we're presenting from the default framebuffer, not an FBO
        glBindFramebuffer(GL_FRAMEBUFFER, 0);

        // Capture screenshot of the GL framebuffer
        // Wait until frame 200 to ensure lighting/sky is fully initialized
        if (swapCount == 200 || swapCount == 600) {
            int w = 0, h = 0;
            SDL_GL_GetDrawableSize(g_SDLWindow, &w, &h);
            if (w > 0 && h > 0) {
                unsigned char* pixels = new unsigned char[w * h * 3];
                // Read from back buffer (where rendering goes)
                glReadBuffer(GL_BACK);
                glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, pixels);
                // Save as BMP
                FILE* f = fopen("/tmp/screenshot_sim.bmp", "wb");
                if (f) {
                    int rowSize = (w * 3 + 3) & ~3;
                    int imageSize = rowSize * h;
                    // BMP header (14 bytes)
                    uint16_t bfType = 0x4D42;
                    uint32_t bfSize = 54 + imageSize;
                    uint16_t bfReserved = 0;
                    uint32_t bfOffBits = 54;
                    fwrite(&bfType, 2, 1, f);
                    fwrite(&bfSize, 4, 1, f);
                    fwrite(&bfReserved, 2, 1, f);
                    fwrite(&bfReserved, 2, 1, f);
                    fwrite(&bfOffBits, 4, 1, f);
                    // DIB header (40 bytes)
                    uint32_t biSize = 40;
                    int32_t biWidth = w, biHeight = h;
                    uint16_t biPlanes = 1, biBitCount = 24;
                    uint32_t biCompression = 0, biSizeImage = imageSize;
                    int32_t biXPPM = 2835, biYPPM = 2835;
                    uint32_t biClrUsed = 0, biClrImportant = 0;
                    fwrite(&biSize, 4, 1, f);
                    fwrite(&biWidth, 4, 1, f);
                    fwrite(&biHeight, 4, 1, f);
                    fwrite(&biPlanes, 2, 1, f);
                    fwrite(&biBitCount, 2, 1, f);
                    fwrite(&biCompression, 4, 1, f);
                    fwrite(&biSizeImage, 4, 1, f);
                    fwrite(&biXPPM, 4, 1, f);
                    fwrite(&biYPPM, 4, 1, f);
                    fwrite(&biClrUsed, 4, 1, f);
                    fwrite(&biClrImportant, 4, 1, f);
                    // Pixel data - glReadPixels gives us bottom-up RGB, BMP wants bottom-up BGR
                    unsigned char* row = new unsigned char[rowSize];
                    for (int y = 0; y < h; y++) {
                        memset(row, 0, rowSize);
                        for (int x = 0; x < w; x++) {
                            unsigned char* src = pixels + (y * w + x) * 3;
                            row[x * 3 + 0] = src[2]; // B
                            row[x * 3 + 1] = src[1]; // G
                            row[x * 3 + 2] = src[0]; // R
                        }
                        fwrite(row, rowSize, 1, f);
                    }
                    delete[] row;
                    fclose(f);
                }
                delete[] pixels;
            }
        }

        // Present the frame
        SDL_GL_SwapWindow(g_SDLWindow);
    }
}

// OpenAL - global for DirectSound compatibility layer
ALCdevice* g_alDevice = nullptr;
ALCcontext* g_alContext = nullptr;

// D3D7 interfaces (OpenGL-backed)
static IDirect3D7* g_pD3D = nullptr;
static IDirect3DDevice7* g_pD3DDevice = nullptr;
static IDirectDraw7* g_pDD = nullptr;
static IDirectDrawSurface7* g_pRenderTarget = nullptr;
static DXContext* g_pDXContext = nullptr;
static bool g_graphicsInitialized = false;

// DXEngine global (declared in dxengine.h as extern)
bool g_Use_DX_Engine = false;

// Game state
static bool g_running = true;
static bool g_gameInitialized = false;
static bool g_autoTestInstantAction = false;  // TEST: Set by auto-launch code
bool g_testInstantActionFlag = false;  // Command-line flag for auto-testing
volatile int g_requestedPanel = -1;  // Set by main thread, read by sim thread for view testing
volatile int g_requestedViewMode = -1;  // Set by main thread, -1=none, 0=HUD, 1=cockpit, 2=chase, 3=orbit
volatile int g_screenshotRequest = 0;   // Set by main thread, read by sim thread to take screenshot
const char* g_screenshotFilename = "/tmp/ff_screenshot.bmp"; // Filename for next screenshot

// These globals are defined in ui/src/winmain.cpp - use extern
extern HWND mainAppWnd;
extern HWND mainMenuWnd;
extern HINSTANCE hInst;
extern const char* FREE_FALCON_BRAND;
extern const char* FREE_FALCON_PROJECT;
extern const char* FREE_FALCON_VERSION;

// Message queue for Windows-style message passing

struct GameMessage {
    UINT message;
    WPARAM wParam;
    LPARAM lParam;
};

static std::queue<GameMessage> g_messageQueue;
static std::mutex g_messageMutex;

// Post a message to the queue (like Windows PostMessage)
void PostGameMessage(UINT msg, WPARAM wParam, LPARAM lParam) {
    std::lock_guard<std::mutex> lock(g_messageMutex);
    g_messageQueue.push({msg, wParam, lParam});
}

// Process messages in the queue
bool ProcessGameMessages();

// Post a message without locking (for use inside ProcessGameMessages)
static std::vector<GameMessage> g_pendingMessages;

// =============================================================================
// SDL TO DIRECTINPUT SCANCODE TRANSLATION
// SDL scancodes differ from DirectInput DIK_* codes - build a translation table
// =============================================================================

// =============================================================================
// SDL KEYBOARD EVENT BUFFER FOR SIM INPUT
// The sim reads keyboard input via DirectInput's GetDeviceData() (sikeybd.cpp).
// On Linux, DirectInput is disabled. Instead, SDL keyboard events are buffered
// here and read by OnSimKeyboardInput() via FF_PopKeyEvents().
// =============================================================================
#include "dinput.h"  // For DIDEVICEOBJECTDATA

static std::mutex g_keyEventMutex;
static DIDEVICEOBJECTDATA g_keyEventBuf[64];
static int g_keyEventHead = 0;
static int g_keyEventTail = 0;
static unsigned char g_keyState[256] = {0};  // Current key state (0x80 = pressed)

// Push a keyboard event into the buffer (called from SDL event loop)
void FF_PushKeyEvent(int dikCode, bool isDown) {
    if (dikCode <= 0 || dikCode >= 256) return;
    std::lock_guard<std::mutex> lock(g_keyEventMutex);
    g_keyState[dikCode] = isDown ? 0x80 : 0x00;
    int next = (g_keyEventHead + 1) % 64;
    if (next == g_keyEventTail) return;  // Buffer full, drop event
    g_keyEventBuf[g_keyEventHead].dwOfs = (DWORD)dikCode;
    g_keyEventBuf[g_keyEventHead].dwData = isDown ? 0x80 : 0x00;
    g_keyEventBuf[g_keyEventHead].dwTimeStamp = GetTickCount();
    g_keyEventBuf[g_keyEventHead].dwSequence = 0;
    g_keyEventHead = next;
}

// Pop keyboard events from the buffer (called from sim thread's OnSimKeyboardInput)
int FF_PopKeyEvents(DIDEVICEOBJECTDATA* outBuf, int maxEvents) {
    std::lock_guard<std::mutex> lock(g_keyEventMutex);
    int count = 0;
    while (g_keyEventTail != g_keyEventHead && count < maxEvents) {
        outBuf[count] = g_keyEventBuf[g_keyEventTail];
        g_keyEventTail = (g_keyEventTail + 1) % 64;
        count++;
    }
    return count;
}

// Get current keyboard state (called from sim thread)
void FF_GetKeyState(unsigned char* outState, int size) {
    std::lock_guard<std::mutex> lock(g_keyEventMutex);
    int copySize = (size < 256) ? size : 256;
    memcpy(outState, g_keyState, copySize);
}

// =============================================================================
// SDL Mouse Event Buffer for Sim Input
// Similar to the keyboard buffer - SDL mouse events are pushed from the main
// thread and popped by the sim thread's OnSimMouseInput().
// =============================================================================
static std::mutex g_mouseEventMutex;
static DIDEVICEOBJECTDATA g_mouseEventBuf[128];
static int g_mouseEventHead = 0;
static int g_mouseEventTail = 0;

void FF_PushMouseEvent(DWORD dwOfs, DWORD dwData) {
    std::lock_guard<std::mutex> lock(g_mouseEventMutex);
    int next = (g_mouseEventHead + 1) % 128;
    if (next == g_mouseEventTail) return;  // Buffer full, drop event
    g_mouseEventBuf[g_mouseEventHead].dwOfs = dwOfs;
    g_mouseEventBuf[g_mouseEventHead].dwData = dwData;
    g_mouseEventBuf[g_mouseEventHead].dwTimeStamp = GetTickCount();
    g_mouseEventBuf[g_mouseEventHead].dwSequence = 0;
    g_mouseEventHead = next;
}

int FF_PopMouseEvents(DIDEVICEOBJECTDATA* outBuf, int maxEvents) {
    std::lock_guard<std::mutex> lock(g_mouseEventMutex);
    int count = 0;
    while (g_mouseEventTail != g_mouseEventHead && count < maxEvents) {
        outBuf[count] = g_mouseEventBuf[g_mouseEventTail];
        g_mouseEventTail = (g_mouseEventTail + 1) % 128;
        count++;
    }
    return count;
}

// SDL joystick globals
static SDL_Joystick* g_SDLJoystick = nullptr;
static int g_JoystickIndex = -1;
static int g_JoystickNumAxes = 0;
static int g_JoystickNumButtons = 0;
static int g_JoystickNumHats = 0;

// Axis value cache (raw SDL values)
static int16_t g_JoystickAxes[16] = {0};

// SDL scancode to DIK code translation table
static int SDL_to_DIK[SDL_NUM_SCANCODES] = {0};

// Initialize the SDL to DIK translation table
static void InitScancodeTranslation() {
    memset(SDL_to_DIK, 0, sizeof(SDL_to_DIK));

    // Escape and function keys
    SDL_to_DIK[SDL_SCANCODE_ESCAPE] = DIK_ESCAPE;
    SDL_to_DIK[SDL_SCANCODE_F1] = DIK_F1;
    SDL_to_DIK[SDL_SCANCODE_F2] = DIK_F2;
    SDL_to_DIK[SDL_SCANCODE_F3] = DIK_F3;
    SDL_to_DIK[SDL_SCANCODE_F4] = DIK_F4;
    SDL_to_DIK[SDL_SCANCODE_F5] = DIK_F5;
    SDL_to_DIK[SDL_SCANCODE_F6] = DIK_F6;
    SDL_to_DIK[SDL_SCANCODE_F7] = DIK_F7;
    SDL_to_DIK[SDL_SCANCODE_F8] = DIK_F8;
    SDL_to_DIK[SDL_SCANCODE_F9] = DIK_F9;
    SDL_to_DIK[SDL_SCANCODE_F10] = DIK_F10;
    SDL_to_DIK[SDL_SCANCODE_F11] = DIK_F11;
    SDL_to_DIK[SDL_SCANCODE_F12] = DIK_F12;

    // Number row
    SDL_to_DIK[SDL_SCANCODE_1] = DIK_1;
    SDL_to_DIK[SDL_SCANCODE_2] = DIK_2;
    SDL_to_DIK[SDL_SCANCODE_3] = DIK_3;
    SDL_to_DIK[SDL_SCANCODE_4] = DIK_4;
    SDL_to_DIK[SDL_SCANCODE_5] = DIK_5;
    SDL_to_DIK[SDL_SCANCODE_6] = DIK_6;
    SDL_to_DIK[SDL_SCANCODE_7] = DIK_7;
    SDL_to_DIK[SDL_SCANCODE_8] = DIK_8;
    SDL_to_DIK[SDL_SCANCODE_9] = DIK_9;
    SDL_to_DIK[SDL_SCANCODE_0] = DIK_0;
    SDL_to_DIK[SDL_SCANCODE_MINUS] = DIK_MINUS;
    SDL_to_DIK[SDL_SCANCODE_EQUALS] = DIK_EQUALS;
    SDL_to_DIK[SDL_SCANCODE_BACKSPACE] = DIK_BACK;

    // Top row letters
    SDL_to_DIK[SDL_SCANCODE_TAB] = DIK_TAB;
    SDL_to_DIK[SDL_SCANCODE_Q] = DIK_Q;
    SDL_to_DIK[SDL_SCANCODE_W] = DIK_W;
    SDL_to_DIK[SDL_SCANCODE_E] = DIK_E;
    SDL_to_DIK[SDL_SCANCODE_R] = DIK_R;
    SDL_to_DIK[SDL_SCANCODE_T] = DIK_T;
    SDL_to_DIK[SDL_SCANCODE_Y] = DIK_Y;
    SDL_to_DIK[SDL_SCANCODE_U] = DIK_U;
    SDL_to_DIK[SDL_SCANCODE_I] = DIK_I;
    SDL_to_DIK[SDL_SCANCODE_O] = DIK_O;
    SDL_to_DIK[SDL_SCANCODE_P] = DIK_P;
    SDL_to_DIK[SDL_SCANCODE_LEFTBRACKET] = DIK_LBRACKET;
    SDL_to_DIK[SDL_SCANCODE_RIGHTBRACKET] = DIK_RBRACKET;
    SDL_to_DIK[SDL_SCANCODE_RETURN] = DIK_RETURN;

    // Home row letters
    SDL_to_DIK[SDL_SCANCODE_CAPSLOCK] = DIK_CAPITAL;
    SDL_to_DIK[SDL_SCANCODE_A] = DIK_A;
    SDL_to_DIK[SDL_SCANCODE_S] = DIK_S;
    SDL_to_DIK[SDL_SCANCODE_D] = DIK_D;
    SDL_to_DIK[SDL_SCANCODE_F] = DIK_F;
    SDL_to_DIK[SDL_SCANCODE_G] = DIK_G;
    SDL_to_DIK[SDL_SCANCODE_H] = DIK_H;
    SDL_to_DIK[SDL_SCANCODE_J] = DIK_J;
    SDL_to_DIK[SDL_SCANCODE_K] = DIK_K;
    SDL_to_DIK[SDL_SCANCODE_L] = DIK_L;
    SDL_to_DIK[SDL_SCANCODE_SEMICOLON] = DIK_SEMICOLON;
    SDL_to_DIK[SDL_SCANCODE_APOSTROPHE] = DIK_APOSTROPHE;
    SDL_to_DIK[SDL_SCANCODE_GRAVE] = DIK_GRAVE;

    // Bottom row letters
    SDL_to_DIK[SDL_SCANCODE_LSHIFT] = DIK_LSHIFT;
    SDL_to_DIK[SDL_SCANCODE_BACKSLASH] = DIK_BACKSLASH;
    SDL_to_DIK[SDL_SCANCODE_Z] = DIK_Z;
    SDL_to_DIK[SDL_SCANCODE_X] = DIK_X;
    SDL_to_DIK[SDL_SCANCODE_C] = DIK_C;
    SDL_to_DIK[SDL_SCANCODE_V] = DIK_V;
    SDL_to_DIK[SDL_SCANCODE_B] = DIK_B;
    SDL_to_DIK[SDL_SCANCODE_N] = DIK_N;
    SDL_to_DIK[SDL_SCANCODE_M] = DIK_M;
    SDL_to_DIK[SDL_SCANCODE_COMMA] = DIK_COMMA;
    SDL_to_DIK[SDL_SCANCODE_PERIOD] = DIK_PERIOD;
    SDL_to_DIK[SDL_SCANCODE_SLASH] = DIK_SLASH;
    SDL_to_DIK[SDL_SCANCODE_RSHIFT] = DIK_RSHIFT;

    // Modifiers and space
    SDL_to_DIK[SDL_SCANCODE_LCTRL] = DIK_LCONTROL;
    SDL_to_DIK[SDL_SCANCODE_LALT] = DIK_LMENU;
    SDL_to_DIK[SDL_SCANCODE_SPACE] = DIK_SPACE;
    SDL_to_DIK[SDL_SCANCODE_RALT] = DIK_RMENU;
    SDL_to_DIK[SDL_SCANCODE_RCTRL] = DIK_RCONTROL;

    // Navigation keys
    SDL_to_DIK[SDL_SCANCODE_INSERT] = DIK_INSERT;
    SDL_to_DIK[SDL_SCANCODE_HOME] = DIK_HOME;
    SDL_to_DIK[SDL_SCANCODE_PAGEUP] = DIK_PRIOR;
    SDL_to_DIK[SDL_SCANCODE_DELETE] = DIK_DELETE;
    SDL_to_DIK[SDL_SCANCODE_END] = DIK_END;
    SDL_to_DIK[SDL_SCANCODE_PAGEDOWN] = DIK_NEXT;

    // Arrow keys
    SDL_to_DIK[SDL_SCANCODE_UP] = DIK_UP;
    SDL_to_DIK[SDL_SCANCODE_DOWN] = DIK_DOWN;
    SDL_to_DIK[SDL_SCANCODE_LEFT] = DIK_LEFT;
    SDL_to_DIK[SDL_SCANCODE_RIGHT] = DIK_RIGHT;

    // Numpad
    SDL_to_DIK[SDL_SCANCODE_NUMLOCKCLEAR] = DIK_NUMLOCK;
    SDL_to_DIK[SDL_SCANCODE_KP_DIVIDE] = DIK_DIVIDE;
    SDL_to_DIK[SDL_SCANCODE_KP_MULTIPLY] = DIK_MULTIPLY;
    SDL_to_DIK[SDL_SCANCODE_KP_MINUS] = DIK_SUBTRACT;
    SDL_to_DIK[SDL_SCANCODE_KP_7] = DIK_NUMPAD7;
    SDL_to_DIK[SDL_SCANCODE_KP_8] = DIK_NUMPAD8;
    SDL_to_DIK[SDL_SCANCODE_KP_9] = DIK_NUMPAD9;
    SDL_to_DIK[SDL_SCANCODE_KP_PLUS] = DIK_ADD;
    SDL_to_DIK[SDL_SCANCODE_KP_4] = DIK_NUMPAD4;
    SDL_to_DIK[SDL_SCANCODE_KP_5] = DIK_NUMPAD5;
    SDL_to_DIK[SDL_SCANCODE_KP_6] = DIK_NUMPAD6;
    SDL_to_DIK[SDL_SCANCODE_KP_1] = DIK_NUMPAD1;
    SDL_to_DIK[SDL_SCANCODE_KP_2] = DIK_NUMPAD2;
    SDL_to_DIK[SDL_SCANCODE_KP_3] = DIK_NUMPAD3;
    SDL_to_DIK[SDL_SCANCODE_KP_ENTER] = DIK_NUMPADENTER;
    SDL_to_DIK[SDL_SCANCODE_KP_0] = DIK_NUMPAD0;
    SDL_to_DIK[SDL_SCANCODE_KP_PERIOD] = DIK_DECIMAL;

    // Lock keys
    SDL_to_DIK[SDL_SCANCODE_SCROLLLOCK] = DIK_SCROLL;
    SDL_to_DIK[SDL_SCANCODE_PRINTSCREEN] = DIK_SYSRQ;

    // Windows keys
    SDL_to_DIK[SDL_SCANCODE_LGUI] = DIK_LWIN;
    SDL_to_DIK[SDL_SCANCODE_RGUI] = DIK_RWIN;
    SDL_to_DIK[SDL_SCANCODE_APPLICATION] = DIK_APPS;
}

// Convert SDL scancode to DIK code
static int ConvertSDLToDIK(SDL_Scancode scancode) {
    if (scancode >= 0 && scancode < SDL_NUM_SCANCODES) {
        return SDL_to_DIK[scancode];
    }
    return 0;
}

// =============================================================================
// SDL JOYSTICK SUPPORT
// Initialize, poll, and convert joystick data to FreeFalcon format
// =============================================================================

// Initialize SDL joystick subsystem and open first available joystick
static void InitSDLJoystick() {
    // Initialize joystick subsystem if not already done
    if (SDL_WasInit(SDL_INIT_JOYSTICK) == 0) {
        if (SDL_InitSubSystem(SDL_INIT_JOYSTICK) < 0) {
            FF_ERROR("Failed to initialize joystick subsystem: %s\n", SDL_GetError());
            return;
        }
    }

    int numJoysticks = SDL_NumJoysticks();
    FF_DEBUG_JOYSTICK("Found %d joystick(s)\n", numJoysticks);

    if (numJoysticks > 0) {
        // Open the first joystick
        g_SDLJoystick = SDL_JoystickOpen(0);
        if (g_SDLJoystick) {
            g_JoystickIndex = 0;
            g_JoystickNumAxes = SDL_JoystickNumAxes(g_SDLJoystick);
            g_JoystickNumButtons = SDL_JoystickNumButtons(g_SDLJoystick);
            g_JoystickNumHats = SDL_JoystickNumHats(g_SDLJoystick);

            FF_DEBUG_JOYSTICK("Opened joystick 0: %s\n", SDL_JoystickName(g_SDLJoystick));
            FF_DEBUG_JOYSTICK("  Axes: %d, Buttons: %d, Hats: %d\n",
                    g_JoystickNumAxes, g_JoystickNumButtons, g_JoystickNumHats);

            // Enable joystick events
            SDL_JoystickEventState(SDL_ENABLE);
        } else {
            FF_ERROR("Failed to open joystick 0: %s\n", SDL_GetError());
        }
    }
}

// Cleanup SDL joystick
static void CleanupSDLJoystick() {
    if (g_SDLJoystick) {
        SDL_JoystickClose(g_SDLJoystick);
        g_SDLJoystick = nullptr;
        g_JoystickIndex = -1;
        FF_DEBUG_JOYSTICK("Joystick closed\n");
    }
}

// Convert SDL hat value to DirectInput POV angle (hundredths of degrees)
// SDL_HAT_CENTERED=0, SDL_HAT_UP=1, SDL_HAT_RIGHT=2, SDL_HAT_DOWN=4, SDL_HAT_LEFT=8
static DWORD ConvertSDLHatToPOV(Uint8 hat) {
    switch (hat) {
        case SDL_HAT_UP:        return 0;       // 0 degrees
        case SDL_HAT_RIGHTUP:   return 4500;    // 45 degrees
        case SDL_HAT_RIGHT:     return 9000;    // 90 degrees
        case SDL_HAT_RIGHTDOWN: return 13500;   // 135 degrees
        case SDL_HAT_DOWN:      return 18000;   // 180 degrees
        case SDL_HAT_LEFTDOWN:  return 22500;   // 225 degrees
        case SDL_HAT_LEFT:      return 27000;   // 270 degrees
        case SDL_HAT_LEFTUP:    return 31500;   // 315 degrees
        default:                return (DWORD)-1; // Centered
    }
}

// Poll joystick and update IO structure for simulation
// NOTE: Currently unused - we use event-driven input (SDL_JOYAXISMOTION etc.)
// This function is kept for potential future use if polling is preferred.
#if 0
static void PollSDLJoystick() {
    if (!g_SDLJoystick) return;

    // Update joystick state (needed if not using event loop for all input)
    SDL_JoystickUpdate();

    // Read axis values (SDL: -32768 to 32767)
    // FreeFalcon expects -10000 to 10000 for bipolar axes, 0 to 15000 for unipolar
    for (int i = 0; i < g_JoystickNumAxes && i < 16; i++) {
        g_JoystickAxes[i] = SDL_JoystickGetAxis(g_SDLJoystick, i);
    }

    // Map SDL joystick axes to FreeFalcon IO structure
    // Common joystick mapping:
    //   Axis 0: X axis (roll/aileron)
    //   Axis 1: Y axis (pitch/elevator)
    //   Axis 2: Z axis or throttle
    //   Axis 3: Rudder (Rz on some sticks)

    // Convert and store in IO structure
    // SDL range: -32768 to 32767
    // FreeFalcon bipolar range: -10000 to 10000

    if (g_JoystickNumAxes >= 1) {
        // Roll (X axis)
        IO.analog[AXIS_ROLL].ioVal = (int)(g_JoystickAxes[0] * 10000 / 32767);
        IO.analog[AXIS_ROLL].engrValue = (float)IO.analog[AXIS_ROLL].ioVal / 10000.0f;
        IO.analog[AXIS_ROLL].isUsed = true;
    }

    if (g_JoystickNumAxes >= 2) {
        // Pitch (Y axis) - note: may need inversion depending on joystick
        IO.analog[AXIS_PITCH].ioVal = (int)(g_JoystickAxes[1] * 10000 / 32767);
        IO.analog[AXIS_PITCH].engrValue = (float)IO.analog[AXIS_PITCH].ioVal / 10000.0f;
        IO.analog[AXIS_PITCH].isUsed = true;
    }

    if (g_JoystickNumAxes >= 3) {
        // Throttle (Z axis) - unipolar, 0 to 15000
        // SDL: -32768 (full forward) to 32767 (full back)
        // Invert and map to 0-15000
        int rawZ = g_JoystickAxes[2];
        int throttleVal = (32767 - rawZ) * 15000 / 65535;
        IO.analog[AXIS_THROTTLE].ioVal = throttleVal;
        IO.analog[AXIS_THROTTLE].engrValue = (float)throttleVal / 15000.0f;
        IO.analog[AXIS_THROTTLE].isUsed = true;
    }

    if (g_JoystickNumAxes >= 4) {
        // Yaw/Rudder (Rz or axis 3)
        IO.analog[AXIS_YAW].ioVal = (int)(g_JoystickAxes[3] * 10000 / 32767);
        IO.analog[AXIS_YAW].engrValue = (float)IO.analog[AXIS_YAW].ioVal / 10000.0f;
        IO.analog[AXIS_YAW].isUsed = true;
    }

    // Read button states
    for (int i = 0; i < g_JoystickNumButtons && i < SIMLIB_MAX_DIGITAL; i++) {
        IO.digital[i] = SDL_JoystickGetButton(g_SDLJoystick, i) ? TRUE : FALSE;
    }

    // Read POV hat
    for (int i = 0; i < g_JoystickNumHats && i < SIMLIB_MAX_POV; i++) {
        Uint8 hat = SDL_JoystickGetHat(g_SDLJoystick, i);
        IO.povHatAngle[i] = ConvertSDLHatToPOV(hat);
    }
}
#endif

// =============================================================================
// FALLBACK MENU SYSTEM
// Simple OpenGL-based menu when UI95 rendering isn't working
// =============================================================================
static bool g_useFallbackMenu = false;  // Disabled - testing texture rendering
static const char* g_menuStatusMessage = nullptr;  // Status message to display
static Uint32 g_menuStatusTime = 0;  // When the status message was set

struct MenuButton {
    const char* label;
    float x, y, w, h;
    void (*callback)();
};

// Callback declarations
static void FallbackExit();
static void FallbackDogfight();
static void FallbackCampaign();
static void FallbackSetup();
static void FallbackComms();
static void FallbackACMI();
static void FallbackLogbook();
static void FallbackInstantAction();

// Menu buttons - positioned at bottom of screen like the real menu
static MenuButton g_menuButtons[] = {
    {"EXIT",      20,  720, 80, 30, FallbackExit},
    {"LOGBOOK",   110, 720, 90, 30, FallbackLogbook},
    {"ACMI",      210, 720, 70, 30, FallbackACMI},
    {"SETUP",     290, 720, 80, 30, FallbackSetup},
    {"COMMS",     380, 720, 80, 30, FallbackComms},
    {"INSTANT",   560, 720, 90, 30, FallbackInstantAction},
    {"DOGFIGHT",  750, 720, 100, 30, FallbackDogfight},
    {"CAMPAIGN",  920, 720, 100, 30, FallbackCampaign},
};
static const int g_numMenuButtons = sizeof(g_menuButtons) / sizeof(g_menuButtons[0]);
static int g_hoveredButton = -1;

// Simple bitmap font rendering using OpenGL lines
static void DrawChar(float x, float y, char c, float scale) {
    // Simple 5x7 bitmap font represented as line segments
    glBegin(GL_LINES);

    switch(c) {
        case 'A':
            glVertex2f(x, y+7*scale); glVertex2f(x+2.5f*scale, y);
            glVertex2f(x+2.5f*scale, y); glVertex2f(x+5*scale, y+7*scale);
            glVertex2f(x+1*scale, y+4*scale); glVertex2f(x+4*scale, y+4*scale);
            break;
        case 'B':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+5*scale, y+1*scale);
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+5*scale, y+3*scale);
            glVertex2f(x+5*scale, y+3*scale); glVertex2f(x+4*scale, y+3.5f*scale);
            glVertex2f(x, y+3.5f*scale); glVertex2f(x+4*scale, y+3.5f*scale);
            glVertex2f(x+4*scale, y+3.5f*scale); glVertex2f(x+5*scale, y+4.5f*scale);
            glVertex2f(x+5*scale, y+4.5f*scale); glVertex2f(x+5*scale, y+6*scale);
            glVertex2f(x+5*scale, y+6*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x, y+7*scale); glVertex2f(x+4*scale, y+7*scale);
            break;
        case 'C':
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+1*scale, y);
            glVertex2f(x+1*scale, y); glVertex2f(x, y+1*scale);
            glVertex2f(x, y+1*scale); glVertex2f(x, y+6*scale);
            glVertex2f(x, y+6*scale); glVertex2f(x+1*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x+4*scale, y+7*scale); glVertex2f(x+5*scale, y+6*scale);
            break;
        case 'D':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+3*scale, y);
            glVertex2f(x+3*scale, y); glVertex2f(x+5*scale, y+2*scale);
            glVertex2f(x+5*scale, y+2*scale); glVertex2f(x+5*scale, y+5*scale);
            glVertex2f(x+5*scale, y+5*scale); glVertex2f(x+3*scale, y+7*scale);
            glVertex2f(x, y+7*scale); glVertex2f(x+3*scale, y+7*scale);
            break;
        case 'E':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+5*scale, y);
            glVertex2f(x, y+3.5f*scale); glVertex2f(x+4*scale, y+3.5f*scale);
            glVertex2f(x, y+7*scale); glVertex2f(x+5*scale, y+7*scale);
            break;
        case 'F':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+5*scale, y);
            glVertex2f(x, y+3.5f*scale); glVertex2f(x+4*scale, y+3.5f*scale);
            break;
        case 'G':
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+1*scale, y);
            glVertex2f(x+1*scale, y); glVertex2f(x, y+1*scale);
            glVertex2f(x, y+1*scale); glVertex2f(x, y+6*scale);
            glVertex2f(x, y+6*scale); glVertex2f(x+1*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x+4*scale, y+7*scale); glVertex2f(x+5*scale, y+6*scale);
            glVertex2f(x+5*scale, y+6*scale); glVertex2f(x+5*scale, y+4*scale);
            glVertex2f(x+5*scale, y+4*scale); glVertex2f(x+3*scale, y+4*scale);
            break;
        case 'H':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x+5*scale, y); glVertex2f(x+5*scale, y+7*scale);
            glVertex2f(x, y+3.5f*scale); glVertex2f(x+5*scale, y+3.5f*scale);
            break;
        case 'I':
            glVertex2f(x+1*scale, y); glVertex2f(x+4*scale, y);
            glVertex2f(x+2.5f*scale, y); glVertex2f(x+2.5f*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x+4*scale, y+7*scale);
            break;
        case 'K':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x+5*scale, y); glVertex2f(x, y+3.5f*scale);
            glVertex2f(x, y+3.5f*scale); glVertex2f(x+5*scale, y+7*scale);
            break;
        case 'L':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y+7*scale); glVertex2f(x+5*scale, y+7*scale);
            break;
        case 'M':
            glVertex2f(x, y+7*scale); glVertex2f(x, y);
            glVertex2f(x, y); glVertex2f(x+2.5f*scale, y+3*scale);
            glVertex2f(x+2.5f*scale, y+3*scale); glVertex2f(x+5*scale, y);
            glVertex2f(x+5*scale, y); glVertex2f(x+5*scale, y+7*scale);
            break;
        case 'N':
            glVertex2f(x, y+7*scale); glVertex2f(x, y);
            glVertex2f(x, y); glVertex2f(x+5*scale, y+7*scale);
            glVertex2f(x+5*scale, y+7*scale); glVertex2f(x+5*scale, y);
            break;
        case 'O':
            glVertex2f(x+1*scale, y); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+5*scale, y+1*scale);
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+5*scale, y+6*scale);
            glVertex2f(x+5*scale, y+6*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x+4*scale, y+7*scale); glVertex2f(x+1*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x, y+6*scale);
            glVertex2f(x, y+6*scale); glVertex2f(x, y+1*scale);
            glVertex2f(x, y+1*scale); glVertex2f(x+1*scale, y);
            break;
        case 'P':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+5*scale, y+1*scale);
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+5*scale, y+3*scale);
            glVertex2f(x+5*scale, y+3*scale); glVertex2f(x+4*scale, y+4*scale);
            glVertex2f(x+4*scale, y+4*scale); glVertex2f(x, y+4*scale);
            break;
        case 'R':
            glVertex2f(x, y); glVertex2f(x, y+7*scale);
            glVertex2f(x, y); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+5*scale, y+1*scale);
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+5*scale, y+3*scale);
            glVertex2f(x+5*scale, y+3*scale); glVertex2f(x+4*scale, y+4*scale);
            glVertex2f(x+4*scale, y+4*scale); glVertex2f(x, y+4*scale);
            glVertex2f(x+2*scale, y+4*scale); glVertex2f(x+5*scale, y+7*scale);
            break;
        case 'S':
            glVertex2f(x+5*scale, y+1*scale); glVertex2f(x+4*scale, y);
            glVertex2f(x+4*scale, y); glVertex2f(x+1*scale, y);
            glVertex2f(x+1*scale, y); glVertex2f(x, y+1*scale);
            glVertex2f(x, y+1*scale); glVertex2f(x, y+3*scale);
            glVertex2f(x, y+3*scale); glVertex2f(x+1*scale, y+3.5f*scale);
            glVertex2f(x+1*scale, y+3.5f*scale); glVertex2f(x+4*scale, y+3.5f*scale);
            glVertex2f(x+4*scale, y+3.5f*scale); glVertex2f(x+5*scale, y+4.5f*scale);
            glVertex2f(x+5*scale, y+4.5f*scale); glVertex2f(x+5*scale, y+6*scale);
            glVertex2f(x+5*scale, y+6*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x+4*scale, y+7*scale); glVertex2f(x+1*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x, y+6*scale);
            break;
        case 'T':
            glVertex2f(x, y); glVertex2f(x+5*scale, y);
            glVertex2f(x+2.5f*scale, y); glVertex2f(x+2.5f*scale, y+7*scale);
            break;
        case 'U':
            glVertex2f(x, y); glVertex2f(x, y+6*scale);
            glVertex2f(x, y+6*scale); glVertex2f(x+1*scale, y+7*scale);
            glVertex2f(x+1*scale, y+7*scale); glVertex2f(x+4*scale, y+7*scale);
            glVertex2f(x+4*scale, y+7*scale); glVertex2f(x+5*scale, y+6*scale);
            glVertex2f(x+5*scale, y+6*scale); glVertex2f(x+5*scale, y);
            break;
        case 'X':
            glVertex2f(x, y); glVertex2f(x+5*scale, y+7*scale);
            glVertex2f(x+5*scale, y); glVertex2f(x, y+7*scale);
            break;
        case 'Y':
            glVertex2f(x, y); glVertex2f(x+2.5f*scale, y+3.5f*scale);
            glVertex2f(x+5*scale, y); glVertex2f(x+2.5f*scale, y+3.5f*scale);
            glVertex2f(x+2.5f*scale, y+3.5f*scale); glVertex2f(x+2.5f*scale, y+7*scale);
            break;
        case ' ':
            break;
        default:
            // Draw a box for unknown chars
            glVertex2f(x, y); glVertex2f(x+5*scale, y);
            glVertex2f(x+5*scale, y); glVertex2f(x+5*scale, y+7*scale);
            glVertex2f(x+5*scale, y+7*scale); glVertex2f(x, y+7*scale);
            glVertex2f(x, y+7*scale); glVertex2f(x, y);
            break;
    }
    glEnd();
}

static void DrawString(float x, float y, const char* str, float scale) {
    float charWidth = 6 * scale;
    while (*str) {
        DrawChar(x, y, *str, scale);
        x += charWidth;
        str++;
    }
}

static void DrawFallbackMenu() {
    // Set up 2D orthographic projection
    glMatrixMode(GL_PROJECTION);
    glPushMatrix();
    glLoadIdentity();
    glOrtho(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadIdentity();

    glDisable(GL_DEPTH_TEST);
    glDisable(GL_TEXTURE_2D);
    glLineWidth(2.0f);

    // Dark background
    glColor3f(0.15f, 0.2f, 0.25f);
    glBegin(GL_QUADS);
    glVertex2f(0, 0);
    glVertex2f(WINDOW_WIDTH, 0);
    glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT);
    glVertex2f(0, WINDOW_HEIGHT);
    glEnd();

    // Title
    glColor3f(1.0f, 0.9f, 0.3f);  // Gold
    DrawString(350, 100, "FREE FALCON", 4.0f);

    glColor3f(0.7f, 0.7f, 0.8f);  // Silver
    DrawString(380, 160, "LINUX PORT", 3.0f);

    // Instructions
    glColor3f(0.6f, 0.8f, 0.6f);  // Light green
    DrawString(300, 300, "CLICK A BUTTON BELOW", 2.0f);
    DrawString(350, 340, "OR PRESS ESC TO EXIT", 2.0f);

    // Draw buttons
    for (int i = 0; i < g_numMenuButtons; i++) {
        MenuButton& btn = g_menuButtons[i];

        // Button background
        if (i == g_hoveredButton) {
            glColor3f(0.3f, 0.5f, 0.7f);  // Highlighted
        } else {
            glColor3f(0.2f, 0.25f, 0.3f);  // Normal
        }
        glBegin(GL_QUADS);
        glVertex2f(btn.x, btn.y);
        glVertex2f(btn.x + btn.w, btn.y);
        glVertex2f(btn.x + btn.w, btn.y + btn.h);
        glVertex2f(btn.x, btn.y + btn.h);
        glEnd();

        // Button border
        if (i == g_hoveredButton) {
            glColor3f(1.0f, 1.0f, 0.5f);  // Yellow highlight
        } else {
            glColor3f(0.5f, 0.5f, 0.6f);
        }
        glBegin(GL_LINE_LOOP);
        glVertex2f(btn.x, btn.y);
        glVertex2f(btn.x + btn.w, btn.y);
        glVertex2f(btn.x + btn.w, btn.y + btn.h);
        glVertex2f(btn.x, btn.y + btn.h);
        glEnd();

        // Button text
        glColor3f(1.0f, 1.0f, 1.0f);
        float textX = btn.x + 5;
        float textY = btn.y + 8;
        DrawString(textX, textY, btn.label, 1.5f);
    }

    // Draw status message if present (fades out after 3 seconds)
    if (g_menuStatusMessage) {
        Uint32 elapsed = SDL_GetTicks() - g_menuStatusTime;
        if (elapsed < 3000) {
            // Fade out effect
            float alpha = 1.0f - (elapsed / 3000.0f);
            glColor3f(1.0f * alpha, 0.5f * alpha, 0.5f * alpha);  // Red-ish
            DrawString(300, 400, g_menuStatusMessage, 2.0f);
        } else {
            g_menuStatusMessage = nullptr;
        }
    }

    // Restore matrices
    glMatrixMode(GL_MODELVIEW);
    glPopMatrix();
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();
}

static int GetButtonAtPosition(int x, int y) {
    for (int i = 0; i < g_numMenuButtons; i++) {
        MenuButton& btn = g_menuButtons[i];
        if (x >= btn.x && x <= btn.x + btn.w &&
            y >= btn.y && y <= btn.y + btn.h) {
            return i;
        }
    }
    return -1;
}

static void HandleFallbackMenuClick(int x, int y) {
    int btn = GetButtonAtPosition(x, y);
    if (btn >= 0 && g_menuButtons[btn].callback) {
        fprintf(stderr, "[FallbackMenu] Button clicked: %s\n", g_menuButtons[btn].label);
        fflush(stderr);
        g_menuButtons[btn].callback();
        fprintf(stderr, "[FallbackMenu] Callback returned, g_running=%d\n", g_running ? 1 : 0);
        fflush(stderr);
    }
}

static void HandleFallbackMenuHover(int x, int y) {
    g_hoveredButton = GetButtonAtPosition(x, y);
}

// Helper to show a status message on the fallback menu
static void ShowMenuStatus(const char* message) {
    g_menuStatusMessage = message;
    g_menuStatusTime = SDL_GetTicks();
    fprintf(stderr, "[FallbackMenu] Status: %s\n", message);
    fflush(stderr);
}

// Fallback menu callbacks
static void FallbackExit() {
    fprintf(stderr, "[FallbackMenu] EXIT selected - shutting down\n");
    fflush(stderr);
    g_running = false;
}

static void FallbackDogfight() {
    ShowMenuStatus("DOGFIGHT - Not yet implemented");
}

static void FallbackCampaign() {
    ShowMenuStatus("CAMPAIGN - Not yet implemented");
}

static void FallbackSetup() {
    ShowMenuStatus("SETUP - Not yet implemented");
}

static void FallbackComms() {
    ShowMenuStatus("COMMS - Not yet implemented");
}

static void FallbackACMI() {
    ShowMenuStatus("ACMI - Not yet implemented");
}

static void FallbackLogbook() {
    ShowMenuStatus("LOGBOOK - Not yet implemented");
}

static void FallbackInstantAction() {
    ShowMenuStatus("INSTANT ACTION - Not yet implemented");
}

// =============================================================================
// END FALLBACK MENU SYSTEM
// =============================================================================

// Signal handler for clean shutdown when process is killed
static volatile sig_atomic_t g_signalReceived = 0;

static void signal_handler(int sig) {
    g_signalReceived = sig;
    g_running = false;

    // For immediate cleanup on signal, directly destroy the SDL window
    // This ensures the window disappears even if the main loop doesn't get to cleanup()
    if (g_GLContext) {
        SDL_GL_DeleteContext(g_GLContext);
        g_GLContext = nullptr;
    }
    if (g_SDLWindow) {
        SDL_DestroyWindow(g_SDLWindow);
        g_SDLWindow = nullptr;
    }
    SDL_Quit();

    // Re-raise the signal with default handler so the process terminates properly
    signal(sig, SIG_DFL);
    raise(sig);
}

// FF_LINUX: SIGSEGV/SIGFPE handler with backtrace for crash diagnosis
static void crash_signal_handler(int sig) {
    const char *signame = (sig == SIGSEGV) ? "SIGSEGV" : (sig == SIGFPE) ? "SIGFPE" : (sig == SIGABRT) ? "SIGABRT" : "UNKNOWN";
    fprintf(stderr, "\n=== CRASH: %s (signal %d) ===\n", signame, sig);

    void *frames[64];
    int nframes = backtrace(frames, 64);
    backtrace_symbols_fd(frames, nframes, STDERR_FILENO);

    fprintf(stderr, "=== END BACKTRACE ===\n");
    fflush(stderr);

    // Re-raise with default handler
    signal(sig, SIG_DFL);
    raise(sig);
}

static void setup_signal_handlers() {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;

    sigaction(SIGTERM, &sa, nullptr);  // Terminate (default from kill)
    sigaction(SIGINT, &sa, nullptr);   // Interrupt (Ctrl+C)
    sigaction(SIGHUP, &sa, nullptr);   // Hangup

    // Crash signal handlers with backtrace
    struct sigaction crash_sa;
    memset(&crash_sa, 0, sizeof(crash_sa));
    crash_sa.sa_handler = crash_signal_handler;
    sigemptyset(&crash_sa.sa_mask);
    crash_sa.sa_flags = SA_RESETHAND;  // One-shot to avoid infinite loops

    sigaction(SIGSEGV, &crash_sa, nullptr);
    sigaction(SIGFPE, &crash_sa, nullptr);
    sigaction(SIGABRT, &crash_sa, nullptr);
}

// Forward declarations
static void print_usage(const char* progname);
static bool init_data_directory(const char* dataDir);
static bool init_resource_manager(void);
static bool init_sdl(bool fullscreen);
static bool init_opengl(void);
static bool init_openal(void);
static bool init_d3d_graphics(void);
static void cleanup(void);
static void handle_sdl_events(void);
static void render_frame(void);
static void main_loop(void);

// Game initialization stages
static bool init_game_paths(void);
static bool init_game_core(void);

static void print_usage(const char* progname) {
    printf("Usage: %s [options]\n", progname);
    printf("Options:\n");
    printf("  -d <path>    Set game data directory\n");
    printf("  -w           Run in windowed mode (default)\n");
    printf("  -f           Run in fullscreen mode\n");
    printf("  -nosound     Disable sound\n");
    printf("  -test-ia     Auto-launch Instant Action after 3 seconds (for testing)\n");
    printf("  -h           Show this help\n");
}

static bool init_data_directory(const char* dataDir) {
    // Check if directory exists
    if (access(dataDir, R_OK) != 0) {
        fprintf(stderr, "Error: Cannot access data directory: %s\n", dataDir);
        return false;
    }

    // Set the global data directory
    strncpy(FalconDataDirectory, dataDir, _MAX_PATH - 1);
    FalconDataDirectory[_MAX_PATH - 1] = '\0';

    printf("Data directory: %s\n", FalconDataDirectory);

    return true;
}

static bool init_game_paths(void) {
    printf("Setting up game paths...\n");

    // Set up derived paths (using forward slashes for Linux)
    // Note: FalconTerrainDataDir needs to include the theater name (default: "korea")
    // because DeviceIndependentGraphicsSetup is called before theater loading
    snprintf(FalconCampaignSaveDirectory, _MAX_PATH, "%s/campaign/save", FalconDataDirectory);
    snprintf(FalconCampUserSaveDirectory, _MAX_PATH, "%s/campaign/save", FalconDataDirectory);
    snprintf(FalconTerrainDataDir, _MAX_PATH, "%s/terrdata/korea", FalconDataDirectory);  // Include default theater
    snprintf(FalconMiscTexDataDir, _MAX_PATH, "%s/terrdata/misctex", FalconDataDirectory);
    snprintf(FalconPictureDirectory, _MAX_PATH, "%s/pictures", FalconDataDirectory);
    snprintf(FalconObjectDataDir, _MAX_PATH, "%s/terrdata/objects", FalconDataDirectory);
    snprintf(Falcon3DDataDir, _MAX_PATH, "%s/terrdata/objects", FalconDataDirectory);

    // Sound-related directories (using forward slashes for Linux)
    snprintf(FalconSoundThrDirectory, _MAX_PATH, "%s/sounds", FalconDataDirectory);
    snprintf(FalconUISoundDirectory, _MAX_PATH, "%s/sounds", FalconDataDirectory);
    snprintf(FalconCockpitThrDirectory, _MAX_PATH, "%s/art/ckptart", FalconDataDirectory);
    snprintf(FalconZipsThrDirectory, _MAX_PATH, "%s/zips", FalconDataDirectory);
    snprintf(FalconTacrefThrDirectory, _MAX_PATH, "%s/tacref", FalconDataDirectory);
    snprintf(FalconSplashThrDirectory, _MAX_PATH, "%s/art/splash", FalconDataDirectory);
    snprintf(FalconMovieDirectory, _MAX_PATH, "%s/movies", FalconDataDirectory);
    snprintf(FalconMovieMode, _MAX_PATH, "normals");  // Default movie mode
    snprintf(FalconUIArtDirectory, _MAX_PATH, "%s/art", FalconDataDirectory);
    snprintf(FalconUIArtThrDirectory, _MAX_PATH, "%s/art", FalconDataDirectory);

    // Create picture directory if it doesn't exist
    mkdir(FalconPictureDirectory, 0755);

    printf("  Campaign saves: %s\n", FalconCampaignSaveDirectory);
    printf("  Terrain data: %s\n", FalconTerrainDataDir);
    printf("  Object data: %s\n", FalconObjectDataDir);
    printf("  Sound directory: %s\n", FalconSoundThrDirectory);

    return true;
}

static bool init_resource_manager(void) {
    printf("Initializing resource manager...\n");

    // Initialize the resource manager with the data directory
    ResInit(FalconDataDirectory);
    ResCreatePath(FalconDataDirectory, FALSE);

    // Add common paths
    char tmpPath[_MAX_PATH];

    snprintf(tmpPath, _MAX_PATH, "%s/campaign/save", FalconDataDirectory);
    ResAddPath(tmpPath, FALSE);

    snprintf(tmpPath, _MAX_PATH, "%s/config", FalconDataDirectory);
    ResAddPath(tmpPath, FALSE);

    snprintf(tmpPath, _MAX_PATH, "%s/art", FalconDataDirectory);
    ResAddPath(tmpPath, TRUE);

    snprintf(tmpPath, _MAX_PATH, "%s/sim", FalconDataDirectory);
    ResAddPath(tmpPath, TRUE);

    snprintf(tmpPath, _MAX_PATH, "%s/pictures", FalconDataDirectory);
    ResAddPath(tmpPath, TRUE);

    ResSetDirectory(FalconDataDirectory);

    return true;
}

static bool init_sdl(bool fullscreen) {
    printf("Initializing SDL2...\n");

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_TIMER | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK) < 0) {
        fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return false;
    }

    fprintf(stderr, "[TRACE] SDL_Init completed, setting GL attributes\n"); fflush(stderr);

    // Set OpenGL attributes - minimal requirements, let driver pick best match
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);  // FF_LINUX: Required for 3D cockpit stencil masking
    // Don't specify version - let driver use default compatibility context
    // Don't specify color/depth sizes - let driver pick available format

    fprintf(stderr, "[TRACE] About to create window\n"); fflush(stderr);

    // Create window - simple fixed-size window for stability
    Uint32 windowFlags = SDL_WINDOW_OPENGL | SDL_WINDOW_SHOWN;
    if (fullscreen) {
        windowFlags |= SDL_WINDOW_FULLSCREEN_DESKTOP;
    }
    // Note: Not using RESIZABLE for now to avoid potential issues

    g_SDLWindow = SDL_CreateWindow(
        WINDOW_TITLE,
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        windowFlags
    );

    if (!g_SDLWindow) {
        fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        return false;
    }

    // Set mainAppWnd to a pseudo-handle (the SDL window pointer cast)
    mainAppWnd = (HWND)g_SDLWindow;
    mainMenuWnd = mainAppWnd;

    printf("  Window created: %dx%d\n", WINDOW_WIDTH, WINDOW_HEIGHT);

    // Initialize keyboard scancode translation table
    InitScancodeTranslation();
    printf("  Keyboard scancode translation initialized.\n");

    // Initialize joystick support
    InitSDLJoystick();

    return true;
}

static bool init_opengl(void) {
    printf("Initializing OpenGL...\n");
    fprintf(stderr, "[TRACE] About to call SDL_GL_CreateContext\n"); fflush(stderr);

    // Create OpenGL context
    g_GLContext = SDL_GL_CreateContext(g_SDLWindow);
    if (!g_GLContext) {
        fprintf(stderr, "SDL_GL_CreateContext failed: %s\n", SDL_GetError());
        return false;
    }

    // Initialize GLEW
    glewExperimental = GL_TRUE;
    GLenum glewErr = glewInit();
    if (glewErr != GLEW_OK) {
        fprintf(stderr, "glewInit failed: %s\n", glewGetErrorString(glewErr));
        return false;
    }

    // Enable vsync
    SDL_GL_SetSwapInterval(1);

    // Print OpenGL info
    printf("  OpenGL Vendor: %s\n", glGetString(GL_VENDOR));
    printf("  OpenGL Renderer: %s\n", glGetString(GL_RENDERER));
    printf("  OpenGL Version: %s\n", glGetString(GL_VERSION));
    {
        GLint stencilBits = 0;
        glGetIntegerv(GL_STENCIL_BITS, &stencilBits);
        printf("  OpenGL Stencil Bits: %d\n", stencilBits);
    }

    // Set up basic OpenGL state - minimal for test pattern
    glClearColor(0.2f, 0.2f, 0.3f, 1.0f);  // Neutral gray-blue
    glDisable(GL_DEPTH_TEST);   // Not needed for 2D test pattern
    glDisable(GL_LIGHTING);     // No lighting
    glDisable(GL_TEXTURE_2D);   // No textures
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();

    // Clear any OpenGL errors from init
    while (glGetError() != GL_NO_ERROR) {}

    return true;
}

static bool init_d3d_graphics(void) {
    printf("Initializing D3D7-to-OpenGL graphics layer...\n");

    // Get window dimensions
    int width, height;
    SDL_GetWindowSize(g_SDLWindow, &width, &height);

    // Create DirectDraw7 interface first (needed for surface creation)
    g_pDD = FF_CreateDirectDraw7();
    if (!g_pDD) {
        fprintf(stderr, "Failed to create DirectDraw7 interface\n");
        return false;
    }
    printf("  Created DirectDraw7 interface\n");

    // Create D3D7 interface
    g_pD3D = FF_CreateDirect3D7();
    if (!g_pD3D) {
        fprintf(stderr, "Failed to create Direct3D7 interface\n");
        return false;
    }
    printf("  Created Direct3D7 interface\n");

    // Create render target surface
    g_pRenderTarget = FF_CreateRenderTargetSurface(width, height);
    if (!g_pRenderTarget) {
        fprintf(stderr, "Failed to create render target surface\n");
        return false;
    }
    printf("  Created render target surface: %dx%d\n", width, height);

    // Create D3D device
    g_pD3DDevice = FF_CreateDirect3DDevice7(g_pD3D, g_pRenderTarget);
    if (!g_pD3DDevice) {
        fprintf(stderr, "Failed to create Direct3DDevice7\n");
        return false;
    }
    printf("  Created Direct3DDevice7\n");

    // Set up initial viewport
    D3DVIEWPORT7 vp;
    memset(&vp, 0, sizeof(vp));
    vp.dwX = 0;
    vp.dwY = 0;
    vp.dwWidth = width;
    vp.dwHeight = height;
    vp.dvMinZ = 0.0f;
    vp.dvMaxZ = 1.0f;
    g_pD3DDevice->SetViewport(&vp);

    // Create DXContext with our OpenGL-backed interfaces
    g_pDXContext = FF_CreateDXContext(width, height, g_pD3D, g_pD3DDevice, g_pDD);
    if (!g_pDXContext) {
        fprintf(stderr, "Failed to create DXContext\n");
        return false;
    }
    printf("  Created DXContext\n");

    // Initialize the texture system with our DXContext
    // Get texture path from data directory
    char texturePath[256];
    snprintf(texturePath, sizeof(texturePath), "%s/terrdata/objects", FalconDataDirectory);
    printf("  Initializing texture system (path: %s)...\n", texturePath);
    Texture::SetupForDevice(g_pDXContext, texturePath);
    printf("  Texture system initialized\n");

    // Initialize the DXEngine with our OpenGL-backed D3D device
    printf("  Initializing DXEngine...\n");
    TheDXEngine.Setup(g_pD3DDevice, g_pD3D, g_pDD);
    // Don't enable DXEngine rendering yet - game needs to fully load first
    // g_Use_DX_Engine will be set to true when the game enters simulation mode
    g_Use_DX_Engine = false;
    printf("  NOTE: DXEngine initialized but rendering disabled until game enters simulation mode\n");

    g_graphicsInitialized = true;
    printf("  D3D7-to-OpenGL graphics layer initialized successfully\n");

    return true;
}

static bool init_openal(void) {
    printf("Initializing OpenAL...\n");

    g_alDevice = alcOpenDevice(nullptr);
    if (!g_alDevice) {
        fprintf(stderr, "Warning: Could not open OpenAL device\n");
        return false;
    }

    g_alContext = alcCreateContext(g_alDevice, nullptr);
    if (!g_alContext) {
        fprintf(stderr, "Warning: Could not create OpenAL context\n");
        alcCloseDevice(g_alDevice);
        g_alDevice = nullptr;
        return false;
    }

    alcMakeContextCurrent(g_alContext);

    printf("  OpenAL Vendor: %s\n", alGetString(AL_VENDOR));
    printf("  OpenAL Renderer: %s\n", alGetString(AL_RENDERER));
    printf("  OpenAL Version: %s\n", alGetString(AL_VERSION));

    return true;
}

// Initialize core game systems
static bool init_game_core(void) {
    printf("\n--- Initializing Game Core Systems ---\n");

    // Initialize communications / Winsock emulation
    // This sets up CAPI function pointers needed by VU network code
    printf("  Initializing communications layer...\n");
    WSADATA wsaData;
    int wsaResult = initialize_windows_sockets(&wsaData);
    if (wsaResult == 0) {  // EXIT_SUCCESS = 0 means failure in this API
        fprintf(stderr, "Warning: initialize_windows_sockets returned failure code\n");
    } else {
        printf("  Communications layer initialized successfully\n");
    }

    // Set FPU rounding mode to truncate (equivalent to Windows _controlfp)
    fesetround(FE_TOWARDZERO);

    // Seed random number generator
    srand((unsigned int)time(NULL));

    // Set up FalconDisplay for Linux
    // Set the SDL window handle as the app window
    printf("  Setting up FalconDisplay for Linux...\n");
    FalconDisplay.appWin = (HWND)g_SDLWindow;
    FalconDisplay.displayFullScreen = false;  // Windowed mode for now
    int width, height;
    SDL_GetWindowSize(g_SDLWindow, &width, &height);
    FalconDisplay.width[FalconDisplayConfiguration::UI] = width;
    FalconDisplay.height[FalconDisplayConfiguration::UI] = height;
    FalconDisplay.depth[FalconDisplayConfiguration::UI] = 16;  // Use 16-bit for UI mode (matches FreeFalcon convention)
    FalconDisplay.currentMode = FalconDisplayConfiguration::UI;

    // Initialize the DeviceManager (enumerates display modes and D3D devices)
    printf("  Initializing DeviceManager...\n");
    FalconDisplay.Setup(0);  // Language number 0 for English

    // Initialize memory pools
    printf("  Initializing simulation memory pools...\n");
    SimDriver.InitializeSimMemoryPools();

    // Load particle system parameters
    printf("  Loading particle system parameters...\n");
    DrawableParticleSys::LoadParameters();

    // Load theater list
    printf("  Loading theater list...\n");
    LoadTheaterList();

    // Try to get a theater - either from saved preference or first available
    TheaterDef *td = g_theaters.GetCurrentTheater();
    if (!td) {
        // No saved theater preference, try to find any available theater
        printf("  No saved theater, looking for first available...\n");
        td = g_theaters.GetTheater(0);  // Get first theater in list
    }

    if (td) {
        fprintf(stderr, "  Setting theater: %s\n", td->m_name);
        g_theaters.SetNewTheater(td);
        fprintf(stderr, "  [main_linux] SetNewTheater returned, calling InitVU...\n");

        // Initialize VU (Virtual Universe - entity management)
        fprintf(stderr, "  Initializing VU system...\n");
        InitVU();
        fprintf(stderr, "  [main_linux] InitVU returned\n");
    } else {
        printf("  No theater found, loading default data...\n");

        // Add sim path for raw sim files
        char tmpPath[_MAX_PATH];
        snprintf(tmpPath, _MAX_PATH, "%s/sim", FalconDataDirectory);
        ResAddPath(tmpPath, TRUE);

        // Load AI inputs
        printf("  Loading campaign AI inputs...\n");
        ReadCampAIInputs((char*)"Falcon4");

        // Load class table (entity definitions)
        printf("  Loading class table...\n");
        if (!LoadClassTable((char*)"Falcon4")) {
            fprintf(stderr, "Error: Failed to load class table\n");
            return false;
        }

        // Initialize VU
        printf("  Initializing VU system...\n");
        InitVU();

        // Load tactics
        printf("  Loading tactics...\n");
        if (!LoadTactics((char*)"Falcon4")) {
            fprintf(stderr, "Warning: Failed to load tactics\n");
        }

        // Load flight trails
        printf("  Loading trails...\n");
        LoadTrails();
    }

    // Initialize threading
    fprintf(stderr, "  Setting up thread manager...\n");
    ThreadManager::setup();
    fprintf(stderr, "  [main_linux] ThreadManager::setup() returned\n");

    // NOTE: TheTimeManager.Setup() is already called by DeviceIndependentGraphicsSetup()
    // in FalconDisplay.Setup(), so we don't need to call it again here.

    // Initialize sound system (creates gSoundDriver and calls InstallDSound)
    fprintf(stderr, "  Initializing sound manager...\n");
    if (InitSoundManager(FalconDisplay.appWin, 0, FalconDataDirectory)) {
        fprintf(stderr, "  [main_linux] InitSoundManager() succeeded\n");
    } else {
        fprintf(stderr, "  [main_linux] InitSoundManager() failed - sounds disabled\n");
    }

    // Start sound system (resumes playback if initialized)
    fprintf(stderr, "  Starting sound system...\n");
    F4SoundStart();
    fprintf(stderr, "  [main_linux] F4SoundStart() returned\n");

    // Start simulation loop
    fprintf(stderr, "  Starting simulation loop...\n");
    SimulationLoopControl::StartSim();
    fprintf(stderr, "  [main_linux] SimulationLoopControl::StartSim() returned\n");

    // FF_LINUX: Initialize weather system (required before campaign loading)
    fprintf(stderr, "  Initializing weather system...\n");
    realWeather = new WeatherClass();
    fprintf(stderr, "  [main_linux] realWeather created\n");

    // Initialize campaign
    fprintf(stderr, "  Initializing campaign system...\n");
    Camp_Init(1);
    fprintf(stderr, "  [main_linux] Camp_Init() returned\n");

    // Build ASCII key mappings
    fprintf(stderr, "  Building key mappings...\n");
    BuildAscii();
    fprintf(stderr, "  [main_linux] BuildAscii() returned\n");

    // FF_LINUX: Initialize comms manager (required for campaign loading)
    fprintf(stderr, "  Initializing comms manager...\n");
    gCommsMgr = new UIComms;
    gCommsMgr->Setup(FalconDisplay.appWin);
    fprintf(stderr, "  [main_linux] gCommsMgr->Setup() returned\n");

    // FF_LINUX: Load keyboard command bindings from keystrokes.key
    // This populates UserFunctionTable so keyboard commands work in the sim.
    // Must be called after SetupInputFunctions() (called by SimInputInit via OTWDriver.Enter),
    // but we call it here during init so bindings are ready before first flight.
    fprintf(stderr, "  Loading keyboard function tables...\n");
    LoadFunctionTables();
    fprintf(stderr, "  [main_linux] LoadFunctionTables() returned\n");

    fprintf(stderr, "  Game core initialization complete.\n");
    g_gameInitialized = true;

    return true;
}

static void cleanup(void) {
    FF_DEBUG_CLEANUP("Starting cleanup...\n");
    FF_DEBUG_FLUSH();

    // First, destroy the window immediately so it disappears
    // This provides visual feedback that the app is shutting down
    FF_DEBUG_CLEANUP("Destroying SDL window first for immediate visual feedback...\n");
    FF_DEBUG_FLUSH();

    if (g_GLContext) {
        SDL_GL_DeleteContext(g_GLContext);
        g_GLContext = nullptr;
    }
    if (g_SDLWindow) {
        SDL_DestroyWindow(g_SDLWindow);
        g_SDLWindow = nullptr;
    }
    FF_DEBUG_CLEANUP("Window destroyed.\n");
    FF_DEBUG_FLUSH();

    // Cleanup game systems (in reverse order of initialization)
    // These may block, but at least the window is gone
    if (g_gameInitialized) {
        FF_DEBUG_CLEANUP("Shutting down game systems...\n");
        FF_DEBUG_FLUSH();

        // Stop campaign - this can block on threading issues
        FF_DEBUG_CLEANUP("Stopping campaign...\n");
        FF_DEBUG_FLUSH();
        Camp_Exit();
        FF_DEBUG_CLEANUP("Campaign stopped.\n");
        FF_DEBUG_FLUSH();

        // Only stop simulation loop if we were actually in simulation mode
        // StopSim() has a blocking wait for RunningSim state that will hang
        // if we're just in UI mode (which uses the fallback menu)
        if (SimulationLoopControl::InSim()) {
            FF_DEBUG_CLEANUP("Stopping simulation loop...\n");
            FF_DEBUG_FLUSH();
            SimulationLoopControl::StopSim();
            FF_DEBUG_CLEANUP("Simulation loop stopped.\n");
            FF_DEBUG_FLUSH();
        } else {
            FF_DEBUG_CLEANUP("Skipping StopSim (not in simulation mode)\n");
            FF_DEBUG_FLUSH();
        }

        // Cleanup particle system
        FF_DEBUG_CLEANUP("Unloading particle system...\n");
        FF_DEBUG_FLUSH();
        DrawableParticleSys::UnloadParameters();
        FF_DEBUG_CLEANUP("Particle system unloaded.\n");
        FF_DEBUG_FLUSH();
    }

    // Cleanup D3D/DXEngine
    if (g_graphicsInitialized) {
        FF_DEBUG_CLEANUP("Releasing DXEngine...\n");
        FF_DEBUG_FLUSH();
        TheDXEngine.Release();
        g_graphicsInitialized = false;
        FF_DEBUG_CLEANUP("DXEngine released.\n");
        FF_DEBUG_FLUSH();
    }

    // Release D3D interfaces
    FF_DEBUG_CLEANUP("Releasing D3D interfaces...\n");
    FF_DEBUG_FLUSH();
    if (g_pD3DDevice) {
        g_pD3DDevice->Release();
        g_pD3DDevice = nullptr;
    }
    if (g_pRenderTarget) {
        g_pRenderTarget->Release();
        g_pRenderTarget = nullptr;
    }
    if (g_pD3D) {
        g_pD3D->Release();
        g_pD3D = nullptr;
    }
    FF_DEBUG_CLEANUP("D3D interfaces released.\n");
    FF_DEBUG_FLUSH();

    // Cleanup audio
    FF_DEBUG_CLEANUP("Cleaning up audio...\n");
    FF_DEBUG_FLUSH();
    if (g_alContext) {
        alcMakeContextCurrent(nullptr);
        alcDestroyContext(g_alContext);
        g_alContext = nullptr;
    }
    if (g_alDevice) {
        alcCloseDevice(g_alDevice);
        g_alDevice = nullptr;
    }
    FF_DEBUG_CLEANUP("Audio cleaned up.\n");
    FF_DEBUG_FLUSH();

    // Cleanup SDL joystick
    FF_DEBUG_CLEANUP("Closing SDL joystick...\n");
    FF_DEBUG_FLUSH();
    CleanupSDLJoystick();
    FF_DEBUG_CLEANUP("SDL joystick closed.\n");
    FF_DEBUG_FLUSH();

    // Cleanup SDL
    FF_DEBUG_CLEANUP("Quitting SDL...\n");
    FF_DEBUG_FLUSH();
    SDL_Quit();
    FF_DEBUG_CLEANUP("SDL quit.\n");
    FF_DEBUG_FLUSH();

    // Cleanup resource manager
    FF_DEBUG_CLEANUP("Cleaning up resource manager...\n");
    FF_DEBUG_FLUSH();
    ResExit();
    FF_DEBUG_CLEANUP("Resource manager cleaned up.\n");
    FF_DEBUG_FLUSH();

    FF_DEBUG_CLEANUP("Cleanup complete!\n");
    FF_DEBUG_FLUSH();
}

// Convert SDL events to Windows-style messages
static void handle_sdl_events(void) {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        switch (event.type) {
            case SDL_QUIT:
                g_running = false;
                PostGameMessage(WM_QUIT, 0, 0);
                break;

            case SDL_KEYDOWN:
                if (event.key.keysym.sym == SDLK_ESCAPE) {
                    g_running = false;
                }
                if (event.key.keysym.sym == SDLK_F5 && doUI && !g_autoTestInstantAction) {
                    // F5: Quick-launch Instant Action (bypasses UI clicking)
                    fprintf(stderr, "[F5] Launching Instant Action...\n");
                    g_autoTestInstantAction = true;
                    strcpy(gUI_CampaignFile, "Instant");
                    PostGameMessage(FM_LOAD_CAMPAIGN, 0, game_InstantAction);
                }
                if (event.key.keysym.sym == SDLK_F11) {
                    // Toggle fullscreen
                    Uint32 flags = SDL_GetWindowFlags(g_SDLWindow);
                    if (flags & SDL_WINDOW_FULLSCREEN_DESKTOP) {
                        SDL_SetWindowFullscreen(g_SDLWindow, 0);
                    } else {
                        SDL_SetWindowFullscreen(g_SDLWindow, SDL_WINDOW_FULLSCREEN_DESKTOP);
                    }
                }
                // Shift+Numpad: cockpit panel switching (sim mode only)
                if (!doUI && (event.key.keysym.mod & KMOD_SHIFT)) {
                    switch (event.key.keysym.sym) {
                        case SDLK_KP_8: g_requestedPanel = 1100; break; // Front
                        case SDLK_KP_4: g_requestedPanel = 600;  break; // Left
                        case SDLK_KP_6: g_requestedPanel = 700;  break; // Right
                        case SDLK_KP_2: g_requestedPanel = 100;  break; // Down
                        default: break;
                    }
                }
                // Post keyboard message with DIK scancode translation
                {
                    int dikCode = ConvertSDLToDIK(event.key.keysym.scancode);
                    if (dikCode != 0) {
                        PostGameMessage(WM_KEYDOWN, dikCode, 0);
                        FF_PushKeyEvent(dikCode, true);
                    }
                }
                break;

            case SDL_KEYUP:
                {
                    int dikCode = ConvertSDLToDIK(event.key.keysym.scancode);
                    if (dikCode != 0) {
                        PostGameMessage(WM_KEYUP, dikCode, 0);
                        FF_PushKeyEvent(dikCode, false);
                    }
                }
                break;

            case SDL_MOUSEBUTTONDOWN:
                {
                    int x = event.button.x;
                    int y = event.button.y;
                    // Handle fallback menu clicks
                    if (g_useFallbackMenu && doUI && event.button.button == SDL_BUTTON_LEFT) {
                        HandleFallbackMenuClick(x, y);
                        if (!g_running) {
                            return;
                        }
                    } else if (!doUI) {
                        // FF_LINUX: In sim mode, push to mouse event buffer for OnSimMouseInput
                        DWORD ofs = 0;
                        if (event.button.button == SDL_BUTTON_LEFT)   ofs = DIMOFS_BUTTON0;
                        else if (event.button.button == SDL_BUTTON_RIGHT)  ofs = DIMOFS_BUTTON1;
                        else if (event.button.button == SDL_BUTTON_MIDDLE) ofs = DIMOFS_BUTTON2;
                        else if (event.button.button == SDL_BUTTON_X1)     ofs = DIMOFS_BUTTON3;
                        if (ofs) FF_PushMouseEvent(ofs, 0x80);  // 0x80 = pressed
                    } else {
                        int scaledX = x * 1024 / WINDOW_WIDTH;
                        int scaledY = y * 768 / WINDOW_HEIGHT;
                        if (event.button.button == SDL_BUTTON_LEFT) {
                            PostGameMessage(WM_LBUTTONDOWN, 0, MAKELPARAM(scaledX, scaledY));
                        } else if (event.button.button == SDL_BUTTON_RIGHT) {
                            PostGameMessage(WM_RBUTTONDOWN, 0, MAKELPARAM(scaledX, scaledY));
                        }
                    }
                }
                break;

            case SDL_MOUSEBUTTONUP:
                {
                    int x = event.button.x;
                    int y = event.button.y;
                    if (!doUI) {
                        // FF_LINUX: In sim mode, push to mouse event buffer for OnSimMouseInput
                        DWORD ofs = 0;
                        if (event.button.button == SDL_BUTTON_LEFT)   ofs = DIMOFS_BUTTON0;
                        else if (event.button.button == SDL_BUTTON_RIGHT)  ofs = DIMOFS_BUTTON1;
                        else if (event.button.button == SDL_BUTTON_MIDDLE) ofs = DIMOFS_BUTTON2;
                        else if (event.button.button == SDL_BUTTON_X1)     ofs = DIMOFS_BUTTON3;
                        if (ofs) FF_PushMouseEvent(ofs, 0x00);  // 0x00 = released
                    } else if (!g_useFallbackMenu) {
                        int scaledX = x * 1024 / WINDOW_WIDTH;
                        int scaledY = y * 768 / WINDOW_HEIGHT;
                        if (event.button.button == SDL_BUTTON_LEFT) {
                            PostGameMessage(WM_LBUTTONUP, 0, MAKELPARAM(scaledX, scaledY));
                        } else if (event.button.button == SDL_BUTTON_RIGHT) {
                            PostGameMessage(WM_RBUTTONUP, 0, MAKELPARAM(scaledX, scaledY));
                        }
                    }
                }
                break;

            case SDL_MOUSEMOTION:
                {
                    int x = event.motion.x;
                    int y = event.motion.y;
                    if (!doUI) {
                        // FF_LINUX: In sim mode, push relative motion to mouse event buffer
                        if (event.motion.xrel != 0)
                            FF_PushMouseEvent(DIMOFS_X, (DWORD)(int)event.motion.xrel);
                        if (event.motion.yrel != 0)
                            FF_PushMouseEvent(DIMOFS_Y, (DWORD)(int)event.motion.yrel);
                    } else if (g_useFallbackMenu) {
                        HandleFallbackMenuHover(x, y);
                    } else {
                        int scaledX = x * 1024 / WINDOW_WIDTH;
                        int scaledY = y * 768 / WINDOW_HEIGHT;
                        PostGameMessage(WM_MOUSEMOVE, 0, MAKELPARAM(scaledX, scaledY));
                    }
                }
                break;

            case SDL_MOUSEWHEEL:
                {
                    if (!doUI) {
                        // FF_LINUX: In sim mode, push scroll wheel to mouse event buffer
                        // SDL wheel y>0 = scroll up, y<0 = scroll down
                        // DirectInput DIMOFS_Z uses positive = forward, negative = backward
                        if (event.wheel.y != 0)
                            FF_PushMouseEvent(DIMOFS_Z, (DWORD)(int)(event.wheel.y * 120));
                    }
                }
                break;

            case SDL_WINDOWEVENT:
                switch (event.window.event) {
                    case SDL_WINDOWEVENT_CLOSE:
                        // Window X button clicked
                        g_running = false;
                        PostGameMessage(WM_QUIT, 0, 0);
                        break;
                    case SDL_WINDOWEVENT_RESIZED:
                        glViewport(0, 0, event.window.data1, event.window.data2);
                        PostGameMessage(WM_SIZE, 0, MAKELPARAM(event.window.data1, event.window.data2));
                        break;
                    default:
                        break;
                }
                break;

            // Joystick events - update IO structure directly
            case SDL_JOYAXISMOTION:
                if (event.jaxis.which == g_JoystickIndex && event.jaxis.axis < 16) {
                    g_JoystickAxes[event.jaxis.axis] = event.jaxis.value;
                    // Update IO structure based on axis mapping
                    // Axis 0: Roll, Axis 1: Pitch, Axis 2: Throttle, Axis 3: Yaw
                    int axisVal = event.jaxis.value * 10000 / 32767;
                    switch (event.jaxis.axis) {
                        case 0:  // Roll (X)
                            IO.analog[AXIS_ROLL].ioVal = axisVal;
                            IO.analog[AXIS_ROLL].engrValue = (float)axisVal / 10000.0f;
                            IO.analog[AXIS_ROLL].isUsed = true;
                            break;
                        case 1:  // Pitch (Y)
                            IO.analog[AXIS_PITCH].ioVal = axisVal;
                            IO.analog[AXIS_PITCH].engrValue = (float)axisVal / 10000.0f;
                            IO.analog[AXIS_PITCH].isUsed = true;
                            break;
                        case 2:  // Throttle (Z) - unipolar
                            {
                                int throttleVal = (32767 - event.jaxis.value) * 15000 / 65535;
                                IO.analog[AXIS_THROTTLE].ioVal = throttleVal;
                                IO.analog[AXIS_THROTTLE].engrValue = (float)throttleVal / 15000.0f;
                                IO.analog[AXIS_THROTTLE].isUsed = true;
                            }
                            break;
                        case 3:  // Yaw (Rz)
                            IO.analog[AXIS_YAW].ioVal = axisVal;
                            IO.analog[AXIS_YAW].engrValue = (float)axisVal / 10000.0f;
                            IO.analog[AXIS_YAW].isUsed = true;
                            break;
                    }
                }
                break;

            case SDL_JOYBUTTONDOWN:
                if (event.jbutton.which == g_JoystickIndex && event.jbutton.button < SIMLIB_MAX_DIGITAL) {
                    IO.digital[event.jbutton.button] = TRUE;
                }
                break;

            case SDL_JOYBUTTONUP:
                if (event.jbutton.which == g_JoystickIndex && event.jbutton.button < SIMLIB_MAX_DIGITAL) {
                    IO.digital[event.jbutton.button] = FALSE;
                }
                break;

            case SDL_JOYHATMOTION:
                if (event.jhat.which == g_JoystickIndex && event.jhat.hat < SIMLIB_MAX_POV) {
                    IO.povHatAngle[event.jhat.hat] = ConvertSDLHatToPOV(event.jhat.value);
                }
                break;

            case SDL_JOYDEVICEADDED:
                FF_DEBUG_JOYSTICK("Device added: %d\n", event.jdevice.which);
                if (g_SDLJoystick == nullptr) {
                    // Try to open the newly connected joystick
                    InitSDLJoystick();
                }
                break;

            case SDL_JOYDEVICEREMOVED:
                FF_DEBUG_JOYSTICK("Device removed: %d\n", event.jdevice.which);
                if (event.jdevice.which == g_JoystickIndex) {
                    // Our joystick was disconnected
                    CleanupSDLJoystick();
                }
                break;
        }
    }
}

// Helper to queue a message for posting after message processing (avoids deadlock)
static void QueuePendingMessage(UINT msg, WPARAM wParam, LPARAM lParam) {
    g_pendingMessages.push_back({msg, wParam, lParam});
}

// Process game messages (FM_* messages from falcuser.h)
bool ProcessGameMessages() {
    // First, process pending messages that were queued during previous processing
    if (!g_pendingMessages.empty()) {
        std::lock_guard<std::mutex> lock(g_messageMutex);
        for (const auto& msg : g_pendingMessages) {
            g_messageQueue.push(msg);
        }
        g_pendingMessages.clear();
    }

    // Now process the queue
    std::vector<GameMessage> messagesToProcess;
    {
        std::lock_guard<std::mutex> lock(g_messageMutex);
        while (!g_messageQueue.empty()) {
            messagesToProcess.push_back(g_messageQueue.front());
            g_messageQueue.pop();
        }
    }

    // Process messages without holding the lock
    for (const auto& msg : messagesToProcess) {
        // Handle game-specific messages
        switch (msg.message) {
            case WM_QUIT:
                return false;

            case FM_START_GAME:
                fprintf(stderr, "[FM] FM_START_GAME received\n");
                // SystemLevelInit is handled by init_game_core()
                // Send FM_START_UI to start the UI (queue it to avoid deadlock)
                QueuePendingMessage(FM_START_UI, 0, 0);
                break;

            case FM_START_UI:
                fprintf(stderr, "[FM] FM_START_UI received\n");
                // FF_LINUX: Restore OS cursor for UI mode
                SDL_SetRelativeMouseMode(SDL_FALSE);
                // Re-acquire GL context on main thread if sim was running
                if (!doUI) {
                    FF_AcquireGLContext();
                    fprintf(stderr, "[FM] Main thread re-acquired GL context\n");
                }
                TheCampaign.Suspend();
                if (msg.wParam) {
                    g_theaters.DoSoundSetup();
                }
                FalconLocalSession->SetFlyState(FLYSTATE_IN_UI);
                doUI = TRUE;
                fprintf(stderr, "[FM] Calling UI_Startup()...\n");
                UI_Startup();
                TheCampaign.Resume();
                fprintf(stderr, "[FM] UI_Startup() complete\n");
                break;

            case FM_END_UI:
                fprintf(stderr, "[FM] FM_END_UI received\n");
                doUI = FALSE;
                TheCampaign.Suspend();
                UI_Cleanup();
                TheCampaign.Resume();
                break;

            case FM_TIMER_UPDATE:
                // Called periodically to update the UI
                // On Linux, we handle Update/CopyToPrimary directly here instead of
                // using the background OutputLoop thread (which is disabled on Linux).
                if (gMainHandler != nullptr) {
                    gMainHandler->ProcessUserCallbacks();
                    // Trigger a full screen refresh
                    UI95_RECT fullRect = { 0, 0, gMainHandler->GetW(), gMainHandler->GetH() };
                    gMainHandler->RefreshAll(&fullRect);
                    // Draw windows to the Front_ buffer
                    gMainHandler->Update();
                    // Copy from Front_ to Primary_ surface
                    gMainHandler->CopyToPrimary();
                }
                break;

            case FM_EXIT_GAME:
                fprintf(stderr, "[FM] FM_EXIT_GAME received\n");
                g_running = false;
                return false;

            // FM_DISP_ENTER_MODE is not needed on Linux - EnterMode directly calls _EnterMode
            // FM_DISP_LEAVE_MODE is also not needed on Linux

            // =========================================================
            // Campaign loading / joining / shutdown
            // =========================================================
            case FM_LOAD_CAMPAIGN:
            {
                fprintf(stderr, "[FM] FM_LOAD_CAMPAIGN received (type=%ld)\n", (long)msg.lParam);
                // For non-campaign/TE types, use "Instant" as campaign file
                if ((FalconGameType)msg.lParam != game_Campaign &&
                    (FalconGameType)msg.lParam != game_TacticalEngagement) {
                    strcpy(gUI_CampaignFile, "Instant");
                }
                fprintf(stderr, "[FM] FM_LOAD_CAMPAIGN: Calling TheCampaign.LoadCampaign()...\n");
                int retval = TheCampaign.LoadCampaign((FalconGameType)msg.lParam, gUI_CampaignFile);
                fprintf(stderr, "[FM] FM_LOAD_CAMPAIGN: LoadCampaign() returned %d\n", retval);
                if (retval) {
                    fprintf(stderr, "[FM] FM_LOAD_CAMPAIGN: Queueing FM_JOIN_SUCCEEDED\n");
                    QueuePendingMessage(FM_JOIN_SUCCEEDED, 0, 0);
                } else {
                    fprintf(stderr, "[FM] FM_LOAD_CAMPAIGN: Queueing FM_JOIN_FAILED\n");
                    QueuePendingMessage(FM_JOIN_FAILED, 0, 0);
                }
                break;
            }

            case FM_JOIN_SUCCEEDED:
                fprintf(stderr, "[FM] FM_JOIN_SUCCEEDED received\n");
                CampaignJoinSuccess();
                if (!gMainHandler) {
                    QueuePendingMessage(FM_START_UI, 0, 0);
                }
                // TEST: Auto-start instant action if triggered by test code
                if (g_autoTestInstantAction) {
                    g_autoTestInstantAction = false;
                    fprintf(stderr, "[TEST] Campaign joined, now posting FM_START_INSTANTACTION...\n");
                    QueuePendingMessage(FM_START_INSTANTACTION, 0, 0);
                }
                break;

            case FM_JOIN_FAILED:
                fprintf(stderr, "[FM] FM_JOIN_FAILED received\n");
                CampaignJoinFail();
                break;

            case FM_SHUTDOWN_CAMPAIGN:
                fprintf(stderr, "[FM] FM_SHUTDOWN_CAMPAIGN received\n");
                ShutdownCampaign();
                break;

            case FM_AUTOSAVE_CAMPAIGN:
                fprintf(stderr, "[FM] FM_AUTOSAVE_CAMPAIGN received\n");
                CampaignAutoSave((FalconGameType)msg.lParam);
                break;

            case FM_ONLINE_STATUS:
                if (doUI && gMainHandler) {
                    UI_CommsErrorMessage(static_cast<WORD>(msg.wParam));
                }
                break;

            case FM_GOT_CAMPAIGN_DATA:
                fprintf(stderr, "[FM] FM_GOT_CAMPAIGN_DATA received (wParam=%lu)\n",
                        (unsigned long)msg.wParam);
                // Handle campaign data based on what we received
                if (msg.wParam == CAMP_NEED_PRELOAD && FalconLocalGame) {
                    CampaignPreloadSuccess(!FalconLocalGame->IsLocal());
                }
                break;

            // =========================================================
            // Sim entry: start flying
            // =========================================================
            case FM_START_INSTANTACTION:
                fprintf(stderr, "[FM] FM_START_INSTANTACTION received\n");
                fflush(stderr);
                fprintf(stderr, "[FM] Calling SetFlyState...\n");
                fflush(stderr);
                FalconLocalSession->SetFlyState(FLYSTATE_LOADING);
                fprintf(stderr, "[FM] Calling set_campaign_time (start_time will be %ld)...\n",
                        instant_action::get_start_time());
                fflush(stderr);
                instant_action::set_campaign_time();
                fprintf(stderr, "[FM] After set_campaign_time: vuxGameTime=%u\n",
                        (unsigned)vuxGameTime);
                fflush(stderr);
                fprintf(stderr, "[FM] Calling move_player_flight...\n");
                fflush(stderr);
                instant_action::move_player_flight();
                fprintf(stderr, "[FM] Calling create_wave...\n");
                fflush(stderr);
                instant_action::create_wave();
                fprintf(stderr, "[FM] Starting instant action... vuxRealTime=%lu\n",
                        (unsigned long)vuxRealTime);
                fflush(stderr);
                // CRITICAL ORDER:
                // 1. StartGraphics() - signals sim thread to start graphics (just sets a flag)
                // 2. Release GL context - sim thread will need it when StartLoop() wakes up
                // 3. EndUI() - may block in TheCampaign.Suspend(), so must be last
                fprintf(stderr, "[FM] Calling StartGraphics()...\n");
                fflush(stderr);
                SimulationLoopControl::StartGraphics();
                fprintf(stderr, "[FM] StartGraphics() returned, releasing GL context...\n");
                fflush(stderr);
                FF_ReleaseGLContext();
                fprintf(stderr, "[FM] GL context released, calling EndUI()...\n");
                fflush(stderr);
                EndUI();
                // FF_LINUX: Hide OS cursor and grab mouse for sim mode
                SDL_SetRelativeMouseMode(SDL_TRUE);
                fprintf(stderr, "[FM] EndUI() returned, relative mouse mode ON\n");
                fflush(stderr);
                break;

            case FM_START_DOGFIGHT:
                fprintf(stderr, "[FM] FM_START_DOGFIGHT received\n");
                FalconLocalSession->SetFlyState(FLYSTATE_LOADING);
                // Same critical order as INSTANTACTION
                SimulationLoopControl::StartGraphics();
                FF_ReleaseGLContext();
                EndUI();
                SDL_SetRelativeMouseMode(SDL_TRUE);
                fprintf(stderr, "[FM] Main thread released GL context for sim\n");
                break;

            case FM_START_CAMPAIGN:
                fprintf(stderr, "[FM] FM_START_CAMPAIGN received\n");
                FalconLocalSession->SetFlyState(FLYSTATE_LOADING);
                // Same critical order as INSTANTACTION
                SimulationLoopControl::StartGraphics();
                FF_ReleaseGLContext();
                EndUI();
                SDL_SetRelativeMouseMode(SDL_TRUE);
                break;

            case FM_START_TACTICAL:
                fprintf(stderr, "[FM] FM_START_TACTICAL received\n");
                FalconLocalSession->SetFlyState(FLYSTATE_LOADING);
                // Same critical order as INSTANTACTION
                SimulationLoopControl::StartGraphics();
                FF_ReleaseGLContext();
                EndUI();
                SDL_SetRelativeMouseMode(SDL_TRUE);
                break;

            // =========================================================
            // Sim exit: return to menu
            // =========================================================
            case FM_END_INSTANTACTION:
            case FM_END_DOGFIGHT:
                fprintf(stderr, "[FM] FM_END_INSTANTACTION/DOGFIGHT received\n");
                // These are currently no-ops in Windows too (winmain.cpp:1736-1737)
                break;

            case FM_REVERT_CAMPAIGN:
            {
                fprintf(stderr, "[FM] FM_REVERT_CAMPAIGN received\n");
                int gametype = FalconLocalGame->GetGameType();

                // Game aborted - reload current campaign
                strcpy(gUI_CampaignFile, TheCampaign.SaveFile);
                PostGameMessage(FM_SHUTDOWN_CAMPAIGN, 0, 0);

                if (gametype == game_Campaign) {
                    StartCampaignGame(1, gametype);
                } else if (gametype == game_TacticalEngagement) {
                    tactical_restart_mission();
                }
                break;
            }

            // Route mouse and keyboard events to the UI handler
            case WM_LBUTTONDOWN:
                if (gMainHandler != nullptr) {
                    static int lbdCount = 0;
                    lbdCount++;
                    if (lbdCount <= 5) {
                        fprintf(stderr, "[Mouse] LBUTTONDOWN at (%d, %d)\n",
                                LOWORD(msg.lParam), HIWORD(msg.lParam));
                    }
                    gMainHandler->EventHandler(NULL, msg.message, msg.wParam, msg.lParam);
                }
                break;
            case WM_LBUTTONUP:
                if (gMainHandler != nullptr) {
                    static int lbuCount = 0;
                    lbuCount++;
                    gMainHandler->EventHandler(NULL, msg.message, msg.wParam, msg.lParam);
                }
                break;
            case WM_RBUTTONDOWN:
            case WM_RBUTTONUP:
            case WM_MOUSEMOVE:
            case WM_KEYDOWN:
            case WM_KEYUP:
                if (gMainHandler != nullptr) {
                    gMainHandler->EventHandler(NULL, msg.message, msg.wParam, msg.lParam);
                }
                break;

            default:
                // Message not handled - that's okay for many messages
                break;
        }
    }
    return true;
}

static void render_frame(void) {
    // Use fallback menu if enabled (temporary workaround for UI95 issues)
    if (g_useFallbackMenu && doUI) {
        glClear(GL_COLOR_BUFFER_BIT);
        DrawFallbackMenu();
        SDL_GL_SwapWindow(g_SDLWindow);
        return;
    }

    // When in UI mode (doUI=1), the UI has been drawn to the primary DirectDraw surface
    // We need to present that surface via OpenGL
    if (doUI) {
        FF_PresentPrimarySurface();
        SDL_GL_SwapWindow(g_SDLWindow);
    } else if (g_simOwnsGLContext) {
        // Sim mode: the sim thread owns the GL context and handles rendering.
        // The main thread has no GL access. Just pump messages and events.
        // Don't call any GL functions here - the context belongs to the sim thread.
        return;
    }
    // If neither doUI nor g_simOwnsGLContext, this is a transitional state - just return
}

static void main_loop(void) {
    fprintf(stderr, "\n========================================\n");
    fprintf(stderr, "Entering main loop\n");
    fprintf(stderr, "  ESC = quit, Click X to close\n");
    fprintf(stderr, "========================================\n\n");

    Uint32 frameCount = 0;
    Uint32 lastFPSTime = SDL_GetTicks();
    Uint32 lastTimerTime = SDL_GetTicks();
    const Uint32 targetFrameTime = 16;  // ~60 FPS cap
    const Uint32 timerUpdateInterval = 100; // UI timer update interval in ms
    int fpsReportCounter = 0;

    // Post FM_START_GAME to trigger the game initialization sequence
    // This will internally call FM_START_UI which starts the UI
    fprintf(stderr, "[Main] Posting FM_START_GAME to initialize game...\n");
    PostGameMessage(FM_START_GAME, 0, 0);

    // TEST: Auto-launch instant action after delay for testing
    // Set to 0 to disable auto-launch (user can click buttons normally)
    // Use -test-ia command line option to enable (3 second delay)
    Uint32 autoLaunchTime = g_testInstantActionFlag ? 3000 : 0;
    bool autoLaunchTriggered = false;
    Uint32 startTime = SDL_GetTicks();

    while (g_running) {
        Uint32 frameStart = SDL_GetTicks();

        // Handle SDL events and convert to game messages
        handle_sdl_events();

        // Check if we should exit after event handling
        if (!g_running) {
            fprintf(stderr, "[main_loop] g_running set to false, breaking out of loop\n");
            fflush(stderr);
            break;
        }

        // Process game message queue
        if (!ProcessGameMessages()) {
            break;
        }

        // Send periodic timer updates for the UI system
        Uint32 currentTime = SDL_GetTicks();
        if (currentTime - lastTimerTime >= timerUpdateInterval) {
            PostGameMessage(FM_TIMER_UPDATE, 0, 0);
            lastTimerTime = currentTime;
        }

        // TEST: Auto-launch instant action after delay
        if (autoLaunchTime > 0 && !autoLaunchTriggered && doUI &&
            (currentTime - startTime) >= autoLaunchTime) {
            autoLaunchTriggered = true;
            g_autoTestInstantAction = true;  // Flag to trigger FM_START_INSTANTACTION after join
            fprintf(stderr, "\n============================================\n");
            fprintf(stderr, "[TEST] Auto-launching Instant Action...\n");
            fprintf(stderr, "============================================\n\n");

            // Set up for instant action - mirror what InstantActionFlyCB does
            strcpy(gUI_CampaignFile, "Instant");

            // Set start time to noon (43200 seconds = 12:00:00)
            // This is what the IA setup screen does in instant.cpp:678
            instant_action::set_start_time(static_cast<long>(12.0f * 60.0f * 60.0f));
            fprintf(stderr, "[TEST] Set IA start_time to %ld (noon)\n",
                    instant_action::get_start_time());

            // Load the instant action campaign
            fprintf(stderr, "[TEST] Posting FM_LOAD_CAMPAIGN (game_InstantAction)...\n");
            PostGameMessage(FM_LOAD_CAMPAIGN, 0, game_InstantAction);
        }

        // Render frame
        render_frame();
        frameCount++;

        // FPS counter - only print every 5 seconds to reduce spam
        if (currentTime - lastFPSTime >= 5000) {
            fpsReportCounter++;
            // Only print periodically, don't use \r which causes terminal issues
            if (fpsReportCounter <= 3) {
                fprintf(stderr, "FPS: %u (avg over 5 sec), doUI=%d, gMainHandler=%p\n",
                       frameCount / 5, doUI, (void*)gMainHandler);
            }
            frameCount = 0;
            lastFPSTime = currentTime;
        }

        // Automatic UI screen test
        // Tests that UI screens can load correctly
        // Note: Only tests ONE screen per run since clicking a button changes the active screen
        static bool screenTestDone = false;
        // Automatic UI tests disabled - use manual testing
        // (The test code was automatically clicking Setup button after 3 seconds)

        // Auto view cycling during -test-ia for cockpit panel testing
        // Tests all cockpit panels: front(1100), left(600), right(700), down(100)
        if (g_testInstantActionFlag && !doUI) {
            static Uint32 simStartTime = 0;
            static int viewPhase = 0;
            if (simStartTime == 0) simStartTime = currentTime;
            Uint32 simElapsed = currentTime - simStartTime;

            struct ViewTestStep {
                Uint32 timeMs;
                int viewMode;     // -1=no change, 0=HUD, 1=cockpit
                int panel;        // -1=no change, panel ID otherwise
                const char* screenshotFile; // NULL=no screenshot
                const char* desc;
            };
            static const ViewTestStep steps[] = {
                {  3000, 1, 1100, NULL,                       "Cockpit front panel" },
                {  6000, -1, -1, "/tmp/ff_pit_front.bmp",     "Screenshot front" },
                {  8000, -1, 600, NULL,                       "Left panel" },
                { 11000, -1, -1, "/tmp/ff_pit_left.bmp",      "Screenshot left" },
                { 13000, -1, 700, NULL,                       "Right panel" },
                { 16000, -1, -1, "/tmp/ff_pit_right.bmp",     "Screenshot right" },
                { 18000, -1, 100, NULL,                       "Down panel" },
                { 21000, -1, -1, "/tmp/ff_pit_down.bmp",      "Screenshot down" },
                { 23000, 0, -1, NULL,                         "HUD-only view" },
                { 26000, -1, -1, "/tmp/ff_view_hud.bmp",      "Screenshot HUD" },
                { 28000, 3, -1, NULL,                         "Orbit view" },
                { 31000, -1, -1, "/tmp/ff_view_orbit.bmp",    "Screenshot orbit" },
                { 33000, 1, 1100, NULL,                       "Back to cockpit front" },
            };
            static const int numSteps = sizeof(steps) / sizeof(steps[0]);

            if (viewPhase < numSteps && simElapsed >= steps[viewPhase].timeMs) {
                const ViewTestStep& s = steps[viewPhase];
                fprintf(stderr, "[VIEW_TEST] Phase %d: %s\n", viewPhase, s.desc);
                if (s.viewMode >= 0) g_requestedViewMode = s.viewMode;
                if (s.panel >= 0) g_requestedPanel = s.panel;
                if (s.screenshotFile) {
                    g_screenshotFilename = s.screenshotFile;
                    g_screenshotRequest = 1;
                }
                viewPhase++;
            }
        }

        // Simple frame rate limiting
        Uint32 frameTime = SDL_GetTicks() - frameStart;
        if (frameTime < targetFrameTime) {
            SDL_Delay(targetFrameTime - frameTime);
        }
    }

    fprintf(stderr, "\n[main_loop] Exiting main loop...\n");
    fflush(stderr);
}

int main(int argc, char** argv) {
    const char* dataDir = DEFAULT_DATA_DIR;
    bool fullscreen = false;
    bool enableSound = true;

    printf("========================================\n");
    printf("%s %s\n", FREE_FALCON_BRAND, FREE_FALCON_VERSION);
    printf("%s\n", FREE_FALCON_PROJECT);
    printf("Build: %s %s\n", __DATE__, __TIME__);
    printf("========================================\n\n");

    // Set up signal handlers for clean window cleanup on kill
    setup_signal_handlers();

    // Note: X11 error handling is handled by SDL2 internally.
    // GLX context errors are caught by SDL and don't cause crashes.

    // Check for data directory environment variable
    const char* envDataDir = getenv("FF_DATA_DIR");
    if (envDataDir) {
        dataDir = envDataDir;
    }

    // Parse command line arguments
    bool testInstantAction = false;  // Auto-launch instant action for testing
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-d") == 0 && i + 1 < argc) {
            dataDir = argv[++i];
        } else if (strcmp(argv[i], "-f") == 0) {
            fullscreen = true;
        } else if (strcmp(argv[i], "-w") == 0) {
            fullscreen = false;
        } else if (strcmp(argv[i], "-nosound") == 0) {
            enableSound = false;
        } else if (strcmp(argv[i], "-test-ia") == 0 || strcmp(argv[i], "--test-instant-action") == 0) {
            testInstantAction = true;
            fprintf(stderr, "[TEST] Auto-launch Instant Action enabled (3 second delay)\n");
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }

    // Export testInstantAction flag for use in main loop
    extern bool g_testInstantActionFlag;
    g_testInstantActionFlag = testInstantAction;

    // Require a data directory
    if (!dataDir) {
        fprintf(stderr, "\nError: No game data directory specified.\n");
        fprintf(stderr, "Use -d /path/to/FreeFalcon6 or set FF_DATA_DIR.\n\n");
        print_usage(argv[0]);
        return 1;
    }

    // Initialize data directory
    if (!init_data_directory(dataDir)) {
        fprintf(stderr, "\nFailed to initialize data directory.\n");
        fprintf(stderr, "Make sure the game data is at: %s\n", dataDir);
        fprintf(stderr, "Or specify a different path with: %s -d /path/to/FreeFalcon6\n", argv[0]);
        fprintf(stderr, "You can also set the FF_DATA_DIR environment variable.\n");
        return 1;
    }

    // Change to data directory
    if (chdir(FalconDataDirectory) != 0) {
        fprintf(stderr, "Warning: Could not change to data directory\n");
    }

    // Initialize game paths
    fprintf(stderr, "[TRACE] About to call init_game_paths\n"); fflush(stderr);
    if (!init_game_paths()) {
        fprintf(stderr, "Failed to set up game paths\n");
        return 1;
    }
    fprintf(stderr, "[TRACE] init_game_paths completed\n"); fflush(stderr);

    // Initialize resource manager
    fprintf(stderr, "[TRACE] About to call init_resource_manager\n"); fflush(stderr);
    if (!init_resource_manager()) {
        fprintf(stderr, "Warning: Resource manager initialization issues\n");
    }
    fprintf(stderr, "[TRACE] init_resource_manager completed\n"); fflush(stderr);

    // Initialize SDL2
    fprintf(stderr, "[TRACE] About to call init_sdl\n"); fflush(stderr);
    if (!init_sdl(fullscreen)) {
        fprintf(stderr, "Failed to initialize SDL2\n");
        return 1;
    }
    fprintf(stderr, "[TRACE] init_sdl completed\n"); fflush(stderr);

    // Initialize OpenGL
    fprintf(stderr, "[TRACE] About to call init_opengl\n"); fflush(stderr);
    if (!init_opengl()) {
        fprintf(stderr, "Failed to initialize OpenGL\n");
        cleanup();
        return 1;
    }
    fprintf(stderr, "[TRACE] init_opengl completed\n"); fflush(stderr);

    // Initialize OpenAL (optional - continue if fails)
    if (enableSound) {
        init_openal();
    }

    // Initialize game core systems first (needed for DXEngine)
    fprintf(stderr, "[main] Calling init_game_core...\n");
    if (!init_game_core()) {
        fprintf(stderr, "Warning: Some game systems failed to initialize\n");
        // Continue anyway to show the window
    }
    fprintf(stderr, "[main] init_game_core() returned\n");

    // Initialize D3D7-to-OpenGL graphics layer (after game core is ready)
    fprintf(stderr, "[main] Calling init_d3d_graphics...\n");
    if (!init_d3d_graphics()) {
        fprintf(stderr, "Failed to initialize D3D graphics layer\n");
        // Continue with test rendering
    }
    fprintf(stderr, "[main] init_d3d_graphics() returned\n");

    fprintf(stderr, "\n========================================\n");
    fprintf(stderr, "Initialization complete!\n");
    fprintf(stderr, "========================================\n");

    // Run main loop
    fprintf(stderr, "[main] Entering main_loop...\n");
    main_loop();

    // Cleanup
    cleanup();

    printf("Goodbye!\n");
    return 0;
}
