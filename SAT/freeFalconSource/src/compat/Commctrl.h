/*
 * FreeFalcon Linux Port - commctrl.h compatibility
 *
 * Windows Common Controls API stub for Linux.
 */

#ifndef FF_COMPAT_COMMCTRL_H
#define FF_COMPAT_COMMCTRL_H

#ifdef FF_LINUX

#include "compat_types.h"
#include "compat_winuser.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Common control initialization */
typedef struct tagINITCOMMONCONTROLSEX {
    DWORD dwSize;
    DWORD dwICC;
} INITCOMMONCONTROLSEX, *LPINITCOMMONCONTROLSEX;

/* Control classes */
#define ICC_LISTVIEW_CLASSES    0x00000001
#define ICC_TREEVIEW_CLASSES    0x00000002
#define ICC_BAR_CLASSES         0x00000004
#define ICC_TAB_CLASSES         0x00000008
#define ICC_UPDOWN_CLASS        0x00000010
#define ICC_PROGRESS_CLASS      0x00000020
#define ICC_HOTKEY_CLASS        0x00000040
#define ICC_ANIMATE_CLASS       0x00000080
#define ICC_WIN95_CLASSES       0x000000FF
#define ICC_DATE_CLASSES        0x00000100
#define ICC_USEREX_CLASSES      0x00000200
#define ICC_COOL_CLASSES        0x00000400
#define ICC_INTERNET_CLASSES    0x00000800
#define ICC_PAGESCROLLER_CLASS  0x00001000
#define ICC_NATIVEFNTCTL_CLASS  0x00002000
#define ICC_STANDARD_CLASSES    0x00004000
#define ICC_LINK_CLASS          0x00008000

/* Stub functions */
static inline void InitCommonControls(void) {}
static inline BOOL InitCommonControlsEx(const INITCOMMONCONTROLSEX* picce) {
    (void)picce;
    return TRUE;
}

/* Property sheet */
typedef struct _PROPSHEETPAGEA {
    DWORD dwSize;
    DWORD dwFlags;
    HINSTANCE hInstance;
    union {
        LPCSTR pszTemplate;
        LPCDLGTEMPLATE pResource;
    };
    union {
        HICON hIcon;
        LPCSTR pszIcon;
    };
    LPCSTR pszTitle;
    DLGPROC pfnDlgProc;
    LPARAM lParam;
    void* pfnCallback;
    UINT* pcRefParent;
    LPCSTR pszHeaderTitle;
    LPCSTR pszHeaderSubTitle;
} PROPSHEETPAGEA, *LPPROPSHEETPAGEA;

typedef PROPSHEETPAGEA PROPSHEETPAGE;
typedef LPPROPSHEETPAGEA LPPROPSHEETPAGE;
typedef const PROPSHEETPAGEA *LPCPROPSHEETPAGEA;

typedef struct _PROPSHEETHEADERA {
    DWORD dwSize;
    DWORD dwFlags;
    HWND hwndParent;
    HINSTANCE hInstance;
    union {
        HICON hIcon;
        LPCSTR pszIcon;
    };
    LPCSTR pszCaption;
    UINT nPages;
    union {
        UINT nStartPage;
        LPCSTR pStartPage;
    };
    union {
        LPCPROPSHEETPAGEA ppsp;
        HWND* phpage;
    };
    void* pfnCallback;
    union {
        HBITMAP hbmWatermark;
        LPCSTR pszbmWatermark;
    };
    HPALETTE hplWatermark;
    union {
        HBITMAP hbmHeader;
        LPCSTR pszbmHeader;
    };
} PROPSHEETHEADERA, *LPPROPSHEETHEADERA;

typedef PROPSHEETHEADERA PROPSHEETHEADER;
typedef LPPROPSHEETHEADERA LPPROPSHEETHEADER;
typedef const PROPSHEETHEADERA *LPCPROPSHEETHEADERA;

/* Property sheet flags */
#define PSH_DEFAULT             0x00000000
#define PSH_PROPTITLE           0x00000001
#define PSH_USEHICON            0x00000002
#define PSH_USEICONID           0x00000004
#define PSH_PROPSHEETPAGE       0x00000008
#define PSH_WIZARDHASFINISH     0x00000010
#define PSH_WIZARD              0x00000020
#define PSH_USEPSTARTPAGE       0x00000040
#define PSH_NOAPPLYNOW          0x00000080
#define PSH_USECALLBACK         0x00000100
#define PSH_HASHELP             0x00000200
#define PSH_MODELESS            0x00000400
#define PSH_RTLREADING          0x00000800
#define PSH_WIZARDCONTEXTHELP   0x00001000

#define PSP_DEFAULT             0x00000000
#define PSP_DLGINDIRECT         0x00000001
#define PSP_USEHICON            0x00000002
#define PSP_USEICONID           0x00000004
#define PSP_USETITLE            0x00000008
#define PSP_RTLREADING          0x00000010
#define PSP_HASHELP             0x00000020
#define PSP_USEREFPARENT        0x00000040
#define PSP_USECALLBACK         0x00000080
#define PSP_PREMATURE           0x00000400
#define PSP_HIDEHEADER          0x00000800
#define PSP_USEHEADERTITLE      0x00001000
#define PSP_USEHEADERSUBTITLE   0x00002000

static inline INT_PTR PropertySheetA(LPCPROPSHEETHEADERA psh) {
    (void)psh;
    return -1;
}
#define PropertySheet PropertySheetA

/* List view */
#define LVS_ICON                0x0000
#define LVS_REPORT              0x0001
#define LVS_SMALLICON           0x0002
#define LVS_LIST                0x0003
#define LVS_TYPEMASK            0x0003
#define LVS_SINGLESEL           0x0004
#define LVS_SHOWSELALWAYS       0x0008
#define LVS_SORTASCENDING       0x0010
#define LVS_SORTDESCENDING      0x0020
#define LVS_SHAREIMAGELISTS     0x0040
#define LVS_NOLABELWRAP         0x0080
#define LVS_AUTOARRANGE         0x0100
#define LVS_EDITLABELS          0x0200
#define LVS_NOSCROLL            0x2000
#define LVS_ALIGNTOP            0x0000
#define LVS_ALIGNLEFT           0x0800
#define LVS_ALIGNMASK           0x0c00
#define LVS_OWNERDRAWFIXED      0x0400
#define LVS_NOCOLUMNHEADER      0x4000
#define LVS_NOSORTHEADER        0x8000

#define LVM_FIRST               0x1000
#define LVM_GETITEMCOUNT        (LVM_FIRST + 4)
#define LVM_DELETEITEM          (LVM_FIRST + 8)
#define LVM_DELETEALLITEMS      (LVM_FIRST + 9)
#define LVM_INSERTITEMA         (LVM_FIRST + 7)
#define LVM_INSERTITEM          LVM_INSERTITEMA
#define LVM_SETITEMA            (LVM_FIRST + 6)
#define LVM_SETITEM             LVM_SETITEMA
#define LVM_GETITEMA            (LVM_FIRST + 5)
#define LVM_GETITEM             LVM_GETITEMA
#define LVM_INSERTCOLUMNA       (LVM_FIRST + 27)
#define LVM_INSERTCOLUMN        LVM_INSERTCOLUMNA
#define LVM_SETCOLUMNA          (LVM_FIRST + 26)
#define LVM_SETCOLUMN           LVM_SETCOLUMNA
#define LVM_GETCOLUMNA          (LVM_FIRST + 25)
#define LVM_GETCOLUMN           LVM_GETCOLUMNA
#define LVM_SETITEMSTATE        (LVM_FIRST + 43)
#define LVM_GETITEMSTATE        (LVM_FIRST + 44)
#define LVM_GETNEXTITEM         (LVM_FIRST + 12)
#define LVM_ENSUREVISIBLE       (LVM_FIRST + 19)
#define LVM_SCROLL              (LVM_FIRST + 20)
#define LVM_SETBKCOLOR          (LVM_FIRST + 1)
#define LVM_SETTEXTCOLOR        (LVM_FIRST + 36)
#define LVM_SETTEXTBKCOLOR      (LVM_FIRST + 38)
#define LVM_SETIMAGELIST        (LVM_FIRST + 3)
#define LVM_GETIMAGELIST        (LVM_FIRST + 2)
#define LVM_SETEXTENDEDLISTVIEWSTYLE (LVM_FIRST + 54)
#define LVM_GETEXTENDEDLISTVIEWSTYLE (LVM_FIRST + 55)

#define LVIF_TEXT               0x0001
#define LVIF_IMAGE              0x0002
#define LVIF_PARAM              0x0004
#define LVIF_STATE              0x0008

#define LVIS_FOCUSED            0x0001
#define LVIS_SELECTED           0x0002
#define LVIS_CUT                0x0004
#define LVIS_DROPHILITED        0x0008
#define LVIS_STATEIMAGEMASK     0xF000

#define LVNI_ALL                0x0000
#define LVNI_FOCUSED            0x0001
#define LVNI_SELECTED           0x0002
#define LVNI_CUT                0x0004
#define LVNI_DROPHILITED        0x0008

#define LVSIL_NORMAL            0
#define LVSIL_SMALL             1
#define LVSIL_STATE             2

typedef struct tagLVITEMA {
    UINT mask;
    int iItem;
    int iSubItem;
    UINT state;
    UINT stateMask;
    LPSTR pszText;
    int cchTextMax;
    int iImage;
    LPARAM lParam;
    int iIndent;
} LVITEMA, *LPLVITEMA;

typedef LVITEMA LVITEM;
typedef LPLVITEMA LPLVITEM;

typedef struct tagLVCOLUMNA {
    UINT mask;
    int fmt;
    int cx;
    LPSTR pszText;
    int cchTextMax;
    int iSubItem;
    int iImage;
    int iOrder;
} LVCOLUMNA, *LPLVCOLUMNA;

typedef LVCOLUMNA LVCOLUMN;
typedef LPLVCOLUMNA LPLVCOLUMN;

#define LVCF_FMT                0x0001
#define LVCF_WIDTH              0x0002
#define LVCF_TEXT               0x0004
#define LVCF_SUBITEM            0x0008
#define LVCF_IMAGE              0x0010
#define LVCF_ORDER              0x0020

#define LVCFMT_LEFT             0x0000
#define LVCFMT_RIGHT            0x0001
#define LVCFMT_CENTER           0x0002
#define LVCFMT_JUSTIFYMASK      0x0003

/* Macros for ListView messages */
#define ListView_InsertItem(hwnd, pitem) \
    (int)SendMessageA((hwnd), LVM_INSERTITEM, 0, (LPARAM)(const LVITEMA*)(pitem))
#define ListView_SetItem(hwnd, pitem) \
    (BOOL)SendMessageA((hwnd), LVM_SETITEM, 0, (LPARAM)(const LVITEMA*)(pitem))
#define ListView_GetItem(hwnd, pitem) \
    (BOOL)SendMessageA((hwnd), LVM_GETITEM, 0, (LPARAM)(LVITEMA*)(pitem))
#define ListView_DeleteItem(hwnd, i) \
    (BOOL)SendMessageA((hwnd), LVM_DELETEITEM, (WPARAM)(int)(i), 0L)
#define ListView_DeleteAllItems(hwnd) \
    (BOOL)SendMessageA((hwnd), LVM_DELETEALLITEMS, 0, 0L)
#define ListView_GetItemCount(hwnd) \
    (int)SendMessageA((hwnd), LVM_GETITEMCOUNT, 0, 0L)
#define ListView_InsertColumn(hwnd, iCol, pcol) \
    (int)SendMessageA((hwnd), LVM_INSERTCOLUMN, (WPARAM)(int)(iCol), (LPARAM)(const LVCOLUMNA*)(pcol))
#define ListView_SetColumn(hwnd, iCol, pcol) \
    (BOOL)SendMessageA((hwnd), LVM_SETCOLUMN, (WPARAM)(int)(iCol), (LPARAM)(const LVCOLUMNA*)(pcol))
#define ListView_GetColumn(hwnd, iCol, pcol) \
    (BOOL)SendMessageA((hwnd), LVM_GETCOLUMN, (WPARAM)(int)(iCol), (LPARAM)(LVCOLUMNA*)(pcol))
#define ListView_SetItemState(hwnd, i, data, mask) \
    { LVITEM _lvi; _lvi.stateMask = (mask); _lvi.state = (data); \
      SendMessageA((hwnd), LVM_SETITEMSTATE, (WPARAM)(i), (LPARAM)&_lvi); }
#define ListView_GetItemState(hwnd, i, mask) \
    (UINT)SendMessageA((hwnd), LVM_GETITEMSTATE, (WPARAM)(i), (LPARAM)(mask))
#define ListView_GetNextItem(hwnd, i, flags) \
    (int)SendMessageA((hwnd), LVM_GETNEXTITEM, (WPARAM)(i), MAKELPARAM((flags), 0))
#define ListView_EnsureVisible(hwnd, i, fPartialOK) \
    (BOOL)SendMessageA((hwnd), LVM_ENSUREVISIBLE, (WPARAM)(i), MAKELPARAM((fPartialOK), 0))
#define ListView_SetBkColor(hwnd, clrBk) \
    (BOOL)SendMessageA((hwnd), LVM_SETBKCOLOR, 0, (LPARAM)(COLORREF)(clrBk))
#define ListView_SetTextColor(hwnd, clrText) \
    (BOOL)SendMessageA((hwnd), LVM_SETTEXTCOLOR, 0, (LPARAM)(COLORREF)(clrText))
#define ListView_SetTextBkColor(hwnd, clrTextBk) \
    (BOOL)SendMessageA((hwnd), LVM_SETTEXTBKCOLOR, 0, (LPARAM)(COLORREF)(clrTextBk))
#define ListView_SetImageList(hwnd, himl, iImageList) \
    (HIMAGELIST)SendMessageA((hwnd), LVM_SETIMAGELIST, (WPARAM)(iImageList), (LPARAM)(HIMAGELIST)(himl))
#define ListView_GetImageList(hwnd, iImageList) \
    (HIMAGELIST)SendMessageA((hwnd), LVM_GETIMAGELIST, (WPARAM)(iImageList), 0L)

/* Tree view */
#define TVS_HASBUTTONS          0x0001
#define TVS_HASLINES            0x0002
#define TVS_LINESATROOT         0x0004
#define TVS_EDITLABELS          0x0008
#define TVS_DISABLEDRAGDROP     0x0010
#define TVS_SHOWSELALWAYS       0x0020
#define TVS_RTLREADING          0x0040
#define TVS_NOTOOLTIPS          0x0080
#define TVS_CHECKBOXES          0x0100
#define TVS_TRACKSELECT         0x0200
#define TVS_SINGLEEXPAND        0x0400
#define TVS_INFOTIP             0x0800
#define TVS_FULLROWSELECT       0x1000
#define TVS_NOSCROLL            0x2000
#define TVS_NONEVENHEIGHT       0x4000
#define TVS_NOHSCROLL           0x8000

#define TVM_FIRST               0x1100
#define TVM_INSERTITEMA         (TVM_FIRST + 0)
#define TVM_INSERTITEM          TVM_INSERTITEMA
#define TVM_DELETEITEM          (TVM_FIRST + 1)
#define TVM_EXPAND              (TVM_FIRST + 2)
#define TVM_GETITEMRECT         (TVM_FIRST + 4)
#define TVM_GETCOUNT            (TVM_FIRST + 5)
#define TVM_GETINDENT           (TVM_FIRST + 6)
#define TVM_SETINDENT           (TVM_FIRST + 7)
#define TVM_GETIMAGELIST        (TVM_FIRST + 8)
#define TVM_SETIMAGELIST        (TVM_FIRST + 9)
#define TVM_GETNEXTITEM         (TVM_FIRST + 10)
#define TVM_SELECTITEM          (TVM_FIRST + 11)
#define TVM_GETITEMA            (TVM_FIRST + 12)
#define TVM_GETITEM             TVM_GETITEMA
#define TVM_SETITEMA            (TVM_FIRST + 13)
#define TVM_SETITEM             TVM_SETITEMA
#define TVM_EDITLABELA          (TVM_FIRST + 14)
#define TVM_EDITLABEL           TVM_EDITLABELA
#define TVM_GETEDITCONTROL      (TVM_FIRST + 15)
#define TVM_GETVISIBLECOUNT     (TVM_FIRST + 16)
#define TVM_HITTEST             (TVM_FIRST + 17)
#define TVM_SORTCHILDREN        (TVM_FIRST + 19)
#define TVM_ENDEDITLABELNOW     (TVM_FIRST + 22)
#define TVM_GETISEARCHSTRINGA   (TVM_FIRST + 23)
#define TVM_GETISEARCHSTRING    TVM_GETISEARCHSTRINGA
#define TVM_SETTOOLTIPS         (TVM_FIRST + 24)
#define TVM_GETTOOLTIPS         (TVM_FIRST + 25)
#define TVM_SETINSERTMARK       (TVM_FIRST + 26)
#define TVM_SETITEMHEIGHT       (TVM_FIRST + 27)
#define TVM_GETITEMHEIGHT       (TVM_FIRST + 28)
#define TVM_SETBKCOLOR          (TVM_FIRST + 29)
#define TVM_SETTEXTCOLOR        (TVM_FIRST + 30)
#define TVM_GETBKCOLOR          (TVM_FIRST + 31)
#define TVM_GETTEXTCOLOR        (TVM_FIRST + 32)
#define TVM_SETSCROLLTIME       (TVM_FIRST + 33)
#define TVM_GETSCROLLTIME       (TVM_FIRST + 34)
#define TVM_SETINSERTMARKCOLOR  (TVM_FIRST + 37)
#define TVM_GETINSERTMARKCOLOR  (TVM_FIRST + 38)

typedef HANDLE HTREEITEM;

#define TVI_ROOT                ((HTREEITEM)(ULONG_PTR)-0x10000)
#define TVI_FIRST               ((HTREEITEM)(ULONG_PTR)-0x0FFFF)
#define TVI_LAST                ((HTREEITEM)(ULONG_PTR)-0x0FFFE)
#define TVI_SORT                ((HTREEITEM)(ULONG_PTR)-0x0FFFD)

#define TVIF_TEXT               0x0001
#define TVIF_IMAGE              0x0002
#define TVIF_PARAM              0x0004
#define TVIF_STATE              0x0008
#define TVIF_HANDLE             0x0010
#define TVIF_SELECTEDIMAGE      0x0020
#define TVIF_CHILDREN           0x0040
#define TVIF_INTEGRAL           0x0080

#define TVIS_SELECTED           0x0002
#define TVIS_CUT                0x0004
#define TVIS_DROPHILITED        0x0008
#define TVIS_BOLD               0x0010
#define TVIS_EXPANDED           0x0020
#define TVIS_EXPANDEDONCE       0x0040
#define TVIS_EXPANDPARTIAL      0x0080
#define TVIS_OVERLAYMASK        0x0F00
#define TVIS_STATEIMAGEMASK     0xF000

#define TVE_COLLAPSE            0x0001
#define TVE_EXPAND              0x0002
#define TVE_TOGGLE              0x0003
#define TVE_EXPANDPARTIAL       0x4000
#define TVE_COLLAPSERESET       0x8000

#define TVGN_ROOT               0x0000
#define TVGN_NEXT               0x0001
#define TVGN_PREVIOUS           0x0002
#define TVGN_PARENT             0x0003
#define TVGN_CHILD              0x0004
#define TVGN_FIRSTVISIBLE       0x0005
#define TVGN_NEXTVISIBLE        0x0006
#define TVGN_PREVIOUSVISIBLE    0x0007
#define TVGN_DROPHILITE         0x0008
#define TVGN_CARET              0x0009
#define TVGN_LASTVISIBLE        0x000A

typedef struct tagTVITEMA {
    UINT mask;
    HTREEITEM hItem;
    UINT state;
    UINT stateMask;
    LPSTR pszText;
    int cchTextMax;
    int iImage;
    int iSelectedImage;
    int cChildren;
    LPARAM lParam;
} TVITEMA, *LPTVITEMA;

typedef TVITEMA TVITEM;
typedef LPTVITEMA LPTVITEM;

typedef struct tagTVINSERTSTRUCTA {
    HTREEITEM hParent;
    HTREEITEM hInsertAfter;
    union {
        TVITEMA itemex;
        TVITEMA item;
    };
} TVINSERTSTRUCTA, *LPTVINSERTSTRUCTA;

typedef TVINSERTSTRUCTA TVINSERTSTRUCT;
typedef LPTVINSERTSTRUCTA LPTVINSERTSTRUCT;

/* TreeView macros */
#define TreeView_InsertItem(hwnd, lpis) \
    (HTREEITEM)SendMessageA((hwnd), TVM_INSERTITEM, 0, (LPARAM)(LPTVINSERTSTRUCTA)(lpis))
#define TreeView_DeleteItem(hwnd, hitem) \
    (BOOL)SendMessageA((hwnd), TVM_DELETEITEM, 0, (LPARAM)(HTREEITEM)(hitem))
#define TreeView_DeleteAllItems(hwnd) \
    (BOOL)SendMessageA((hwnd), TVM_DELETEITEM, 0, (LPARAM)TVI_ROOT)
#define TreeView_Expand(hwnd, hitem, code) \
    (BOOL)SendMessageA((hwnd), TVM_EXPAND, (WPARAM)(code), (LPARAM)(HTREEITEM)(hitem))
#define TreeView_GetItemRect(hwnd, hitem, prc, code) \
    (*(HTREEITEM*)(prc) = (hitem), (BOOL)SendMessageA((hwnd), TVM_GETITEMRECT, (WPARAM)(code), (LPARAM)(RECT*)(prc)))
#define TreeView_GetCount(hwnd) \
    (UINT)SendMessageA((hwnd), TVM_GETCOUNT, 0, 0)
#define TreeView_GetIndent(hwnd) \
    (UINT)SendMessageA((hwnd), TVM_GETINDENT, 0, 0)
#define TreeView_SetIndent(hwnd, indent) \
    (BOOL)SendMessageA((hwnd), TVM_SETINDENT, (WPARAM)(indent), 0)
#define TreeView_GetImageList(hwnd, iImage) \
    (HIMAGELIST)SendMessageA((hwnd), TVM_GETIMAGELIST, (WPARAM)(iImage), 0)
#define TreeView_SetImageList(hwnd, himl, iImage) \
    (HIMAGELIST)SendMessageA((hwnd), TVM_SETIMAGELIST, (WPARAM)(iImage), (LPARAM)(HIMAGELIST)(himl))
#define TreeView_GetNextItem(hwnd, hitem, code) \
    (HTREEITEM)SendMessageA((hwnd), TVM_GETNEXTITEM, (WPARAM)(code), (LPARAM)(HTREEITEM)(hitem))
#define TreeView_GetChild(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_CHILD)
#define TreeView_GetNextSibling(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_NEXT)
#define TreeView_GetPrevSibling(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_PREVIOUS)
#define TreeView_GetParent(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_PARENT)
#define TreeView_GetFirstVisible(hwnd) \
    TreeView_GetNextItem(hwnd, NULL, TVGN_FIRSTVISIBLE)
#define TreeView_GetNextVisible(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_NEXTVISIBLE)
#define TreeView_GetPrevVisible(hwnd, hitem) \
    TreeView_GetNextItem(hwnd, hitem, TVGN_PREVIOUSVISIBLE)
#define TreeView_GetSelection(hwnd) \
    TreeView_GetNextItem(hwnd, NULL, TVGN_CARET)
#define TreeView_GetDropHilight(hwnd) \
    TreeView_GetNextItem(hwnd, NULL, TVGN_DROPHILITE)
#define TreeView_GetRoot(hwnd) \
    TreeView_GetNextItem(hwnd, NULL, TVGN_ROOT)
#define TreeView_GetLastVisible(hwnd) \
    TreeView_GetNextItem(hwnd, NULL, TVGN_LASTVISIBLE)
#define TreeView_Select(hwnd, hitem, code) \
    (BOOL)SendMessageA((hwnd), TVM_SELECTITEM, (WPARAM)(code), (LPARAM)(HTREEITEM)(hitem))
#define TreeView_SelectItem(hwnd, hitem) \
    TreeView_Select(hwnd, hitem, TVGN_CARET)
#define TreeView_SelectDropTarget(hwnd, hitem) \
    TreeView_Select(hwnd, hitem, TVGN_DROPHILITE)
#define TreeView_SelectSetFirstVisible(hwnd, hitem) \
    TreeView_Select(hwnd, hitem, TVGN_FIRSTVISIBLE)
#define TreeView_GetItem(hwnd, pitem) \
    (BOOL)SendMessageA((hwnd), TVM_GETITEM, 0, (LPARAM)(LPTVITEMA)(pitem))
#define TreeView_SetItem(hwnd, pitem) \
    (BOOL)SendMessageA((hwnd), TVM_SETITEM, 0, (LPARAM)(const TVITEMA*)(pitem))

/* Tab control */
#define TCS_SCROLLOPPOSITE      0x0001
#define TCS_BOTTOM              0x0002
#define TCS_RIGHT               0x0002
#define TCS_MULTISELECT         0x0004
#define TCS_FLATBUTTONS         0x0008
#define TCS_FORCEICONLEFT       0x0010
#define TCS_FORCELABELLEFT      0x0020
#define TCS_HOTTRACK            0x0040
#define TCS_VERTICAL            0x0080
#define TCS_TABS                0x0000
#define TCS_BUTTONS             0x0100
#define TCS_SINGLELINE          0x0000
#define TCS_MULTILINE           0x0200
#define TCS_RIGHTJUSTIFY        0x0000
#define TCS_FIXEDWIDTH          0x0400
#define TCS_RAGGEDRIGHT         0x0800
#define TCS_FOCUSONBUTTONDOWN   0x1000
#define TCS_OWNERDRAWFIXED      0x2000
#define TCS_TOOLTIPS            0x4000
#define TCS_FOCUSNEVER          0x8000

#define TCM_FIRST               0x1300
#define TCM_GETIMAGELIST        (TCM_FIRST + 2)
#define TCM_SETIMAGELIST        (TCM_FIRST + 3)
#define TCM_GETITEMCOUNT        (TCM_FIRST + 4)
#define TCM_GETITEMA            (TCM_FIRST + 5)
#define TCM_GETITEM             TCM_GETITEMA
#define TCM_SETITEMA            (TCM_FIRST + 6)
#define TCM_SETITEM             TCM_SETITEMA
#define TCM_INSERTITEMA         (TCM_FIRST + 7)
#define TCM_INSERTITEM          TCM_INSERTITEMA
#define TCM_DELETEITEM          (TCM_FIRST + 8)
#define TCM_DELETEALLITEMS      (TCM_FIRST + 9)
#define TCM_GETITEMRECT         (TCM_FIRST + 10)
#define TCM_GETCURSEL           (TCM_FIRST + 11)
#define TCM_SETCURSEL           (TCM_FIRST + 12)
#define TCM_ADJUSTRECT          (TCM_FIRST + 40)
#define TCM_SETITEMSIZE         (TCM_FIRST + 41)
#define TCM_SETPADDING          (TCM_FIRST + 43)
#define TCM_GETROWCOUNT         (TCM_FIRST + 44)
#define TCM_GETCURFOCUS         (TCM_FIRST + 47)
#define TCM_SETCURFOCUS         (TCM_FIRST + 48)
#define TCM_SETMINTABWIDTH      (TCM_FIRST + 49)
#define TCM_DESELECTALL         (TCM_FIRST + 50)

#define TCIF_TEXT               0x0001
#define TCIF_IMAGE              0x0002
#define TCIF_RTLREADING         0x0004
#define TCIF_PARAM              0x0008
#define TCIF_STATE              0x0010

typedef struct tagTCITEMA {
    UINT mask;
    DWORD dwState;
    DWORD dwStateMask;
    LPSTR pszText;
    int cchTextMax;
    int iImage;
    LPARAM lParam;
} TCITEMA, *LPTCITEMA;

typedef TCITEMA TCITEM;
typedef LPTCITEMA LPTCITEM;

/* Tab control macros */
#define TabCtrl_GetImageList(hwnd) \
    (HIMAGELIST)SendMessageA((hwnd), TCM_GETIMAGELIST, 0, 0L)
#define TabCtrl_SetImageList(hwnd, himl) \
    (HIMAGELIST)SendMessageA((hwnd), TCM_SETIMAGELIST, 0, (LPARAM)(HIMAGELIST)(himl))
#define TabCtrl_GetItemCount(hwnd) \
    (int)SendMessageA((hwnd), TCM_GETITEMCOUNT, 0, 0L)
#define TabCtrl_GetItem(hwnd, iItem, pitem) \
    (BOOL)SendMessageA((hwnd), TCM_GETITEM, (WPARAM)(int)(iItem), (LPARAM)(TCITEMA*)(pitem))
#define TabCtrl_SetItem(hwnd, iItem, pitem) \
    (BOOL)SendMessageA((hwnd), TCM_SETITEM, (WPARAM)(int)(iItem), (LPARAM)(TCITEMA*)(pitem))
#define TabCtrl_InsertItem(hwnd, iItem, pitem) \
    (int)SendMessageA((hwnd), TCM_INSERTITEM, (WPARAM)(int)(iItem), (LPARAM)(const TCITEMA*)(pitem))
#define TabCtrl_DeleteItem(hwnd, i) \
    (BOOL)SendMessageA((hwnd), TCM_DELETEITEM, (WPARAM)(int)(i), 0L)
#define TabCtrl_DeleteAllItems(hwnd) \
    (BOOL)SendMessageA((hwnd), TCM_DELETEALLITEMS, 0, 0L)
#define TabCtrl_GetItemRect(hwnd, i, prc) \
    (BOOL)SendMessageA((hwnd), TCM_GETITEMRECT, (WPARAM)(int)(i), (LPARAM)(RECT*)(prc))
#define TabCtrl_GetCurSel(hwnd) \
    (int)SendMessageA((hwnd), TCM_GETCURSEL, 0, 0)
#define TabCtrl_SetCurSel(hwnd, i) \
    (int)SendMessageA((hwnd), TCM_SETCURSEL, (WPARAM)(i), 0)
#define TabCtrl_AdjustRect(hwnd, bLarger, prc) \
    (int)SendMessageA((hwnd), TCM_ADJUSTRECT, (WPARAM)(BOOL)(bLarger), (LPARAM)(RECT*)(prc))
#define TabCtrl_SetItemSize(hwnd, x, y) \
    (DWORD)SendMessageA((hwnd), TCM_SETITEMSIZE, 0, MAKELPARAM(x,y))
#define TabCtrl_SetPadding(hwnd, cx, cy) \
    (void)SendMessageA((hwnd), TCM_SETPADDING, 0, MAKELPARAM(cx, cy))
#define TabCtrl_GetRowCount(hwnd) \
    (int)SendMessageA((hwnd), TCM_GETROWCOUNT, 0, 0L)
#define TabCtrl_GetCurFocus(hwnd) \
    (int)SendMessageA((hwnd), TCM_GETCURFOCUS, 0, 0)
#define TabCtrl_SetCurFocus(hwnd, i) \
    SendMessageA((hwnd), TCM_SETCURFOCUS, (WPARAM)(i), 0)
#define TabCtrl_SetMinTabWidth(hwnd, x) \
    (int)SendMessageA((hwnd), TCM_SETMINTABWIDTH, 0, (LPARAM)(x))
#define TabCtrl_DeselectAll(hwnd, fExcludeFocus) \
    (void)SendMessageA((hwnd), TCM_DESELECTALL, (WPARAM)(fExcludeFocus), 0)

/* Progress bar */
#define PBS_SMOOTH              0x01
#define PBS_VERTICAL            0x04

#define PBM_SETRANGE            (WM_USER + 1)
#define PBM_SETPOS              (WM_USER + 2)
#define PBM_DELTAPOS            (WM_USER + 3)
#define PBM_SETSTEP             (WM_USER + 4)
#define PBM_STEPIT              (WM_USER + 5)
#define PBM_SETRANGE32          (WM_USER + 6)
#define PBM_GETRANGE            (WM_USER + 7)
#define PBM_GETPOS              (WM_USER + 8)
#define PBM_SETBARCOLOR         (WM_USER + 9)
#define PBM_SETBKCOLOR          0x2001

/* Slider/Trackbar */
#define TBS_AUTOTICKS           0x0001
#define TBS_VERT                0x0002
#define TBS_HORZ                0x0000
#define TBS_TOP                 0x0004
#define TBS_BOTTOM              0x0000
#define TBS_LEFT                0x0004
#define TBS_RIGHT               0x0000
#define TBS_BOTH                0x0008
#define TBS_NOTICKS             0x0010
#define TBS_ENABLESELRANGE      0x0020
#define TBS_FIXEDLENGTH         0x0040
#define TBS_NOTHUMB             0x0080
#define TBS_TOOLTIPS            0x0100

#define TBM_GETPOS              (WM_USER)
#define TBM_GETRANGEMIN         (WM_USER + 1)
#define TBM_GETRANGEMAX         (WM_USER + 2)
#define TBM_SETPOS              (WM_USER + 5)
#define TBM_SETRANGE            (WM_USER + 6)
#define TBM_SETRANGEMIN         (WM_USER + 7)
#define TBM_SETRANGEMAX         (WM_USER + 8)
#define TBM_SETTICFREQ          (WM_USER + 20)
#define TBM_SETPAGESIZE         (WM_USER + 21)
#define TBM_GETPAGESIZE         (WM_USER + 22)
#define TBM_SETLINESIZE         (WM_USER + 23)
#define TBM_GETLINESIZE         (WM_USER + 24)
#define TBM_GETTHUMBRECT        (WM_USER + 25)
#define TBM_GETCHANNELRECT      (WM_USER + 26)
#define TBM_SETTHUMBLENGTH      (WM_USER + 27)
#define TBM_GETTHUMBLENGTH      (WM_USER + 28)

/* Spin control (Up-Down) */
#define UDS_WRAP                0x0001
#define UDS_SETBUDDYINT         0x0002
#define UDS_ALIGNRIGHT          0x0004
#define UDS_ALIGNLEFT           0x0008
#define UDS_AUTOBUDDY           0x0010
#define UDS_ARROWKEYS           0x0020
#define UDS_HORZ                0x0040
#define UDS_NOTHOUSANDS         0x0080
#define UDS_HOTTRACK            0x0100

#define UDM_SETRANGE            (WM_USER + 101)
#define UDM_GETRANGE            (WM_USER + 102)
#define UDM_SETPOS              (WM_USER + 103)
#define UDM_GETPOS              (WM_USER + 104)
#define UDM_SETBUDDY            (WM_USER + 105)
#define UDM_GETBUDDY            (WM_USER + 106)
#define UDM_SETACCEL            (WM_USER + 107)
#define UDM_GETACCEL            (WM_USER + 108)
#define UDM_SETBASE             (WM_USER + 109)
#define UDM_GETBASE             (WM_USER + 110)
#define UDM_SETRANGE32          (WM_USER + 111)
#define UDM_GETRANGE32          (WM_USER + 112)
#define UDM_SETPOS32            (WM_USER + 113)
#define UDM_GETPOS32            (WM_USER + 114)

/* Image list */
typedef HANDLE HIMAGELIST;

#define ILC_MASK                0x0001
#define ILC_COLOR               0x0000
#define ILC_COLORDDB            0x00FE
#define ILC_COLOR4              0x0004
#define ILC_COLOR8              0x0008
#define ILC_COLOR16             0x0010
#define ILC_COLOR24             0x0018
#define ILC_COLOR32             0x0020
#define ILC_PALETTE             0x0800
#define ILC_MIRROR              0x2000

#define ILD_NORMAL              0x0000
#define ILD_TRANSPARENT         0x0001
#define ILD_MASK                0x0010
#define ILD_IMAGE               0x0020
#define ILD_BLEND25             0x0002
#define ILD_BLEND50             0x0004
#define ILD_OVERLAYMASK         0x0F00
#define INDEXTOOVERLAYMASK(i)   ((i) << 8)

#define ILD_SELECTED            ILD_BLEND50
#define ILD_FOCUS               ILD_BLEND25
#define ILD_BLEND               ILD_BLEND50

static inline HIMAGELIST ImageList_Create(int cx, int cy, UINT flags, int cInitial, int cGrow) {
    (void)cx; (void)cy; (void)flags; (void)cInitial; (void)cGrow;
    return NULL;
}
static inline BOOL ImageList_Destroy(HIMAGELIST himl) {
    (void)himl;
    return TRUE;
}
static inline int ImageList_Add(HIMAGELIST himl, HBITMAP hbmImage, HBITMAP hbmMask) {
    (void)himl; (void)hbmImage; (void)hbmMask;
    return -1;
}
static inline int ImageList_AddIcon(HIMAGELIST himl, HICON hicon) {
    (void)himl; (void)hicon;
    return -1;
}
static inline int ImageList_AddMasked(HIMAGELIST himl, HBITMAP hbmImage, COLORREF crMask) {
    (void)himl; (void)hbmImage; (void)crMask;
    return -1;
}
static inline BOOL ImageList_Draw(HIMAGELIST himl, int i, HDC hdcDst, int x, int y, UINT fStyle) {
    (void)himl; (void)i; (void)hdcDst; (void)x; (void)y; (void)fStyle;
    return FALSE;
}
static inline HICON ImageList_GetIcon(HIMAGELIST himl, int i, UINT flags) {
    (void)himl; (void)i; (void)flags;
    return NULL;
}
static inline int ImageList_GetImageCount(HIMAGELIST himl) {
    (void)himl;
    return 0;
}
static inline BOOL ImageList_Remove(HIMAGELIST himl, int i) {
    (void)himl; (void)i;
    return TRUE;
}
static inline BOOL ImageList_SetOverlayImage(HIMAGELIST himl, int iImage, int iOverlay) {
    (void)himl; (void)iImage; (void)iOverlay;
    return TRUE;
}
#define ImageList_RemoveAll(himl) ImageList_Remove(himl, -1)

/* Toolbar */
#define TBSTYLE_BUTTON          0x0000
#define TBSTYLE_SEP             0x0001
#define TBSTYLE_CHECK           0x0002
#define TBSTYLE_GROUP           0x0004
#define TBSTYLE_CHECKGROUP      (TBSTYLE_GROUP | TBSTYLE_CHECK)
#define TBSTYLE_DROPDOWN        0x0008
#define TBSTYLE_AUTOSIZE        0x0010
#define TBSTYLE_NOPREFIX        0x0020
#define TBSTYLE_TOOLTIPS        0x0100
#define TBSTYLE_WRAPABLE        0x0200
#define TBSTYLE_ALTDRAG         0x0400
#define TBSTYLE_FLAT            0x0800
#define TBSTYLE_LIST            0x1000
#define TBSTYLE_CUSTOMERASE     0x2000
#define TBSTYLE_REGISTERDROP    0x4000
#define TBSTYLE_TRANSPARENT     0x8000

#define TB_ENABLEBUTTON         (WM_USER + 1)
#define TB_CHECKBUTTON          (WM_USER + 2)
#define TB_PRESSBUTTON          (WM_USER + 3)
#define TB_HIDEBUTTON           (WM_USER + 4)
#define TB_INDETERMINATE        (WM_USER + 5)
#define TB_ISBUTTONENABLED      (WM_USER + 9)
#define TB_ISBUTTONCHECKED      (WM_USER + 10)
#define TB_ISBUTTONPRESSED      (WM_USER + 11)
#define TB_ISBUTTONHIDDEN       (WM_USER + 12)
#define TB_ISBUTTONINDETERMINATE (WM_USER + 13)
#define TB_SETSTATE             (WM_USER + 17)
#define TB_GETSTATE             (WM_USER + 18)
#define TB_ADDBITMAP            (WM_USER + 19)
#define TB_ADDBUTTONSA          (WM_USER + 20)
#define TB_ADDBUTTONS           TB_ADDBUTTONSA
#define TB_INSERTBUTTONA        (WM_USER + 21)
#define TB_INSERTBUTTON         TB_INSERTBUTTONA
#define TB_DELETEBUTTON         (WM_USER + 22)
#define TB_GETBUTTON            (WM_USER + 23)
#define TB_BUTTONCOUNT          (WM_USER + 24)
#define TB_COMMANDTOINDEX       (WM_USER + 25)
#define TB_CUSTOMIZE            (WM_USER + 27)
#define TB_ADDSTRINGA           (WM_USER + 28)
#define TB_ADDSTRING            TB_ADDSTRINGA
#define TB_GETITEMRECT          (WM_USER + 29)
#define TB_BUTTONSTRUCTSIZE     (WM_USER + 30)
#define TB_SETBUTTONSIZE        (WM_USER + 31)
#define TB_SETBITMAPSIZE        (WM_USER + 32)
#define TB_AUTOSIZE             (WM_USER + 33)
#define TB_SETBUTTONWIDTH       (WM_USER + 43)
#define TB_SETMAXTEXTROWS       (WM_USER + 60)
#define TB_GETTEXTROWS          (WM_USER + 61)

typedef struct _TBBUTTON {
    int iBitmap;
    int idCommand;
    BYTE fsState;
    BYTE fsStyle;
    BYTE bReserved[2];
    DWORD_PTR dwData;
    INT_PTR iString;
} TBBUTTON, *PTBBUTTON, *LPTBBUTTON;

typedef const TBBUTTON *LPCTBBUTTON;

#define TBSTATE_CHECKED         0x01
#define TBSTATE_PRESSED         0x02
#define TBSTATE_ENABLED         0x04
#define TBSTATE_HIDDEN          0x08
#define TBSTATE_INDETERMINATE   0x10
#define TBSTATE_WRAP            0x20
#define TBSTATE_ELLIPSES        0x40
#define TBSTATE_MARKED          0x80

/* Status bar */
#define SBARS_SIZEGRIP          0x0100
#define SBARS_TOOLTIPS          0x0800

#define SB_SETTEXTA             (WM_USER + 1)
#define SB_SETTEXT              SB_SETTEXTA
#define SB_GETTEXTA             (WM_USER + 2)
#define SB_GETTEXT              SB_GETTEXTA
#define SB_GETTEXTLENGTHA       (WM_USER + 3)
#define SB_GETTEXTLENGTH        SB_GETTEXTLENGTHA
#define SB_SETPARTS             (WM_USER + 4)
#define SB_GETPARTS             (WM_USER + 6)
#define SB_GETBORDERS           (WM_USER + 7)
#define SB_SETMINHEIGHT         (WM_USER + 8)
#define SB_SIMPLE               (WM_USER + 9)
#define SB_GETRECT              (WM_USER + 10)
#define SB_ISSIMPLE             (WM_USER + 14)
#define SB_SETICON              (WM_USER + 15)
#define SB_GETICON              (WM_USER + 20)

/* Tooltip */
#define TTS_ALWAYSTIP           0x01
#define TTS_NOPREFIX            0x02
#define TTS_NOANIMATE           0x10
#define TTS_NOFADE              0x20
#define TTS_BALLOON             0x40
#define TTS_CLOSE               0x80

#define TTM_ACTIVATE            (WM_USER + 1)
#define TTM_SETDELAYTIME        (WM_USER + 3)
#define TTM_ADDTOOLA            (WM_USER + 4)
#define TTM_ADDTOOL             TTM_ADDTOOLA
#define TTM_DELTOOLA            (WM_USER + 5)
#define TTM_DELTOOL             TTM_DELTOOLA
#define TTM_NEWTOOLRECTA        (WM_USER + 6)
#define TTM_NEWTOOLRECT         TTM_NEWTOOLRECTA
#define TTM_RELAYEVENT          (WM_USER + 7)
#define TTM_GETTOOLINFOA        (WM_USER + 8)
#define TTM_GETTOOLINFO         TTM_GETTOOLINFOA
#define TTM_SETTOOLINFOA        (WM_USER + 9)
#define TTM_SETTOOLINFO         TTM_SETTOOLINFOA
#define TTM_HITTESTA            (WM_USER + 10)
#define TTM_HITTEST             TTM_HITTESTA
#define TTM_GETTEXTA            (WM_USER + 11)
#define TTM_GETTEXT             TTM_GETTEXTA
#define TTM_UPDATETIPTEXTA      (WM_USER + 12)
#define TTM_UPDATETIPTEXT       TTM_UPDATETIPTEXTA
#define TTM_GETTOOLCOUNT        (WM_USER + 13)
#define TTM_ENUMTOOLSA          (WM_USER + 14)
#define TTM_ENUMTOOLS           TTM_ENUMTOOLSA
#define TTM_GETCURRENTTOOLA     (WM_USER + 15)
#define TTM_GETCURRENTTOOL      TTM_GETCURRENTTOOLA
#define TTM_WINDOWFROMPOINT     (WM_USER + 16)
#define TTM_TRACKACTIVATE       (WM_USER + 17)
#define TTM_TRACKPOSITION       (WM_USER + 18)
#define TTM_SETTIPBKCOLOR       (WM_USER + 19)
#define TTM_SETTIPTEXTCOLOR     (WM_USER + 20)
#define TTM_GETDELAYTIME        (WM_USER + 21)
#define TTM_GETTIPBKCOLOR       (WM_USER + 22)
#define TTM_GETTIPTEXTCOLOR     (WM_USER + 23)
#define TTM_SETMAXTIPWIDTH      (WM_USER + 24)
#define TTM_GETMAXTIPWIDTH      (WM_USER + 25)
#define TTM_SETMARGIN           (WM_USER + 26)
#define TTM_GETMARGIN           (WM_USER + 27)
#define TTM_POP                 (WM_USER + 28)
#define TTM_UPDATE              (WM_USER + 29)

#define TTF_IDISHWND            0x0001
#define TTF_CENTERTIP           0x0002
#define TTF_RTLREADING          0x0004
#define TTF_SUBCLASS            0x0010
#define TTF_TRACK               0x0020
#define TTF_ABSOLUTE            0x0080
#define TTF_TRANSPARENT         0x0100
#define TTF_PARSELINKS          0x1000

typedef struct tagTOOLINFOA {
    UINT cbSize;
    UINT uFlags;
    HWND hwnd;
    UINT_PTR uId;
    RECT rect;
    HINSTANCE hinst;
    LPSTR lpszText;
    LPARAM lParam;
    void *lpReserved;
} TOOLINFOA, *PTOOLINFOA, *LPTOOLINFOA;

typedef TOOLINFOA TOOLINFO;
typedef PTOOLINFOA PTOOLINFO;
typedef LPTOOLINFOA LPTOOLINFO;

/* Notification codes */
#define NM_FIRST                (0U - 0U)
#define NM_OUTOFMEMORY          (NM_FIRST - 1)
#define NM_CLICK                (NM_FIRST - 2)
#define NM_DBLCLK               (NM_FIRST - 3)
#define NM_RETURN               (NM_FIRST - 4)
#define NM_RCLICK               (NM_FIRST - 5)
#define NM_RDBLCLK              (NM_FIRST - 6)
#define NM_SETFOCUS             (NM_FIRST - 7)
#define NM_KILLFOCUS            (NM_FIRST - 8)
#define NM_CUSTOMDRAW           (NM_FIRST - 12)
#define NM_HOVER                (NM_FIRST - 13)
#define NM_NCHITTEST            (NM_FIRST - 14)
#define NM_KEYDOWN              (NM_FIRST - 15)
#define NM_RELEASEDCAPTURE      (NM_FIRST - 16)
#define NM_SETCURSOR            (NM_FIRST - 17)
#define NM_CHAR                 (NM_FIRST - 18)
#define NM_TOOLTIPSCREATED      (NM_FIRST - 19)

#define LVN_FIRST               (0U - 100U)
#define LVN_LAST                (0U - 199U)
#define LVN_ITEMCHANGING        (LVN_FIRST - 0)
#define LVN_ITEMCHANGED         (LVN_FIRST - 1)
#define LVN_INSERTITEM          (LVN_FIRST - 2)
#define LVN_DELETEITEM          (LVN_FIRST - 3)
#define LVN_DELETEALLITEMS      (LVN_FIRST - 4)
#define LVN_BEGINLABELEDITA     (LVN_FIRST - 5)
#define LVN_BEGINLABELEDIT      LVN_BEGINLABELEDITA
#define LVN_ENDLABELEDITA       (LVN_FIRST - 6)
#define LVN_ENDLABELEDIT        LVN_ENDLABELEDITA
#define LVN_COLUMNCLICK         (LVN_FIRST - 8)
#define LVN_BEGINDRAG           (LVN_FIRST - 9)
#define LVN_BEGINRDRAG          (LVN_FIRST - 11)
#define LVN_GETDISPINFOA        (LVN_FIRST - 50)
#define LVN_GETDISPINFO         LVN_GETDISPINFOA
#define LVN_SETDISPINFOA        (LVN_FIRST - 51)
#define LVN_SETDISPINFO         LVN_SETDISPINFOA

#define TVN_FIRST               (0U - 400U)
#define TVN_LAST                (0U - 499U)
#define TVN_SELCHANGINGA        (TVN_FIRST - 1)
#define TVN_SELCHANGING         TVN_SELCHANGINGA
#define TVN_SELCHANGEDA         (TVN_FIRST - 2)
#define TVN_SELCHANGED          TVN_SELCHANGEDA
#define TVN_GETDISPINFOA        (TVN_FIRST - 3)
#define TVN_GETDISPINFO         TVN_GETDISPINFOA
#define TVN_SETDISPINFOA        (TVN_FIRST - 4)
#define TVN_SETDISPINFO         TVN_SETDISPINFOA
#define TVN_ITEMEXPANDINGA      (TVN_FIRST - 5)
#define TVN_ITEMEXPANDING       TVN_ITEMEXPANDINGA
#define TVN_ITEMEXPANDEDA       (TVN_FIRST - 6)
#define TVN_ITEMEXPANDED        TVN_ITEMEXPANDEDA
#define TVN_BEGINDRAGA          (TVN_FIRST - 7)
#define TVN_BEGINDRAG           TVN_BEGINDRAGA
#define TVN_BEGINRDRAGA         (TVN_FIRST - 8)
#define TVN_BEGINRDRAG          TVN_BEGINRDRAGA
#define TVN_DELETEITEMA         (TVN_FIRST - 9)
#define TVN_DELETEITEM          TVN_DELETEITEMA
#define TVN_BEGINLABELEDITA     (TVN_FIRST - 10)
#define TVN_BEGINLABELEDIT      TVN_BEGINLABELEDITA
#define TVN_ENDLABELEDITA       (TVN_FIRST - 11)
#define TVN_ENDLABELEDIT        TVN_ENDLABELEDITA
#define TVN_KEYDOWN             (TVN_FIRST - 12)

#define TCN_FIRST               (0U - 550U)
#define TCN_LAST                (0U - 580U)
#define TCN_KEYDOWN             (TCN_FIRST - 0)
#define TCN_SELCHANGE           (TCN_FIRST - 1)
#define TCN_SELCHANGING         (TCN_FIRST - 2)

/* Notification header */
typedef struct tagNMHDR {
    HWND hwndFrom;
    UINT_PTR idFrom;
    UINT code;
} NMHDR, *LPNMHDR;

/* Common control class names */
#define WC_LISTVIEWA            "SysListView32"
#define WC_LISTVIEW             WC_LISTVIEWA
#define WC_TREEVIEWA            "SysTreeView32"
#define WC_TREEVIEW             WC_TREEVIEWA
#define WC_TABCONTROLA          "SysTabControl32"
#define WC_TABCONTROL           WC_TABCONTROLA
#define STATUSCLASSNAMEA        "msctls_statusbar32"
#define STATUSCLASSNAME         STATUSCLASSNAMEA
#define TOOLBARCLASSNAMEA       "ToolbarWindow32"
#define TOOLBARCLASSNAME        TOOLBARCLASSNAMEA
#define PROGRESS_CLASSA         "msctls_progress32"
#define PROGRESS_CLASS          PROGRESS_CLASSA
#define TRACKBAR_CLASSA         "msctls_trackbar32"
#define TRACKBAR_CLASS          TRACKBAR_CLASSA
#define UPDOWN_CLASSA           "msctls_updown32"
#define UPDOWN_CLASS            UPDOWN_CLASSA
#define TOOLTIPS_CLASSA         "tooltips_class32"
#define TOOLTIPS_CLASS          TOOLTIPS_CLASSA

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_COMMCTRL_H */
