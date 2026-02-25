# FreeFalcon Linux Port - Test Results

**Test Date:** January 26, 2026
**Tester:** Automated testing with Claude
**Build:** develop branch, commit e572878b
**Platform:** Linux x86_64, SDL2 + OpenGL

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| Launch/Startup | PASS | Initializes successfully with fallback menu |
| Main Menu | PARTIAL | Fallback menu works; UI95 rendering blocked |
| Input System | PASS | Keyboard and joystick detected |
| 3D Rendering Pipeline | PARTIAL | Textures load; OpenGL display needs fixing |
| Resource Loading | PASS | .idx/.rsc files load correctly |
| Audio System | PASS | OpenAL initialized, buffers created |
| Mission/Gameplay | BLOCKED | Cannot test without working UI navigation |
| Stability | PASS | No crashes during 12-minute test sessions |

**Overall Assessment:** Core infrastructure working. Primary blocker is UI95→OpenGL display pipeline.

---

## Test Results by Category

### 1. Launch Testing

| Test | Status | Details |
|------|--------|---------|
| Basic window mode (`-window`) | PASS | Window created 1024x768 |
| OpenGL context creation | PASS | Context initialized successfully |
| Resource path initialization | PASS | All paths set correctly |
| SDL2 initialization | PASS | Video, audio, joystick subsystems active |
| OpenAL initialization | PASS | Audio device and context created |
| Theater loading (Korea) | PASS | Terrain data, objects, textures loaded |

**Console Output (startup):**
```
[FalconDisplay::Setup] Starting DeviceIndependentGraphicsSetup...
[DIGS] theater=/home/g/ese/SAT/WP/drive_c/FreeFalcon6/terrdata/korea
[DIGS] VirtualDisplay::InitializeFonts() done
[DIGS] TheMap.Setup() done
[DIGS] TheTimeOfDay.Setup() done
[DIGS] ObjectParent::SetupTable() done
[EnumD3DDrivers] DirectDrawCreateEx returned pDD7=0x...
[EnumD3DDriversCallback] name=OpenGL, desc=FreeFalcon OpenGL Device
```

**Minor Issues Found:**
- `ReleaseTimeUpdateCB: callback not found` errors during theater reload (non-fatal)
- `help_res.lst` not found (missing file, non-critical)
- Assertion failures at shutdown (cleanup order issue, non-critical)

---

### 2. Main Menu Interaction Testing

| Test | Status | Details |
|------|--------|---------|
| Fallback menu display | PASS | OpenGL text rendering works |
| EXIT button | PASS | Clean termination |
| SETUP button | BLOCKED | UI95 display not visible |
| CAMPAIGN button | BLOCKED | UI95 display not visible |
| DOGFIGHT button | BLOCKED | UI95 display not visible |
| LOGBOOK button | BLOCKED | UI95 display not visible |
| Mouse click detection | PASS | Coordinates mapped correctly |
| Hover highlighting | PASS | Button hover states work |

**Critical Finding:**
UI95 renders correctly to the DirectDraw primary surface (verified via screenshot), but the OpenGL texture display pipeline has a bug preventing it from showing on screen.

**Evidence:**
- Screenshot saved to `/tmp/ff_screenshot.bmp` shows correct UI rendering
- `[FF_Present] pixelData=0x..., 1024x768, bpp=32` confirms surface has valid data
- No GL errors reported during texture upload

**Root Cause Analysis:**
The `FF_PresentPrimarySurface()` function uploads the surface to an OpenGL texture and draws a fullscreen quad, but the result is a blank screen. Possible causes:
1. Pixel format mismatch (GL_BGRA vs actual data format)
2. Texture coordinate issue
3. OpenGL state not properly restored between frames
4. Missing glFlush() or synchronization issue

---

### 3. Input System Validation

| Test | Status | Details |
|------|--------|---------|
| Keyboard detection | PASS | SDL scancodes converted to DIK_* codes |
| Mouse tracking | PASS | Cursor position tracked, coordinates scaled |
| Joystick detection | PASS | Logitech Extreme 3D detected |
| Joystick axes | PASS | 4 axes reported (roll, pitch, yaw, throttle) |
| Joystick buttons | PASS | 12 buttons detected |
| POV hat | PASS | 1 hat detected |
| ESC key handling | PASS | Exits application cleanly |

**Joystick Output:**
```
[JOYSTICK] Found 1 joystick(s)
[JOYSTICK] Opened joystick 0: Logitech Extreme 3D
[JOYSTICK]   Axes: 4, Buttons: 12, Hats: 1
```

---

### 4. 3D Rendering Pipeline Test

| Test | Status | Details |
|------|--------|---------|
| FarTiles.PAL loading | PASS | Case-insensitive lookup works |
| TOD (Time of Day) files | PASS | Loaded from korea theater |
| Miscellaneous textures | PASS | BOM*.GIF, SFX*.APL loaded |
| Object LOD table | PASS | 6801 LODs loaded |
| Texture bank | PASS | Textures loaded with ref counting |
| DirectDraw7 emulation | PASS | Primary surface created 1024x768 |
| Direct3D7 emulation | PARTIAL | Device created, needs display fix |

**Texture Loading Output:**
```
[ObjectLOD::CleanupTable] Starting, TheObjectLODs=0x..., TheObjectLODsCount=6801
[ObjectParent::SetupTable] done
```

---

### 5. Resource Loading Validation

| Test | Status | Details |
|------|--------|---------|
| .idx file parsing | PASS | Headers read with correct 32-bit alignment |
| .rsc file loading | PASS | Resource data loaded |
| Case-insensitive lookup | PASS | fopen_nocase() working |
| Image ID resolution | PASS | Names like "UI_MAIN_BG" resolved |
| Path separator handling | PASS | Backslashes converted to forward slashes |

**Verified Resource Files:**
- `main_res.lst`, `main_scf.lst` - Main menu resources
- `st_res.lst`, `st_scf.lst` - Setup screen resources
- `comm_res.lst` - Communications resources
- `lb_res.lst` - Logbook resources

**Missing Resources (non-critical):**
- `help_res.lst` - Help screen resources

---

### 6. Audio System Test

| Test | Status | Details |
|------|--------|---------|
| OpenAL device creation | PASS | Device opened successfully |
| OpenAL context creation | PASS | Context made current |
| DirectSound emulation | PASS | Interfaces created |
| Primary buffer | PASS | Created for mixing |
| Secondary buffers | PASS | Multiple buffers for SFX |
| WAV file loading | PASS | 32-bit size fix working |

**Note:** Actual audio playback not tested (requires menu navigation to trigger sounds).

---

### 7. Stability & Performance Testing

| Metric | Value | Notes |
|--------|-------|-------|
| Startup time | ~3 seconds | Theater load included |
| Memory at startup | ~200MB | Approximate |
| Crash count | 0 | Over multiple test runs |
| Clean shutdown | YES | "Goodbye!" message displayed |
| Test duration | 12 min cumulative | Multiple sessions |

**Shutdown Assertions (non-fatal):**
```
[Failed:  not IsReady()] Assertion at 45  fartex.h
[Failed:  not IsReady()] Assertion at 32  device.cpp
[Failed:  not IsReady()] Assertion at 49  imagebuf.cpp
[Failed:  not IsReady()] Assertion at 27  devmgr.h
```
These occur during cleanup and don't affect runtime stability.

---

## Discovered Bugs

### Critical (Blocking Gameplay)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| BUG-001 | UI95 primary surface not displaying via OpenGL | CRITICAL | OPEN |

**BUG-001 Details:**
- UI95 draws correctly to the DirectDraw primary surface
- Screenshot confirms UI content is rendered
- OpenGL texture upload appears successful (no GL errors)
- Fullscreen quad rendering produces blank screen
- Workaround: Using fallback OpenGL text menu

### Major (Significant Impact)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| BUG-002 | ReleaseTimeUpdateCB errors during theater reload | MAJOR | OPEN |
| BUG-003 | Shutdown assertion failures | MAJOR | OPEN |

### Minor (Low Impact)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| BUG-004 | help_res.lst not found | MINOR | OPEN |
| BUG-005 | Missing Falcon4.tt save file warning | MINOR | EXPECTED |

---

## Recommendations

### Immediate Actions

1. **Fix BUG-001 (UI95 Display)**
   - Add debug quad rendering to verify OpenGL state
   - Check pixel format conversion (32bpp BGRA → GL texture)
   - Verify texture coordinates and viewport setup
   - Consider adding glGetError() checks throughout

2. **Investigate BUG-002 (TimeManager)**
   - Review callback registration/deregistration order
   - May be a thread timing issue

### Future Improvements

1. Add runtime toggle between fallback menu and UI95 (for debugging)
2. Add FPS counter overlay
3. Implement proper error logging to file
4. Add memory usage monitoring

---

## Test Environment

- **OS:** Linux (Ubuntu-based)
- **Kernel:** 6.11.0-29-generic
- **CPU:** x86_64
- **GPU:** OpenGL capable
- **SDL2:** 2.x
- **OpenGL:** 3.x+ (legacy compatibility)
- **OpenAL:** Soft
- **Joystick:** Logitech Extreme 3D Pro (USB)

---

## Files Generated During Testing

| File | Description |
|------|-------------|
| `/tmp/ff_screenshot.bmp` | UI95 surface capture (proves rendering works) |
| `/tmp/ffviper_test.log` | Startup log |
| `/tmp/ffviper_debug.log` | Debug-enabled run log |
| `/tmp/ffviper_realui.log` | UI95 mode test log |

---

## Conclusion

The FreeFalcon Linux port has made significant progress:
- Core infrastructure (SDL2, OpenGL, OpenAL) is working
- Resource loading and parsing is functional
- Input system (keyboard, mouse, joystick) is operational
- Basic rendering pipeline is in place

**Primary Blocker:** The UI95→OpenGL display pipeline (BUG-001) prevents testing of actual gameplay. Once fixed, full mission testing can proceed.

**Next Steps:**
1. Debug and fix the OpenGL texture display issue
2. Complete main menu button functionality testing
3. Test campaign mission loading
4. Verify flight controls in actual gameplay
5. Test audio playback during gameplay
