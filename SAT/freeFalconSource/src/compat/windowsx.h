/*
 * FreeFalcon Linux Port - windowsx.h compatibility
 *
 * Windows extended macros compatibility for Linux
 * This header provides convenience macros for window message handling
 */

#ifndef FF_COMPAT_WINDOWSX_H
#define FF_COMPAT_WINDOWSX_H

#ifdef FF_LINUX

#include "windows.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Message Cracker Macros
 * ============================================================ */

/* GET macros for extracting values from LPARAM/WPARAM */
#define GET_WM_COMMAND_ID(wp, lp)           LOWORD(wp)
#define GET_WM_COMMAND_HWND(wp, lp)         ((HWND)(lp))
#define GET_WM_COMMAND_CMD(wp, lp)          HIWORD(wp)

#define GET_X_LPARAM(lp)                    ((int)(short)LOWORD(lp))
#define GET_Y_LPARAM(lp)                    ((int)(short)HIWORD(lp))

/* FORWARD macros for message forwarding */
#define FORWARD_WM_COMMAND(hwnd, id, hwndCtl, codeNotify, fn) \
    (void)(fn)((hwnd), WM_COMMAND, MAKEWPARAM((UINT)(id),(UINT)(codeNotify)), (LPARAM)(hwndCtl))

/* HANDLE macros for message handling */
#define HANDLE_MSG(hwnd, message, fn) \
    case (message): return HANDLE_##message((hwnd), (wParam), (lParam), (fn))

/* Button control macros */
#define Button_Enable(hwndCtl, fEnable)     EnableWindow((hwndCtl), (fEnable))
#define Button_GetCheck(hwndCtl)            ((int)(DWORD)SendMessageA((hwndCtl), BM_GETCHECK, 0L, 0L))
#define Button_SetCheck(hwndCtl, check)     ((void)SendMessageA((hwndCtl), BM_SETCHECK, (WPARAM)(int)(check), 0L))

/* Edit control macros */
#define Edit_Enable(hwndCtl, fEnable)       EnableWindow((hwndCtl), (fEnable))
#define Edit_GetText(hwndCtl, lpch, cchMax) GetWindowTextA((hwndCtl), (lpch), (cchMax))
#define Edit_SetText(hwndCtl, lpsz)         SetWindowTextA((hwndCtl), (lpsz))
#define Edit_GetTextLength(hwndCtl)         GetWindowTextLengthA(hwndCtl)
#define Edit_LimitText(hwndCtl, cchMax)     ((void)SendMessageA((hwndCtl), EM_LIMITTEXT, (WPARAM)(cchMax), 0L))
#define Edit_SetSel(hwndCtl, ichStart, ichEnd) ((void)SendMessageA((hwndCtl), EM_SETSEL, (ichStart), (ichEnd)))

/* ListBox control macros */
#define ListBox_Enable(hwndCtl, fEnable)    EnableWindow((hwndCtl), (fEnable))
#define ListBox_GetCount(hwndCtl)           ((int)(DWORD)SendMessageA((hwndCtl), LB_GETCOUNT, 0L, 0L))
#define ListBox_GetCurSel(hwndCtl)          ((int)(DWORD)SendMessageA((hwndCtl), LB_GETCURSEL, 0L, 0L))
#define ListBox_SetCurSel(hwndCtl, index)   ((int)(DWORD)SendMessageA((hwndCtl), LB_SETCURSEL, (WPARAM)(int)(index), 0L))
#define ListBox_AddString(hwndCtl, lpsz)    ((int)(DWORD)SendMessageA((hwndCtl), LB_ADDSTRING, 0L, (LPARAM)(LPCTSTR)(lpsz)))
#define ListBox_DeleteString(hwndCtl, index) ((int)(DWORD)SendMessageA((hwndCtl), LB_DELETESTRING, (WPARAM)(int)(index), 0L))
#define ListBox_ResetContent(hwndCtl)       ((BOOL)(DWORD)SendMessageA((hwndCtl), LB_RESETCONTENT, 0L, 0L))
#define ListBox_GetItemData(hwndCtl, index) ((LRESULT)(ULONG_PTR)SendMessageA((hwndCtl), LB_GETITEMDATA, (WPARAM)(int)(index), 0L))
#define ListBox_SetItemData(hwndCtl, index, data) ((int)(DWORD)SendMessageA((hwndCtl), LB_SETITEMDATA, (WPARAM)(int)(index), (LPARAM)(data)))
#define ListBox_GetText(hwndCtl, index, lpszBuffer) ((int)(DWORD)SendMessageA((hwndCtl), LB_GETTEXT, (WPARAM)(int)(index), (LPARAM)(LPCTSTR)(lpszBuffer)))

/* ComboBox control macros */
#define ComboBox_Enable(hwndCtl, fEnable)   EnableWindow((hwndCtl), (fEnable))
#define ComboBox_GetCount(hwndCtl)          ((int)(DWORD)SendMessageA((hwndCtl), CB_GETCOUNT, 0L, 0L))
#define ComboBox_GetCurSel(hwndCtl)         ((int)(DWORD)SendMessageA((hwndCtl), CB_GETCURSEL, 0L, 0L))
#define ComboBox_SetCurSel(hwndCtl, index)  ((int)(DWORD)SendMessageA((hwndCtl), CB_SETCURSEL, (WPARAM)(int)(index), 0L))
#define ComboBox_AddString(hwndCtl, lpsz)   ((int)(DWORD)SendMessageA((hwndCtl), CB_ADDSTRING, 0L, (LPARAM)(LPCTSTR)(lpsz)))
#define ComboBox_DeleteString(hwndCtl, index) ((int)(DWORD)SendMessageA((hwndCtl), CB_DELETESTRING, (WPARAM)(int)(index), 0L))
#define ComboBox_ResetContent(hwndCtl)      ((int)(DWORD)SendMessageA((hwndCtl), CB_RESETCONTENT, 0L, 0L))
#define ComboBox_GetItemData(hwndCtl, index) ((LRESULT)(ULONG_PTR)SendMessageA((hwndCtl), CB_GETITEMDATA, (WPARAM)(int)(index), 0L))
#define ComboBox_SetItemData(hwndCtl, index, data) ((int)(DWORD)SendMessageA((hwndCtl), CB_SETITEMDATA, (WPARAM)(int)(index), (LPARAM)(data)))
#define ComboBox_GetText(hwndCtl, lpch, cchMax) GetWindowTextA((hwndCtl), (lpch), (cchMax))
#define ComboBox_SetText(hwndCtl, lpsz)     SetWindowTextA((hwndCtl), (lpsz))
#define ComboBox_LimitText(hwndCtl, cchLimit) ((int)(DWORD)SendMessageA((hwndCtl), CB_LIMITTEXT, (WPARAM)(int)(cchLimit), 0L))

/* Static control macros */
#define Static_Enable(hwndCtl, fEnable)     EnableWindow((hwndCtl), (fEnable))
#define Static_SetText(hwndCtl, lpsz)       SetWindowTextA((hwndCtl), (lpsz))
#define Static_GetText(hwndCtl, lpch, cchMax) GetWindowTextA((hwndCtl), (lpch), (cchMax))

/* ScrollBar control macros */
#define ScrollBar_Enable(hwndCtl, flags)    EnableScrollBar((hwndCtl), SB_CTL, (flags))
#define ScrollBar_GetPos(hwndCtl)           GetScrollPos((hwndCtl), SB_CTL)
#define ScrollBar_SetPos(hwndCtl, pos, fRedraw) SetScrollPos((hwndCtl), SB_CTL, (pos), (fRedraw))

/* Window macros */
#define SetWindowFont(hwnd, hfont, fRedraw) \
    ((void)SendMessageA((hwnd), WM_SETFONT, (WPARAM)(HFONT)(hfont), (LPARAM)(BOOL)(fRedraw)))
#define GetWindowFont(hwnd) \
    ((HFONT)(UINT_PTR)SendMessageA((hwnd), WM_GETFONT, 0L, 0L))

/* Memory allocation macros (GlobalAlloc/GlobalFree wrappers) */
#define GlobalAllocPtr(flags, cb)           ((LPVOID)GlobalAlloc((flags), (cb)))
#define GlobalFreePtr(lp)                   (GlobalFree((HGLOBAL)(lp)), (void)0)
#define GlobalPtrHandle(lp)                 ((HGLOBAL)(lp))
#define GlobalLockPtr(lp)                   ((LPVOID)(lp))
#define GlobalUnlockPtr(lp)                 ((void)0)
#define GlobalReAllocPtr(lp, cbNew, flags)  ((LPVOID)GlobalReAlloc((HGLOBAL)(lp), (cbNew), (flags)))

/* SelectFont, SelectBrush, SelectPen macros */
#define SelectFont(hdc, hfont)              ((HFONT)SelectObject((hdc), (HGDIOBJ)(HFONT)(hfont)))
#define SelectBrush(hdc, hbr)               ((HBRUSH)SelectObject((hdc), (HGDIOBJ)(HBRUSH)(hbr)))
#define SelectPen(hdc, hpen)                ((HPEN)SelectObject((hdc), (HGDIOBJ)(HPEN)(hpen)))
#define SelectBitmap(hdc, hbm)              ((HBITMAP)SelectObject((hdc), (HGDIOBJ)(HBITMAP)(hbm)))

/* DeleteFont, DeleteBrush, DeletePen macros */
#define DeleteFont(hfont)                   DeleteObject((HGDIOBJ)(HFONT)(hfont))
#define DeleteBrush(hbr)                    DeleteObject((HGDIOBJ)(HBRUSH)(hbr))
#define DeletePen(hpen)                     DeleteObject((HGDIOBJ)(HPEN)(hpen))
#define DeleteBitmap(hbm)                   DeleteObject((HGDIOBJ)(HBITMAP)(hbm))

/* GetStockFont, GetStockBrush, GetStockPen */
#define GetStockFont(i)                     ((HFONT)GetStockObject(i))
#define GetStockBrush(i)                    ((HBRUSH)GetStockObject(i))
#define GetStockPen(i)                      ((HPEN)GetStockObject(i))

/* Color macros */
#define GetRValue(rgb)                      ((BYTE)(rgb))
#define GetGValue(rgb)                      ((BYTE)(((WORD)(rgb)) >> 8))
#define GetBValue(rgb)                      ((BYTE)((rgb) >> 16))

/* GDI object macros */
#define InsetRect(lprc, dx, dy)             InflateRect((lprc), -(dx), -(dy))

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_WINDOWSX_H */
