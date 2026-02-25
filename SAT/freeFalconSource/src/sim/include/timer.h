/******************************************************************************/
/*                                                                            */
/*  Unit Name : timer.h                                                       */
/*                                                                            */
/*  Abstract  : Header file with class definition for SIMLIB_TIMER_CLASS      */
/*              and defines used in its implementation.                       */
/*                                                                            */
/*  Development History :                                                     */
/*  Date      Programer           Description                                 */
/*----------------------------------------------------------------------------*/
/*  23-Jan-95 LR                  Initial Write                               */
/*                                                                            */
/******************************************************************************/
#ifndef _TIMER_H
#define _TIMER_H

#include "simlib.h"

/* Constants */
#define SIM_MAX_TIMERS      20

/* Timer types */
#define SIM_TIMER_PERIODIC  1
#define SIM_TIMER_ONESHOT   2

/* Type definitions */
typedef SIM_INT SIM_TIMER_HANDLE;

/* Timer callback type - matches Windows LPTIMECALLBACK signature */
typedef void (CALLBACK *LPTIMECALLBACK)(UINT uTimerID, UINT uMsg, DWORD_PTR dwUser, DWORD_PTR dw1, DWORD_PTR dw2);

/* Instance data for timer callbacks */
struct SIMLIB_TIMER_INSTANCE_DATA
{
    SIM_TIMER_HANDLE _hTimer;
    class SIMLIB_TIMER_CLASS *_pTimer;
};

/* Internal timer data structure */
struct SIMLIB_TIMER_DATA
{
    SIM_INT id;
    SIM_INT period;
    SIM_INT resolution;
    SIM_INT type;
    SIMLIB_TIMER_INSTANCE_DATA inst;
};

/* Timer class */
class SIMLIB_TIMER_CLASS
{
private:
    SIMLIB_TIMER_DATA _timer[SIM_MAX_TIMERS];

    SIM_TIMER_HANDLE FindUnusedHandle(void);
    SIM_TIMER_HANDLE IndexToHandle(int index) { return index + 1; }

public:
    /* These are public because CountdownEventCleanup needs access */
    int HandleToIndex(SIM_TIMER_HANDLE handle) { return handle - 1; }
    void Cleanup(int index) { _timer[index].id = 0; }
    SIMLIB_TIMER_CLASS(void);
    ~SIMLIB_TIMER_CLASS(void);

    SIM_TIMER_HANDLE StartTimer(SIM_INT period, SIM_INT res, LPTIMECALLBACK funcPtr, DWORD userData);
    SIM_INT StopTimer(SIM_TIMER_HANDLE hTimer);
    SIM_TIMER_HANDLE StartCountdown(SIM_INT delay, SIM_INT res, LPTIMECALLBACK funcPtr, DWORD userData);
    SIM_INT Wait(SIM_INT delay);
};

/* External timer instance */
extern SIMLIB_TIMER_CLASS Timer;

/* External timer variables */
extern SIM_FLOAT SimLibMinorFrameTime;
extern SIM_FLOAT SimLibMinorFrameRate;
extern SIM_FLOAT SimLibMajorFrameTime;
extern SIM_FLOAT SimLibMajorFrameRate;
extern SIM_FLOAT SimLibTimeOfDay;
extern VU_TIME SimLibElapsedTime;  // FF_LINUX: Use VU_TIME for binary compat
extern SIM_UINT SimLibFrameCount;
extern SIM_INT SimLibMinorPerMajor;

/* Timer cleanup function */
void CountdownEventCleanup(SIMLIB_TIMER_INSTANCE_DATA *cleanupData);

#endif
