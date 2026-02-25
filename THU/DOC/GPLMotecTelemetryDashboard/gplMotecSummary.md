## Study Guide: GPLMotec and GPLMotecLogger Software

### General Overview
- **GPLMotec**: A software designed to assist with fine-tuning car setups in the GPL (Grand Prix Legends) game.
  - Works by reading game data using low-level Windows functions and displaying telemetry information.
  - Useful for optimizing lap times and understanding detailed car performance.
- **Versions Supported**: GPL.EXE (original 1967 UE/US version), GPLc67.EXE, GPLc66.EXE, and Mod 1955 (GPLc55.exe).

### Key Features
- Real-time telemetry.
- Tire temperature and friction data.
- Differential and brake performance analysis.
- Fine-tuning tools for car setups (e.g., tire pressure, camber, differential, gearbox ratios).
- Optional virtual desktop (GPLMotec-VD) for single-monitor setups.

---

## Installation Instructions
1. **Download and Extract**: Copy the `GPLMotecAdd` folder to your preferred directory (e.g., SIERRA).
2. **Admin Privileges**: Enable "Run as Administrator" for `GPLMotec.EXE`, `GPLMotecLogger.EXE`, and `GPLMotecVD.EXE`.
3. **Install Necessary Fonts**: Install the provided DS-DIGI*.TTF files to Windows.
4. **Screen Setup**:
   - Requires at least two screens for the standard version.
   - Configure the second screen for optimal resolution (e.g., 1024x768).
5. **Launch**: Start GPLMotec—initially, it auto-detects the second screen and positions itself.

---

## Hotkeys Overview
### General Hotkeys
- **CTRL-M**: Enable/disable GPLMotec shortcuts.
- **CTRL-SPACEBAR**: Display GPLMotec on Screen 2 manually.
- **SHIFT-TAB**: Switch through display modules in the "Motec-Sim" window.
- **CTRL-TAB**: Cycle through technical modules on the right side of the screen.

### Tire Temperature Controls
- **CTRL-A**: Toggles between real-time display and average tire temperatures.
- **CTRL-T**: Switch tire temperature recording modes:
  - **TURN RIGHT**: Records temperatures during right turns.
  - **TURN LEFT**: Records temperatures during left turns.
  - **TURN RIGHT and LEFT**: Records temperatures during all turns.
  - **POWER**: Records when engine power is high on rear wheels (ignores braking).

### Setup Page Fine-Tuning Hotkeys
- Use fine-tuning features only when in the game’s setup page. Changes are saved when exiting the page.
1. **CTRL-K**: Adjust tire pressure.
   - Use **+/-** (numeric keypad) to increase/decrease tire pressure.
2. **CTRL-C**: Adjust camber angle.
   - Use **+/-** to modify the camber.
3. **CTRL-D**: Adjust differential angles (requires Differential module displayed first).
4. **CTRL-G**: Adjust gearbox ratios (requires Gearbox module displayed first).

### Additional Utility
- **CTRL-R**: Reset lap time counting.
- **CTRL-L**: Enable/disable logging (indicated by a red LED in the MotecSim module).

---

## Tire Temperature Module
### Color Codes for Pressure and Temperature Analysis:
- **Green**: Optimal pressure and temperature balance.
- **Red**: Pressure too high.
- **Light Blue**: Pressure too low.
- **Yellow**: Adjust camber for improvement.

### Notes:
- Perform analysis after completing at least:
  - **2-3 laps (qualifying setups)** or
  - **6 laps (race setups)**.
- Avoid interpreting data after crashes or intense braking 20 seconds prior.

---

## Differential and Brake Module
- **Hits**: Indicates significant discrepancies between wheel speeds.
  - **Pink LED Flashes**: Highlights the wheel experiencing the most hits.
  - Higher hits suggest potential wheel locking during acceleration/braking.
- Separate sections for acceleration and braking:
  - Acceleration: Monitors slippage when throttle >10%.
  - Braking: Monitors slippage when the brake is engaged (>10%) with throttle at 0%.

---

## Traction/Brake G-Force Module
1. **Bar Graphs**:
   - Left bar (with red tip): Maximum G-force achieved in a gear.
   - Right bar (with blue tip): Real-time G-force representation.
2. **G-Force LED**:
   - **Green**: Good continuation of force when shifting gears.
   - **Red**: Indicates force drop during gear shifts (e.g., shifting too early).
3. **Maximum G-Force Values**:
   - Use to optimize braking force with different tire setups.
4. **Gear-Specific Analysis**:
   - Helps identify optimal shift points for performance improvement.

---

## Logger (GPLMotec_Logger)
- Provides a simplified version of GPLMotec for single-monitor users.
- Records tire temperatures, lap times, and fuel consumption.
- Data remains viewable after exiting GPL for analysis.
- Key Hotkeys:
  - **CTRL-A**: Toggle average/contact patch tire temperature mode.
  - **CTRL-M**: Mute shortcuts.
  - **CTRL-T**: Loops between tire temperature modes (accompanied by sound cues for left/right/both G-forces).

---

## Known Bugs and Limitations
1. **Speed Calculation**: Approximate due to lack of precise memory addresses in the game code.
2. **False Popups**: "Prepare your setup! The race begins now!" sometimes appears when exiting GPL.
3. **Hits Display**: Inaccurate for high-speed scenarios; primarily useful for low-speed analysis.
4. **Imperial/Metric Display**: Option to toggle unit systems but requires appropriate INI configuration.

---

## INI File Configuration
### Key Options
1. **Measurement Units**:
   - `ImperialConversion=1`: Imperial units.
   - `GallonUSA=1`: Converts liters to US gallons.
2. **Logging Options**:
   - `AlwaysLogging=1`: Enables continuous logging.
3. **Screen Positioning**:
   - `GPLMotecMonitorNumber=1`: Assigns GPLMotec to a specific screen.
4. **Shift Light System** (VD version only):
   - `ShiftLight=1`: Displays an orange popup for gear shifts.

---

## Examples & Practical Use
1. **Improving Setup**:
   - Start with pre-made setups (e.g., Greger Huttu v2).
   - Analyze tire data after multiple laps (e.g., cold left front tire indicates low pressure).
   - Make necessary fine-tuning adjustments (e.g., increasing camber or tire pressure).

2. **Differential Adjustments**:
   - Example: Adjusting aggressive ramp angle (e.g., 30° to 40°) for smoother acceleration during high-speed corners like Monza Curva Grande.

3. **G-Force Analysis**:
   - Optimal shifting patterns can be determined by observing bar graphs and LED feedback in the Traction/Brake G-Force module.

---

## Newer Version Additions
1. **Version 1141**:
   - Clutch gauge added.
   - Tire pressures display updated to 1 decimal precision.
   - Fuel lap prediction now accounts for unusable reserve fuel (1.9L or 0.5 gallons).
2. **Version 1131**:
   - Wheel lock control module added.
   - Imperial units option introduced.

---

## Pro Tips
- Always analyze data after clean laps; avoid using data from laps with major incidents.
- Use fine adjustment features selectively to perfect race setups.
- Regularly update INI files to enable new functionality.

