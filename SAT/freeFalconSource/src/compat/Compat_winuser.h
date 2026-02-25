/*
 * FreeFalcon Linux Port - winuser.h compatibility
 *
 * Windows User Interface function stubs - will be replaced by SDL2
 */

#ifndef FF_COMPAT_WINUSER_H
#define FF_COMPAT_WINUSER_H

#ifdef FF_LINUX

#include "compat_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Window Messages
 * ============================================================ */

#define WM_NULL             0x0000
#define WM_CREATE           0x0001
#define WM_DESTROY          0x0002
#define WM_MOVE             0x0003
#define WM_SIZE             0x0005
#define WM_ACTIVATE         0x0006
#define WM_SETFOCUS         0x0007
#define WM_KILLFOCUS        0x0008
#define WM_ENABLE           0x000A
#define WM_SETREDRAW        0x000B
#define WM_SETTEXT          0x000C
#define WM_GETTEXT          0x000D
#define WM_GETTEXTLENGTH    0x000E
#define WM_PAINT            0x000F
#define WM_CLOSE            0x0010
#define WM_QUIT             0x0012
#define WM_ERASEBKGND       0x0014
#define WM_SHOWWINDOW       0x0018
#define WM_ACTIVATEAPP      0x001C
#define WM_SETCURSOR        0x0020
#define WM_MOUSEACTIVATE    0x0021
#define WM_GETMINMAXINFO    0x0024
#define WM_NOTIFY           0x004E
#define WM_KEYDOWN          0x0100
#define WM_KEYUP            0x0101
#define WM_CHAR             0x0102
#define WM_SYSKEYDOWN       0x0104
#define WM_SYSKEYUP         0x0105
#define WM_SYSCHAR          0x0106
#define WM_COMMAND          0x0111
#define WM_SYSCOMMAND       0x0112
#define WM_TIMER            0x0113
#define WM_HSCROLL          0x0114
#define WM_VSCROLL          0x0115
#define WM_INITMENU         0x0116
#define WM_INITMENUPOPUP    0x0117
#define WM_MENUSELECT       0x011F
#define WM_MENUCHAR         0x0120
#define WM_ENTERIDLE        0x0121
#define WM_MOUSEMOVE        0x0200
#define WM_LBUTTONDOWN      0x0201
#define WM_LBUTTONUP        0x0202
#define WM_LBUTTONDBLCLK    0x0203
#define WM_RBUTTONDOWN      0x0204
#define WM_RBUTTONUP        0x0205
#define WM_RBUTTONDBLCLK    0x0206
#define WM_MBUTTONDOWN      0x0207
#define WM_MBUTTONUP        0x0208
#define WM_MBUTTONDBLCLK    0x0209
#define WM_MOUSEWHEEL       0x020A
#define WM_SIZING           0x0214
#define WM_MOVING           0x0216
#define WM_ENTERSIZEMOVE    0x0231
#define WM_EXITSIZEMOVE     0x0232
#define WM_USER             0x0400

/* Listbox Notification Codes */
#define LBN_ERRSPACE        (-2)
#define LBN_SELCHANGE       1
#define LBN_DBLCLK          2
#define LBN_SELCANCEL       3
#define LBN_SETFOCUS        4
#define LBN_KILLFOCUS       5

/* Listbox Messages */
#define LB_ADDSTRING        0x0180
#define LB_INSERTSTRING     0x0181
#define LB_DELETESTRING     0x0182
#define LB_SELITEMRANGEEX   0x0183
#define LB_RESETCONTENT     0x0184
#define LB_SETSEL           0x0185
#define LB_SETCURSEL        0x0186
#define LB_GETSEL           0x0187
#define LB_GETCURSEL        0x0188
#define LB_GETTEXT          0x0189
#define LB_GETTEXTLEN       0x018A
#define LB_GETCOUNT         0x018B
#define LB_SELECTSTRING     0x018C
#define LB_DIR              0x018D
#define LB_GETTOPINDEX      0x018E
#define LB_FINDSTRING       0x018F
#define LB_GETSELCOUNT      0x0190
#define LB_GETSELITEMS      0x0191
#define LB_SETTABSTOPS      0x0192
#define LB_GETHORIZONTALEXTENT 0x0193
#define LB_SETHORIZONTALEXTENT 0x0194
#define LB_SETCOLUMNWIDTH   0x0195
#define LB_ADDFILE          0x0196
#define LB_SETTOPINDEX      0x0197
#define LB_GETITEMRECT      0x0198
#define LB_GETITEMDATA      0x0199
#define LB_SETITEMDATA      0x019A
#define LB_SELITEMRANGE     0x019B
#define LB_SETANCHORINDEX   0x019C
#define LB_GETANCHORINDEX   0x019D
#define LB_SETCARETINDEX    0x019E
#define LB_GETCARETINDEX    0x019F
#define LB_SETITEMHEIGHT    0x01A0
#define LB_GETITEMHEIGHT    0x01A1
#define LB_FINDSTRINGEXACT  0x01A2

/* Keyboard */
#define WM_KEYFIRST         0x0100
#define WM_KEYLAST          0x0109

/* Mouse */
#define WM_MOUSEFIRST       0x0200
#define WM_MOUSELAST        0x020D

/* ============================================================
 * List Box Messages
 * ============================================================ */

#define LB_ADDSTRING        0x0180
#define LB_INSERTSTRING     0x0181
#define LB_DELETESTRING     0x0182
#define LB_SELITEMRANGEEX   0x0183
#define LB_RESETCONTENT     0x0184
#define LB_SETSEL           0x0185
#define LB_SETCURSEL        0x0186
#define LB_GETSEL           0x0187
#define LB_GETCURSEL        0x0188
#define LB_GETTEXT          0x0189
#define LB_GETTEXTLEN       0x018A
#define LB_GETCOUNT         0x018B
#define LB_SELECTSTRING     0x018C
#define LB_DIR              0x018D
#define LB_GETTOPINDEX      0x018E
#define LB_FINDSTRING       0x018F
#define LB_GETSELCOUNT      0x0190
#define LB_GETSELITEMS      0x0191
#define LB_SETTABSTOPS      0x0192
#define LB_GETHORIZONTALEXTENT 0x0193
#define LB_SETHORIZONTALEXTENT 0x0194
#define LB_SETCOLUMNWIDTH   0x0195
#define LB_ADDFILE          0x0196
#define LB_SETTOPINDEX      0x0197
#define LB_GETITEMRECT      0x0198
#define LB_GETITEMDATA      0x0199
#define LB_SETITEMDATA      0x019A
#define LB_SELITEMRANGE     0x019B
#define LB_SETANCHORINDEX   0x019C
#define LB_GETANCHORINDEX   0x019D
#define LB_SETCARETINDEX    0x019E
#define LB_GETCARETINDEX    0x019F
#define LB_SETITEMHEIGHT    0x01A0
#define LB_GETITEMHEIGHT    0x01A1
#define LB_FINDSTRINGEXACT  0x01A2
#define LB_SETLOCALE        0x01A5
#define LB_GETLOCALE        0x01A6
#define LB_SETCOUNT         0x01A7

/* List Box Return Values */
#define LB_OKAY             0
#define LB_ERR              (-1)
#define LB_ERRSPACE         (-2)

/* ============================================================
 * Combo Box Messages
 * ============================================================ */

#define CB_GETEDITSEL       0x0140
#define CB_LIMITTEXT        0x0141
#define CB_SETEDITSEL       0x0142
#define CB_ADDSTRING        0x0143
#define CB_DELETESTRING     0x0144
#define CB_DIR              0x0145
#define CB_GETCOUNT         0x0146
#define CB_GETCURSEL        0x0147
#define CB_GETLBTEXT        0x0148
#define CB_GETLBTEXTLEN     0x0149
#define CB_INSERTSTRING     0x014A
#define CB_RESETCONTENT     0x014B
#define CB_FINDSTRING       0x014C
#define CB_SELECTSTRING     0x014D
#define CB_SETCURSEL        0x014E
#define CB_SHOWDROPDOWN     0x014F
#define CB_GETITEMDATA      0x0150
#define CB_SETITEMDATA      0x0151
#define CB_GETDROPPEDCONTROLRECT 0x0152
#define CB_SETITEMHEIGHT    0x0153
#define CB_GETITEMHEIGHT    0x0154
#define CB_SETEXTENDEDUI    0x0155
#define CB_GETEXTENDEDUI    0x0156
#define CB_GETDROPPEDSTATE  0x0157
#define CB_FINDSTRINGEXACT  0x0158
#define CB_SETLOCALE        0x0159
#define CB_GETLOCALE        0x015A

/* ============================================================
 * Virtual Key Codes
 * ============================================================ */

#define VK_LBUTTON          0x01
#define VK_RBUTTON          0x02
#define VK_CANCEL           0x03
#define VK_MBUTTON          0x04
#define VK_BACK             0x08
#define VK_TAB              0x09
#define VK_CLEAR            0x0C
#define VK_RETURN           0x0D
#define VK_SHIFT            0x10
#define VK_CONTROL          0x11
#define VK_MENU             0x12
#define VK_PAUSE            0x13
#define VK_CAPITAL          0x14
#define VK_ESCAPE           0x1B
#define VK_SPACE            0x20
#define VK_PRIOR            0x21
#define VK_NEXT             0x22
#define VK_END              0x23
#define VK_HOME             0x24
#define VK_LEFT             0x25
#define VK_UP               0x26
#define VK_RIGHT            0x27
#define VK_DOWN             0x28
#define VK_SELECT           0x29
#define VK_PRINT            0x2A
#define VK_EXECUTE          0x2B
#define VK_SNAPSHOT         0x2C
#define VK_INSERT           0x2D
#define VK_DELETE           0x2E
#define VK_HELP             0x2F

/* 0-9, A-Z are same as ASCII */

#define VK_LWIN             0x5B
#define VK_RWIN             0x5C
#define VK_APPS             0x5D
#define VK_NUMPAD0          0x60
#define VK_NUMPAD1          0x61
#define VK_NUMPAD2          0x62
#define VK_NUMPAD3          0x63
#define VK_NUMPAD4          0x64
#define VK_NUMPAD5          0x65
#define VK_NUMPAD6          0x66
#define VK_NUMPAD7          0x67
#define VK_NUMPAD8          0x68
#define VK_NUMPAD9          0x69
#define VK_MULTIPLY         0x6A
#define VK_ADD              0x6B
#define VK_SEPARATOR        0x6C
#define VK_SUBTRACT         0x6D
#define VK_DECIMAL          0x6E
#define VK_DIVIDE           0x6F
#define VK_F1               0x70
#define VK_F2               0x71
#define VK_F3               0x72
#define VK_F4               0x73
#define VK_F5               0x74
#define VK_F6               0x75
#define VK_F7               0x76
#define VK_F8               0x77
#define VK_F9               0x78
#define VK_F10              0x79
#define VK_F11              0x7A
#define VK_F12              0x7B
#define VK_NUMLOCK          0x90
#define VK_SCROLL           0x91
#define VK_LSHIFT           0xA0
#define VK_RSHIFT           0xA1
#define VK_LCONTROL         0xA2
#define VK_RCONTROL         0xA3
#define VK_LMENU            0xA4
#define VK_RMENU            0xA5

/* ============================================================
 * Show Window Commands
 * ============================================================ */

#define SW_HIDE             0
#define SW_SHOWNORMAL       1
#define SW_NORMAL           1
#define SW_SHOWMINIMIZED    2
#define SW_SHOWMAXIMIZED    3
#define SW_MAXIMIZE         3
#define SW_SHOWNOACTIVATE   4
#define SW_SHOW             5
#define SW_MINIMIZE         6
#define SW_SHOWMINNOACTIVE  7
#define SW_SHOWNA           8
#define SW_RESTORE          9
#define SW_SHOWDEFAULT      10
#define SW_FORCEMINIMIZE    11

/* ============================================================
 * Message Box Types
 * ============================================================ */

#define MB_OK                   0x00000000
#define MB_OKCANCEL             0x00000001
#define MB_ABORTRETRYIGNORE     0x00000002
#define MB_YESNOCANCEL          0x00000003
#define MB_YESNO                0x00000004
#define MB_RETRYCANCEL          0x00000005
#define MB_ICONHAND             0x00000010
#define MB_ICONQUESTION         0x00000020
#define MB_ICONEXCLAMATION      0x00000030
#define MB_ICONASTERISK         0x00000040
#define MB_ICONWARNING          MB_ICONEXCLAMATION
#define MB_ICONERROR            MB_ICONHAND
#define MB_ICONINFORMATION      MB_ICONASTERISK
#define MB_ICONSTOP             MB_ICONHAND
#define MB_DEFBUTTON1           0x00000000
#define MB_DEFBUTTON2           0x00000100
#define MB_DEFBUTTON3           0x00000200
#define MB_DEFBUTTON4           0x00000300
#define MB_APPLMODAL            0x00000000
#define MB_SYSTEMMODAL          0x00001000
#define MB_TASKMODAL            0x00002000
#define MB_TOPMOST              0x00040000
#define MB_SETFOREGROUND        0x00010000

/* Message box return values */
#define IDOK        1
#define IDCANCEL    2
#define IDABORT     3
#define IDRETRY     4
#define IDIGNORE    5
#define IDYES       6
#define IDNO        7
#define IDCLOSE     8
#define IDHELP      9

/* ============================================================
 * Class Styles
 * ============================================================ */

#define CS_VREDRAW          0x0001
#define CS_HREDRAW          0x0002
#define CS_DBLCLKS          0x0008
#define CS_OWNDC            0x0020
#define CS_CLASSDC          0x0040
#define CS_PARENTDC         0x0080
#define CS_NOCLOSE          0x0200
#define CS_SAVEBITS         0x0800
#define CS_BYTEALIGNCLIENT  0x1000
#define CS_BYTEALIGNWINDOW  0x2000
#define CS_GLOBALCLASS      0x4000
#define CS_IME              0x00010000
#define CS_DROPSHADOW       0x00020000

/* ============================================================
 * Window Styles
 * ============================================================ */

#define WS_OVERLAPPED       0x00000000
#define WS_POPUP            0x80000000
#define WS_CHILD            0x40000000
#define WS_MINIMIZE         0x20000000
#define WS_VISIBLE          0x10000000
#define WS_DISABLED         0x08000000
#define WS_CLIPSIBLINGS     0x04000000
#define WS_CLIPCHILDREN     0x02000000
#define WS_MAXIMIZE         0x01000000
#define WS_CAPTION          0x00C00000
#define WS_BORDER           0x00800000
#define WS_DLGFRAME         0x00400000
#define WS_VSCROLL          0x00200000
#define WS_HSCROLL          0x00100000
#define WS_SYSMENU          0x00080000
#define WS_THICKFRAME       0x00040000
#define WS_GROUP            0x00020000
#define WS_TABSTOP          0x00010000
#define WS_MINIMIZEBOX      0x00020000
#define WS_MAXIMIZEBOX      0x00010000
#define WS_OVERLAPPEDWINDOW (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
#define WS_POPUPWINDOW      (WS_POPUP | WS_BORDER | WS_SYSMENU)

/* CreateWindow default position/size */
#define CW_USEDEFAULT       ((int)0x80000000)

/* Extended window styles */
#define WS_EX_DLGMODALFRAME     0x00000001
#define WS_EX_TOPMOST           0x00000008
#define WS_EX_ACCEPTFILES       0x00000010
#define WS_EX_TRANSPARENT       0x00000020
#define WS_EX_TOOLWINDOW        0x00000080
#define WS_EX_WINDOWEDGE        0x00000100
#define WS_EX_CLIENTEDGE        0x00000200
#define WS_EX_CONTEXTHELP       0x00000400
#define WS_EX_APPWINDOW         0x00040000

/* ============================================================
 * Structures
 * ============================================================ */

typedef struct tagMSG {
    HWND   hwnd;
    UINT   message;
    WPARAM wParam;
    LPARAM lParam;
    DWORD  time;
    POINT  pt;
} MSG, *PMSG, *LPMSG;

typedef struct tagWNDCLASSA {
    UINT      style;
    LPVOID    lpfnWndProc;  /* WNDPROC */
    int       cbClsExtra;
    int       cbWndExtra;
    HINSTANCE hInstance;
    HICON     hIcon;
    HCURSOR   hCursor;
    HBRUSH    hbrBackground;
    LPCSTR    lpszMenuName;
    LPCSTR    lpszClassName;
} WNDCLASSA, *PWNDCLASSA, *LPWNDCLASSA;

typedef WNDCLASSA WNDCLASS;
typedef PWNDCLASSA PWNDCLASS;
typedef LPWNDCLASSA LPWNDCLASS;

typedef struct tagWNDCLASSEXA {
    UINT      cbSize;
    UINT      style;
    LPVOID    lpfnWndProc;
    int       cbClsExtra;
    int       cbWndExtra;
    HINSTANCE hInstance;
    HICON     hIcon;
    HCURSOR   hCursor;
    HBRUSH    hbrBackground;
    LPCSTR    lpszMenuName;
    LPCSTR    lpszClassName;
    HICON     hIconSm;
} WNDCLASSEXA, *PWNDCLASSEXA, *LPWNDCLASSEXA;

typedef WNDCLASSEXA WNDCLASSEX;
typedef PWNDCLASSEXA PWNDCLASSEX;
typedef LPWNDCLASSEXA LPWNDCLASSEX;

typedef struct tagPAINTSTRUCT {
    HDC  hdc;
    BOOL fErase;
    RECT rcPaint;
    BOOL fRestore;
    BOOL fIncUpdate;
    BYTE rgbReserved[32];
} PAINTSTRUCT, *PPAINTSTRUCT, *LPPAINTSTRUCT;

typedef struct tagCREATESTRUCTA {
    LPVOID    lpCreateParams;
    HINSTANCE hInstance;
    HMENU     hMenu;
    HWND      hwndParent;
    int       cy;
    int       cx;
    int       y;
    int       x;
    LONG      style;
    LPCSTR    lpszName;
    LPCSTR    lpszClass;
    DWORD     dwExStyle;
} CREATESTRUCTA, *LPCREATESTRUCTA;

typedef CREATESTRUCTA CREATESTRUCT;
typedef LPCREATESTRUCTA LPCREATESTRUCT;

/* ============================================================
 * Function Stubs - All return failure/default
 * Real implementations will use SDL2
 * ============================================================ */

/* Window procedure type */
typedef LRESULT (*WNDPROC)(HWND, UINT, WPARAM, LPARAM);

/* Default window proc - does nothing */
static inline LRESULT DefWindowProcA(HWND hWnd, UINT Msg, WPARAM wParam, LPARAM lParam) {
    (void)hWnd; (void)Msg; (void)wParam; (void)lParam;
    return 0;
}
#define DefWindowProc DefWindowProcA

/* Register/unregister window class */
static inline ATOM RegisterClassA(const WNDCLASSA *lpWndClass) { (void)lpWndClass; return 0; }
static inline ATOM RegisterClassExA(const WNDCLASSEXA *lpWndClass) { (void)lpWndClass; return 0; }
static inline BOOL UnregisterClassA(LPCSTR lpClassName, HINSTANCE hInstance) { (void)lpClassName; (void)hInstance; return TRUE; }
#define RegisterClass RegisterClassA
#define RegisterClassEx RegisterClassExA
#define UnregisterClass UnregisterClassA

/* Window creation/destruction */
static inline HWND CreateWindowExA(DWORD dwExStyle, LPCSTR lpClassName, LPCSTR lpWindowName,
    DWORD dwStyle, int X, int Y, int nWidth, int nHeight, HWND hWndParent, HMENU hMenu,
    HINSTANCE hInstance, LPVOID lpParam) {
    (void)dwExStyle; (void)lpClassName; (void)lpWindowName; (void)dwStyle;
    (void)X; (void)Y; (void)nWidth; (void)nHeight; (void)hWndParent;
    (void)hMenu; (void)hInstance; (void)lpParam;
    return NULL;
}
#define CreateWindowEx CreateWindowExA
#define CreateWindow(a,b,c,d,e,f,g,h,i,j,k) CreateWindowExA(0,a,b,c,d,e,f,g,h,i,j,k)
#define CreateWindowA CreateWindow

static inline BOOL DestroyWindow(HWND hWnd) { (void)hWnd; return TRUE; }

/* Window display */
static inline BOOL ShowWindow(HWND hWnd, int nCmdShow) { (void)hWnd; (void)nCmdShow; return TRUE; }
static inline BOOL UpdateWindow(HWND hWnd) { (void)hWnd; return TRUE; }
static inline BOOL InvalidateRect(HWND hWnd, const RECT *lpRect, BOOL bErase) {
    (void)hWnd; (void)lpRect; (void)bErase; return TRUE;
}
static inline BOOL ValidateRect(HWND hWnd, const RECT *lpRect) {
    (void)hWnd; (void)lpRect; return TRUE;
}
static inline BOOL GetUpdateRect(HWND hWnd, LPRECT lpRect, BOOL bErase) {
    (void)hWnd; (void)lpRect; (void)bErase; return FALSE; /* No update region */
}
static inline BOOL SetRect(LPRECT lprc, int xLeft, int yTop, int xRight, int yBottom) {
    if (lprc) {
        lprc->left = xLeft;
        lprc->top = yTop;
        lprc->right = xRight;
        lprc->bottom = yBottom;
        return TRUE;
    }
    return FALSE;
}

/* Message handling */
static inline BOOL GetMessageA(LPMSG lpMsg, HWND hWnd, UINT wMsgFilterMin, UINT wMsgFilterMax) {
    (void)lpMsg; (void)hWnd; (void)wMsgFilterMin; (void)wMsgFilterMax;
    return FALSE; /* No messages - exit loop */
}
static inline BOOL PeekMessageA(LPMSG lpMsg, HWND hWnd, UINT wMsgFilterMin, UINT wMsgFilterMax, UINT wRemoveMsg) {
    (void)lpMsg; (void)hWnd; (void)wMsgFilterMin; (void)wMsgFilterMax; (void)wRemoveMsg;
    return FALSE;
}
static inline BOOL TranslateMessage(const MSG *lpMsg) { (void)lpMsg; return TRUE; }
static inline LRESULT DispatchMessageA(const MSG *lpMsg) { (void)lpMsg; return 0; }
static inline void PostQuitMessage(int nExitCode) { (void)nExitCode; }
static inline BOOL PostMessageA(HWND hWnd, UINT Msg, WPARAM wParam, LPARAM lParam) {
    (void)hWnd; (void)Msg; (void)wParam; (void)lParam; return TRUE;
}
static inline LRESULT SendMessageA(HWND hWnd, UINT Msg, WPARAM wParam, LPARAM lParam) {
    (void)hWnd; (void)Msg; (void)wParam; (void)lParam; return 0;
}
#define GetMessage GetMessageA
#define PeekMessage PeekMessageA
#define DispatchMessage DispatchMessageA
#define PostMessage PostMessageA
/* NOTE: SendMessage macro disabled - conflicts with class methods in vu2 */
/* #define SendMessage SendMessageA */

#define PM_NOREMOVE     0x0000
#define PM_REMOVE       0x0001
#define PM_NOYIELD      0x0002

/* Window properties */
static inline BOOL GetClientRect(HWND hWnd, LPRECT lpRect) {
    (void)hWnd; if (lpRect) memset(lpRect, 0, sizeof(*lpRect)); return TRUE;
}
static inline BOOL GetWindowRect(HWND hWnd, LPRECT lpRect) {
    (void)hWnd; if (lpRect) memset(lpRect, 0, sizeof(*lpRect)); return TRUE;
}
static inline BOOL SetWindowPos(HWND hWnd, HWND hWndInsertAfter, int X, int Y, int cx, int cy, UINT uFlags) {
    (void)hWnd; (void)hWndInsertAfter; (void)X; (void)Y; (void)cx; (void)cy; (void)uFlags;
    return TRUE;
}
static inline BOOL MoveWindow(HWND hWnd, int X, int Y, int nWidth, int nHeight, BOOL bRepaint) {
    (void)hWnd; (void)X; (void)Y; (void)nWidth; (void)nHeight; (void)bRepaint;
    return TRUE;
}
static inline HWND GetParent(HWND hWnd) { (void)hWnd; return NULL; }
static inline HWND SetParent(HWND hWndChild, HWND hWndNewParent) { (void)hWndChild; (void)hWndNewParent; return NULL; }
static inline HWND GetForegroundWindow(void) { return NULL; }
static inline BOOL SetForegroundWindow(HWND hWnd) { (void)hWnd; return TRUE; }
static inline HWND GetFocus(void) { return NULL; }
static inline HWND SetFocus(HWND hWnd) { (void)hWnd; return NULL; }
static inline HWND GetActiveWindow(void) { return NULL; }
static inline HWND SetActiveWindow(HWND hWnd) { (void)hWnd; return NULL; }
static inline BOOL IsWindowVisible(HWND hWnd) { (void)hWnd; return TRUE; }
static inline BOOL EnableWindow(HWND hWnd, BOOL bEnable) { (void)hWnd; (void)bEnable; return TRUE; }

/* Painting */
static inline HDC BeginPaint(HWND hWnd, LPPAINTSTRUCT lpPaint) {
    (void)hWnd; if (lpPaint) memset(lpPaint, 0, sizeof(*lpPaint)); return NULL;
}
static inline BOOL EndPaint(HWND hWnd, const PAINTSTRUCT *lpPaint) { (void)hWnd; (void)lpPaint; return TRUE; }

/* Cursor */
static inline HCURSOR SetCursor(HCURSOR hCursor) { (void)hCursor; return NULL; }
static inline HCURSOR LoadCursorA(HINSTANCE hInstance, LPCSTR lpCursorName) { (void)hInstance; (void)lpCursorName; return NULL; }
static inline int ShowCursor(BOOL bShow) { (void)bShow; return 0; }
static inline BOOL SetCursorPos(int X, int Y) { (void)X; (void)Y; return TRUE; }
static inline BOOL GetCursorPos(LPPOINT lpPoint) { if (lpPoint) { lpPoint->x = 0; lpPoint->y = 0; } return TRUE; }
#define LoadCursor LoadCursorA

#define IDC_ARROW           ((LPCSTR)32512)
#define IDC_IBEAM           ((LPCSTR)32513)
#define IDC_WAIT            ((LPCSTR)32514)
#define IDC_CROSS           ((LPCSTR)32515)
#define IDC_UPARROW         ((LPCSTR)32516)
#define IDC_SIZENWSE        ((LPCSTR)32642)
#define IDC_SIZENESW        ((LPCSTR)32643)
#define IDC_SIZEWE          ((LPCSTR)32644)
#define IDC_SIZENS          ((LPCSTR)32645)
#define IDC_SIZEALL         ((LPCSTR)32646)
#define IDC_NO              ((LPCSTR)32648)
#define IDC_HAND            ((LPCSTR)32649)
#define IDC_APPSTARTING     ((LPCSTR)32650)
#define IDC_HELP            ((LPCSTR)32651)

/* Keyboard */
static inline SHORT GetAsyncKeyState(int vKey) { (void)vKey; return 0; }
static inline SHORT GetKeyState(int nVirtKey) { (void)nVirtKey; return 0; }
static inline BOOL GetKeyboardState(PBYTE lpKeyState) { (void)lpKeyState; return TRUE; }

/* Timer */
static inline UINT_PTR SetTimer(HWND hWnd, UINT_PTR nIDEvent, UINT uElapse, LPVOID lpTimerFunc) {
    (void)hWnd; (void)nIDEvent; (void)uElapse; (void)lpTimerFunc; return 0;
}
static inline BOOL KillTimer(HWND hWnd, UINT_PTR uIDEvent) { (void)hWnd; (void)uIDEvent; return TRUE; }

/* Message box - prints to stderr */
static inline int MessageBoxA(HWND hWnd, LPCSTR lpText, LPCSTR lpCaption, UINT uType) {
    (void)hWnd;
    fprintf(stderr, "[%s] %s\n", lpCaption ? lpCaption : "Message", lpText ? lpText : "");
    /* F4Assert uses MB_ABORTRETRYIGNORE and loops until IDIGNORE is returned */
    if (uType & MB_ABORTRETRYIGNORE) {
        return IDIGNORE;
    }
    return IDOK;
}
#define MessageBox MessageBoxA

/* Screen info */
static inline int GetSystemMetrics(int nIndex) { (void)nIndex; return 0; }
#define SM_CXSCREEN     0
#define SM_CYSCREEN     1
#define SM_CXFULLSCREEN 16
#define SM_CYFULLSCREEN 17

/* Clipboard - stubs */
static inline BOOL OpenClipboard(HWND hWndNewOwner) { (void)hWndNewOwner; return FALSE; }
static inline BOOL CloseClipboard(void) { return TRUE; }
static inline BOOL EmptyClipboard(void) { return FALSE; }
static inline HANDLE GetClipboardData(UINT uFormat) { (void)uFormat; return NULL; }
static inline HANDLE SetClipboardData(UINT uFormat, HANDLE hMem) { (void)uFormat; (void)hMem; return NULL; }

#define CF_TEXT     1
#define CF_BITMAP   2
#define CF_DIB      8

/* SetWindowPos flags */
#define SWP_NOSIZE          0x0001
#define SWP_NOMOVE          0x0002
#define SWP_NOZORDER        0x0004
#define SWP_NOREDRAW        0x0008
#define SWP_NOACTIVATE      0x0010
#define SWP_FRAMECHANGED    0x0020
#define SWP_SHOWWINDOW      0x0040
#define SWP_HIDEWINDOW      0x0080
#define SWP_NOCOPYBITS      0x0100
#define SWP_NOOWNERZORDER   0x0200
#define SWP_NOSENDCHANGING  0x0400
#define SWP_DRAWFRAME       SWP_FRAMECHANGED
#define SWP_NOREPOSITION    SWP_NOOWNERZORDER

#define HWND_TOP            ((HWND)0)
#define HWND_BOTTOM         ((HWND)1)
#define HWND_TOPMOST        ((HWND)-1)
#define HWND_NOTOPMOST      ((HWND)-2)

/* Track mouse event */
typedef struct tagTRACKMOUSEEVENT {
    DWORD cbSize;
    DWORD dwFlags;
    HWND  hwndTrack;
    DWORD dwHoverTime;
} TRACKMOUSEEVENT, *LPTRACKMOUSEEVENT;

#define TME_HOVER       0x00000001
#define TME_LEAVE       0x00000002
#define TME_NONCLIENT   0x00000010
#define TME_QUERY       0x40000000
#define TME_CANCEL      0x80000000
#define HOVER_DEFAULT   0xFFFFFFFF

static inline BOOL TrackMouseEvent(LPTRACKMOUSEEVENT lpEventTrack) { (void)lpEventTrack; return TRUE; }

/* Dialog procedure */
typedef INT_PTR (CALLBACK *DLGPROC)(HWND, UINT, WPARAM, LPARAM);

/* Dialog template - minimal stub */
typedef struct {
    DWORD style;
    DWORD dwExtendedStyle;
    WORD cdit;
    short x;
    short y;
    short cx;
    short cy;
} DLGTEMPLATE, *LPDLGTEMPLATE;

typedef const DLGTEMPLATE *LPCDLGTEMPLATE;

/* Resource macros */
#define MAKEINTRESOURCEA(i)     ((LPSTR)((ULONG_PTR)((WORD)(i))))
#define MAKEINTRESOURCEW(i)     ((LPWSTR)((ULONG_PTR)((WORD)(i))))
#define MAKEINTRESOURCE         MAKEINTRESOURCEA

/* Icon loading */
static inline HICON LoadIconA(HINSTANCE hInstance, LPCSTR lpIconName) {
    (void)hInstance; (void)lpIconName;
    return NULL;
}
#define LoadIcon LoadIconA

#define IDI_APPLICATION     MAKEINTRESOURCE(32512)
#define IDI_HAND            MAKEINTRESOURCE(32513)
#define IDI_QUESTION        MAKEINTRESOURCE(32514)
#define IDI_EXCLAMATION     MAKEINTRESOURCE(32515)
#define IDI_ASTERISK        MAKEINTRESOURCE(32516)
#define IDI_WINLOGO         MAKEINTRESOURCE(32517)
#define IDI_WARNING         IDI_EXCLAMATION
#define IDI_ERROR           IDI_HAND
#define IDI_INFORMATION     IDI_ASTERISK

/* AdjustWindowRect */
static inline BOOL AdjustWindowRect(LPRECT lpRect, DWORD dwStyle, BOOL bMenu) {
    (void)lpRect; (void)dwStyle; (void)bMenu;
    return TRUE;
}
static inline BOOL AdjustWindowRectEx(LPRECT lpRect, DWORD dwStyle, BOOL bMenu, DWORD dwExStyle) {
    (void)lpRect; (void)dwStyle; (void)bMenu; (void)dwExStyle;
    return TRUE;
}

/* GetWindowThreadProcessId */
static inline DWORD GetWindowThreadProcessId(HWND hWnd, LPDWORD lpdwProcessId) {
    (void)hWnd;
    if (lpdwProcessId) *lpdwProcessId = getpid();
    /* Return current thread ID - on Linux with SDL, all windows are on the main thread */
    return (DWORD)pthread_self();
}

/* NOTE: SendMessage macro not defined - conflicts with class methods.
 * Code should use SendMessageA directly instead. */

/* MAKELPARAM */
#ifndef MAKELPARAM
#define MAKELPARAM(l, h)    ((LPARAM)(DWORD)MAKELONG(l, h))
#endif
#ifndef MAKEWPARAM
#define MAKEWPARAM(l, h)    ((WPARAM)(DWORD)MAKELONG(l, h))
#endif

/* Mouse button messages parameter macros */
#define GET_X_LPARAM(lp)    ((int)(short)LOWORD(lp))
#define GET_Y_LPARAM(lp)    ((int)(short)HIWORD(lp))

/* GetDC/ReleaseDC - defined in compat_wingdi.h */
/* GetWindowDC */
static inline HDC GetWindowDC(HWND hWnd) { (void)hWnd; return NULL; }

/* ScreenToClient / ClientToScreen */
static inline BOOL ScreenToClient(HWND hWnd, LPPOINT lpPoint) { (void)hWnd; (void)lpPoint; return TRUE; }
static inline BOOL ClientToScreen(HWND hWnd, LPPOINT lpPoint) { (void)hWnd; (void)lpPoint; return TRUE; }

/* SetCapture/ReleaseCapture */
static inline HWND SetCapture(HWND hWnd) { (void)hWnd; return NULL; }
static inline BOOL ReleaseCapture(void) { return TRUE; }
static inline HWND GetCapture(void) { return NULL; }

/* DrawText format flags */
#define DT_TOP                  0x00000000
#define DT_LEFT                 0x00000000
#define DT_CENTER               0x00000001
#define DT_RIGHT                0x00000002
#define DT_VCENTER              0x00000004
#define DT_BOTTOM               0x00000008
#define DT_WORDBREAK            0x00000010
#define DT_SINGLELINE           0x00000020
#define DT_EXPANDTABS           0x00000040
#define DT_TABSTOP              0x00000080
#define DT_NOCLIP               0x00000100
#define DT_EXTERNALLEADING      0x00000200
#define DT_CALCRECT             0x00000400
#define DT_NOPREFIX             0x00000800
#define DT_INTERNAL             0x00001000

/* DrawText stub */
static inline int DrawText(HDC hDC, LPCSTR lpString, int nCount, LPRECT lpRect, UINT uFormat) {
    (void)hDC; (void)lpString; (void)nCount; (void)lpRect; (void)uFormat;
    return 0;
}

/* Dialog Box Functions - additional stubs */
typedef INT_PTR (CALLBACK *DLGPROC)(HWND, UINT, WPARAM, LPARAM);

#define MAKEINTRESOURCEA(i) ((LPSTR)((ULONG_PTR)((WORD)(i))))
#define MAKEINTRESOURCEW(i) ((LPWSTR)((ULONG_PTR)((WORD)(i))))
#define MAKEINTRESOURCE MAKEINTRESOURCEA

static inline INT_PTR DialogBoxA(HINSTANCE hInstance, LPCSTR lpTemplate, HWND hWndParent, DLGPROC lpDialogFunc) {
    (void)hInstance; (void)lpTemplate; (void)hWndParent; (void)lpDialogFunc;
    return 0;
}
#define DialogBox DialogBoxA
#define DialogBoxW DialogBoxA

static inline HWND CreateDialogA(HINSTANCE hInstance, LPCSTR lpTemplate, HWND hWndParent, DLGPROC lpDialogFunc) {
    (void)hInstance; (void)lpTemplate; (void)hWndParent; (void)lpDialogFunc;
    return NULL;
}
#define CreateDialog CreateDialogA

static inline BOOL SetDlgItemInt(HWND hDlg, int nIDDlgItem, UINT uValue, BOOL bSigned) {
    (void)hDlg; (void)nIDDlgItem; (void)uValue; (void)bSigned;
    return TRUE;
}

static inline UINT GetDlgItemInt(HWND hDlg, int nIDDlgItem, BOOL *lpTranslated, BOOL bSigned) {
    (void)hDlg; (void)nIDDlgItem; (void)bSigned;
    if (lpTranslated) *lpTranslated = FALSE;
    return 0;
}

static inline LRESULT SendDlgItemMessageA(HWND hDlg, int nIDDlgItem, UINT Msg, WPARAM wParam, LPARAM lParam) {
    (void)hDlg; (void)nIDDlgItem; (void)Msg; (void)wParam; (void)lParam;
    return 0;
}
#define SendDlgItemMessage SendDlgItemMessageA

static inline BOOL CheckRadioButton(HWND hDlg, int nIDFirstButton, int nIDLastButton, int nIDCheckButton) {
    (void)hDlg; (void)nIDFirstButton; (void)nIDLastButton; (void)nIDCheckButton;
    return TRUE;
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINUSER_H */
