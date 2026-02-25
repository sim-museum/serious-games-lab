### **1. Introduction**
- **Pribluda Overview:** 
   - Real-time telemetry addon for Grand Prix Legends (GPL).
   - Originally created by Denis Fedorov (2003/4), updated by Amir Kamal (v1.1.1.0, released 2008-02-09).
   - Enhances driver experience with sector times, tire temperatures, race standings, a dashboard, and more.

- **Key Display Methods:**
   - OpenGL: Default method for screenshots.
   - D3D: Displays black background boxes instead of translucent ones.

---

### **2. Requirements**
- **Software/Hardware Compatibility:**
   - Grand Prix Legends v1.2.0.2.
   - Standard OpenGL or D3D7 rasterizers (hacked rasterizers for alternate resolutions may work).
- **Operating Systems:**
   - Windows 98/2000/XP/Vista (Confirmed XP64 compatibility via GPLPS installer; Linux version available by Petteri Pajunen).
- **Unconfirmed Support:**
   - Windows 95.

---

### **3. Installation Steps**
1. **Backup Files:** Existing `pribluda.dll` and `pribluda.ini`.
2. **Extract Files:** Unzip contents into the GPL directory.
3. **Patch Installation:** Run `patch.com` for first-time users.
4. **Optional Customization:** Edit `pribluda.ini` to modify configurations.
5. **Start GPL:** Test the setup for correct functionality.

**Special Note for '65 Mod Users:**
- Remove patch files and backup specific mod files before updating.
- Use GEM+ to regenerate `gplc65.exe` for proper integration with the new features.

---

### **4. Configuration**
- **INI File Settings:**
   - **Global Configuration:**
     - **Version:** Must match DLL version.
     - **BlackBarRatio:** Adjusts display’s black bar height.
     - **Font Settings:** Font type (`Courier New`), size (default: 12), and bold option (0 = off, 1 = on).
     - **BorderSize:** Pixel gap around text backgrounds.
   - **Keyboard Controls:** Assign keys for toggling displays (e.g., F4 for tire temperatures).
   
---

### **5. Features**
#### **Dashboard:**
- Displays essential data: Oil Pressure, Oil Temperature, Fuel Pressure/Level, Speed, Gear, RPM.
- Configurable warning colors for oil temperature and fuel level thresholds.
- Compatible with either **Imperial** or **Metric** units.

#### **Tire Temperatures (F4):**
- **Readings & Display:**
   - Shows temperatures for inner, middle, and outer edges of each tire.
   - Colored temperature ranges for grip level:
     - Dark Blue = Low Grip (Cold Tire)
     - Bright Red = Low Grip (Hot Tire)
     - Bright Green = Maximum Grip.
   - Metric/Imperial units based on GPL settings.
- **Settings:**
   - Options to show average temperatures, contact patch temperatures, or both.
   - Configurable positions for temperature displays.

#### **Sector Times:**
- Highlights sector performance with customizable colors:
   - Best Sector = **Green**
   - Current Sector = **Red.**
- Allows toggling visibility of ideal lap, best lap, last lap, and current lap lines.

#### **Player Board (F6):**
- Shows race positions and lap times relative to the player.
- Highlights:
   - Lapped/Lapping Drivers (Different Colors).
   - Retired Drivers.
   - Drivers passed for position.
   - Lap count, elapsed/remaining time.
- Configurable settings for driver name length and display position.

#### **Leaderboard (F7):**
- Displays positions and time gaps relative to the race leader.
- Highlights:
   - Player, Leader, Lapped Drivers, and Retired Drivers.
- Options to always show the leader or hide unnecessary details.
- Customizable colors for each driver’s category.

#### **TrackPosition Board (F8):**
- Visual representation of car positions relative to the player.
- Gaps displayed as distance (meters/miles) or time, based on configuration.
- Excludes retired or disconnected drivers.

#### **FPS Display (F11):**
- Simple FPS counter to avoid conflicts with GPL’s built-in FPS display.

---

### **6. Troubleshooting**
- **Checklist:** Ensure compatibility with requirements (rasterizer, OS, etc.).
- **Debugging:** Review `pribluda.log` in the GPL folder for errors.
- **Forum Support:** Report bugs to the GPL forums at racesimcentral.com.
- **Potential Issues:**
   - Minor discrepancies (sector/lap times vs. GPL’s internal timing).
   - Audio crackling on some systems.
   - D3D-only limitations (e.g., non-translucent backgrounds, crashes at 640x480 resolution).

---

### **7. Known Issues**
- Slight timing inaccuracies compared to GPL and GPL Replay Analyzer.
- D3D-specific limitations (e.g., crashes, visual differences).

---

### **8. Change Log**
- **v1.1.1.0 (2008-02-09):**
   - Compatibility fixes for 64-bit OS.
   - Enhanced grip calculations and configuration options.
   - Bug fixes for display and game inconsistencies.
- **v1.1.0.0 (2008-02-02):**
   - Complete overhaul of `pribluda.ini`.
   - New features (Dashboard, FPS display) and improved color-coding.
   - Numerous feature additions for playerboard, leaderboard, and tire displays.
- Previous Versions: Incremental improvements such as the addition of the Player Board (v0.97b, 2004).

---

### **9. Credits & Thanks**
- **Key Contributors:**
   - Amir Kamal (v1.x), Denis Fedorov (v0.97), and others (e.g., testers, source code contributors).
- **GPL Community Support:** Acknowledgment of GPL modders, testers, and developers.

---

### **10. License**
- Licensed under **Creative Commons Attribution-Non-Commercial-No Derivative Works 2.0 UK**.
- Use at your own risk; always back up your files.
- Not affiliated with Vivendi Universal/Sierra/Papyrus.

---

### **11. Downloads**
- Latest version: Pribluda v1.1.1.0.
- Linux port by Petteri Pajunen.

