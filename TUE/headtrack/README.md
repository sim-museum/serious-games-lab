# TrackIR head tracking for MiG Alley, Battle of Britain and FreeFalcon (Linux)

The games read opentrack-style UDP poses (six little-endian doubles: x, y, z in cm, yaw, pitch, roll in degrees) on
127.0.0.1:4242. A TrackIR reaches them through linuxtrack and `ltr_udp_bridge`. Set up and tested by hand on 2026-10-25
with a TrackIR 5 Pro (USB 131d:0158) and a TrackClip Pro. Packaging this for a fresh PC is a later item.

1. Build linuxtrack (github.com/uglyDwarf/linuxtrack) into `~/opt/linuxtrack`. On Ubuntu 26.04 it needs:
   - `autoreconf -fi`;
   - `#include <pthread.h>` in `src/ltr_srv_master.cpp`;
   - webcam support off in `configure.ac`.

   It also needs these packages: libusb-1.0-0-dev, libmxml-dev, bison, flex, qttools5-dev, qttools5-dev-tools,
   libqt5opengl5-dev. Install its udev rule `src/99-TIR.rules` into `/etc/udev/rules.d/`.
2. Install the firmware without running NaturalPoint's installer. Download TrackIR_5.4.2.exe, then run
   `7z x` on it, `isx_stream.py` on the overlay `[0]`, then `7z x` on `TrackIR 5.msi` and on `Data1.cab`. Then run
   `tir_fw_scan.py <linuxtrack>/src/qt_gui/spec.txt ~/.config/linuxtrack/tir_firmware <cab dir>`. The firmware sits
   raw inside trackir5.exe.
3. In `~/.config/linuxtrack/linuxtrack1.conf`, set these under `[Global]`:
   `Prefix = "<prefix>/bin"`, `Input = TrackIR` and `Model = NP TrackClip Pro`.
4. Build and run the bridge: `cc -O2 -o ltr_udp_bridge ltr_udp_bridge.c <linuxtrack>/src/linuxtrack.c -I<linuxtrack>/src -ldl -lm`.
   - Recentre with `ltr_recenter`.
   - `ltr_udp_bridge --blobs` prints the LED points linuxtrack sees. Use it instead of ltr_gui, whose camera
     view never redraws on this Qt.
5. Game switches:
   - MA: `MA_WINDOW_DISPLAY=<n>` picks the monitor. Lean-to-zoom needs `TRACKIR6DOF=ON` in `bdg.txt`.
   - BoB: no lean-to-zoom yet.
   - FreeFalcon: tick 3D (and 2D) TrackIR in Setup -> Controls, or use `FF_HEADTRACK_3D=1`. Use
     `set g_n6DOFTIR 2` for lean-to-zoom.
   - All three: `*_TRACE_HEADTRACK=1` prints one pose line a second.

The bridge mirrors yaw, roll and x (linuxtrack's left-right is the opposite of opentrack's). It holds frames where
fewer than three LEDs are seen or the pose jumps further than a head can move. In a 22 s FreeFalcon test that was
about 1 frame in 9.
