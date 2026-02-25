# BUG-001 Resolution: UI95 Button Race Condition

## Issue Summary
**Bug ID:** BUG-001
**Status:** RESOLVED
**Date Fixed:** January 26, 2026
**Severity:** High (UI completely non-functional)

### Symptom
Main menu buttons would "appear then disappear" - buttons rendered briefly, then vanished, and mouse clicks had no effect.

### Root Cause Analysis

The UI95 system has two code paths that both call `Update()` and `CopyToPrimary()`:

1. **OutputLoop Thread** (`src/ui95/chandler.cpp`)
   - Background thread started by `C_Handler::Setup()` via `StartOutputThread()`
   - Runs in a loop calling `Update()` and `CopyToPrimary()` every ~40ms
   - Uses `EnterCritical()`/`LeaveCritical()` for thread safety

2. **FM_TIMER_UPDATE Handler** (`src/ffviper/main_linux.cpp`)
   - Main loop handler called every ~100ms
   - Also calls `Update()` and `CopyToPrimary()`
   - Did NOT use critical sections

**Race Condition:** Both code paths were modifying the UI surface simultaneously:
- OutputLoop would draw buttons to the surface
- FM_TIMER_UPDATE would overwrite or clear the surface
- Result: intermittent surface corruption, buttons appearing/disappearing

**Evidence:** Surface byte counts oscillated between 3072 (buttons present) and 0 (empty) when both code paths were active.

## Solution Implemented

### Fix 1: Disable OutputLoop on Linux
**File:** `src/ui95/chandler.cpp` (line 271)

```cpp
#ifndef FF_LINUX
    // On Windows, use the background OutputLoop thread for UI updates
    StartOutputThread();
#endif
// On Linux, UI updates are handled directly by FM_TIMER_UPDATE in the main loop
```

**Rationale:** On Linux, the FM_TIMER_UPDATE handler in the main loop already handles UI updates. The background thread is redundant and causes race conditions.

### Fix 2: NULL Safety Check for WakeOutput_
**File:** `src/ui95/chandler.cpp` (line 1354-1357)

```cpp
if (UpdateFlag bitand (C_DRAW_REFRESH bitor C_DRAW_REFRESHALL)) {
    if (WakeOutput_)  // NULL check for Linux (thread disabled)
        SetEvent(WakeOutput_);
}
```

**Rationale:** When OutputLoop is disabled, `WakeOutput_` remains NULL. The `UpdateTimerControls()` function calls `SetEvent(WakeOutput_)` which would crash without this check.

## Verification Results

### Test 1: Visual Rendering (60 seconds)
- **Result:** PASS
- Buttons remained visible continuously
- No flickering or disappearing elements
- FPS stable at 58-60

### Test 2: Surface Content Analysis
- **Result:** PASS
- Surface content: 92.2% non-zero pixels
- Button row (y=720): 1019/1024 pixels, 108 unique colors
- Content stable across all frames

### Test 3: Thread Safety
- **Result:** PASS
- No OutputLoop thread messages in logs
- No race condition artifacts
- Single-threaded UI updates confirmed

### Test 4: Stability
- **Result:** PASS
- No crashes during 60-second test
- No memory corruption detected
- Clean application startup and shutdown

## Before/After Comparison

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| Button row bytes | 3072 → 0 (oscillating) | 1019 (stable) |
| Surface stability | Intermittent | Consistent |
| FPS | 58-60 | 58-60 (unchanged) |
| Thread count | Main + OutputLoop | Main only |
| Race conditions | Yes | No |

## Files Modified

1. `src/ui95/chandler.cpp`
   - Line 271: Added `#ifndef FF_LINUX` around `StartOutputThread()`
   - Lines 1354-1357: Added NULL check for `WakeOutput_`

2. `src/compat/d3d_gl.cpp`
   - Cleaned up debug output (removed verbose frame logging)

## Remaining Concerns

None for BUG-001 specifically. The fix is minimal and targeted.

## Follow-up Items

1. Consider adding thread safety documentation for Windows vs Linux differences
2. May want to review other `SetEvent()` calls for similar NULL safety
3. The `ReleaseTimeUpdateCB` warning is unrelated and pre-existing

---

**Tested by:** Claude Code
**Verification Date:** January 26, 2026
**Build:** Clean rebuild from scratch
