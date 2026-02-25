/***************************************************************************
  SimLoop.cpp
  Scott Randolph
  June 18, 1998

  This class is the master loop for the simulation and graphics.
  It starts and stops each as appropriate during transitions between
  the SIM and UI.
***************************************************************************/
#include "stdhdr.h"
#ifdef FF_LINUX
#include <fenv.h>
#include <pthread.h>
#endif
#include "graphics/include/loader.h"
#include "find.h"
#include "Flight.h"
#include "FalcSess.h"
#include "ui/include/FalcUser.h"
#include "ThreadMgr.h"
#include "dispcfg.h"
#include "simdrive.h"
#include "otwdrive.h"
#include "sinput.h"
#include "Statistics.h"
#include "SimLoop.h"
#include "Campaign.h"
#include "Dogfight.h"
#include "TimerThread.h"
#include "playerop.h"
#include "GameMgr.h"
#include "fsound.h"
#include "graphics/include/texbank.h"
#include "MsgInc/SimCampMsg.h"
#include "acmi/src/include/acmirec.h"
#include "ui/include/uicomms.h"
#include "ehandler.h"
#include "VRInput.h"
#include "aircrft.h"
#include "playerop.h"
#include "graphics/include/tod.h"

// Almost works, but seems to cause trouble if wait for loader is disabled or on very fast (450+) machines.
#define DELAY_TEX_LOAD // Define this to delay object texture loads for improved disk access locality

extern int endAbort; // From OTWdrive.cpp
extern volatile int gLeftToDeaggregate; // defined in Campaign.cpp
extern unsigned short BUBBLE_REBUILD_TIME;
extern int wait_for_loaded;
extern int prevskycol;
extern char FalconTerrainDataDir[_MAX_PATH];

extern void RebuildBubble(int forced);
extern void CampaignAutoSave(FalconGameType gametype); // defined in WinMain.cpp
extern void set_spinner1(int);
extern void ACMI_ImportFile(void);
extern int tactical_is_training(void);
extern void RecordPlayerFlightStart(void);
bool g_bSleepAll;//me123
// FF_LINUX: volatile for cross-thread visibility
volatile SimulationLoopControl::SimLoopControlMode SimulationLoopControl::currentMode = SimulationLoopControl::Stopped;
HANDLE SimulationLoopControl::wait_for_start_graphics = 0;
HANDLE SimulationLoopControl::wait_for_stop_graphics = 0;
HANDLE SimulationLoopControl::wait_for_sim_cleanup = 0;
HANDLE SimulationLoopControl::wait_for_graphics_cleanup = 0;
int SimulationLoopControl::sim_tick;
int gRebuildBubbleNow = 0;
int sRewakeSessions = 0;
int dumpMem = 0;
void FixupGroundHeights(void);
void RewakeSessions(void);
extern CampaignTime gLaunchTime;
// Move this to AIInput when I feel like rebuilding
int DIRTY_SEND_TIME_MS = 100;

#ifdef DEBUG
#define DO_SIM_TIME
#endif
DWORD gSimThreadID;

#ifdef CHECK_PROC_TIMES
#ifndef DO_SIM_TIME
#define DO_SIM_TIME
#endif
ulong gMaxSimTime = 0;
ulong gMaxGraphicsTime = 0;
ulong gInputTime = 0;
ulong gBubbleTime = 0;
ulong gMaxInputTime = 0;
ulong gMaxBubbleTime = 0;
extern int gCampTime;
ulong gMaxCampTime;
ulong gDDMaxTime = 0;
ulong gDDTime = 0;

extern ulong terrTime;
extern ulong objTime;
#endif

#ifdef DEBUG
#define FUNKY_KEVIN_DEBUG_STUFF 1
extern int inMission;
#endif

#include "IVibeData.h"
extern IntellivibeData g_intellivibeData;
extern void *gSharedIntellivibe;

// This function just gets from C call style required by the threader
// back into C++
static unsigned int __stdcall SimLoopWrapper(void)
{
    //#ifdef DEBUG
    gSimThreadID = GetCurrentThreadId();
    //#endif

    int Result = 0;

#ifdef _WIN32
    __try
    {
        SimulationLoopControl::Loop();
    }
    __except (RecordExceptionInfo(GetExceptionInformation(), "SimLoop Thread"))
    {
        // Do nothing here - RecordExceptionInfo() has already done
        // everything that is needed. Actually this code won't even
        // get called unless you return EXCEPTION_EXECUTE_HANDLER from
        // the __except clause.
    }
#else
    // On Linux, we don't have SEH - just call directly
    SimulationLoopControl::Loop();
#endif

    return Result;
}


static unsigned int __stdcall StartingGraphicsWrapper(void)
{
#ifdef _MSC_VER
    // Set the FPU to Truncate
    _controlfp(_RC_CHOP, MCW_RC);

    // Set the FPU to 24bit precision
    _controlfp(_PC_24, MCW_PC);
#endif

    int Result = 0;

#ifdef _WIN32
    __try
    {
        SimulationLoopControl::StartLoop();
    }
    __except (RecordExceptionInfo(GetExceptionInformation(), "StartLoop Thread"))
    {
        // Do nothing here - RecordExceptionInfo() has already done
        // everything that is needed. Actually this code won't even
        // get called unless you return EXCEPTION_EXECUTE_HANDLER from
        // the __except clause.
    }
#else
    // On Linux, we don't have SEH - just call directly
    SimulationLoopControl::StartLoop();
#endif

    return Result;
}

// Initialize our selves and start a new thread to run the loop.
// We only create the thread.  It will actually start executing later.
void SimulationLoopControl::StartSim(void)
{
    DWORD value;

    // Don't start until we're ready
    while (currentMode not_eq Stopped)
    {
        Sleep(50);
    }

    SimDriver.Startup();

    // Start the thread looping
    ThreadManager::start_sim_thread(SimLoopWrapper);

    wait_for_start_graphics = CreateEvent(0, 0, 0, 0);
    wait_for_stop_graphics = CreateEvent(0, 0, 0, 0);
    wait_for_sim_cleanup = CreateEvent(0, 0, 0, 0);
    wait_for_graphics_cleanup = CreateEvent(0, 0, 0, 0);

    CreateThread(
        NULL, 0, (unsigned long(__stdcall*)(void*))StartingGraphicsWrapper, 0, 0, &value
    );
}


// Kill the simluation loop.  Graphics must already be stopped.
// This function blocks until the simulation loop is really gone.
void SimulationLoopControl::StopSim(void)
{
    // Don't stop until we're sure we're running
    while (currentMode not_eq RunningSim)
    {
        Sleep(50);
    }

    currentMode = StoppingSim;

    // in case its blocked
    ThreadManager::campaign_signal_sim();

    // sfr: This blocks until the thread is gone...
    ThreadManager::stop_sim_thread();

    SimDriver.Cleanup();

    currentMode = Stopped;

    CloseHandle(wait_for_start_graphics);
    CloseHandle(wait_for_stop_graphics);
    CloseHandle(wait_for_sim_cleanup);
    CloseHandle(wait_for_graphics_cleanup);
}


// This sets a flag to ask that the loop begin drawing graphics.
// We only set a flag.  The graphics will actually start later.

void SimulationLoopControl::StartGraphics(void)
{
    // Don't start until we're ready
    ///////////////////MP hacK
    int delayCounter = 1200; // 2 minutes
    bool someoneawake = 1;
    g_bSleepAll = TRUE;//me123 host it's ok to sleep

    // gRebuildBubbleNow = TRUE;
    while (someoneawake and (delayCounter))
    {
        someoneawake = FALSE;
        SimBaseClass* theObject;
        VuListIterator objectWalker(SimDriver.objectList);
        theObject = (SimBaseClass*)objectWalker.GetFirst();

        while (theObject and not someoneawake)
        {
            if (theObject->IsAwake())
            {
                someoneawake = TRUE;
            }

            theObject = (SimBaseClass*)objectWalker.GetNext();
        }

        VuListIterator objecttiveswalker(SimDriver.campObjList);
        theObject = (SimBaseClass*)objecttiveswalker.GetFirst();

        while (theObject and not someoneawake)
        {
            if (theObject->IsAwake())
            {
                someoneawake = TRUE;
            }

            theObject = (SimBaseClass*)objecttiveswalker.GetNext();
        }

        Sleep(100);
        delayCounter --;
    }

    ////////////////// mp hack
    if (OTWDriver.IsActive())
    {
        SimDriver.Exit();
        OTWDriver.SetActive(FALSE);
    }

    while (currentMode not_eq RunningSim)
    {
        Sleep(50);
    }

    currentMode = StartingGraphics;
    __sync_synchronize();  // Full memory barrier
}


// This sets a flag to ask that the loop shutdown the graphics
// We only set a flag.  The graphics will actually stop later.
void SimulationLoopControl::StopGraphics()
{
    // Don't stop until we're sure we're running
    while (currentMode not_eq RunningGraphics)
    {
        Sleep(50);
    }

    currentMode = StoppingGraphics;
}

int gSimWaitTime = 0;
int gSimTime = 0;
int gGraphicsTime = 0;
int gGraphicsTimeLast = 0;
int gAveSimGraphicsTime = 0;

#ifdef DEMO_VERSION_THAT_WE_ALL_HATE
int first_frame_time = 0;
#endif

///////////////////////////////////////////////////////////////////////////////
// This is the main processing loop for the simulation and graphics

void SimulationLoopControl::Loop(void)
{
    DWORD delta;
    DWORD real_delta;
    CampaignTime lastBubbleTime = 0;
#ifdef NO_TIMER_THREAD
    CampaignTime tmpTime;
#endif

    static int last_vr = 0;

#if defined(_MSC_VER)
    _controlfp(_RC_CHOP, MCW_RC); // Set the FPU to Truncate
    _controlfp(_PC_24, MCW_PC); // Set the FPU to 24 bit precision
#elif defined(FF_LINUX)
    /* Linux: Use fesetround for rounding mode.
     * Note: 24-bit precision control is x87-specific and not available on SSE.
     * Modern compilers use SSE by default which has fixed precision.
     */
    fesetround(FE_TOWARDZERO); // Equivalent to _RC_CHOP (truncate toward zero)
#else
#error Pay special attention to rounding mode and precision effects on floating point ops
#endif

    // Record the fact that we're up and running
    currentMode = RunningSim;

    //while (currentMode not_eq StoppingSim)
    do
    {
#ifdef FF_LINUX
        // On Linux, block during Step5 (StoppingGraphics) to avoid race conditions.
        // Step2 cannot be completely blocked because RebuildBubble() is needed for deaggregation.
        if (currentMode == Step5)
        {
            Sleep(10);  // Yield while waiting for state transition
            continue;   // Skip this iteration entirely
        }
        // During Step2, add a small yield to reduce contention but allow processing
        if (currentMode == Step2)
        {
            Sleep(5);
        }
#endif

        //START_PROFILE("INPUT");

        sim_tick ++;
        set_spinner1(sim_tick);

        // Get input if we're "in game"
        if (currentMode == RunningGraphics)
        {
            InputCycle();
        }
        else
        {
            NoInputCycle();
        }

        //STOP_PROFILE("INPUT");

        //START_PROFILE("BUBBLE");

        // Rebuild the bubble here - CRITICAL for deaggregation during Step2
#ifdef FF_LINUX
        // FF_LINUX: During Step2, force RebuildBubble to run every iteration
        // to ensure deaggregation happens even though vuxRealTime isn't advancing
        if (
            currentMode == Step2 or
            gRebuildBubbleNow or (
                static_cast<CampaignTime>(vuxRealTime - lastBubbleTime) >
                static_cast<CampaignTime>(BUBBLE_REBUILD_TIME * CampaignSeconds)
            )
        )
#else
        if (
            gRebuildBubbleNow or (
                static_cast<CampaignTime>(vuxRealTime - lastBubbleTime) >
                static_cast<CampaignTime>(BUBBLE_REBUILD_TIME * CampaignSeconds)
            )
        )
#endif
        {
            int forced = 0;

            if (gRebuildBubbleNow == 2)
            {
                forced = 1;
            }

            if (
                (static_cast<CampaignTime>(vuxRealTime - lastBubbleTime) >
                 static_cast<CampaignTime>(BUBBLE_REBUILD_TIME * CampaignSeconds))
            )
            {
                forced = 0;
            }

            RebuildBubble(forced);

            if ( not forced)
            {
                lastBubbleTime = vuxRealTime;
            }

            gRebuildBubbleNow = 0;

        }

#ifdef FF_LINUX
        // FF_LINUX: During Step2 (graphics initialization), we need to process VU messages
        // for deaggregation to happen, but then must let the switch statement run
        // to check for mode transitions (Step2 -> StartRunningGraphics -> RunningGraphics).
        if (currentMode == Step2)
        {
            // CRITICAL: Update vuxRealTime before RealTimeFunction or it will skip
            // the gMainThread->Update() call due to rate limiting (vuxRealTime > update_time)
            vuxRealTime = GetTickCount();

            // Process VU messages via RealTimeFunction - this is needed for deaggregation
            // RealTimeFunction calls gMainThread->Update() which processes the
            // simcampDeaggregate message sent by RebuildBubble
            RealTimeFunction(vuxRealTime, NULL);

            // Signal campaign thread and give it time to run
            ThreadManager::sim_signal_campaign();
            ThreadManager::sim_wait_for_campaign(10);
            // NOTE: Don't continue here - fall through to switch statement for mode transition check
        }
#endif

        //STOP_PROFILE("BUBBLE");

        //START_PROFILE("TIMER");
#ifdef NO_TIMER_THREAD

        // Increment time
        vuxRealTime = GetTickCount();
        real_delta = delta = (vuxRealTime - lastStartTime);

        if (
            FalconLocalGame and (
                ((vuPlayerPoolGroup) and (FalconLocalGame->Id() not_eq vuPlayerPoolGroup->Id())) or not vuPlayerPoolGroup
            )
        )
        {
            if (( not FalconLocalGame->IsLocal()) and (lastTimingMessage > 0))
            {
                static int last_ratio = 0;
                int y, ratio, lookahead;

                lookahead = 2000;

                // KCK Add half of lookahead time, so we round to nearest
                // integer compression
                //me123 added 100 for latency
                y = vuxTargetGameTime + (targetGameCompressionRatio * lookahead) - vuxGameTime;

                if (y < 0)
                {
                    ratio = 0;
                }
                else if (y <= lookahead + 2000)
                {
                    //  me123 changed this to ajust fluently
                    // we are less then 2 sec infront
                    if ((y >= lookahead) and (delta))
                    {
                        // we are behind
                        delta = delta * (min(10, (y - lookahead) / 10) + 100) / 100; //
                    }
                    else if ((y <= lookahead) and (delta))
                    {
                        // we are infront
                        delta = delta * ((100 - min(10, (lookahead - y) / 10)) / 100); //
                    }

                    ratio = 1;
                }
                else
                {
                    ratio = y / lookahead;

                    if (ratio < 4)
                    {
                        ratio = 2;
                    }
                    else if (ratio < 8)
                    {
                        ratio = 4;
                    }
                }

                if (vuxRealTime > vuxDeadReconTime)
                {
                    ratio = 0;
                }

                if (ratio not_eq last_ratio)
                {
                    last_ratio = ratio;
                }

                SetOnlineTimeCompression(ratio);

                tmpTime = vuxGameTime + delta * gameCompressionRatio;

                if (vuxRealTime < vuxDeadReconTime)
                {
                    int compress;
                    compress = targetGameCompressionRatio;

                    if (compress > 4)
                    {
                        compress = 4;
                    }

                    vuxTargetGameTime = vuxTargetGameTime + real_delta * compress; // lets dead recon time
                }
            }
            else
            {
                //we are host
                VuSessionsIterator sessionIter(vuLocalGame);
                int flying = FALSE;

                for (
                    VuSessionEntity *sess = sessionIter.GetFirst(), *nextSess;
                    sess not_eq NULL and not flying;
                    sess = nextSess
                )
                {
                    nextSess = sessionIter.GetNext();
                    FalconSessionEntity *sessionEntity = static_cast<FalconSessionEntity*>(sess);

                    if (sessionEntity not_eq NULL)
                    {
                        uchar flyState = sessionEntity->GetFlyState();

                        if (
                            (flyState ==  FLYSTATE_FLYING) or
                            (flyState ==  FLYSTATE_WAITING) or
                            (flyState ==  FLYSTATE_LOADING)
                        )
                        {
                            flying = TRUE;
                        }
                    }
                }

                if (
                    flying and gameCompressionRatio > 4
                   and (gCommsMgr and gCommsMgr->Online())
                )
                {
                    SetTimeCompression(1) ;
                }

                tmpTime = vuxGameTime + delta * gameCompressionRatio;
            }

            if (
                FalconLocalSession->GetFlyState() not_eq FLYSTATE_FLYING and 
                gCompressTillTime and tmpTime > gLaunchTime + 1000
            )
            {
                if (vuxGameTime < gCompressTillTime)
                {
                    tmpTime = gCompressTillTime; // We don't want to advance time past here
                }
                else
                {
                    tmpTime = vuxGameTime;       // Unless it's already to late
                }
            }

            vuxGameTime = tmpTime;
            lastStartTime = vuxRealTime;
        }
        else
        {
            lastTimingMessage = 0;
        }

        // Call "RealTime" function.. Not really real time with this implementation
        // here all threads MUST be waiting, and can only proceed after barrier

#if NEW_SYNC
        //START_PROFILE("CA WAIT");
        //bool gotSig = ThreadManager::sim_wait_for_campaign((currentMode == RunningGraphics) ? 5 : INFINITE);
#ifdef FF_LINUX
        // FF_LINUX: Don't use INFINITE wait during Step2/startup phases.
        // The campaign thread may not be signaling properly during initialization,
        // which causes Loop() to hang. Use a bounded timeout instead.
        DWORD waitTime = (currentMode == Step2 || currentMode == StartRunningGraphics) ? 50 :
                         (currentMode == RunningGraphics) ? 5 : 100;
        bool gotSig = ThreadManager::sim_wait_for_campaign(waitTime);
#else
        bool gotSig = ThreadManager::sim_wait_for_campaign(INFINITE);
#endif

        //STOP_PROFILE("CA WAIT");
        // life goes on
        if (gotSig)
        {
            RealTimeFunction(vuxRealTime, NULL);

            if (currentMode == StoppingSim)
            {
                // here we exit, since capaign is waiting, its safe to do now...
                break;
            }

            ThreadManager::sim_signal_campaign();
        }
#ifdef FF_LINUX
        else
        {
            // Even if we didn't get the signal, still process real-time functions
            // to prevent hangs during startup
            RealTimeFunction(vuxRealTime, NULL);
        }
#endif

#else
        RealTimeFunction(vuxRealTime, NULL);
#endif
#endif // NO_TIMER_THREAD
        //STOP_PROFILE("TIMER");

        //START_PROFILE("SIMDIRTY");
#ifdef FF_LINUX
        // On Linux, skip SimDriver work during Step2 to avoid race conditions with
        // StartLoop() which is initializing graphics. RebuildBubble() still runs above.
        if (currentMode != Step2)
        {
#endif
        FalconEntity::DoSimDirtyData(vuxRealTime);
        //STOP_PROFILE("SIMDIRTY");

        //START_PROFILE("SIMCYCLE");
#if NO_CAMP_LOCK
        SimDriver.Cycle();
#else
        CampEnterCriticalSection();
        SimDriver.Cycle();
        CampLeaveCriticalSection();
#endif
#ifdef FF_LINUX
        }
#endif
        //STOP_PROFILE("SIMCYCLE");

        // Do any graphics related processing required
        switch (currentMode)
        {
            case StartRunningGraphics:
                if ( not SimDriver.lastRealTime)
                {
                    SimDriver.lastRealTime = vuxGameTime;
                }
#ifdef FF_LINUX
                // Acquire GL context on this thread (the Loop thread) for rendering.
                // StartLoop released it before setting currentMode = StartRunningGraphics.
                {
                    extern void FF_SimThreadAcquireGL();
                    extern bool g_simOwnsGLContext;
                    if (!g_simOwnsGLContext)
                    {
                        FF_SimThreadAcquireGL();
                    }
                }
#endif
                // Fall through to RunningGraphics
            case RunningGraphics:
                if (sRewakeSessions)
                {
                    RewakeSessions();
                    sRewakeSessions = 0;
                }

                gGraphicsTime = GetTickCount();
                // we cant profile here, since its zeroed inside function
                OTWDriver.Cycle();
                gGraphicsTimeLast = GetTickCount() - gGraphicsTime;

                // Campaign gets fed some food by putting us to sleep
                // the length of time is determined by how long the sim and graphics
                // take.  Unfortunately, the longer these take the longer we must
                // sleep so that the campaign doesn't starve

                // average over 8 frames
                gAveSimGraphicsTime = (gAveSimGraphicsTime * 7 + gSimTime + gGraphicsTimeLast * 100) / 8;

                // WARNING  WARNING  WARNING  WARNING  WARNING 
                // COBRA - RED - REMOVED THIS WAITING FOR CAMPAIGN - HAS TO BE TESTED FOR SIDE EFFECTS
                //START_PROFILE("SIMLOOP:");
                //ThreadManager::sim_signal_campaign();
                //ThreadManager::sim_wait_for_campaign ( min( 50, ( gAveSimGraphicsTime )/3 ) );
                //STOP_PROFILE("SIMLOOP:");
                // WARNING  WARNING  WARNING  WARNING  WARNING 
                if (currentMode == StartRunningGraphics)
                {
                    currentMode = RunningGraphics;
                }

                break;

            case RunningSim:
#if not NEW_SYNC
                ThreadManager::sim_signal_campaign();
                ThreadManager::sim_wait_for_campaign(10);
#endif
                break;

            case StartingGraphics:
                OTWDriver.ClearSfxLists();
                SetEvent(wait_for_start_graphics);
                currentMode = Step2;
                break;

            case StoppingGraphics:
#ifdef FF_LINUX
                // Release GL context before signaling StartLoop thread,
                // which will re-acquire it for cleanup operations.
                {
                    extern void FF_SimThreadReleaseGL();
                    extern bool g_simOwnsGLContext;
                    if (g_simOwnsGLContext)
                    {
                        FF_SimThreadReleaseGL();
                    }
                }
#endif
                SetEvent(wait_for_stop_graphics);
                currentMode = Step5;
                break;
        }

#ifdef FF_LINUX
        // FF_LINUX: After the switch, check if StartLoop has changed currentMode to
        // StartRunningGraphics. This is needed because the switch above doesn't have
        // a case for Step2, so we need to check for the transition here.
        // The mode can transition from Step2 → StartRunningGraphics while we're in
        // the switch (which has no case for Step2), so we catch it here.
        if (currentMode == StartRunningGraphics)
        {
            // Acquire GL context on this thread before transitioning to RunningGraphics.
            extern void FF_SimThreadAcquireGL();
            extern bool g_simOwnsGLContext;
            if (!g_simOwnsGLContext)
            {
                FF_SimThreadAcquireGL();
            }
            currentMode = RunningGraphics;
        }
#endif
    }
    while (1);

#ifdef FF_LINUX
    // Release GL context when Loop thread exits (StoppingSim break).
    // This allows the StartLoop thread to re-acquire it for cleanup.
    {
        extern void FF_SimThreadReleaseGL();
        extern bool g_simOwnsGLContext;
        if (g_simOwnsGLContext)
        {
            FF_SimThreadReleaseGL();
        }
    }
#endif
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
//sfr: pie screens
void SimulationLoopControl::StartLoop(void)
{
    // FF_LINUX: Use VuBin to hold a strong reference to the flight during deaggregation wait.
    // This prevents the flight from being deleted while we're waiting for it to deaggregate.
    VuBin<FlightClass> flightRef;
    FlightClass *flight;
    SimMoverClass *player;
    int delayCounter;
    int abortMission;

    fprintf(stderr, "[StartLoop] Thread started, entering main loop\n");
    fflush(stderr);

    while (1)
    {
        fprintf(stderr, "[StartLoop] Waiting for wait_for_start_graphics event...\n");
        fflush(stderr);
        WaitForSingleObject(wait_for_start_graphics, INFINITE);
        fprintf(stderr, "[StartLoop] Event received! Proceeding.\n");
        fflush(stderr);

#ifdef FF_LINUX
        // On Linux, acquire the OpenGL context for this thread.
        // The main thread released it when EndUI() was called.
        extern void FF_SimThreadAcquireGL();
        FF_SimThreadAcquireGL();
        fprintf(stderr, "[StartLoop] GL context acquired\n");
        fflush(stderr);
#endif

        //if the voices try to play during this time the sounds get all messed up, so be quiet
        F4SilenceVoices();

        TheTimeOfDay.Cleanup(); // destroy the old tod data
        char theaterdir[1024];
        sprintf(theaterdir, "%s/weather", FalconTerrainDataDir);
        TheTimeOfDay.Setup(theaterdir); // load the new one

        // Our pause/suspend state varies by type of game and online status - set appropriately
        if (gCommsMgr and not gCommsMgr->Online())
        {
            TheCampaign.Suspend();
        }
        else
        {
            switch (FalconLocalGame->GetGameType())
            {
                default:
                case game_InstantAction:
                    // Same as single player
                    TheCampaign.Suspend();
                    break;

                case game_Dogfight:
                    if (SimDogfight.GetGameType() == dog_TeamMatchplay)
                        TheCampaign.Suspend();
                    else
                        SetTimeCompression(1);

                    break;

                case game_TacticalEngagement:
                    if (tactical_is_training())
                        TheCampaign.Suspend();
                    else
                        SetTimeCompression(1);

                    break;

                case game_Campaign:
                    SetTimeCompression(1);
                    break;
            }
        }


        SimDriver.SetMotion(1);

        ///////////////////////////////////////////////////////////////////////////////

        //MonoPrint ("Starting Graphics on Thread\n");

        ThreadManager::slow_campaign();

        OTWDriver.todOffset = 0.0F;

        // Get a reasonable guess as to where we are so we can start the terrain loading
        flight = FalconLocalSession->GetPlayerFlight();
        ShiAssert(flight);
        // FF_LINUX: Hold a strong reference to flight during deaggregation wait loop
        // to prevent it from being deleted by another thread (RebuildBubble, etc.)
        flightRef.reset(flight);

        if (flight)
        {
            // JB 010616 CTD
            OTWDriver.SetOwnshipPosition(flight->XPos(), flight->YPos(), flight->ZPos());

            // Get the graphics control up and running
            OTWDriver.Enter();

            // Ask the game to send all deag entities to me
            VuTargetEntity* target = (VuTargetEntity*) vuDatabase->Find(FalconLocalGame->OwnerId());

            if (target && not target->IsLocal())
            {
                FalconSimCampMessage *msg;
                //here we ask for all deaggregated data
                msg = new FalconSimCampMessage(flight->Id(), target);
                msg->dataBlock.from = FalconLocalSessionId;
                msg->dataBlock.message = FalconSimCampMessage::simcampRequestAllDeagData;
                msg->RequestReliableTransmit();
                msg->RequestOutOfBandTransmit();
                FalconSendMessage(msg, TRUE);
            }

            // Attach camera to our flight momentarily while we rebuild our initial bubble
            if (FalconLocalSession->CameraCount() == 0)
            {
                // JB New MP code
                FalconLocalSession->AttachCamera(flight);
            }

            // Perpare the simulation for real time graphics...
            SimDriver.Enter();

#ifdef FF_LINUX
            // Brief delay to allow sim loop to synchronize
            // This helps prevent race conditions during graphics init
            Sleep(50);
#endif
        }
        else
        {
            player = NULL;
        }

        //MonoPrint("Done initializing graphics, waiting for deaggregation..  %d\n", GetTickCount());

        OTWDriver.SplashScreenUpdate(1);

        ///////////////////////////////////////////////////////////////////////////////

        //sfr: number of seconds to wait for data
        delayCounter = 120;

        // Wait until our flight is deaggregated
        g_bSleepAll = FALSE;//me123 host it's ok to wake again now you are attached

        fprintf(stderr, "[StartLoop] Starting deagg wait: flight=%p IsAggregate=%d\n",
                (void*)flight, flight ? flight->IsAggregate() : -1);

        while (flight and flight->IsAggregate() and (delayCounter))
        {
#ifdef FF_LINUX
            // FF_LINUX: Instead of just sleeping, we need to:
            // 1. Call RebuildBubble to send deaggregation messages
            // 2. Process VU messages so the deaggregation actually happens
            // Without this, the Loop() thread is stuck here and can't process messages.

            // Update time for VU rate limiting
            vuxRealTime = GetTickCount();

            // Call RebuildBubble to trigger deaggregation message
            RebuildBubble(0);

            // Process VU messages via RealTimeFunction
            RealTimeFunction(vuxRealTime, NULL);

            // Signal campaign thread and wait briefly
            ThreadManager::sim_signal_campaign();
            ThreadManager::sim_wait_for_campaign(10);

            // Short sleep to avoid busy-waiting
            Sleep(100);

            static int deagLoopCounter = 0;
            deagLoopCounter++;
            if (deagLoopCounter % 10 == 0)
            {
                delayCounter--;  // Decrement timeout every ~1 second
            }
#else
            Sleep(1000);
            delayCounter --;
#endif
        }

        fprintf(stderr, "[StartLoop] Deagg wait done: flight=%p IsAggregate=%d delayCounter=%d\n",
                (void*)flight, flight ? flight->IsAggregate() : -1, delayCounter);

        // If we didn't deaggregate ourselves - RH
        if (flight and flight->IsAggregate())
        {
            MonoPrint("Flight didn't deaggregate before timeout.\n");
            player = NULL;
        }
        else
        {
            if (flight)
            {
                MonoPrint("Flight deaggregation done... %d, %d\n", flight->IsAggregate(), GetTickCount());
            }

            // Attach the player to the aircraft
            MonoPrint("Attaching player to aircraft... %d\n", GetTickCount());
            //player = GameManager.AttachPlayerToVehicle (
            //FalconLocalSession, flight, FalconLocalSession->GetAircraftNum(),
            //FalconLocalSession->GetPilotSlot()
            //);
            player = GameManager.FindPlayerVehicle(flight, FalconLocalSession->GetAircraftNum());
            FalconLocalSession->SetPlayerEntity(player);
            MonoPrint("Player %08x\n", player);
        }

        // Check if the player was successfully attached (They could have been killed in the meantime)
        if (player and not player->IsDead())
        {
            GameManager.AnnounceEntry();
#define START_GRAPHICS_WAIT_FOR_SIMDRIVE 1
#if START_GRAPHICS_WAIT_FOR_SIMDRIVE

            fprintf(stderr, "[StartLoop] Waiting for SimDriver.GetPlayerEntity()...\n");
            // sfr: wait simDriver player entity
            while (SimDriver.GetPlayerEntity() == NULL)
            {
#ifdef FF_LINUX
                // FF_LINUX: Must process VU messages during this wait.
                // AnnounceEntry() sends FalconPlayerStatusMessage which must be processed
                // to trigger AttachPlayerToVehicle() -> SimDriver.SetPlayerEntity()
                vuxRealTime = GetTickCount();
                RealTimeFunction(vuxRealTime, NULL);
                ThreadManager::sim_signal_campaign();
                ThreadManager::sim_wait_for_campaign(10);

                static int simDriverWaitCount = 0;
                simDriverWaitCount++;
                // Timeout after ~30 seconds to prevent infinite loop
                if (simDriverWaitCount > 300)
                {
                    break;
                }
#endif
                Sleep(100);
            }

#endif
            fprintf(stderr, "[StartLoop] SimDriver.GetPlayerEntity()=%p, calling SplashScreenUpdate(2)\n",
                    (void*)SimDriver.GetPlayerEntity());
            OTWDriver.SplashScreenUpdate(2);

            ///////////////////////////////////////////////////////////////////////////////

            // Push garbage into this campaign global to ensure we don't pop out of
            // our wait loop before the campaign has a chance to update it.
            gLeftToDeaggregate = -1;

            delayCounter = 100;

            // Wait until all necessary deaggregation events have been handled
            fprintf(stderr, "[StartLoop] Waiting for gLeftToDeaggregate=%d, player=%p, IsLocal=%d\n",
                    gLeftToDeaggregate, (void*)SimDriver.GetPlayerEntity(),
                    SimDriver.GetPlayerEntity() ? SimDriver.GetPlayerEntity()->IsLocal() : -1);
            while (
                (gLeftToDeaggregate) and
                (delayCounter) and
                (SimDriver.GetPlayerEntity()) and
                ( not (SimDriver.GetPlayerEntity()->IsLocal()))
            )
            {
                Sleep(100);
                delayCounter--;
            }
            fprintf(stderr, "[StartLoop] gLeftToDeaggregate wait done: gLeft=%d counter=%d\n",
                    gLeftToDeaggregate, delayCounter);

            // Render the first frame to get all requisit data into the IO queue
            //MonoPrint("Done deaggregating. Remaining entities: %d.\n",gLeftToDeaggregate);

            // We need to ensure the display list and drawable stuff isn't touched while we're rendering...
            CampEnterCriticalSection();
            /*
            #ifdef DELAY_TEX_LOAD
             if (wait_for_loaded) {
             TheTextureBank.SetDeferredLoad( TRUE ); // Hold off loading object textures 'till later
             TheLoader.SetPause( TRUE ); // Stop the loader so that we queue up all object requests.
             }
            #endif

            */// OTWDriver.RenderFirstFrame();
            /*
            #ifdef DELAY_TEX_LOAD
             if (wait_for_loaded) {
             TheLoader.SetPause( FALSE ); // Resume async loading
             }
            #endif
            */
            CampLeaveCriticalSection();

            OTWDriver.SplashScreenUpdate(3);

            ///////////////////////////////////////////////////////////////////////////////

            //MonoPrint("Waiting for loader:  %d\n",vuxRealTime);
            /*
             if (wait_for_loaded)
             {
             delayCounter = 0;
             while ( not TheLoader.LoaderQueueEmpty())
             {
             Sleep (100);
             delayCounter++;
             if ( delayCounter == 300 )
             {
             OTWDriver.SplashScreenUpdate( 4 );
             }
             }

             //MonoPrint("Loader Finished:  %d\n",vuxRealTime);

            #ifdef DELAY_TEX_LOAD
             TheTextureBank.SetDeferredLoad( FALSE ); // Load all the deferred object textures

             delayCounter = 0;
             while ( not TheLoader.LoaderQueueEmpty())
             {
             Sleep (100);
             delayCounter++;
             }

             // MonoPrint("Deferred texture load finished:  %d\n",vuxRealTime);
            #endif
             }
            */
            // Ok, so this is hacky.. KCK
            FixupGroundHeights();
            OTWDriver.SplashScreenUpdate(4);

            ///////////////////////////////////////////////////////////////////////////////

            // At this point, we're ready to go graphics wise -
            // Wait until if all other relevant players are ready
            //MonoPrint("Waiting on other players...  %d\n",vuxRealTime);

            FalconLocalSession->SetFlyState(FLYSTATE_WAITING);
            FalconLocalSession->SetInitAceFactor(LogBook.AceFactor());

            // KCK: Start recording flight hours
            RecordPlayerFlightStart();

            // FFV - The return to the 4rd "pie" is caused by a display of the fore buffer (pie #4)
            // after the last back buffer (pie #5).  Displaying Pie 5(#4) again fills both buffers with 5 (#4).
            OTWDriver.SplashScreenUpdate(4);

#ifdef DEBUG
            // Go ahead and start rendering frames
            InitializeStatistics();
#endif
            // stop and cleanup splash screen
            OTWDriver.CleanupSplashScreen();

            //TheLoader.WaitLoader();

            //turn the voices back on again
            F4HearVoices();

            // Dogfights have some special case start code -
            // i.e. For match play and instant entry
            if ( not SimDriver.RunningDogfight() or SimDogfight.GetGameType() not_eq dog_TeamMatchplay)
            {
                GameManager.ReleasePlayer(FalconLocalSession);
            }

            //sfr: im leaving only this one
            OTWDriver.RenderFirstFrame();

            /*delayCounter = 20;
            // Delay to make the Loader working
            while (delayCounter){
             Sleep(100);
             delayCounter--;
            }*/

            g_intellivibeData.In3D = true;
            g_intellivibeData.IsEndFlight = false;

#ifdef FF_LINUX
            // FF_LINUX: Now that the player aircraft exists, set the display mode.
            // The earlier SetOTWDisplayMode() call in Enter() at otwdrive.cpp:2553 fails
            // because SimDriver.GetPlayerAircraft() is NULL at that point (deaggregation
            // hasn't completed yet). The guard at access.cpp:1139 rejects cockpit modes
            // when player is NULL. Now the player is valid, so the mode will be accepted.
            OTWDriver.SetOTWDisplayMode(OTWDriverClass::Mode2DCockpit);

            // Release the GL context so the Loop thread (which runs OTWDriver.Cycle()) can acquire it.
            // On Windows, D3D devices are not thread-bound, but OpenGL contexts ARE thread-bound.
            // The Loop thread is a different thread from StartLoop and needs the GL context for rendering.
            {
                extern void FF_SimThreadReleaseGL();
                FF_SimThreadReleaseGL();
            }
#endif
            fprintf(stderr, "[StartLoop] Setting currentMode = StartRunningGraphics\n");
            currentMode = StartRunningGraphics;


            ///////////////////////////////////////////////////////////////////////////////

            //MonoPrint("Running:  %d\n",vuxRealTime);

#ifdef DEMO_VERSION_THAT_WE_ALL_HATE
            first_frame_time = vuxRealTime;
#endif

            ///////////////////////////////////////////////////////////////////////////////
            ///////////////////////////////////////////////////////////////////////////////

            WaitForSingleObject(wait_for_stop_graphics, 0xFFFFFFFF);

#ifdef FF_LINUX
            // Re-acquire the GL context for cleanup operations (Reset3DParameters, ShowSimpleWaitScreen).
            // The Loop thread released it when it transitioned out of RunningGraphics mode.
            {
                extern void FF_SimThreadAcquireGL();
                FF_SimThreadAcquireGL();
            }
#endif

            // Reset any remaining parameter like NVG, TV Mode and so...
            OTWDriver.Reset3DParameters();

            g_intellivibeData.In3D = false;
            memcpy(gSharedIntellivibe, &g_intellivibeData, sizeof(g_intellivibeData));

            OTWDriver.ShowSimpleWaitScreen("leave");
        }
        else
        {
            if ( not player)
            {
                MonoPrint("Failed to fly\n");
            }
            else if (player->IsDead())
            {
                MonoPrint("Aircraft was already dead\n");
            }
        }

        //MonoPrint( "Checking for ACMI Tape Import\n" );
        if (gACMIRec.IsRecording())
        {
            gACMIRec.StopRecording();
            SimDriver.SetAVTR(FALSE);
        }

        // ACMI_ImportFile();

#ifdef DEBUG
        CloseStatistics();
#endif
        // Moved up, to remove the annoying engine sound at standby screen...
        // end the sound effects.
        F4SoundFXEnd();

        MonoPrint("Detaching the player...\n");

        // Make sure to remove the player if we have one
        GameManager.AnnounceExit();
        // Remove all active cameras
        vuLocalSessionEntity->ClearCameras();

        // sfr: this is killing remote players when server exits bubble
#define NO_REQUEST_CAMPAIGN_SLEEP 1
#if not NO_REQUEST_CAMPAIGN_SLEEP
        // Request that the campaign do a final bubble rebuild
        // MonoPrint("Requesting campain to do a final bubble rebuild\n");
        CampaignRequestSleep();

        while ( not CampaignAllAsleep())
        {
            Sleep(100);
            // 2002-02-19 REMOVED BY S.G. NO NO NO Wrong thread to do this
            // 2002-01-02 ADDED BY S.G.
            // We are asked to sleep so keep doing bubble rebuild until all sim objects are sleeping
            // MonoPrint("Doing a final bubble rebuild\n");
            // RebuildBubble();
            // gRebuildBubbleNow = 0;
            // END OF ADDED SECTION 2002-01-02
        }

#endif

        // MonoPrint("Slowing down the campaign\n");
        ThreadManager::slow_campaign();

        // MonoPrint("Shutting down sim...\n");
        // edg, calling sim driver exit is NOT thread safe since
        // this could be setting things dead in the midst of their exec'ing.
        // notify the simloop to exit and then wait for it tell us its done
        // SimDriver.Exit();
        // MonoPrint("Notifying it's time to exit\n");
        SimDriver.NotifyExit();
        // MonoPrint("Waiting for wait_for_sim_cleanup\n");
        WaitForSingleObject(wait_for_sim_cleanup, 0xFFFFFFFF);
        // MonoPrint("Cleaning up Graphics...\n");
        // SCR, calling OTW driver exit is NOT thread safe since
        // this will much with the display lists and drawables.
        // abortMission = OTWDriver.Exit();
        // MonoPrint("Notifying it's time to exit graphic\n");
        SimDriver.NotifyGraphicsExit();
        // MonoPrint("Waiting for wait_for_graphics_cleanup\n");
        WaitForSingleObject(wait_for_graphics_cleanup, 0xFFFFFFFF);

        abortMission = endAbort;

        // M.N. moved ACMI import after sim shutdown
        // Sim doesn't need to continue running when we import the ACMI
        ACMI_ImportFile();

#ifdef FF_LINUX
        // Release the GL context back to the main thread before returning to UI
        extern void FF_SimThreadReleaseGL();
        FF_SimThreadReleaseGL();
#endif

        // Special state maintenance stuff for Campaign.
        // If much more gets added, it should become its own function
        // with a function per game type if necessary.
        if (SimDriver.RunningCampaignOrTactical())
        {
            // MonoPrint("Posting message to main handler\n");
            if (abortMission)
            {
                // Game aborted - reload current campaign
                PostMessage(FalconDisplay.appWin, FM_REVERT_CAMPAIGN, 0, 0);
            }
            else
            {
                // Game continues.  Save our current state.
                CampaignAutoSave(FalconLocalGame->GetGameType());
                PostMessage(FalconDisplay.appWin, FM_START_UI, 0, 0);
            }
        }
        else
        {
            PostMessage(FalconDisplay.appWin, FM_START_UI, 0, 0);
        }

        // MonoPrint("Done leaving simulation.\n");
        ThreadManager::fast_campaign();

        currentMode = RunningSim;
    }
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////

// In Multi-player, we often get creation events for aircraft on the ground when
// we still have no terrain data.  Since we're not execing remote models, these
// guys don't get stuck back on the ground in the "normal" way. We need to do
// this here. Bit hacky, but it works.
void FixupGroundHeights()
{
    SimBaseClass *theObject;
    float gndz;

    // We need to ensure that nobody changes the VU database contents while we're iterating
    VuEnterCriticalSection();
    VuListIterator objectWalker(SimDriver.objectList);
    theObject = (SimBaseClass*)objectWalker.GetFirst();

    while (theObject)
    {
        gndz = OTWDriver.GetGroundLevel(theObject->XPos(), theObject->YPos());

        if (theObject->ZPos() > gndz)
        {
            theObject->SetPosition(theObject->XPos(), theObject->YPos(), gndz);
        }

        theObject = (SimBaseClass*)objectWalker.GetNext();
    }

    VuExitCriticalSection();

    // KCK: Even hackier...
    sRewakeSessions = 1;
}

// KCK HACK HACK:  Make sure any sessions which are flying are awake..
void RewakeSessions(void)
{
    VuSessionsIterator sessionWalker(FalconLocalGame);
    FalconSessionEntity *session;
    SimBaseClass *theObject;
    UnitClass *theUnit;

    ShiAssert(GetCurrentThreadId() == gSimThreadID);

    session = (FalconSessionEntity*)sessionWalker.GetFirst();

    while (session)
    {
        theObject = (SimBaseClass*) session->GetPlayerEntity();
        theUnit = (UnitClass*) session->GetPlayerFlight();

        if (theObject and theUnit and theUnit->IsAwake() and not theObject->IsAwake() and not theObject->IsDead() and not theObject->IsExploding())
            SimDriver.WakeObject(theObject);

        session = (FalconSessionEntity*)sessionWalker.GetNext();
    }
}

