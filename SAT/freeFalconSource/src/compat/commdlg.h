/*
 * FreeFalcon Linux Port - commdlg.h compatibility stub
 *
 * Windows Common Dialogs headers replacement.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_COMMDLG_H
#define FF_COMPAT_COMMDLG_H

#ifdef FF_LINUX

#include <windows.h>

/* OPENFILENAME structure */
typedef struct tagOFNA {
    DWORD         lStructSize;
    HWND          hwndOwner;
    HINSTANCE     hInstance;
    LPCSTR        lpstrFilter;
    LPSTR         lpstrCustomFilter;
    DWORD         nMaxCustFilter;
    DWORD         nFilterIndex;
    LPSTR         lpstrFile;
    DWORD         nMaxFile;
    LPSTR         lpstrFileTitle;
    DWORD         nMaxFileTitle;
    LPCSTR        lpstrInitialDir;
    LPCSTR        lpstrTitle;
    DWORD         Flags;
    WORD          nFileOffset;
    WORD          nFileExtension;
    LPCSTR        lpstrDefExt;
    LPARAM        lCustData;
    void*         lpfnHook;
    LPCSTR        lpTemplateName;
    void*         pvReserved;
    DWORD         dwReserved;
    DWORD         FlagsEx;
} OPENFILENAMEA, *LPOPENFILENAMEA;

typedef OPENFILENAMEA OPENFILENAME;
typedef LPOPENFILENAMEA LPOPENFILENAME;

/* OPENFILENAME flags */
#define OFN_READONLY                0x00000001
#define OFN_OVERWRITEPROMPT         0x00000002
#define OFN_HIDEREADONLY            0x00000004
#define OFN_NOCHANGEDIR             0x00000008
#define OFN_SHOWHELP                0x00000010
#define OFN_ENABLEHOOK              0x00000020
#define OFN_ENABLETEMPLATE          0x00000040
#define OFN_ENABLETEMPLATEHANDLE    0x00000080
#define OFN_NOVALIDATE              0x00000100
#define OFN_ALLOWMULTISELECT        0x00000200
#define OFN_EXTENSIONDIFFERENT      0x00000400
#define OFN_PATHMUSTEXIST           0x00000800
#define OFN_FILEMUSTEXIST           0x00001000
#define OFN_CREATEPROMPT            0x00002000
#define OFN_SHAREAWARE              0x00004000
#define OFN_NOREADONLYRETURN        0x00008000
#define OFN_NOTESTFILECREATE        0x00010000
#define OFN_NONETWORKBUTTON         0x00020000
#define OFN_NOLONGNAMES             0x00040000
#define OFN_EXPLORER                0x00080000
#define OFN_NODEREFERENCELINKS      0x00100000
#define OFN_LONGNAMES               0x00200000
#define OFN_ENABLEINCLUDENOTIFY     0x00400000
#define OFN_ENABLESIZING            0x00800000
#define OFN_DONTADDTORECENT         0x02000000
#define OFN_FORCESHOWHIDDEN         0x10000000

/* CHOOSECOLOR structure */
typedef struct tagCHOOSECOLORA {
    DWORD         lStructSize;
    HWND          hwndOwner;
    HWND          hInstance;
    COLORREF      rgbResult;
    COLORREF*     lpCustColors;
    DWORD         Flags;
    LPARAM        lCustData;
    void*         lpfnHook;
    LPCSTR        lpTemplateName;
} CHOOSECOLORA, *LPCHOOSECOLORA;

typedef CHOOSECOLORA CHOOSECOLOR;
typedef LPCHOOSECOLORA LPCHOOSECOLOR;

/* CHOOSECOLOR flags */
#define CC_RGBINIT              0x00000001
#define CC_FULLOPEN             0x00000002
#define CC_PREVENTFULLOPEN      0x00000004
#define CC_SHOWHELP             0x00000008
#define CC_ENABLEHOOK           0x00000010
#define CC_ENABLETEMPLATE       0x00000020
#define CC_ENABLETEMPLATEHANDLE 0x00000040
#define CC_SOLIDCOLOR           0x00000080
#define CC_ANYCOLOR             0x00000100

/* Stub functions */
static inline BOOL GetOpenFileNameA(LPOPENFILENAMEA lpofn) {
    (void)lpofn;
    return FALSE;
}

static inline BOOL GetSaveFileNameA(LPOPENFILENAMEA lpofn) {
    (void)lpofn;
    return FALSE;
}

static inline BOOL ChooseColorA(LPCHOOSECOLORA lpcc) {
    (void)lpcc;
    return FALSE;
}

#define GetOpenFileName GetOpenFileNameA
#define GetSaveFileName GetSaveFileNameA
#define ChooseColor ChooseColorA

/* Error codes */
#define CDERR_DIALOGFAILURE     0xFFFF
#define CDERR_GENERALCODES      0x0000
#define CDERR_STRUCTSIZE        0x0001
#define CDERR_INITIALIZATION    0x0002
#define CDERR_NOTEMPLATE        0x0003
#define CDERR_NOHINSTANCE       0x0004
#define CDERR_LOADSTRFAILURE    0x0005
#define CDERR_FINDRESFAILURE    0x0006
#define CDERR_LOADRESFAILURE    0x0007
#define CDERR_LOCKRESFAILURE    0x0008
#define CDERR_MEMALLOCFAILURE   0x0009
#define CDERR_MEMLOCKFAILURE    0x000A
#define CDERR_NOHOOK            0x000B
#define CDERR_REGISTERMSGFAIL   0x000C

static inline DWORD CommDlgExtendedError(void) {
    return 0;
}

#endif /* FF_LINUX */
#endif /* FF_COMPAT_COMMDLG_H */
