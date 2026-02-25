/*
 * FreeFalcon Linux Port - ATL Window compatibility stub
 *
 * Windows ATL Window support replacement.
 */

#ifndef FF_COMPAT_ATLWIN_H
#define FF_COMPAT_ATLWIN_H

#ifdef FF_LINUX

#include "AtlBase.h"

/* CWindow stub */
class CWindow {
public:
    HWND m_hWnd;
    CWindow(HWND hWnd = NULL) : m_hWnd(hWnd) {}
    operator HWND() const { return m_hWnd; }
};

/* CContainedWindow stub */
template <typename T>
class CContainedWindowT : public CWindow {};

typedef CContainedWindowT<CWindow> CContainedWindow;

/* BEGIN_MSG_MAP, MESSAGE_HANDLER, END_MSG_MAP stubs */
#define BEGIN_MSG_MAP(x) bool ProcessWindowMessage(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam, LRESULT& lResult, DWORD dwMsgMapID = 0) { (void)hWnd; (void)uMsg; (void)wParam; (void)lParam; (void)lResult; (void)dwMsgMapID;
#define MESSAGE_HANDLER(msg, func)
#define COMMAND_HANDLER(id, code, func)
#define CHAIN_MSG_MAP(theChainClass)
#define END_MSG_MAP() return false; }

/* Window message crackers */
#define DECLARE_WND_CLASS(WndClassName)
#define DECLARE_WND_CLASS_EX(WndClassName, style, bkgnd)

#endif /* FF_LINUX */
#endif /* FF_COMPAT_ATLWIN_H */
