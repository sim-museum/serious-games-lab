#include "stdhdr.h"
#include "otwdrive.h"
#include "debuggr.h"
#include "commands.h"
#include "sinput.h"

void CallInputFunction(unsigned long val, int state);

#ifdef FF_LINUX
// FF_LINUX: SDL keyboard buffer functions (defined in main_linux.cpp)
extern int FF_PopKeyEvents(DIDEVICEOBJECTDATA* outBuf, int maxEvents);
extern void FF_GetKeyState(unsigned char* outState, int size);
#endif

//***********************************
// void OnSimKeyboardInput()
//***********************************

void OnSimKeyboardInput()
{
    DIDEVICEOBJECTDATA ObjData[DKEYBOARD_BUFFERSIZE];
    DWORD dwElements;
    UINT i;
    static int ShiftCount = 0;
    static int CtrlCount = 0;
    static int AltCount = 0;
    int state;

#ifdef FF_LINUX
    // FF_LINUX: Read keyboard events from SDL buffer instead of DirectInput
    dwElements = FF_PopKeyEvents(ObjData, DKEYBOARD_BUFFERSIZE);
#else
    HRESULT hResult;
    dwElements = DKEYBOARD_BUFFERSIZE;
    hResult = gpDIDevice[SIM_KEYBOARD]->GetDeviceData(sizeof(DIDEVICEOBJECTDATA), ObjData, &dwElements, 0);

    if (hResult == DIERR_INPUTLOST)
    {
        gpDeviceAcquired[SIM_KEYBOARD] = FALSE;
        return;
    }

    if (!SUCCEEDED(hResult))
        return;
#endif

    {
        for (i = 0; i < dwElements; i++)
        {
            if (ObjData[i].dwData bitand 0x80)
            {
                // key is down
                switch (ObjData[i].dwOfs)
                {
                    case DIK_LSHIFT:
                    case DIK_RSHIFT:
                    {
                        ShiftCount ++;
                    }
                    break;

                    case DIK_LCONTROL:
                    case DIK_RCONTROL:
                        CtrlCount ++;
                        break;

                    case DIK_LMENU:
                    case DIK_RMENU:
                        AltCount ++;
                        break;

                    default:
                        state  = KEY_DOWN;
                        state or_eq (ShiftCount > 0 ? SHIFT_KEY : 0);
                        state or_eq (CtrlCount > 0 ? CTRL_KEY : 0);
                        state or_eq (AltCount > 0 ? ALT_KEY : 0);
                        CallInputFunction(ObjData[i].dwOfs, state);
                        break;
                }
            }
            else
            {
                switch (ObjData[i].dwOfs)
                {
                    case DIK_LSHIFT:
                    case DIK_RSHIFT:
                        ShiftCount --;
                        break;

                    case DIK_LCONTROL:
                    case DIK_RCONTROL:
                        CtrlCount --;
                        break;

                    case DIK_LMENU:
                    case DIK_RMENU:
                        AltCount --;
                        break;

                    default:
                        state = (ShiftCount > 0 ? SHIFT_KEY : 0);
                        state or_eq (CtrlCount > 0 ? CTRL_KEY : 0);
                        state or_eq (AltCount > 0 ? ALT_KEY : 0);
                        CallInputFunction(ObjData[i].dwOfs, state);
                        break;
                }
            }
        }

#ifdef FF_LINUX
        // FF_LINUX: Read key state from SDL buffer
        unsigned char buffer[256];
        FF_GetKeyState(buffer, sizeof(buffer));
#else
        //after every pass we reset the counts to try to keep them sane
        char buffer[256];
        hResult = gpDIDevice[SIM_KEYBOARD]->GetDeviceState(sizeof(buffer), (LPVOID)&buffer);

        if (hResult != DI_OK)
            return;
#endif

        {
            if (buffer[DIK_LSHIFT] bitand 0x80)
            {
                ShiftCount = 1;
            }
            else
            {
                ShiftCount = 0;
            }

            if (buffer[DIK_RSHIFT] bitand 0x80)
            {
                ShiftCount++;
            }

            if (buffer[DIK_LCONTROL] bitand 0x80)
            {
                CtrlCount = 1;
            }
            else
            {
                CtrlCount = 0;
            }

            if (buffer[DIK_RCONTROL] bitand 0x80)
            {
                CtrlCount++;
            }

            if (buffer[DIK_LMENU] bitand 0x80)
            {
                AltCount = 1;
            }
            else
            {
                AltCount = 0;
            }

            if (buffer[DIK_RMENU] bitand 0x80)
            {
                AltCount++;
            }
        }
    }
}
