# Comprehensive F-16 Instrument Landing System (ILS) Guide

## Introduction to Instrument Landing

Instrument landing is a precision approach method that uses ground-based navigational aids to guide the aircraft to the runway threshold with minimal visual reference. The F-16 utilizes the **Instrument Landing System (ILS)** which provides both lateral (azimuth/localizer) and vertical (glideslope) guidance for landing operations in low-visibility conditions, from light rain to near-zero visibility (100-200 feet ceiling and visibility).

---

## Phase 1: Pre-Approach Setup and Runway Alignment Using HSD and Navigation

### Step 1: Initial Positioning and Route Planning

**Objective:** Establish yourself on the proper approach course 10-15 miles from the runway.

**Procedure:**

1. **Switch to NAV Master Mode**
   - Ensure your flight plan is loaded into the INS/HSD
   - Set INS knob to NAV position to display steerpoints

2. **Use HSD (Horizontal Situation Display) for Approach Course**
   - The HSD displays your current position, steerpoints, and runway
   - Visual reference: The HSD shows the runway extended centerline as a dashed line
   - Align your aircraft track to this extended centerline
   - Verify runway heading matches your approach course

3. **Altitude Management During Approach**
   - Maintain altitude per ATC vectors until cleared for approach
   - Typical approach altitude: 2000-3000 feet AGL
   - Begin descent only when cleared and established on the approach course

### Step 2: Transitioning to the Approach Course

**At 10-15 NM from the runway:**

1. **Request Approach Clearance via Radio**
   - Check in with approach control
   - Request ILS approach for your target runway
   - Confirm runway heading and ILS frequency

2. **Calculate and Maintain Proper Descent Rate**
   - Descent rate formula: Ground speed ÷ 2 × 10 = descent rate in feet per minute
   - Example: 450 knots ground speed ÷ 2 = 225 × 10 = 2,250 feet per minute
   - Maintain stable, constant descent rate

3. **Reduce Airspeed to Approach Configuration**
   - Begin slowing aircraft in stages
   - Target approach speed: 200-250 knots (without gear)
   - Do NOT lower landing gear above 305 knots (gear damage limit)
   - As you slow, lower gear when below 305 knots

### Step 3: Landing Gear Configuration

**Below 305 Knots Airspeed:**

1. **Lower Landing Gear**
   - Command: Press **G key** to toggle landing gear handle DOWN
   - Automatic effect: Gear lowering automatically deploys leading and trailing edge flaps
   - Automatic effect: FLCS switches to Takeoff/Landing gains mode
   - Verify: Check for three green gear-down lights on gear panel

2. **Deploy Speed Brakes**
   - Command: Press **SPD BRK switch** (thumb on throttle) to OPEN position
   - Position: Speed brakes open to 43 degrees maximum with gear down
   - Purpose: Increases drag, reduces airspeed, controls descent rate
   - When nose gear touches down: Speed brakes can fully open and remain open

3. **Expected Drag Effects**
   - Aircraft pitch will nose down slightly due to gear/flap drag
   - Continue descent at proper glide slope
   - Expect airspeed to reduce further

---

## Phase 2: ILS Setup and Tuning

### Step 1: Access ILS Controls on DED

**Command: Press T-ILS button (button 1) on the ICP**

This displays the ILS setup page on your DED (Data Entry Display).

### Step 2: Tune ILS Frequency

**Procedure:**

1. **Enter ILS Frequency in Scratchpad**
   - Type the four or five-digit frequency (example: 109.50)
   - Press ENTR key

2. **System Recognition**
   - System recognizes ILS frequency automatically
   - Asterisks step to the **CRS (Course)** window

3. **Enter Approach Course Heading**
   - Input runway heading (example: 180 for south-running runway)
   - Press ENTR key
   - **Important:** CRS setting in DED is independent from HSI CRS setting
   - Set runway heading on both DED and HSI for consistency

### Step 3: Enable Command Steering

**On DED T-ILS Page:**

1. **Locate CMD STRG (Command Steering) field**
   - Default: Mode-selected at FCCMMC power up
   - To verify: Should show "CMD STRG" highlighted

2. **If Not Active, Activate Command Steering**
   - Position asterisks (*) around CMD STRG field
   - Press M-SEL button to toggle ON
   - When active, "CMD STRG" displays as highlighted/selected

---

## Phase 3: Approach Interception and Tracking

### Understanding ILS Coverage Zones

The ILS provides guidance in two coverage zones:

1. **Primary Coverage Zone**
   - Radius: 10-18 nautical miles
   - Shape: Narrow pie-wedge centered on extended runway centerline
   - Purpose: Initial approach guidance

2. **Secondary Coverage Zone**
   - Radius: 10 nautical miles
   - Purpose: Backup coverage zone

**Initial Intercept:** ATC vectors you to approximately 2000 feet AGL on or near the localizer extended centerline, roughly 45 degrees to the approach course.

### Step 1: Localizer Interception (Lateral Guidance)

**Entry into Coverage Zone (10-18 NM):**

1. **CMD STRG Cue Appears**
   - Small circle appears on HUD horizon line
   - Cue is fixed to horizon (appears as small circle)
   - This cue shows lateral steering guidance only initially

2. **Intercept the Localizer Course**
   - Position: Maintain level flight at approximately 2000 feet
   - Objective: Fly the CMD STRG cue to center it on your HUD
   - The cue moves left-right across horizon line
   - Action: Adjust stick left/right to center the cue

3. **Localizer Deviation Bar Becomes Active**
   - Displayed on both HUD and HSI
   - Bars appear as you get within 2-3 degrees of localizer centerline
   - HUD Display: Vertical bar on left side of HUD
   - HSI Display: Horizontal bar in center of HSI
   - When centered: Both bars should be in the middle of their respective displays

4. **Maintain Localizer Course**
   - Fly to keep localizer deviation bar centered
   - Continue inbound toward the runway
   - Monitor heading on heading tape: A "V" cue appears
   - The "V" cue shows wind-corrected heading to maintain ground track
   - Center the "V" cue on the heading tape for proper wind correction

### Step 2: Glideslope Interception (Vertical Guidance)

**Entering Glideslope Zone (3-5 NM from runway):**

1. **Glideslope Becomes Active**
   - You will be within 2-3 degrees of glideslope centerline
   - Pitch deviation bar becomes active on both HUD and HSI
   - HUD Display: Horizontal bar across center of HUD
   - HSI Display: Vertical bar in center of HSI

2. **CMD STRG Cue Evolves**
   - Cue begins to develop a fat tick mark on top
   - Tick indicates pitch steering is now available
   - Small circle with tick = you have both lateral AND vertical guidance

3. **Intercept Glideslope**
   - Reduce power to begin descent on glideslope
   - Maintain approximately 2.5-3 degree descent angle
   - Target: 3-degree glideslope (standard approach angle)
   - Fly the CMD STRG cue to position it where the glideslope intersects

4. **Glideslope Indicators**
   - When on glideslope: Pitch deviation bar is centered
   - Above glideslope: Pitch bar moves down (commands you down)
   - Below glideslope: Pitch bar moves up (commands you up)
   - Objective: Keep pitch bar centered by adjusting power/pitch attitude

### Step 3: Stabilized Descent

**Procedure for Stable ILS Approach:**

1. **Cross-Check Indicators**
   - HUD: Localizer bar (vertical) centered left-right
   - HUD: Glideslope bar (horizontal) centered up-down
   - HSI: Localizer bar (horizontal) centered
   - HSI: Glideslope bar (vertical) centered
   - CMD STRG cue: Positioned at HUD center

2. **Maintain Proper Descent Rate**
   - Calculate: Ground speed ÷ 2 × 10
   - Example for 180 knots GS: (180 ÷ 2) × 10 = 900 feet per minute
   - Monitor vertical speed indicator
   - Adjust power to maintain constant descent rate

3. **Power Settings During Descent**
   - Initial approach: Military power (50-70%)
   - Fine adjustment: Small throttle movements for descent rate control
   - Never use full afterburner during landing approach
   - Expect gradual power reduction as airspeed decreases

4. **Airspeed Management**
   - Target approach speed: 180-190 knots at touchdown
   - Reduce gradually using throttle and pitch attitude
   - Do not allow excessive descent rate
   - Warning: Speed too high = aircraft bounces on touchdown
   - Warning: Speed too low = stall or mush into ground

### Step 4: Monitoring for Glideslope Loss

**Warning Indicator:**

- If you drift above the glideslope and risk losing pitch steering, the CMD STRG tick will display an **X mark superimposed over it**
- Action: Reduce power and/or lower nose to get back on glideslope
- Never allow the X mark to remain; it indicates dangerous energy state

---

## Phase 4: Visual Breakout and Transition

### At 500-1000 Feet AGL:

**Typical Breakout Point:**

1. **Visual Acquisition**
   - Runway lights/PAPI become visible
   - Runway threshold markers appear
   - Aim point (touchdown zone) visible

2. **Declutter Option (Optional)**
   - Command: Press UNCAGE button on throttle (HOTAS)
   - Effect: ILS bars declutter from HUD for clearer view
   - Symbols removed: Some approach symbology disappears
   - Remains: Flight path marker, AOA staple, runway aim point
   - This provides cleaner sight picture for visual landing transition

3. **Transition Decision**
   - Option A: Continue ILS to touchdown (Cat III approach)
   - Option B: Transition to visual approach (Cat I or II)
   - Option C: Execute missed approach if unstable

---

## Phase 5: Final Approach and Landing

### Step 1: Final Descent and Flare Setup

**At 200 Feet AGL:**

1. **Verify Stable Approach**
   - On-speed: 180-190 knots
   - On glideslope: Bars centered, CMD STRG cue centered
   - On localizer: Course bars centered
   - Descent rate: Constant and appropriate

2. **Prepare for Flare**
   - Begin mental calculation of flare altitude
   - Typical flare point: 50 feet AGL
   - Monitor radar altimeter on HUD

3. **Position for Touchdown**
   - Aiming point: Place flight path marker on runway threshold
   - This ensures touchdown on-threshold, not beyond it
   - Maintain 3-degree nose-down attitude until flare begins

### Step 2: Flare Maneuver

**At 50 Feet AGL (Radar Altitude):**

1. **Initiate Flare**
   - Smoothly back on stick to raise nose
   - Objective: Raise nose to approximately 3-degree nose-down attitude
   - Duration: Flare occurs over last 50 feet of descent

2. **Power Management During Flare**
   - Reduce throttle gradually as descent rate decreases
   - Final power setting: Idle (approaching touchdown)
   - Never level off too early or aircraft will float down runway

3. **Touchdown Condition**
   - Attitude: 3 degrees nose down (preferred)
   - AOA: 13 AOA (ideal angle of attack)
   - Airspeed: 180-190 knots (below 200 knots minimum)
   - Main gear touches first, followed by nose gear

### Step 3: Landing Roll and Ground Control

**Upon Touchdown (Main Gear):**

1. **Transition to Ground Control**
   - Main landing gear accepts shock
   - Continue gentle aft stick pressure to maintain nose-up attitude
   - Purpose: Aerobraking to control descent rate and prevent bouncing

2. **Flight Path Marker Management**
   - Keep flight path marker in center of AOA bracket (13 AOA target)
   - Maintain green doughnut illuminated in left indexer
   - This ensures optimal landing angle throughout rollout

3. **Nose Gear Touchdown**
   - Occurs at approximately 90 knots airspeed
   - Cushion nose gear touchdown with gentle aft stick
   - Caution: Full aft stick will scrape tail and damage aircraft

### Step 4: Braking and Directional Control

**After Nose Gear Touches Down (Below 90 Knots):**

1. **Wheel Braking Application**
   - Command: Hold **K key** (wheel brakes)
   - Timing: Begin moderate, steady braking pressure
   - Technique: Use "moderately hard braking for shorter time" rather than early gentle braking
   - Reason: Reduces brake heat buildup

2. **Heat Management**
   - Brake energy model active in BMS
   - Avoid overheating: Do not brake at speeds above 110-120 knots
   - Optimal braking: From 90 knots down to taxi speed
   - Allow aerobraking above 90 knots; apply brakes after

3. **Directional Control**
   - Use rudder pedals for directional control (yaw rate higher at speed)
   - Rudder effectiveness decreases with airspeed
   - At approximately 70-80 knots: Enable nose wheel steering
   - Command: Press **Shift + Forward Slash** key to enable NWS

4. **Nose Wheel Steering (NWS)**
   - Available once below 70-80 knots
   - Provides precise steering for taxi movement
   - Allows turning without skidding or side-loading landing gear
   - Use rudder pedals to steer like an automobile once NWS engaged

### Step 5: Rollout to Stop

**Below Taxi Speed (25 Knots):**

1. **Continue to Parking**
   - Maintain NWS engagement with rudder pedal inputs
   - Reduce braking to light pressure
   - Taxi to assigned parking area or ramp

2. **Final Stop**
   - Reduce throttle to idle
   - Apply parking brake when stopped
   - Complete shutdown checklist

---

## Critical Approach Parameters Summary

### Optimal Landing Conditions:

| Parameter | Value |
|-----------|-------|
| **Approach Airspeed** | 200-250 knots (gear up) |
| **Final Approach Speed** | 180-190 knots |
| **Touchdown Speed** | Below 200 knots, preferably 180-190 |
| **Approach Altitude** | 2000-3000 feet AGL initially |
| **Glideslope Angle** | 2.5-3 degrees down |
| **Descent Rate** | Constant, calculated per formula |
| **Nose Attitude at Touchdown** | 3 degrees nose down |
| **Angle of Attack at Touchdown** | 13 AOA |
| **Gear Down Limit** | 305 knots maximum |
| **Radar Altitude Monitor** | Enable for accurate altitude readout |
| **ILS Frequency Coverage** | 108.10 to 119.95 MHz |

---

## Complete Keyboard Command Reference for Landing

### Pre-Landing Setup:
- **G** = Toggle landing gear up/down
- **UNCAGE** = Declutter HUD for visual approach
- **T-ILS** = Access ILS tuning page (Button 1 on ICP)
- **LIST + ENTR** = Navigation/INS pages

### Final Approach & Landing:
- **K** = Apply/release wheel brakes
- **Shift + Forward Slash** = Toggle nose wheel steering (NWS)
- **Rudder pedals** = Directional control (yaw)
- **Stick back** = Flare and maintain aerobraking attitude
- **Throttle** = Power management throughout approach

### During Rollout:
- **Rudder pedals** = Steering (with NWS engaged, acts like car steering)
- **K held** = Maintain braking pressure
- **Throttle** = Reduce to idle

---

## Common Landing Errors to Avoid

1. **Too Much Speed at Touchdown**
   - Result: Aircraft bounces, does not stay on runway
   - Solution: Reduce power earlier, plan for adequate descent distance

2. **Excessive Descent Rate**
   - Result: Hard landing, gear damage, tail scrape
   - Solution: Maintain calculated descent rate; adjust power for rate control

3. **Not on Glideslope**
   - Result: Miss touchdown zone or overshoot runway
   - Solution: Center pitch deviation bar; use CMD STRG cue as guide

4. **Improper Nose Attitude**
   - Result: Bouncing, tail strike, or inadequate rollout control
   - Solution: Maintain 3-degree nose down; gentle aft stick during flare

5. **Early Brake Application**
   - Result: Brake overheating, loss of directional control
   - Solution: Aerobrake first (keep nose up with stick); brake only after 90 knots

6. **Trying to Reduce Airspeed Too Quickly**
   - Result: Stall, uncontrolled descent
   - Solution: Gradual speed reduction; never pitch up excessively during approach

---

## ILS Approach in Low Visibility (Cat III)

For conditions with visibility under 500 feet and ceiling below 200 feet:

1. **Never Break Visual Contact with Instruments**
   - Keep eyes on HUD and deviation bars
   - Maintain centered CMD STRG cue
   - Do not attempt visual reference if weather is below minimums

2. **Fly Instruments to Touchdown**
   - Continue descent following localizer and glideslope to runway
   - Touchdown occurs when wheels contact runway surface
   - At this point, airspeed drops rapidly from normal landing airspeed

3. **Post-Touchdown Procedure**
   - Complete landing rollout using instruments if necessary
   - Apply brakes moderately once nose gear down
   - Use NWS for directional control
   - Taxi to designated parking with continued instruments if needed

---

## Troubleshooting ILS Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| ILS bars not appearing | Frequency not tuned correctly | Verify frequency in DED; retune if necessary |
| CMD STRG cue not appearing | Outside coverage zone | Proceed to intercept point; verify ATC vectors |
| Deviation bars inconsistent | Not centered on approach course | Adjust heading to center bars; reduce descent rate |
| Pitch steering lost | Above glideslope too much | Reduce power; increase descent rate slightly |
| Cannot track localizer | Off course by more than 3 degrees | Execute missed approach; request new vectors |

---

## Post-Landing Checklist

- [ ] Landing gear down and locked (three green lights)
- [ ] Wheels stopped (airspeed = 0 knots)
- [ ] Engine throttle set to IDLE
- [ ] Parking brake ENGAGED
- [ ] Nose wheel steering DISENGAGED
- [ ] Flaps retracted (cycle gear if needed)
- [ ] Canopy opened when safe
- [ ] Aircraft secured (chocks installed)
- [ ] Post-flight inspection completed

---

## Key Takeaways

The F-16 ILS landing system provides precision guidance for approach and landing in all weather conditions. The process follows this sequence:

1. **Setup Phase:** Tune ILS frequency, set course, enable command steering
2. **Interception Phase:** Enter coverage zone, intercept localizer, intercept glideslope
3. **Descent Phase:** Maintain stable approach with centered deviation bars
4. **Breakout Phase:** Transition to visual reference or continue instruments
5. **Landing Phase:** Execute flare, maintain proper attitude, touchdown below 200 knots
6. **Rollout Phase:** Aerobrake, apply brakes after nose gear down, steer to parking

Mastery of this procedure requires practice, but following these steps will ensure consistent, safe instrument landings in any weather condition, from visual flight to near-zero visibility operations.

---

*This guide is based on BMS 4.32 flight procedures and standard F-16 operations manuals. Always refer to current ROI (Rules of Engagement) and local squadron procedures for specific mission requirements.*
