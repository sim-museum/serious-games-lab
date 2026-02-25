                                                                                                                1




What s New



When executed, the update program will first search the current directory for previous versions. If it locates a
valid copy, it will update the appropriate files while making a backup copy in the rFactor\Support\Backup
directory. You will find an update log file in the support directory as well. If the out-of-date version is not
present in the current directory, the update program will search the registry for the install location and proceed
from there.



What's New in v1.040



What's New in v1.070



What's New in v1.150



What's New in v1.250



What's New in v1.255




                                                                                                                1
2




2
                                                                                                              1




What s New in v1.040?



Graphics:

•     Significantly reduced video memory usage in several components of the graphics engine.

•     Improved shadow performance for Max shadow detail level.

•      Added a new .PLR file option called Low Detail UI, which will force DXT compression on the UI art
to reduce memory usage by about 75%. There are compression artifacts when using this, but most people
wont notice. Set to On by default for the lowest level machine.

•     Added a black background to the frame rate counter, so it can actually be read.

•     Added an FOV option in the graphics section.

•     Prevented garage LOD multiplier in player file from being set to zero, which caused problems.

•     Fixed bug where only steering wheel of opponents would appear.

•     Added triple-rearview to swingman mode.

•     Fixed the rF Config to properly handle multiple video cards.

•      Added a full-time Video Mem Gizmo, which reports pct video mem available, as well as current
auto-texture reduction level, and instantaneous resource allocs. All done up in bright shiny colors.

•     Fixed a couple issues where the Visible Vehicles setting was not working properly. Increased the bias
towards showing vehicles in front. Added a player file value Extra Visible Vehicles which controls how
many vehicles to display in non-driving situations.

•      Modified weather to use only static ambient shadows at night, and to use a much faster skydome
coloring method.

•     Added a PLR file setting to allow 'rearviews in swingman' mode.

•     Improved FSAA support from rF Config.

•     Improved 16-bit support, so in 16-bit video modes, all textures are either dxtn or 16-bit.

•       Added timescale option of "None" which will make the time-of-day stand still. The advantage of this
is that static shadows never need to be updated, perhaps increasing framerate. Note that if you were
previously using the setting "Use Race %", then you will need to re-check the option in the UI. Known issue:
sorry, this does not appear to work well at the moment.



                                                                                                              1
2

•      Fixed screenshot bugs in windowed and multi-monitor modes.



Tracks and Vehicles:

•      Updated Sardian Heights mas file to fix incorrect signage bug.

•      Fixed shadows on windows bug on Rhez.

•      The names of the AI upgrade lists for Trainer had to be updated to match the vehicle filter tokens. This
affected the upgrades.ini file and all the trainer VEH files.

•      Reduced intensity of lights on Orchard Lake tracks.

•      Added Sardian Long.

•      More Sardian changes. New, higher res maps for buildings, arena dome, tunnel.

•      Updated some LOD distances on Sardian Long.



Artificial Intelligence:

•    Fixed an AI tire pressure issue which resulted in a significant top speed discrepancy, especially with
Advanced Trainers on the Orchard Lake Oval.

•      Improved AI passing code both on straights and in corners.

•      Improved mixed class AI driving.

•      Improved AI handling of on-track wrecks.

•      Fixed AI breaking yellow flag speed to enter pits.

•      Reduced tendency for AI to rear end player.

•      Fixed AI pulling offline (and slowing down) when human rides their tail.

•      Reduced AI start chaos.

•      Implemented a more consistent (for different car types) AI passing algorithm.

•      Completely removed AI blocking humans.



Gameplay:

•      Increased tolerances for positioning on formation lap starts, and added a check to ignore disco'd
clients. Also added a failsafe that if everyone is stopped for awhile it will try to correct anybody who is off
and then start the countdown timer.



2
                                                                                                                3

•     A couple improvements to the basic garage sliders: limited brake balance changes and more evenly
spaced gearing.

•     Fixed a garage UI bug where the acceleration, top speed, and gear graph info could be misreported.

•      Added starting time and time scale to season create page, so you don't have to drive open wheel cars at
night.

•      Changed following message (for caution laps, etc.) to use driver name rather than vehicle description.
Also fixed one case where that message should have been shown but was not. Added yellow flag display for
full-course yellows.

•       Fixed an issue where the pitcrew would sometimes get ready even if the player was clearly on the last
lap of the race.

•     Stopped automatically returning player to the monitor when player pitted in non-race sessions.

•     Applied credits when restarting a race if the first race was completed (i.e. official).

•     Fixed bug where running timed season races would result in no points being awarded. Related to this,
one must complete 60% of the leader's number of laps to get points, assuming equal cars. There is an
adjustment based on the relative power-to-weight ratios for class racing, and the final value is always rounded
down. For modders, the base percentage can be adjusted by an RFM value "Min Lap Percentage".

•     Reset damage display upon race restart.

•     Fixed track display when switching between Season and Test/Race (it was sometimes wrong).

•     Reset vehicle upgrades to those currently installed when leaving the Vehicles page.

•     Fixed right-side tire temps.

•      Added player file option "Auto-change Opponent List" which is on by default and will reset the
single-player opponent list filter everytime you change cars. In short, this will automatically choose
opponents whose cars are very similar to your own (same type and class).

•     Fixed HUD MFD cycling - now it will only display the screens as configured in the plr file.

•     Fixed an issue where the onscreen driving aids display would initialize wrong if no aids were being
used.

•      Added "Blue Flags" option to the player file which controls whether they are shown, whether people
can be penalized for ignoring them, and how close the following vehicle needs to be to trigger them. Note
that the new default setting significantly reduces the following distance needed compared to the original
release, and that penalties are still active. Also added a warning before handing out a stop/go penalty.

•       Changed race results format to be very similar to RaceCast XML format so the same parser can be used
for either one.

•      Drag'n'drop now works with SVM files into multiple folders. The visual effects now show up correctly
regardless of screen resolution, and dropping the SVM on the folder it is already in no longer deletes that
SVM.

•     Added support for additional nationalities, but without the flag graphics.


                                                                                                                3
4

•     Fixed a minor issue where the sound would stick on in some situations when restarting a single-player
race.

•       Now keeping track of control (AI or player) used and driving aids used every lap. This info is reported
in the race results.

•      Added new Steering Help level "Full" which basically takes over steering completely if input is kept in
the center. By default, it comes with a 2% mass penalty to avoid it being considered a "cheat".



Input Devices:

•      Made a change so people with both paddle shifters and h-shifters to use the paddle shifter if the
h-shifter stays in neutral.

•       Added optional analog input filter. It's off by default because it could introduce a small amount of
controller lag depending on the settings and your framerate. See the options "Analog Control Filter" and
"Filter Samples" in the controller.ini file for more info.

•     Added controller.ini option "Keyboard Layout Override" which may be used to improve support for
some keyboard layouts. If you are experiencing issues, please try the value "1" and see if that helps.

•      Added two possible workarounds for situations where people lose their force feedback. One is a
controller.ini value "Reset FFB Time" which will automatically reset the force feedback every X seconds.
The other is a new controller mapping "Reset FFB" which can be used to manually reset the force feedback.

•      Added a new force feedback parameter in the controller.ini file "FFB steer force grip factor". Its
default has been changed from the previously hardcoded value.

•      Added optional detection of accidental double-shifts (for noisy paddles). The default value for the new
player file option "Repeat Shifts" is off.



Replay:

•     Fixed special effects when outputting movies from Replay Fridge.

•     Fixed a bug where temporary replay files would get left behind and then never cleaned up. Running
the new executable will clean up the old files.

•      Fixed a replay issue from multiplayer races where disco'd drivers would appear to sit in the middle of
the track for the entire race.

•     Added player file option "Record To Memory" which will write replay info to memory rather than disk,
in hopes of eliminating stuttering on some machines. Memory usage could be significant for longer races,
though, so this option is at your own risk.

•       Added various info to the Replay Fridge - driver name, laptimes, speed, etc. One mysterious addition
is the "Vehicle Upgrade Code" which is a compressed representation of the upgrades installed on the vehicle -
it's mostly useful if you simply want to compare whether two cars have identical upgrades.

•     Updated new Miles filters to include Audio Thief for capturing audio during replay exports.


4
                                                                                                                     5



Multiplayer:

•      Used download rating to estimate the number of servers we can grab for the join list. This is in
addition to the current player value, so it is the max of the two values.

•      Added dedicated server administrators with basic functionality:

•      Only works if admin password is specified. Only one admin allowed.

•     Become administrator by chatting "/admin <password" and relinquish it by exiting or chatting
"/admin".

•     Several different functionalities specified in multiplayer.ini option which concern whether
non-administrators can call votes and when.

Administrator can advance sessions, add AI, etc. by using the normal call voting UI buttons, or by typing chat
commands.

•      Fixed issue where network throttling could slightly overestimate the amount of data it could send to
each client (only significant with small numbers of clients).

•      Took downforce into account when extrapolating vehicles (should keep Formula IS cars from
appearing to catch air over crests in multiplayer) and smoothed out the ground detection code (to reduce
instant jumps over curbs).

•      Reduced default practice/qual/warmup times in multiplayer so we could get to race once in awhile.

•    Added an audible warning for when a multiplayer game goes to the race session. Also restores game if
minimized. Player file options "Net Race Warning" controls what sound is played and whether it will restore.

•      Added a vote to load a specific circuit/event by chatting "/callvote event <event_name>", where
event_name is the specific event for a track, such as Sardian Heights 250. Server's multiplayer.ini option
specifies whether users can call this vote and whether they can call a vote for an event that isn't in the current
server list. Administrators can always call this vote.

•      Added administrator command for editing the grid. See full list of chat commands for more info.

•        Started running collision on remote vehicles to prevent them from penetrating walls. The default is to
only do this for nearby vehicles (within 200 meters). Since collision-detection can be CPU-intensive, you can
turn it off by setting "Remote Vehicle Collision" to 0.0 in the multiplayer.ini file. Alternately, you can have it
run on every vehicle by setting it to a large number (10000.0+). By default, the dedicated server will not run
it at all (which may look less than perfect in replays) unless the multiplayer.ini value is set to 10000.0+.

•      Fixed Multiplayer join select box issue with game names taking up 2 lines when game name includes
'|'.

•     Fixed an issue where non-dedicated servers couldn't create games with vehicle filters that only accepted
non-base vehicle classes such as GP1 or MType.

•      Fixed a crash when cars leave the game.

•      Vehicles no longer exit the race session when a client quits or disconnects. Instead they are switched


                                                                                                                     5
6

over to AI control and parked in the garage. This was done for a variety of reasons: 1) it makes scoring and
results reporting easier and more accurate, 2) some people reported hiccups when unloading vehicles, and 3) it
allows for future support of clients re-joining if disconnect was accidental.

•       Fixed an issue where network throttling could cause tire smoke or other effects from remote vehicles to
get left on for a long time.

•     Added RFM catagory to multiplayer game selecter and allowed you to sort by RFM.

•     Added gizmos to call votes for booting/banning players.

•     Fixed "+maxplayers" command-line option to work with the dedicated server.

•     Fixed an issue where if you created a non-dedicated server without going to the Opponent List page, it
would use the current vehicle filter rather than the multiplayer vehicle filter.

•      Fixed an issue where sometimes incorrect vehicles (not matching the vehicle filter) would show up
while joining or creating a multiplayer game.

•     Changed auto-joining code to work better with passworded games.

•     Fixed possible client crash when server changes session.

•      Added RaceCast version to the server info displayed. An unfortunate side effect is that people running
the original version of rFactor will see an incorrect game version number for servers running the updated
version.

•     Stopped automatically exiting the game when leaving a multiplayer game that was created or joined
through RaceCast (or other external tool).

•     Optimized a search performed for waypoints when extrapolating multiplayer positions. This may
improve both server and client performance in multiplayer games.

•     Made a few more minor dedicated server optimizations.



Modding/Miscellaneous:

•      New player file variable to control the realism of the AI tire slip model (or override in TBC file),
resulting in more accurate scrub in the corners (again, most noticeable with Trainers on Ovals).

•     Fixed an issue where using extended ASCII characters for the installation directory could result in
people being unable to join multiplayer games.

•      Fixed dual processor timing issues by forcing game to only run on one processor. It can be overridden
by using "+fullproc" in the command line, since Microsoft has now announced a fix for dual processors which
is available only with Windows XP SP2.

•      Expanded trace capabilities for better detection of the location of realtime crashes and networking
action. Command-line option "trace=3" will create a new file "tracedyn.txt", and "+logtime" will add a time
value to each line of the regular "trace.txt" output.

•     Added command-line "+nosound" option to disable all sounds and music for testing purposes.


6
                                                                                                              7
•   Added more stock car GDB rules regarding dampers: everything from MinFrontSlowBump to
MaxRearFastRebound.

•     Fixed bug where running timed season races would result in no points being awarded. Related to this,
one must complete 60% of the leader's number of laps to get points, assuming equal cars. There is an
adjustment based on the relative power-to-weight ratios for class racing, and the final value is always rounded
down. For modders, the base percentage can be adjusted by an RFM value "Min Lap Percentage".

•     Changed CCH files to regular text format rather than encrypted.

•      Added new HDV section which can assign extra mass (as a fraction of the total mass) for each driving
aid and level used. This should only be used to add masses for vehicles that do not actually come with the
given driving aid in real life. In other words, legal TC should not be penalized with this extra mass. Mass
fractions are limited to the range 0.00 - 0.10, and are attached the same way fuel is.

•       Added new TDF entry "HATFilterMethod=<method #>" which controls how the HAT database is
filtered (and should be put near the top of the file). By default (method #0), different terrains are not
"smoothed" together, which is the desired functionality for roads with intentionally sharp curbs on the side.
Method #1 smooths all legal terrains together, and all non-legal terrains together. Finally, method #2 smooths
all terrains with the same "FilterID" together. To use this method, the entry "FilterID=<x>" should be added
to every terrain, where x is a number from 0 to 254.




                                                                                                              7
8




8
                                                                                                                1




What s New in v1.070?



Graphics:

•     Fixed a shadow bug that could crash some tracks.

•      Reverted back to 32-bit render targets (in some cases) for now, since 16-bit targets also caused particle
dithering in the rear view.

•     Fixed a bug which would cause texture updating to render targets to fail in 16-bit mode on nVidia.

•     Detached parts will now only have shadows if shadows are set to high or max.

•     Made sparks and fire glow at night rather than be darkly shaded.

•     Fixed scaling/placement problems with the onscreen flags (yellow, checkered, etc).

•     Modified the GRAPHOPT_low_detail_UI flag to affect ALL fonts (including ingame).

•     Fixed the GRAPHOPT_do_UI_bg_bink="0" to work for all UI anims.

•     Fixed LOD switches to eliminate the occasional missing meshes between LODs.

•     Fixed billboard/stamp feature, which was broken in the last update.



Tracks and Vehicles:

•     Added Essington Long track and layout.

•     Fixed the rear-left suspension on the Trainer which was confused with the front-right suspension.

•     Removed Joesville and added Essington Long to the Formula IS season.

•     Fixed minor error in Rhez upgraded suspension geometry.

•       Made minor adjustment to the clutch and tranny frictions on some vehicles. Also changed it so that if
the air dam is knocked off then the vehicle will lose front downforce.

•     Added a few Hammer and Howston seasons to the SR Grand Prix.

•     The Orchard Lake Oval is now available in the SR Grand Prix.

•     Adjusted mirrors on Formula IS so that you could see cars directly behind.

                                                                                                                1
2

•     Added the rF3 car to the Open Wheel Challenge.

•     Significant tweaks to the Formula IS and rF3 physics.



Artificial Intelligence:

•     Improved AI drag calculation.



Gameplay:

•     Improved the internal stat-keeping of laptimes based on track layout and vehicle class.

•     Changed onboard brake bias adjustment to return to default if you press both the forward and rearward
buttons at the same time.

•    Added player file option "Any Camera HUD" to show HUD from trackside cameras (new default is
ON).

•     Added class ranking to monitor.

•     Additional logic to help prevent receiving a blue flag after unlapping yourself from an opponent.

•     Fixed a crash after getting a DQ in multiplayer and then going to the next session.

•     Added a message for when the speed limiter is toggled.

•    Changed default number of vehicles sharing a pitstall from 2 to 1 (in the Open Wheel Challenge and
SR Grand Prix RFM files).

•     Added RPM to the extra info LCD page.

•     Removed configurable damper (shock) settings for HammerGT because they aren't available with other
mid-range SRGrandPrix vehicles.

•      Added "CLASS PACKAGES" to the Upgrades section, so you can buy a complete package (identical
to the AI) with just a couple clicks.

•     Added sector timing to list of lap times (when right-clicking on monitor grid).

•     Fixed minor issue where AutoPit and launch control might not upshift properly.

•     Optimized collision for detached parts and cones so framerate shouldn't drop as much in big crashes.

•     Fixed minor math error when using free look on an attached camera (swingman/cockpit/etc.).

•     When using onboard cameras, we now try to keep the same camera when switching to other vehicles.
Results may be somewhat random when running mixed class vehicles that have different sets of onboard
cameras.

•     Possibly fixed a situation where people would occasionally see two "pitcrews".


2
                                                                                                               3

•     Added one-lap-to-go warning. Player file option "One Lap To Go Warning" controls whether it is a
message, white flag, or both, and whether the warning is given in qualifying.

•     Fixed a minor issue where the standings would briefly change near the s/f line at the beginning of a
race.

•      Made LCD/HUD standings scrollable with the pit up/down controls and added new standings
functionalities: With the pit increment control (or player file option "Standings Func"), you can choose
between non-wraparound standings, wraparound standings, or autoscrolling standings.

•      Made race splits configurable between realtime values (original and default functionality) and
sector-based split times. Use the pit decrement control to toggle between the two choices, or use the
"Realtime Splits" player-file option.

•     Added a plr file option to set the screenshot file type to jpg, bmp, png, or dds.

•      The virtual rearview mirror (available in tv cockpit, nose, and swingman modes) now has an additional
setting for side-mirrors only.



Input Devices:

•     Added new FFB variable in controller.ini file "FFB steer front grip fract".

•      Changed the default value for the new force feedback parameter "FFB steer force grip factor"
introduced in v1.040 back to 0.4.

•    Added controller.ini value "Alternate Neutral Activation" to allow users to select neutral by shifting up
& down simultaneously.

•       Fixed a couple issues where the FFB spring might not work properly if the wheel came up as controller
2 or 3.

•      Stopped resetting the FFB saturation and coefficient values in the controller.ini file when we didn't
detect FFB on that axis.

•     Made change to handling of POV-HAT (D-pad) devices so they could be used as buttons (for
navigating the pit menu, for example).

•      Moved force feedback hardware re-initialization to only occur if you visited the force feedback options
page. This does two good things: 1) it makes force feedback changes take effect if you press the Drive button
from the force feedback page, and 2) it gets rid of the small but annoying delay when you are on any other
options page and return to the Monitor page. Note: this is not the same as the Reset FFB options. If you go to
drive and your force feedback isn't working, we recommend going to the force feedback options page (which
will force a hardware re-initialization) and then try driving again.

•     Fixed red input calibration bars to work on-the fly with sensitivity/deadzone adjustments.

•     Added a controller.ini value "FFB Ignore Controllers" which can be used to prevent rFactor from using
the FFB on certain controllers.

•      Made accidental shift detection time configurable. If you use the PLR file variable "Repeat Shifts",
values 1-4 now use increasing amounts of time while value 5 is the shift completion option.


                                                                                                               3
4

•     Support for 6-DOF head tracking devices.



Replay:

•     Fixed the replay hot lap times by including a little bit of time before and after the lap.

•     Reduced replay size after deleting clips by removing unnecessary events.

•     Fixed replay renaming where you couldn't overwrite an existing file even if you confirmed to do so.

•     Added player file option "Auto Monitor Replay" whether to automatically start a replay when returning
to monitor.

•     Fixed possible crash when watching replay in multiplayer.

•      Fixed vehicle special effects in instant replay (where sometimes you would see glowing brake discs on
vehicles in the garage, or 'dotted line' skidmarks on track). The time-of-day still does not work properly in the
instant replay, however.

•     Optimized some replay code (will affect everybody, but it should noticeably improve dedicated server's
performance with replays on).

•      Added player file option "Compress Replay" to control whether replay files (*.VCR) are compressed.
If turned off, replay files will be roughly 50% larger but may take less time to write out.

•     Fixed the opponents brake lights in replays of multiplayer races.



Multiplayer:

•      Fixed it so that restarting weekend or race in multiplayer automatically releases the AI that took over
for disco'd clients.

•      Made the dedicated server wait a slightly shorter time before switching sessions automatically (as long
as no one is finishing a hot lap in qualifying). Added a multiplayer.ini variable "Delay Between Sessions" to
control that time.

•      Added multiplayer.ini variable "Allow Hotlap Completion" to control whether the dedicated server
automatically advances sessions if someone is still completing a hotlap (a timed lap that was started before the
session time ran out). This option allows you to define which sessions the server will wait for hotlaps to be
completed, with the default being to wait only during the qualifying session.

•     Added multiplayer.ini option "Auto Exit" whether to immediately exit when leaving a game joined
through RaceCast or other external tool.

•     Stopped reading/writing CCH file on dedicated server.

•     Optimized a few more things out of the dedicated server.

•     Changed default dedicated server rate from 333 to 250.



4
                                                                                                                  5
•     Added multiplayer.ini options "Loading Sleep Time" and "Loading Priority" to help control the
dedicated server's CPU usage during track and vehicle loads.

•     Added "+queryportstart" and "+portstart" command-line options to override the respective values.

•      Added "+nowindow" command-line option which is the same as "+oneclick" except that the windows
(and therefore the windows processing) are eliminated, leaving only the process running.

•       Added ability to send current setup in multiplayer to one or all other players. New "Send Setup" button
is on the "Call Vote" page and replaces the currently disabled "Request Replay" button. Received setups will
be put in a new "Received" folder in the garage. Player file value "Keep Received Setups" controls how long
these setups are kept. Note: some issues with this feature in the version 1.048 beta were fixed.

•      Added multiplayer fixed setups. Player file value "Fixed Setups" controls whether they are being
used. "Fixed Free Settings" controls what, if any, settings are still free (for example, steering lock). "Fixed
AI Setups" controls whether the AI uses the fixed setups, too. By default, the fixed setup is the factory
defaults, but can be changed by assigning your favorite setups which are stored in
FavoriteAndFixedSetups.gal.

•      Added "Fixed Upgrades" option to multiplayer. If the server enables this option, all vehicles will be
forced to use one of the class packages.

•      Mismatches are now reported to all clients regardless of the mismatch response setting. Added a new
server mismatch response option to automatically kick out mismatched clients only in qualifying and race (to
allow people to join practice or warmup and ask other people about the latest version). Driving will be
disabled unless the server is configured to do nothing on mismatches.

•    Added a toggle to turn chat window auto-scrolling on or off. Also added color-coding in the chat
window based on driver. Both can be controlled with multiplayer.ini variables.

•     Added more info to Race Settings in multiplayer: race starting time, race time scale, and type of start.

•       Removed some unnecessary time-of-day graphics computations that were running on the dedicated
server.

•     Optimized the network throttler to help reduce dedicated server CPU usage.

•     Adjustment to throttling algorithm which can now send updates for more vehicles by reducing the
frequency of updates for vehicles that are far away. Total net traffic remains exactly the same.

•     Improved throttler's packing of events into network packets. This should slightly reduce server's
upload traffic and client's download traffic.

•       Added IRC chat gizmos to monitor page and removed code that disconnected a player from IRC when
he left the chat lobby. Now only when the player presses the disconnect button does he lose connection with
the IRC server.

•     Added IRC chat box to all monitor pages (Client, Hosting, Quick and Post Race Monitors).

•     Included option in dedicated server UI for whether toggling AI control is allowed.

•    When logged into RaceCast, a copy of your current user's friends and bookmarks are stored in the
RaceCast database.



                                                                                                                  5
6

•     RaceCast plugin now sends driving aid information.

•     Support for class position and class grid position added to RaceCast plugin.

•       Prevented admins from calling Restart Race before the race session because it would cause various
issues.



Results File:

•     Made XML results file UTF-8 compliant. Some "extended ASCII" characters may be changed to other
characters, but we'll address those as they are found.

•     Changed to one session per results file by default. Can be changed to the old way with PLR file option
"Multi-session Results".

•     Added 1st lap start ET to results file.

•     Added class positions to results file.

•     Fixed an issue where results file could have a few errors if a multiplayer race used a different RFM
than your current one.

•     Removed repeated chat lines and admin password from XML output.



Modding/Miscellaneous:

•     Fixed the GDB damper restrictions meant for stock car rules.

•      Changed RFM entry "DriveAnyUnlocked" to allow 3 settings for what type of vehicles you are allowed
to drive: 0=owned, 1=unlocked, 2=any.

•     Fixed a few potential buffer overruns.

•     Per-terrain wear multiplier now supported in TDF file. Default is "Wear=1.0".

•      Added command-line option "+highprio" to set rFactor to use a higher operating system priority. This
may help if user has a lot of background tasks but isn't necessarily recommended because it may starve those
tasks completely. Use at your own risk.

•      Improved a situation where errors in track AIW paths could cause strange warping. While the odd
behavior should be reduced, it is highly recommended that track makers use proper waypoint collision
corridors (please only edit the road corridors to address AI issues).

•     New support for internals plugin DLL that could be used to read vehicle data and/or control force
feedback and all non-driving inputs.

•     Internals plugin telemetry output now occurs at a fixed rate.

•     Added pneumatic trail variable to TBC file.



6
                                                                                                                7
•      Note to modders: the HDV (and upgrades.ini) variables "FWPeakYaw" and "RWPeakYaw" are
actually supposed to be "FWLiftPeakYaw" and "RWLiftPeakYaw" (but "DiffuserPeakYaw" is actually
correct as is). We are not changing the code because that would suddenly make some existing cars drive
differently, which isn't a good idea. We suggest that you update existing vehicles and test using the correct
variable names.

•      Added support for caution lights around the track used for full-course yellows (works on Orchard
Lake).

•      Added "MinimumClass" as an upgrade level variable. This would be used to specify the minimum
configured vehicle class (for example, MinimumClass="ZType") that would be calculated if a particular
upgrade level (for example, a "Type Z Engine") was installed. This feature is not, however, currently used in
any original rFactor vehicles.

•     Added RFM variable "PitOrderByQualifying" which allows mods to set the pit order in the race based
on qualifying results.

•     Added code to detect newly installed mods (RFM files) and automatically bring them up. In general,
we recommend against creating special launcher programs.

•      Addressed minor HAT issue where nearly vertical triangles could generate invalid data. HAT files will
need to be rebuilt which will cause a delay while loading tracks the first time after installation of this update.

•     Improved the handling of using paths in VEH file references (this can be used to reference content in
another directory branch).




                                                                                                                7
8




8
                                                                                                                      1




What s New in v1.150?



Graphics:

•     Disabled some old tree swaying code, since it is not used by us, and was being incorrectly used by
some track conversions.

•      Fixed a bug in setting the special day/night vis groups.

•      Fixed a shadow updating bug with TimeAcceleration=None.

•      Improved handling of MIP d cube maps on machines which don t support them.

•      Update rate of shadow projectors was reduced to lighten CPU load.

•      Additional pipeline and shadow optimizations make this the fastest rFactor ever.

•      Improved the static ambient shadow so it stays directly under the car even on extreme banking. Further
adjusted ambient shadow so that it fades out if vehicle leaves the ground.

•     Added a player file option "Delay Video Swap" which MAY improve framerate in some situations. In
general, it should not be used unless the framerate increase is noticeable.

•     Improved shadow code, now faster, and they work better in DX7 mode, also the shadows should not
break up at the edge when very early or very late in the day.

•      Added "Auto Refresh FPS" to Display options which specifies a framerate threshold below which the
game will automatically start reducing detail to try to improve framerate. This may be useful if your
framerate is low only at the start of the race, for example. A side effect of using this feature is that details or
other vehicles may appear or disappear depending on your current framerate. Note that this is NOT a
"minimum" framerate - if you desire the game to attempt to maintain a particular framerate, you should set
Auto Detail FPS to a value higher than your desired framerate. Furthermore, it can only reduce details a
certain amount, so please don t expect it to double your framerate.

•      Converted to the latest DirectX SDK (Apr 06).

•      Added option to blur shadow maps (in dx9 mode only). Defaults to Off.

•      Added a plr file option to use a shadow map cache with a preset number of maps based on texture
detail. This will clamp the amount of memory used for shadow maps regardless of how many cars are loaded,
while using bigger maps for closer cars. Defaults to On.

•      Made virtual mirror settings (center + side, center-only, or side-only) stick.




                                                                                                                      1
2

•     Made enhancements for widescreen mode (specifically three head/single viewport mode) to display UI
and overlays in the center of the screen (center monitor).

•      Fixed some options pixel shifting issues in (hopefully) all resolutions.

•     Increased the range of available vertical FOV settings. This will reset any previous setting so please
check the display options if you prefer non-default values.

•      Modified player and opponent detail settings so that both texture and object detail are affected by these
settings. The existing Texture Detail setting now affects only track textures.

•      Modified frame rate toggle to allow four states: off, frame rate only, mem bar only, frame rate + mem
bar.

•     Tweaked vehicle visibility algorithm to make sure cars just in front didn't disappear under heavy
braking in heavy traffic.

•     Fixed minor problems with rear-view dithering and HUD transparency in 16-bit video modes on ATI
only.

•     Updated all overlays to maintain 4:3 aspect in widescreen mode if the player file option Graphics
Options / Widescreen Overlays = 0.



Tracks and Vehicles:

•      Added Jacksonville Superspeedway.

•      Added restrictor plate engine as part of the SuperSpeedway package of the NSCRS vehicles so that the
track GDB entry specifying the restricted engine is no longer required (but still needed until veh packages are
track forced).

•      Adjusted the rear spring availability for the SuperSpeedway package of the NSCRS vehicles to comply
with Stockcar rule for the restrictor plate tracks. This also negates the need for the rear spring GDB since
entry. The rule is that only a 375, 400, or 425lb spring is allowed. The v1081 release only specified the
minimum spring rate of 375lbs via the GDB entry.



Artificial Intelligence:

•       AI can attempt to "learn" a track (by learn I mean, better follow the path). To enable turn on
Autocalibrate AI Mode="1" in .plr file. Enter a track in Test Day with a single AI. The AI will take off and
talk to you in chat and tell you how he's doing. Typeing "status" tells you how he's doing and "finish" will
make him end next lap.

•      AI's upon Init now look recursively up from the *.veh directory for a trackname.ini file that modifies
the speed and position of every waypoint on the main track.

•      Improved AI behavior when rolling to standing starts on banks. If all else fails will teleport to their
locations.

•      Improved AI pit behavior, should no longer slow down for cars heading into pits.


2
                                                                                                               3

•     Fixed "Safety car always drives 10 meters off road/crashes into walls" bug.

•     Improved calculation of AI max cornering speed.

•     Slightly more accurate AI tire drag if AITireModel is less than 1.0. This is most noticeable in banked
corners where the AI used to pull away slightly.

•     More accurate AI grip based on tire load (makes TBC value "AISens" obsolete).

•     Better AI support for driving lines where the grip multiplier is not 1.0.

•      AI oval track (multiline) racing implemented. This includes drafting, bump drafting, & multiple fastest
lines.

•     Added more effects to the AI aggression slider (passing).

•     Improved AI special effects (skids, sparks, etc.).

•     Fixed issue where AI wouldn't turn headlights on if you were viewing the tape delay in the monitor.

•     Made AI strength and aggression saved on a per-mod basis.



Gameplay:

•     Implemented Private Qualifying.

•     Fixed broken Steering Wheel option and put it in the UI.

•     Added pit timer using message center.

•      Optimized and updated the vehicle labels to show yellow for the vehicle you should be following on
rolling starts or full-course yellows.

•     Vehicle label now used over safety car (which is useful for indicating if a driver is supposed to be
following it).

•      Now using head-tracking movement in cockpit to affect mirror direction. To disable this effect, add 4
to the PLR file option "Moving Rearview".

•    Added ability to control practice/qual/warmup starting times through player file entries without editing
an RFM. Included are options for random start times (either 24-hours or only daylight hours).

•      Changed player file value "Blue Flags" to "BlueFlags" with the default value of 7 which now means to
take the RFM value "BlueFlags=<0-6>". If player file value is 7 and no value is found in the RFM, the
default behavior is 3: show blue flags for vehicles within 0.5 seconds and penalize if receiver doesn't move
over in a reasonable amount of time.

•     Seat and mirror positions now stored per-vehicle, but only for owned vehicles.

•      Added direct access controls for the HUD MFD pages, which are unmapped by default. They should
interact sensibly with the existing HUD MFD controls.



                                                                                                               3
4

•      Improved time and/or lap deduction code if vehicle finishes race with an outstanding penalty. Penalty
info displayed in results file.

•      Pit speed limit now displayed in message center if your vehicle doesn't have a speed limiter.

•    Fixed a restart weekend bug where the dry tire compound didn't get reset (only relevant if dry tire
compounds are restricted after qualifying starts, modders can specify this by setting the HDV value
[PITMENU]->CompoundRestrictions to 1 or 3).

•     Fixed a bug where the dry tire compound could get set to the wrong value if the player didn't go out
during practice or changed the value after practicing (only relevant if dry tire compounds are restricted).

•     Made tire compound selection in options gray out if dry tire compound has been selected and cannot be
changed (only relevant if dry tire compounds are restricted).

•      Dry tire compound is now not selected until player goes out for the first time in qualifying (only
relevant if dry tire compounds are restricted).

•      Fixed a pitstop strategy bug where the 2nd and 3rd stops defaulted to delivering the amount of fuel
specified for the 1st stop.

•     Traction control driving aid now has a medium level. If you use high, please check your setting as it
may now be set to medium. It uses an average of the low and high settings from the HDV (for both the level
and any weight penalties).

•     Steering help and traction control levels are now referred to as "Off", "Low", "Medium", "High" (rather
than "Off", "Low", "High", "Full").

•     Added new type of start "Fast Rolling" which automatically skips most of the formation (pace) lap.
The multiplayer.ini value "Fast Rolling Starts" is now gone. If you set the type of start to "Use Track
Default", you can now control whether there is a formation lap for either standing or rolling starts by using the
new "Force Formation" player file value (dedicated servers who used the old "Fast Rolling Start" may
consider setting "Force Formation" to 8 or 10).

•      Changed default behavior for ending timed races, but made behavior configurable. Previous versions
of rFactor gave the checkered flag to any vehicle that crossed the finish line after time ran out. New behavior
is to wait until the leader crosses the finish line before showing the checkered flag to all vehicles, unless the
leader has crashed out or is running slowly. Behavior can be configured through the RFM/season/GDB entry
"TimedRaceNonLeaderLaps" - see examples for more info.

•      Fixed a math bug where increased engine boost settings would increase AI engine wear much more
than expected (causing way too many mechanical failures).

•      Fixed mechanical failures UI option to reset basic rules to custom.

•      Added start light sounds.

•       Fixed an issue where if a full-course yellow was called just before the leader crossed the start/finish
line, some vehicles just ahead of the leader on track could get put another lap down.

•     When skipping the formation lap of a formation/standing start, we now automatically select neutral to
prevent you from accidentally driving away from your starting grid location.

•      Added player file entry "Relative Fuel Strategy" to allow you to choose how much fuel to ADD at a


4
                                                                                                               5

pitstop, rather than the default behavior, which is how much fuel TOTAL that you want.

•     Fixed a bug where the pit menu would sometimes default to the wrong stop's fuel.



Input Devices:

•      Added controller.ini option "FFB steer force grip function" that controls how quickly you lose steering
force as the front grip decreases. Lower values will reduce the effect where all force is lost when
understeering. Note that previously hardcoded default was 1.0, but new default is 0.55 which will change the
feel somewhat.

•      Added and changed some force feedback parameters in the controller.ini to address issues where the
steering wheel oscillates:

1.    "FFB steer force prediction" allows a little bit of prediction to help counteract the latency between when
the force is applied in code and when you can actually feel the force.

2.   "FFB steer force average weight" was replaced with "FFB steer force max change" which is a
framerate-independent algorithm.

3.    "FFB steer force max change" can help prevent the force from changing too quickly. However it is
disabled by default because it (like its predecessor) tends to dull and slow the response.

4.   "FFB steer force neutral range" reduces forces near the center (neutral force) location to reduce the
tendency for the forces to overshoot the center.

5.   "FFB steer update thresh" changed name to "FFB steer update threshold" to force a new default which
seems to mildly reduce jerkiness.

•     Vehicle inputs are now read on a thread at over 100Hz for better precision (option can be turned off
with Fixed Rate Inputs="0" in controller.ini file).

•     Added support for up to 32 buttons per controller. New optimization only checks the number of
buttons reported by the device driver. In the case of the driver reporting incorrect info (which is known to
happen), just increase the controller.ini value "Minimum Controller Buttons".

•     Some fixes made to Swiss German keyboard.

•     Detection of the Logitech G25 wheel which automatically selects a specific controller setup.

•     Added controller.ini option for keyboard flags - this may help if multimedia keys are not working while
rFactor is running.

•    Moved Speed Sensitive Steering, Auto Reverse, and Steer Ratio Speed from PLR file to controller.ini.
You may need to reset your speed sensitive steering option in the UI.



Replay:

•     Fixed it so you can maximize dedicated server replays.



                                                                                                               5
6

•      Fixed a problem where replay clips wouldn't play correctly after being saved and re-loaded.

•      Changed replays to save all races regardless of player file option to save all sessions. Previously, a race
replay would get overwritten if that race was restarted.



Multiplayer:

•      Fixed Race Starting Time on client Race Settings tab.

•      Added multiplayer.ini option "Fast Rolling Starts" for the dedicated server to skip the formation lap of
rolling starts (just like non-dedicated servers can do with the Space key).

•     Changed practice/qual/warmup configurable durations (in the multiplayer.ini file) to allow 1-minute
increments up to 10 minutes.

•      Possible fix for custom helmet skin problem in multiplayer.

•      Implemented lobby chat through matchmaker which replaces IRC.

•      Added option to multiplayer.ini to allow/disallow auto joining to lobby chat server.

•      Added inactive command to lobby chat server and client. Unless a lobby chat window is visible you
will not receive any messages and the clients name will be gray in the roster.

•      Removed some more unnecessary vehicle graphics initialization from the dedicated server.

•      Added code for clients to wait near the beginning of a session if they haven't been sync'd by the server.
If anybody is experiencing the server taking a long time to change sessions (more than 30 seconds), please
turn on trace level 1 on the server, save the trace.txt file after experiencing the issue, then contact us.

•      Fixed autoconnect using CLI +connect join timeout issue.

•      Server now stores full lap information (sectors, driving aids, etc.) for clients that exit. Note that
returning clients will still only receive limited information which avoids excessive bandwidth usage.

•     Changed the default of the mismatch response from "immediately kick" to "kick at beginning of race
and don't allow driving in other sessions". This gives people a chance to determine the reason for the
mismatch (for example, if a newer version of a mod was released).

•      Removed the getting of MOTD.txt and banner.jpg during startup.

•      Admin/server command "/setmass <mass> <playername>" applies a penalty mass to the given player
with immediate effect. Mass is in kilograms and can be 0-255. Player name just has to match the first few
unique letters (just like the /editgrid command). Penalty mass applies for the rest of the weekend - restarting a
weekend clears the penalty mass.

•      Penalty mass, if any, written to results file.

•      Admin/server command "/changelaps <laps> <playername>" applies a lap adjustment to the given
player with immediate effect. Command is intended to allow live steward input into the game's scoring
system. Laps must be between -10 and 10. Player name just has to match the first few unique letters.



6
                                                                                                                   7
•     Admin/server command "/addpenalty <code> <playername>" adds a penalty to the given player. The
following are valid values for <code>: -2=longest line, -1=drive-thru, 0-60=stop/go penalty number of
seconds.

•      Admin/server command "/subpenalty <code> <playername>" removes a penalty from the given
player. The following are valid values for <code>: 0=remove one stop/go penalty, 1=remove one drive-thru
penalty, 2=remove one longest line penalty, 3=remove all penalties.

•      Admin/server command "/throwyellow [<laps>]" starts a full-course caution for the given number of
laps (must be at least 2). If laps is not given, normal randomized value will apply.

•      Admin/server command "/clearyellow" ends a full-course caution as soon as possible, regardless of the
planned number of laps. To be able to choose the number of laps on the fly (like a real steward), just use a
large value with the "/throwyellow" command and end it with the "/clearyellow" command when appropriate.

•      Admin/server command "/racelength <code> <value1> [<value2]>" changes the race finish criteria and
length for the next race. <code>=0 indicates to use a <value1> percentage length race. <code>=1 indicates to
use a <value1>-lap race. <code>=2 indicates to use a <value1>-minute (timed) race. <code>=3 indicates to
use a <value1>-lap, <value2>-minute race.

•      Admin command "/shutdownserver" tells a dedicated server to exit immediately.

•      Added options to multiplayer.ini to allow the game to connect to a matchmaker on non-default ports.

•      Added version control to the NetCommUtilPlugin.dll so that game will not crash if it tries to load an
old plugin.

•      Multiplayer servers can now set the maximum allowed level of any driving aid. Multiplayer.ini
variables have been replaced, so you will need to reset all of the driving aid allowances as desired.

•      Removed most variables from the Dedicated<RFM>.ini file (track list, however, is series-dependent).
See new comments in file for more info. If using the "LessenRestrictions" or "Password" variables, you will
need to re-set them in the multiplayer.ini file.

•     Added another multiplayer.ini variable "Delay After Race" for an extra control over how long a
dedicated server waits.

•     Spectator mode is now saved in the multiplayer.ini file (which means it no longer changes back to off if
you quit and restart the game).

•      Added "Rotate To Top" button in dedicated server on track selection page. This button allows a track
to be quickly selected and wihtout messing up the rotation order of the track events.

•     Probably fixed the problem where a race sometimes wouldn't start in multiplayer if a client dropped out
during or before the formation lap.

•      Implemented whisper chats. Format is "/w <sendee> <chat message>". <sendee> can just be the first
few letters if they are unique.

•      Fixed occasional crash when a non-dedicated server changes tracks.

•      Possible fix for "ghost" or "fake spectator" bug, where a client tries to join as a participant but never
receives a vehicle to drive (and chats show up with no name attached).



                                                                                                                   7
8

•     Added RaceCast login on startup option in Multiplayer.ini.

•      Added a chat command to go back to the beginning of warmup (which might be useful if one person
has a lost connection near the beginning of the race and you don't want to re-qualify, etc.). For admins and
servers, type: "/restartwarmup". For clients wishing to call a vote on it: "/callvote restartwarmup".



Results File:

•     Added Mod filename and Season to the results XML file.

•      Added a little bit more information to the results XML line regarding contact - it now includes what or
who the contact was with. Note that Track indicates contact with the ground (for example, when rolling
over or when touching unusually high curbing) and Immovable is usually walls.

•      Local results file on server now includes disconnected clients for practice/qual/warmup if player file
option "Disconnected Results" is on (which it is by default). Existing position reporting will not change, but
new tag "LapRankIncludingDiscos" will show lap rank of everybody who was ever in the session. Another
new tag "Connected" indicates whether vehicle is in the game when the session ends. "IsPlayer" tag should
now be correct for both single and multiplayer games.

•      Changed first DateTime and TimeString (under RaceResults) values to be the time the track was
loaded. In that way, multiple results files (from different sessions) can be 'linked' together by comparing these
times. The second set of DateTime/TimeString values (under the specific session tag
Practice1/Qualify/Warmup/Race) remains unchanged.

•      Added fuel level to local results file. Each lap description includes the approximate fraction of full
capacity.



Modding/Miscellaneous:

•     Modders, please check updated RFM files for all new rules.

•       Allow for vehicles to have a series of categories in VEH file, and display a full tree in option. Category
in .VEH should look like this: Category="Hammer,Sledge,10 lb." Note that the Category value in most VEH
files have been changed to utilize a more organized structure when selecting vehicles. One possibly
unexpected result is that some vehicles will have a different "Class" as shown in the monitor and the results
file. More specifically, any vehicles that don't have any "UpgradeClass"es specified in an upgrades file
default to the last entry in the VEH Category line. Alternately, an upgrades file entry
  DisplayClassOverride can be used which will be used for the monitor and results file regardless of any
upgrade classes or categories. The reason one might use this instead of an UpgradeClass for display purposes
is that the UpgradeClass may be used to generate an appropriate vehicle filter when selecting the given
vehicle.

•      Added RFM option for when yellow is called. "FreezeOrder" where 0=race to the line and 1=track
order gets frozen immediately.

•     Added configurable yellow flag and penalty rules (available through RFM or GDB entries).

•    Added HDV entries to configure the pit menu and the time required to perform pitstop operations.
New options are available for which tires to change, what tire compounds are allowed, tire pressures, spring


8
                                                                                                                 9

rubbers, wedge, radiator, track bar, fender flare, and more damage repair. See the Form06.hdv file for an
example.

•      Added support for lucky dog rule. Lucky dog rule can be enabled with an RFM entry (in the
DefaultScoring section) "LuckyDog=<1-3>". Value 1 implements it for ovals only, 2 for road courses only,
and 3 for both. RFM entry "LuckyDogLapsLeft" specifies how laps much be left in the race to apply the
lucky dog rule - default is 10. PLR file entry "Lucky Dog Override" can be used to override RFM entry.

•     Added support for double-file restarts. Double-file restarts can be enabled with an RFM entry (in the
DefaultScoring section) "DoubleFileRestarts=1". RFM entry can be overridden with PLR file entry "Double
File Override".

•     Added more nationalities (most without flags).

•     Fixed tracedyn.txt to report possibly useful results with trace=3.

•      Changed code to allow caution light and safety car light animations (must use new animation type
"skip frame 0", where frame 0 is off).

•      Added alternate timing for "Max Framerate" player file option due to reports it wasn't working well on
some machines. Negating the target framerate will cause the game to use an alternate timing mechanism
which is more accurate but uses more CPU. Note that the actual problem seemed to be mods that created a
separate player file which had different Max Framerate options, so this workaround should not be necessary.

•   Eliminated redundant and useless PLR file entries: CURNT and RPLAY settings no longer exist;
PRACT, QUICK and GPRIX all share the QUICK setting; and CHAMP info is stored in the CCH files.

•       Added RFM and/or PLR file "Parc Ferme" settings, a.k.a. "Covered Car" which prevent changing most
or all garage settings between qualifying and the race. Also included are RFM options for how the new Parc
Ferme options apply to fuel levels and used tires.

•      Changed player file option "Fixed Free Settings" to "FreeSettings", which is now applicable to both
fixed setups and parc ferme setups. Value can now also be defined in RFM/season/GDB files but can be
overridden by the player file value.

•     Enabled variable-distanced safety car trigger locations to enable smooth safety laps on
unconventionally shaped tracks . In AIW file, look for "SafetyCarReleaseDist=".

•      Removed most unnecessary scoring overrides in existing track GDB files (such as
"QualifyDay=Saturday") and made sure the correct defaults were in the RFM file. Overrides should only be
used when necessary (to create a night event, for example, or to change the pitlane speed limit on small tight
tracks).

•    Added pitbox re-skinning (instance and material on track should be named "PITBOX01" to
"PITBOX52", vehicle skin should be the same as the default skin with "pitbox" appended).

•     Improvement to vehicle sliding-down-hill problem.

•     New TBC entry to define rim properties.

•     Added ability to have non-linear grip drop-off with wear. See "WearGrip" value in Form_Tires.tbc for
more info.

•     Fixed ambient sound locator so crowd and other noises should now be possible.


                                                                                                                 9
10

•      New terrain data file (TDF) entries allow special road or collision sounds. For example, adding the line
"InsideRoad=Secondary\specialroad" under a [FEEDBACK] entry will play an interior sound (the specified
WAV file under the GameData/Sounds directory) when driving over that type of road. "OutsideRoad",
"InsideColl", and "OutsideColl" can also be used. While you can use each of these multiple times within the
TDF file, only one sound file per type can be used currently. In other words, only four unique 'special' sounds
can be specified at this time.

•      Fixed a minor HAT file bug that could actually improve performance slightly.

•     Added more logic to the pit-assigning code to help avoid problems on AIWs that have invalid
(non-zero) pit and garage locations.

•      Now allowing "Speedway", "Superspeedway", and "Short Track" to have " Oval" appended as a valid
track type defined in the GDB. Also changed code to look at "TrackType" rather than "Track Type". Track
type is mostly used to enforce rules that change depending on whether a track is an oval or not. Value is
displayed on dedicated server when choosing tracks.

•       Fixed rolling starts on Lienz Altstadt by deactivating safety car a couple seconds before it crosses the
s/f line. Fix should help on any track where the s/f line is before the pitlane starts.

•      New garage option for front/rear torque split of 4WD vehicles.

•      All differential lock parameters can now be used for center, front, and rear differentials of 4WD
vehicles. See HDV examples for more info.

•      Differential torques are now calculated somewhat more accurately, but should not have a noticeable
effect on driving or laptimes.

•      Setups will now be copied from the track directory to the appropriate setup folder when creating the
setup folder for the first time. In other words, if SVM files are found in the same directory as a new track
SCN file, they will be copied to the "SettingsFolder" specified in the GDB file. If multiple track GDBs share
the same setup folder, we recommend putting the SVMs in each directory because we can't guarantee the
order of creation.

•      Player file variable "Vehicle Sparks" has been replaced with cockpit.ini value "BodySparks".

•    Added ability to specify what vehicle upgrade configurations must be used at a given track. An
example with a decent explanation can be found in
GameData/Vehicles/NationalStockCar/Season_2006/TrackConfigsBase.ini.

•      Fixed a bug whereby hitting "enter" or "esc" in an empty new profile text box would move you onto the
next screen of player creation.

•      Expanded vehicle skinning functionality. "wcextra0" through "wcextra9" normally get re-mapped to
textures "<skin>extra0" through "<skin>extra9", respectively. New VEH entries "Extra0=<override>"
through "Extra9=<override>" make the wildcards get re-mapped to textures "<skin><override>". This can be
used to save texture memory. For example, two otherwise identical cars with different car numbers (32 & 33)
could use the same default skin ("DefaultLivery=Lightning"), but mapping a couple small areas of the car
with the texture "wcextra5" and then adding "Extra5=Num32" to one VEH and "Extra5=Num33" to the other
VEH would result in one car using texture "LightningNum32" and the other car using texture
"LightningNum33".

•     Added a diagnostic feature where incorrectly assigned textures will not cause a load failure, but will
appear solid pink to indicate a problem.


10
                                                                                                               11
•     Added HDV entry "Handbrake4WDRelease" under [CONTROLS] which specifies the handbrake
value where the center differential of a 4WD vehicle is disconnected to prevent stalling the engine. Diff will
be gradually disconnected starting at half of the given value. Range is 0.0 (disconnect immediately with any
handbrake) to 2.0 (default value which means to never even partially disconnect).

•      Added a per-sample volume multiplier to the SFX file. To use, just add a multiplier followed by a
comma before the sample WAV name. For example, "VS_OUTSIDE_HORN=1.5, horn.wav" will play the
horn louder outside the vehicle if it is not already maxed.

•      Added HDV value "LimitFastDampers" under [SUSPENSION] which indicates whether to enforce the
typical damper constraint that the fast damper rate must be lower than or equal to the slow damper rate (the
actual rate, not the numerical setting shown in the garage). The default is 1.

•      Added engine.ini value "LaunchVariables" to specify whether launch control uses traction control and
auto-shifting.

•     Added new TDF parameter "TopSpeed" for 'dust' reactions, which specifies the speed at which the dust
alpha will be maximized. Default is 104 m/s but should be lowered significantly for thicker dust in general.

•      Added a scene file option to adjust max shadow range (outside of which there are no shadows of any
kind). Defaults to 350.0.

•     Added Matchmaker Port overrides to rFm to allow mods to use there own matchmaker.

•     Added loading bar color to rFm (base 10 RGB only).

•      Added scoring info to the internals plugin. New example code required to see how to use it. Older
internals plugins will still work fine.

•     New CAM file variables made to configure the pitch angle limits of swingman. The default is
approximately "PitchLimits=(3.0, 169.0)".

•     Fixed some of the RFM config overrides that didn't work - helmet directory, etc.

•      Fixed some issues with driver swapping, although feature is NOT fully implemented or tested, and
there are several known problems. See multiplayer.ini variables "Show Seating" and "Spectators When
Closed" for some more information.

•     Mod specific credits toggle button added. Will pick a file called MODNAMEcredits.txt to display,
where MODNAME is the name of the rfm, as in "OWChallenge05".

•   Mod specific opening movie will play if there is a MODNAME.bik file in the movie directory, where
MODNAME = the name of the rfm.

•      Made number of frames in starting light animation configurable. GDB entry "NumStartingLights"
defaults to 5 (four red lights plus one green on most ISI tracks). Valid range is 1 to 6.

•      Note to track-makers: if race restarts sometimes delay a lap or more after the safety car pulls off, it may
be because your teleport locations are too close to the start/finish line. This is because the leader's teleport
location helps determine where to throw the green. Please use an AIW editor to fix the issue.

•     More aggressive strategy to make loose objects fall asleep, to reduce their CPU usage.

•     Added new RFM/season/GDB entries that affect the possibility of full-course cautions (safety car


                                                                                                               11
12
threshold). These variables can be defined differently for road course vs. oval races, and are multiplied by the
"Safety Car Thresh" defined in the player file. The NSCRS mod has been updated with these variables to
have more realistic stock car rules in this regard. Note that Flag Rules must be set to Full to get full-course
cautions. Also remember that there are new multiplayer admin commands to manually throw and clear
yellows.

•     Added HDV overrides for the player file variables that affect how the AI estimate their vehicles'
performance. See the Form06.hdv file for more info.

•     Fixed crash with really long vehicle filters.

•       Made engine settings (rev limiter, engine boost, engine braking) part of the configurable Free Settings
(for fixed or parc ferme setups), and made sure onboard adjustments worked the same way as the garage.

•      Now allowing the instance name "DRIVER" in addition to "BODY" for the driver's body. "BODY" is
the recommended name and we updated all of the GEN files.

•     Added new visgroup (M) which is only active during Warmup phase.




12
                                                                                                                    1




What s New in v1.250?



Graphics:

•     Fixed a bug where shadow casters/objects were not using the camera's LOD multiplier, and thus would
switch out too early in cams with an LOD multiplier greater than 1.0.

•      Fixed an ambient shadow bug in which it would disappear at random times.

•       Fixed a bug in night racing where night-specific vis groups and shadows would only work if you
transitioned to night from day.

•      Restored dual-head mode to its previous behavior of emulating a single widescreen rather than two
screen multihead.

•      Added vehicle labels to monitor and replay.

•     New PLR file overrides Player Texture Override and Opponent Texture Override for player and
opponent texture detail levels if you want the textures to have a different detail level than the vehicle models.
Default behavior is the same as version 1.150.

•      Minor automap improvements.



Artificial Intelligence:

•      Significant improvements in oval racing.

•      RCD file updates.



Gameplay:

•     Changed sound priority algorithm to take into account the local volume of each sound (louder sounds
-> more priority).

•    Mostly fixed private qualifying issues where you would see parts that broke off an invisible
competitor's car.

•       Improved driver swapping functionality. Garage setup is now transferred during multiplayer driver
swaps if the server's multiplayer.ini variable "Driver Swap Setups" is enabled (which it is by default). Vehicle
state is also transferred, including fuel, tire wear, and damage. Various other minor improvements and fixes
have been applied to this feature.

                                                                                                                    1
2

•     Now using red outline (configurable through player file variable "Box Outline") for end of
reconnaissance lap, too. Fixed some other issues regarding placement after the reconnaissance lap.

•     Fixed problem where DNF'd vehicles were sometimes scored as if they had actually driven back to the
garage where they are parked.

•     Stopped showing fuel level of competitors (it was wrong for remote vehicles anyway).

•     Added exit confirmation for race (note that it can be configured with the PLR file option "Exit
Confirmation").

•      Fixed issue where you couldn't receive setups if the translation of Received was an illegal Windows
folder name.

•      A player can now press the "Enter" to make the monitor/replay page full screen (removing images to
the top, bottom and left of the replay image). While in this full screen state, the player can remove the cursor
by pressing the "Delete" key.

•       Added player file option "Adjust Frozen Order" to control whether vehicles that are spinning or
stopped on track get moved down the frozen track order while other vehicles pass them. This is only relevant
if the vehicle that caused the full-course caution is actually able to continue the race. The old behavior kept
the order frozen regardless of who caused the full-course caution. The new default will usually move the
offending vehicle to a more appropriate place in the caution track order.

•      Pitcrew now changes damaged tires even if you forgot to ask them to (if you want your pitcrew to be
stupid, set "Smart Pitcrew" to 0).

•     Changed pitstop code to do a regular pitstop if you're not allowed to serve a stop/go (for example,
during a caution), even if your pit choice is to serve a stop/go. Also controlled by "Smart Pitcrew".

•      Made gear graph automatically adjust if gears allow speeds over 300mph or 300kph (depending on
display options).

•    Pit menu automatically comes up when entering the pits now (controlled by PLR file options
"Automatic Pit Menu").

•     Fixed case where 2nd-place driver in a close finish in a timed multiplayer race might be allowed to go
another lap, thereby winning the race incorrectly.

•     Significantly improved handling of track order under caution/formation laps.

•     Basic spotter, mostly geared towards oval racing.



Input Devices:

•     Improved auto-lift/auto-blip behavior for direct shift mode (H-shifters).

•      New controller.ini FFB steer force neutral function that can be used to try to reduce the force
feedback deadzone without introducing new oscillations. Note that the default behavior remains the same
as v1.150.

•     Slightly tweaked default values for the force feedback rumblestrip effects.


2
                                                                                                                   3



Replay:

•      Fixed vehicle jerkiness in replays of long races (2+ hours).

•      Fixed replays display for widescreen and multihead modes.

•      Fixed some replay issues with regards to driver swaps - it now shows the correct driver name for a
given time. Note that the number of participants listed in the replay info (when picking which replay to
watch) is a bit misleading - it is increased every time a driver swap is done, regardless of whether it is a driver
who was previously in the vehicle.

•      Version 1.150 replays and before may not play properly in this version.



Multiplayer:

•      Mistyped chat commands (anything that starts with a slash '/') are now blocked from being seen by
other clients.

•      Fixed problem where RFM variable 'FreeSettings' would not work properly in multiplayer.

•      Now transferring "CrashRecovery" player file option in multiplayer (so everybody uses the server's
setting). Non-default values will need to be reset with this version.

•      Added PLR file option "Safety Car Collidable" to allow collisions with the safety car to be turned off.
This is mostly intended for multiplayer races where warp or unexpected safety car behavior is a possible issue.

•      By default, you now must come to a complete stop in multiplayer before exiting to the monitor. Server
can turn this requirement off by setting the multiplayer.ini variable "Must Be Stopped" to 0.

•      Fixed issue where returning clients wouldn't get their score back if their vehicle's current upgrades (in
the options) did not match the forced upgrades for the track.

•     New server option for forcing particular driving views. Available options are: free,
nosecam/cockpit/TV cockpit, nosecam/cockpit, or cockpit only. If restricted, these only apply when driving.

•      New ability to "unthrottle" one client. Admin command "/unthrottle <name>" or direct editing of the
multiplayer.ini file will cause network data throttling to be turned off for that client. Use with great caution
because the server will ignore all bandwidth limits when sending data to the given client. The purpose of this
feature will usually be to have another client on a LAN who can record and review all the data that the server
processes.

•      Changed message that non-administators can't call votes with administator present to only be displayed
on the client that attempted to call the vote.

•      New administrator functionality: up to 3 regular administrators now allowed, plus 1
super-administrator. Regular admininistrators have a star (*) next to their name in the monitor (assuming they
are driving a vehicle rather than spectating). This postfix (as well as one for multiplayer AIs) is configurable
in the player file ("Monitor AI Postfix" and "Monitor Admin Postfix"). Super-administrators are secret and
can change the regular administrator password with the /apwd command (which also has the effect of taking
control away from anybody currently logged in as a regular administrator). Note the new entry


                                                                                                                   3
4

"SuperAdminPassword" in the multiplayer.ini file.

•      Administrators can now run batch files of chat commands by typing "/batch <file>" where <file> is
expected to be either 1) a path from the root directory of rFactor, or 2) in the UserData/Log/Results directory.
Example files are written after every session (for example, "BatchTemplateSQ.ini" is written after qualifying)
in the UserData/Log/Results directory. Five batch commands are executed every second to avoid bandwidth
overload. Note that mixed commands (such as /editgrid and /setmass) may result in out-of-order confirmation
messages but this shouldn't be a problem.

•     Chat command "/editgrid" can now be typed in at the server.

•     Full list of current chat commands:

•     /vote yes               // same as pressing button

•     /vote no                // same as pressing button

•     /ping                   // same as pressing button

•     /w <sendee> <chat> // whisper to given player - <sendee> can be just the first few letters of player's
name if they are unique

•     /whisper <sendee> <chat> // same functionality as "/w"

•     /callvote nextsession     // proceeds to next session (practice to qual, for example)

•     /callvote nextrace       // proceeds to next event in dedicated server track list

•     /callvote event <name> // proceeds to given event (such as "24 Hours of Toban" or "Mills Special
Event")

•     /callvote restartrace    // restarts the race

•     /callvote restartwarmup // client request to go to the beginning of warmup

•     /restartwarmup          // admin/server command to go to the beginning of warmup

•     /callvote restartweekend // goes back to practice

•     /callvote addai          // adds 1 AI

•     /callvote add5ai         // adds 5 AI

•     /callvote kick <name>      // kick specified player out of race

•     /callvote ban <name>      // bans specified player from server

•     /admin <password>         // take over administrator or super-admin (wrong or no password = stop being
administrator)

•       /apwd <password>          // super-admin/server command to change the regular admin password - this
will eliminate all current regular admins

•     /editgrid <pos> <name> // admin command to move the specified player to the given position on the


4
                                                                                                                5

grid - note that you should do the grid from first to last or you may fail to achieve the expected results

•      /setmass <mass> <name> // admin/server command to apply a penalty mass (0-255 kg) to the
specified player with immediate effect, lasting for the rest of the weekend.

•      /batch <file>         // admin/server command to run given batch file of these chat commands (see full
description elsewhere)

•      /changelaps <laps> <name> // admin/server command to adjust the number of completed laps (-10 to
+10) to the specified player for the purpose of allowing live stewards' input into the game's scoring system.

•     /addpenalty <code> <name> // admin/server command adds a penalty to the given player. The
following are valid values for <code>: -2=longest line, -1=drive-thru, 0-60=stop/go penalty number of
seconds.

•     /subpenalty <code> <name> // admin/server command removes a penalty from the given player. The
following are valid values for <code>: 0=remove one stop/go penalty, 1=remove one drive-thru penalty,
2=remove one longest line penalty, 3=remove all penalties.

•      /throwyellow [<laps>] // admin/server command starts a full-course caution for the given number of
laps (must be at least 2). If laps is not given, normal randomized value will apply.

•      /clearyellow        // admin/server command nds a full-course caution as soon as possible, regardless
of the planned number of laps.

•      /racelength <code> <value1> [<value2] // admin/server command changes the race length for the next
race: <code>=0 sets a <value1> % length race, <code>=1 sets a <value1>-lap race, <code>=2 sets a
<value1>-minute (timed) race, <code>=3 sets a <value1>-lap and <value2>-minute race.

•     /unthrottle <name>        // admin/server command to stop throttling network data to the given client -
use with great caution

•      /shutdownserver         // admin command tells a dedicated server to exit immediately.

•     /set upload <kbps>        // change upload speed (works on own machine only, administrator can't
change server's upload at this time)

•      /set download <kbps>     // change download speed (same as above)

•      /set nagle <0 or 1>     // can only be done on server - specifies whether questionable Nagle TCP
algorithm is used

•      /set warp <0.1 - 3.0> // in future, will affect voicechat. The warp connotation comes from the period
of time to take in between sending each voice packet. 1.0 is the default.



Results File:

•      Points (overall) and ClassPoints scored for each session are now written to results file. Note that
Points/ClassPoints may not be correct in multiplayer qualifying if points are given for PolePosition and the
leader has left the game temporarily. Also note that ClassPoints do not currently include MostLapsLead or
AnyLapsLead relative to class (if points can be scored for those achievements).



                                                                                                                5
6

•      Added "<Swap>" tag to results file if driver swaps were performed. This new tag shows drivers at
each lap.

•     Added PlayerFile name to results file.



Modding/Miscellaneous:

•     Modders, please check updated RFM files for all new rules.

•     Added RFM entry for whether local yellows are shown separately for oval vs. road courses.

•      Added optional point-scoring mechanisms to RFM. Under the heading "OtherScoringInfo", points can
be given for PolePosition, MostLapsLead, AnyLapsLead, and FastestLap. Note that any points now,
including the regular place-based points, can include fractional parts (down to tenths of a point).

•     Fixed possible memory corruption when changing mods.

•      More complex brake response to temperature is now possible. To use, replace "BrakeOptimumTemp"
and "BrakeFadeRange" with "BrakeResponseCurve=(<cold>,<min_optimum>,<max_optimum>,<hot>)",
where each value is a temperature in Celsius. At <cold> temperature, brake torque is half of optimum.
Between <min_optimum> and <max_optimum>, brake torque is optimum. At <hot> temperature, brake
torque is half of optimum.

•    New HDV variable "BrakeTorqueAI" allows a different brake torque for AI. This might be used to
compensate for differences with the player's car, as the AI is not currently affected by cold or faded brakes.

•      Note that there is also an old HDV variable "SpinInertiaAI" which allows a different wheel spin inertia
for AI. If this value is NOT used, the AI by default have twice as much spin inertia to help the physics deal
with their lower sampling frequency. If you choose to use this value and make it more realistic, be careful to
make sure that the AI wheels don't jitter at low speeds.

•       Added ability to specify the texture stage specified for wcextra textures. To use, add a line to the VEH
in the format "Extra<x>TexStage=<stage>" where <x> is 0-9 and <stage> is 0-7 (defaults to 0, the normal
first stage).

•      Now looking for new variable "SpringSquared=(<x>,<y>)" in head physics file (for each spring),
where x is additional spring per unit deflection, and y is additional damping per unit deflection. The default
values are <x> = ~6.67 * the normal spring value, and <y> = 0.0. This is an extra 33.3% force at 5cm
deflection, which is mostly unnoticeable except in high banking where it helps visibility. Note: it is easy to
blow up the physics engine by removing the min/max constraints and/or increasing this spring squared value
significantly.

•      Tracking cams can now have a position offset to avoid perfectly-centered cameras.
"PositionOffset=(<x>,<y>,<z>)" will apply a world-space offset to the target.

•      Tracking cams now have a microphone location and volume multiplier (the latter is probably more
useful if you just need more volume for cameras far away from the track). "ListenerPos=(<x>, <y>, <z>)"
and "ListenerVol=<m>" or "ListenerVol=(<m>)" will do the trick.

•      Support for up to four trackside camera groups. "Groups=<x>" where x is the sum of the values for
which groups it belongs to: 1=group 1, 2=group 2, 4=group 3, 8=group 4. It is recommended that the camera
that shows vehicles crossing the start/finish line belong to each available camera group, as the default


6
                                                                                                                7
behavior is to CYCLE through the camera groups every time the currently-viewed vehicle crosses the
start/finish line. The trackside camera control can also be used to select a specific camera group (which,
unlike the CYCLE mode, will not change camera groups when vehicles cross the start/finish line). Finally, if
track-makers wish to start with trackside group 1 rather than the CYCLE mode, they can set "Trackside1First
= 1" in the track GDB file.

•      Camera editor support for multiple trackside camera groups and microphone volume multiplier.

•      Made properties of loose objects (cones, signs, etc.) configurable through track GDB file. Defaults can
be set for each type, and can be overridden for specific instances. Values can be specified directly (with
positive values) or relatively (by using a negative number which will be multiplied negatively by the original
default value). Entering 0.0 for a property is the same as -1.0: neither input will change the property's value.
Note that the physics sampling rate for loose objects is somewhat low (to keep CPU usage down), so there are
limitations to what range of parameters can be used. If you simply want to increase the mass of an object,
we'd recommend increasing all the parameters except friction by the same proportion (e.g. if you want to
double the mass, also double the inertia values and the spring and damper). Format is "<type or instance
name> = ( <mass>, <inertia x>, <inertia y>, <inertia z>, <spring>, <damper>, <friction> )". Hard-coded
defaults for each type are given below:

•      CONE = ( 2.5, 0.25, 0.20, 0.25, 1425.6, 72.0, 0.80 )

•      POST = ( 1.2, 0.5, 0.1, 0.5, 400.0, 40.0, 0.80 )

•      SIGN = ( 5.0, 4.0, 2.0, 6.0, 1024.0, 44.8, 0.70 ) // default inertia parameters for signs are actually
calculated based on geometry

•      WHEEL = ( 15.0, 0.7, 0.5, 0.5, 5625.0, 45.0, 1.0 )

•      WING = ( 10.0, 1.0, 0.5, 1.5, 3600.0, 60.0, 0.60 )

•      PART = ( 10.0, 1.0, 0.5, 1.5, 3600.0, 60.0, 0.60 )

•      Added loose-object-to-loose-object collision. There are limitations to its effectiveness.

•      Allowed matchmaker location to be changed when rFm is changed.

•      New drafting parameters in RFM: VehicleWidth, SideEffect, SideLeadingExponent,
SideFollowingExponent. Parameters can be defined per-season if desired (copy the Drafting{} section to
within a Season{}).

•     Support for vehicle-specific drafting wake generation. All RFM drafting parameters can be overridden
with new HDV values under [BODYAERO] to make it vehicle-specific (and also possible to be modified
based on upgrades).

•      Drafting can now affect downforce separately from drag. New variables and defaults are
[FRONTWING]FWDraftLiftMult=1.0, [REARWING]RWDraftLiftMult=1.0,
[LEFTFENDER]FenderDraftLiftMult=1.0, [RIGHTFENDER]FenderDraftLiftMult=1.0,
[BODYAERO]BodyDraftLiftMult=1.0, and [DIFFUSER]DiffuserDraftLiftMult=1.0. If you set any of these
to be >1.0, then the affect of the draft on lift (downforce) will increase. This is useful when simulating
vehicles that lose a lot of downforce from other vehicles' turbulence.

•     Drafting can now affect aerodynamic balance. The new variable is
[BODYAERO]DraftBalanceMult=1.0. Note that this balance variable was functionally equivalent to 0.0 in
previous builds, meaning that the draft was calculated once for each vehicle and affected all aerodynamic


                                                                                                                7
8
components equally. Now the draft is calculated at the front and rear of the vehicle, and components are
affected based on their location in the draft. This multiplier allows you to exaggerate or remove the effect.

•     Added "BrakeGlow" for each wheel in the HDV file to define at what temperatures the brake glow
ramps up. Default legacy values are (in Celsius): BrakeGlow=(750.0,1000.0).

•      We used to load *all* DLLs in the plugin directory, even if they were not rFactor plugins. We now
"fixed" our code to dump non-rFactor DLLs (which also took care of a memory leak). The so-called
"problem" with this is if somebody is depending on rFactor to load other DLLs. If they have an rFactor
plugin that wants to load some other non-rFactor DLL, they need to do it themselves from now on.

•     Added "PassingBeforeLineOval" and "PassingBeforeLineRoad" rules to RFM/GDB to specify if and
where it is legal to pass on starts and restarts before the s/f line. Improved code to reduce penalties caused by
person ahead not racing normally or diving into pits.

•      Added ram-air effects on engine. Example usage: RamCenter=(0.0, 0.8, -1.5) // location of ram air
intake; RamDraftEffect=3.0 // multiplier for effect that draft has on ram air velocity;
RamEffects=(2.0e-5,2.0e-5,2.0e-5,2.0e-5) // torque % increase per m/s, power % increase per m/s and RPM,
fuel increase per m/s, engine wear increase per m/s.

•     Many new Internals Plugin features.

•      Added "ClosedPitPenalty" rule to RFM/GDB to control what penalty is given for being serviced on a
closed pitlane. The default has been changed from a drive-through penalty to an end-of-longest-line penalty.

•       Due to a potential discrepancy that could be caused by clients and servers having different values for
"Vehicles Per Pit" in the PLR file, the variable has been eliminated. The number of vehicles that may share a
pitstall should now be determined from the RFM entry "PitGroupOrder", with the first entry extrapolated for
any undefined pitstalls.



rF Config:

•      New Widescreen UI option added for widescreen resolutions, replaces the player file option. Checking
this option will cause the UI and HUD overlay graphics to be stretched to fill the screen in widescreen video
modes.

•     New MultiView option added for triple-head gaming only. Checking this option will use three
viewports with standard FOV instead of one viewport with very wide FOV.



Vehicles:

•     2006 Formula IS - High Performance Open Wheel

•     2005 Hammer - Full Bodied GT

•     2005 Howston - Full Bodied GT

•     National Stock Car - Stock Car

•     2005 Rayzor - Rally Turbo


8
                                                                     9

•     2006 rF3 - Quick and Nimble Open Wheel

•     2005 Rhez - Small FWD Sport Compact

•     2006 Rhez - Small FWD Sport Compact

•     2006 rTrainer - Low Speed Open Wheel

•     2005 Venom - Rally

•     2005 ZR - Affordable High Performance Sedan



Circuits:

•     Barcelona - Permanent Road Course

•     Essington Park - Permanent Road Course

•     Jacksonville Speedway - High Banked Superspeedway

•     Joesville Speedway - Paved Short Track

•     Lienz Festival - Country Roads

•     Mills Metropark - Permanent Road Course with two layouts

•     Northamptonshire - Permanent Road Course

•     Nuerburg - Permanent Road Course

•     Orchard Lake - Banked Tri-Oval with Infield Road Course

•     Sardian Heights - Street Circuit with two layouts

•     Toban Raceway Park - Permanent Road Course with four layouts




                                                                     9
10




10
                                                                                                                  1




PLEASE READ CAREFULLY BEFORE USING THE SOFTWARE:



This End User License Agreement ("EULA") is a legal agreement between you (either an individual or a
single entity) and Image Space Incorporated ("ISI") for the software product "rFactor", which includes
computer software, data files and associated documentation ("Software"). The Software also includes any
updates and supplements to the original Software provided to you by ISI. Any product provided along with
the Software that is associated with a separate end-user license agreement is licensed to you under the terms of
that license agreement. By installing, copying, accessing or otherwise using the Software, you agree to be
bound by the terms of this EULA. If you do not agree to the terms of this EULA, do not install or use the
Software. ISI reserves all rights not expressly granted under this EULA. ISI may update this agreement at
any time and without notice by publishing this update on the rFactor website,
http://www.rFactor.net/legal.html.



GRANT OF LICENSE.

Image Space Incorporated grants to you the right to use one copy of the Software on a single computer. You
may load one copy into permanent memory of one computer and may use that copy only on that same
computer.



LIMITED USE.

Without the prior written consent of Image Space Incorporated, you shall not, directly or indirectly, at any
time:

* Exploit, or permit the exploitation of, this Software or any of its parts commercially.

* Publicly display or permit the display of or charge a fee for the use of this Software or any of its parts.

* Reverse engineer, derive source code, modify, decompile, disassemble this Software, in whole or in part.

* Remove, disable or circumvent any copy protection or proprietary notices or labels contained on or within
the Software.



OWNERSHIP OF THE SOFTWARE.

All title, ownership rights and intellectual property rights in and to the Software and all copies are owned or
expressly licensed by Image Space Incorporated. The rights of the Software are protected by national
copyright laws and by international treaties.



                                                                                                                  1
2



PROPRIETARY INFORMATION.

Any file, information, content, ideas, or other parts relating to this product or its development is proprietary to
Image Space Incorporated.



NO WARRANTY, LIMITATION OF LIABILITY.

ISI HEREBY DISCLAIM ALL WARRANTIES, EXPRESS, IMPLIED AND STATUTORY, INCLUDING,
WITHOUT LIMITATION, THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT OF THIRD PARTY RIGHTS WITH
RESPECT TO THE SOFTWARE PRODUCT. ISI DO NOT WARRANT THAT THE SOFTWARE
PRODUCT IS ERROR-FREE OR THAT ACCESS TO THE SOFTWARE PRODUCT WILL BE
UNINTERRUPTED AND WITHOUT COMPROMISE TO SECURITY SYSTEMS. YOU
ACKNOWLEDGE AND AGREE THAT YOUR USE OF THE SOFTWARE PRODUCT IS "AS IS," AND
"AT YOUR OWN RISK."

ISI WILL NOT BE LIABLE FOR ANY SPECIAL, INCIDENTAL, INDIRECT, OR CONSEQUENTIAL
DAMAGES (INCLUDING, WITHOUT LIMITATION, DAMAGES FOR PERSONAL INJURY, LOSS OF
BUSINESS PROFITS, BUSINESS INTERRUPTION, LOSS OF BUSINESS OR CONFIDENTIAL
INFORMATION, LOSS OF PRIVACY, OR ANY OTHER PECUNIARY LOSS) ARISING OUT OF THE
USE OF OR INABILITY TO USE THE SOFTWARE, EVEN IF ISI HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES. IN ANY CASE, THE ENTIRE LIABILITY OF ISI UNDER THIS
AGREEMENT AND LIMITED WARRANTY SHALL BE LIMITED TO THE AMOUNT ACTUALLY
PAID BY YOU FOR THE SOFTWARE THAT CAUSES THE DAMAGE.



Note: Third-party brands and names are the property of their respective owners.




rFactor (c) 2004-2007 Image Space Incorporated. All Rights Reserved.




2
                                                                                                                1




About the Game:



rFactor is a racing game featuring the latest graphics technology, superb vehicle dynamics, challenging AI,
robust multiplayer, and support for a wide variety of racing formats. Many types of vehicles are available to
drive from 4-cylinder front-wheel drive road cars to V8-powered open-wheel racecars. Tracks include a
mix of oval, road, and street courses.




                                                                                                                1
2




2
                                                                                                                  1




Features:



•      Rules to simulate different types of racing: standing starts, formation laps, rolling starts, racing by time
or laps or both, local or full-course yellows depending on the severity of the accident, etc.

•      Time Of Day (TOD), with headlights and beautiful transitions from day to dusk to night to dawn. Time
scaling allows a full 24-hour transition in as little as 24 minutes.

•     Brand spanking new DX9 graphics with pixel shaders, bump-mapping, etc. Solid DX8 and DX7
support for older cards and/or better framerate.

•      Head physics, cockpit vibrations, detailed bump modeling, and seat adjustments all give the user a
better sense of speed and control.

•      Expanded sound system with incredible unique sounds for most vehicles and engine upgrades.

•     Multiplayer AI, dedicated server with advanced functionality, matchmaking, RaceCast (with live
timing, results, and rankings), plug-in interface. Future support for more league functionality, driver swaps,
downloadable vehicles/skins/tracks, voicechat.

•      Replay Fridge replay system allows AVI creation with effects defined through plug-ins.

•     Camera system include mouse free look and allows you to move anywhere. Each vehicle has custom
cameras.

•      New vehicle upgrade system allows user to buy parts for performance, looks, and/or sound.

•     Improved tire physics and new tire contact calculation, engine boost, support for various types of
suspension including 4-link rear suspensions, other advances in vehicle dynamics.

•      Extensive support for modders.




                                                                                                                  1
2




2
                                                                                                                 1




Controller Setup:



You should take care to set up your basic driving controls - steering, brakes, and throttle. It is also
recommended that you review your Controller Rates, especially Speed Sensitive Steering. For the most
realistic setting using a steering wheel, we recommended a Speed Sensitive Steering value near 0%.
However, inexperienced users or those driving with the joystick or keyboard should try something in the
range of 50-100%.



Note there are some Presets that can be used with different wheel/pedal/joystick setups. Try using one of the
Presets and then customizing if necessary. You can save your current settings as a new Preset and then share
them with other users using the same input devices. The file is saved to UserData/Controller/<preset
name>.ini.



Similarly, you should review your Difficulty settings, as these will affect your driving. Driving aids such as
steering help and braking help cause the game to partially control your steering and braking input. They are
only recommended for novice users who do not know the track layout. Other aids such as Traction Control,
Stability Control, and Antilock Brakes won't guide you around the track, but may help prevent erratic inputs
from destabilizing your vehicle.



There are many features of the game that you can access through the following default keyboard commands:



Insert - Switches between cockpit, roof, and nose cameras on the vehicle

Home - Switches between other onboard cameras

Page Up - Switches to swingman camera

Page Down - Switches to trackside cameras so you can view the race from a spectator's point of view



Number Pad 2 - Moves swingman camera closer to ground

Number Pad 4 - Swings the swingman camera around the car to the left

Number Pad 5 - Resets swingman camera



                                                                                                                 1
2

Number Pad 6 - Swings the swingman camera around the car to the right

Number Pad 7 - Moves swingman camera further from vehicle

Number Pad 8 - Moves swingman camera higher in air

Number Pad 9 - Moves swingman camera closer to vehicle

Number Pad Minus (-) - Changes camera to the vehicle in the next lower place

Number Pad Plus (+) - Changes camera to the vehicle in the next higher place

Number Pad Enter - Returns to your vehicle



F12 - Takes a screenshot and stores it by default off the base rFactor directory as
"UserData\ScreenShots\GRABxxx.JPG".



1 - Vote Yes on a proposal in multiplayer (running on a dedicated server only)

2 - Get ping value to server

3 - Toggle your mirrors on and off (may help framerate)

4 - Toggle the HUD (Heads Up Display) statistics display

5 - Toggle the HUD tachometer display

6 - Toggle the HUD multi-purpose display

7 - Toggle TV overlays

0 - Vote No on a proposal in multiplayer (running on a dedicated server only)

Enter - Cycles through the information displayed on your dash or HUD

Tab - Toggles the driver names above the cars



T - In car chat

B - Look behind you (does not work on all cameras)

V - Look left (does not work on all cameras)

N - Look right (does not work on all cameras)



R - Instant replay. Note that you can use instant replay any time in single-player, but you can only use it at


2
                                                                                                                3

the monitor in multiplayer. Just above the monitor it will say "LIVE" or "Tape Delay" to show you whether
you are watching live action or a replay.



When you are in instant replay mode, the following keys can be used to navigate forward or backward:



Left Arrow - Replay rewind

Control + Left Arrow - Replay rewind fast

Down Arrow + Left Arrow - Replay rewind slow

Up Arrow - Replay stop

Right Arrow - Replay fast forward

Down Arrow - Replay slow motion



There are many other controls and controller options not listed here that you might find useful. Please check
the Controller Assignments page (Customize->Settings->Controls) in the options for a full list of available
controls.




                                                                                                                3
4




4
                                                                                                                    1




Race Options:



Under the Customize icon, click Settings and then click the button to the left of RULES. This page allows
you to customize options for the race. Note that similar options exist when setting up race seasons or
multiplayer races.



Flag Rules affect black and yellow flags. Turning it off completely allows users to do pretty much anything
without getting disqualified. Setting it to Black Only is a good choice if you want players to get penalized or
disqualified for jumping starts, driving backwards on track, etc. Local yellow flags will still be shown if Flag
Rules is set to Black Only, but there will never be full-course cautions. Setting Flag Rules to Full will have
the same rule enforcement as Black Only, but with occasional full-course cautions. By default, there will
need to be at least a couple vehicles blocking the track to enact a full-course caution (see the unsupported
External Options for information about how to tweak the sensitivity for causing full-course cautions).



Fuel Usage sets how quickly fuel is burned up. Turning it off will mean that basically no fuel is necessary to
race (you must start with at least 1 liter, regardless). Normal will burn fuel at a realistic rate. X2 through X7
will cause the fuel to burn at between twice and seven times the realistic rate. This causes more frequent
pitstops, so strategy may be more important in short races.



Tire Usage is similar to Fuel Usage, but works on tire wear.



The default value for Mechanical Failures is "Time Scaled". This means that the rate of wear on the engine
and other components is adjusted based on the length of the race. For longer races, the vehicle automatically
becomes more reliable, so that you have roughly the same chance of finishing a 10-minute race as a 24-hour
race without a mechanical failure. Another setting is "Normal". This is not recommended if you plan on
competing in races longer than two hours, as the normal design of the vehicles in rFactor is to last through a
two-hour race and not much more. Finally you can simply turn Mechanical Failures "Off" altogether. Note
that random variance can cause some vehicles to expire before others - this is true to real-life mechanical
failures.



Private Testing indicates whether you desire to have AIs join you when you select "Testing" under the Control
icon. Setting it to On allows you to be the only car on track. If you get lonely, turn the option Off.




                                                                                                                    1
2

AI Drivers sets how many additional vehicles you will compete against in single player modes (Race
Weekend and possibly Testing if Private Testing is off). Competing against more vehicles gives you a better
chance of earning credits.



Race Grid Position dictates your position on the grid ONLY if the qualifying session is completely skipped.
You can skip the qualifying session by selecting the Race Details tab when going into Testing or a Race
Weekend.



Race Start Time sets the time of day when the race starts. You can set the time to any half-hour or set it to
"Track Default", which will start the race at the typical time for the given track. This option ONLY affects
the race session and testing, not practice, qualify or warmup.



Race Time Scale configures how fast the time of day goes by. The choice "Normal" will have time go by at a
normal rate, where one hour real time equals one hour game time. X2 through X60 will cause the time of day
to appear to pass between twice and sixty time normal rate. For example, one minute real time will cause an
hour of game time to go by at X60. Use this to see the wonderful game transitions between day and night and
back to day again. Another setting is "Use Race %", which will scale the transitions based on how long the
race is set to. If the race is typically 24 hours, but you decide to do 24 minutes, then a whole day->night->day
transition will happen during your race. This option ONLY affects the race session and testing, not practice,
qualify, or warmup.



Type Of Start has four choices: Standing causes the race to be a standing start, where all participants are
parked and accelerate at the green light. Formation/Standing is similar, except that the vehicles do one lap at
reduced speed, park back in their starting locations, and again accelerate at the green light. Rolling starts have
the cars follow the safety car around for one lap. Near the end of the lap, the safety car pulls into the pits
while the other cars head towards the start/finish line at a reduced speed. When the vehicles near the
start/finish line, the green light goes and everybody accelerates. The final Type Of Start setting is Use Track
Default, which will start the race in the default format for the given track (ovals generally use rolling starts
and road courses usually use standing starts).



Race Length Type, Race Laps, and Race Time are all related and affect how long the race will last. If Race
Length Type is "Laps", then the race will last for the number of laps given in the option Race Laps. If the
Type is "Time", then the race will last for the amount of time given in the option Race Time. If the Type is
"Laps and Time", then the race will last for the number of laps or the amount of time, whichever comes first.
If the Type is "% Track Default", then it will again be run by both laps and time, and will be a percentage of
the default race length for the given track.




2
                                                                                                             1




Hardware Plugins:



TrackIR



rFactor features support for Natural Point s TrackIR 3:Pro and TrackIR 4:Pro devices. These devices track a
player s head movement and adjust the position and orientation of the player s viewpoint in game. This
gives the player the ability to look around the rFactor environments, with six degrees of freedom, by simple
turns of the head. Once you have purchased and installed the software that accompanies a TrackIR device, all
you need to enable its functionality is to launch said software, then launch rFactor. At anytime you wish, you
can toggle the TrackIR device on and off by simply pressing the g key on your keyboard. rFactor version
1.070 and associative rFactorTrackIRplugin.dll was tested and developed with TrackIR software version
4.1.028.




                                                                                                             1
2




2
                                                                                                                    1




Monitor:



The monitor is the display you see immediately after loading the track. There are many things to do here
when you are not driving. We will describe the monitor as seen by a multiplayer client (what you will see
after joining a multiplayer game):



In the upper portion of the screen, there is a scrollable list of drivers. Left-clicking your mouse on any driver
will cause the camera to switch to that vehicle. Right-clicking your mouse on any driver will display the full
list of lap times for that driver, if available.



In the lower-left portion of the screen, you may chat with your fellow drivers. Type a message in the black
bar at the bottom and it will be sent to your competitors.



In the lower-left corner of the screen, there are three buttons. These buttons allow you to propose actions and
vote on them when you are connected to a dedicated server (note that some multiplayer games may be on a
non-dedicated server, where the person running that server has complete control over the actions). One
example is when someone would like to move to the next session (from practice to qualifying, qualifying to
warmup, or warmup to race). Hitting the middle button and calling a vote for the next session will give other
clients the opportunity to vote yes or no. If a majority of clients vote yes, then the dedicated server will move
the game to the next session.



At the top of the screen, there are many tabs for options and information to explore. You can visit the garage,
where you can tweak your car to perfection, or you can re-configure your controller/graphical/audio settings.
Note that some of the settings (mostly graphical) are not available from the monitor options because they
cannot take effect immediately. You can also review the server's settings, such as the rules and length of the
race.



In the middle-right portion of the screen, you can see whom you are currently viewing (and change it with the
button if you like). You should also check the current session and how much time is left in it. At the
beginning of the race, it will display the number of laps or length of time (or both) of the race. With that
information you can make a quick adjustment in the garage for fuel before the race starts. Make sure to enter
within 30 seconds or so, or the race will start without you and you will have to start from the pitlane (and wait
until the pit exit goes green).




                                                                                                                    1
2
In the lower-right portion of the screen, you can watch others drive around. Left-clicking on the display
toggles it between almost fullscreen and back. Left-clicking anywhere BESIDES the chat box will also allow
you to use your normal camera and replay keys (see Controller Setup above for more information) to switch to
different vehicles and cameras and rewind/fast forward.




2
                                                                                                                      1




Garage:



At the bare minimum, you should know how to adjust your starting fuel level because having too much fuel in
your tank will slow you down. Hitting the Garage tab at the top of the monitor will take you to the Setups
page where Starting Fuel is the first option. This option shows you the amount of fuel and estimated number
of laps that you can complete with that amount of fuel. If you are qualifying, you generally only need 3 or 4
laps of fuel (one for your out lap, one or two for hot laps, and one for your in lap). For the race, it depends on
whether you can complete the whole race with one tank or not. If so, you should have enough fuel for the
number of laps in the race, plus one in case there is a formation lap, and then maybe a little extra if you plan to
spend some time spinning in the grass. If you can't complete the whole race on one tank, then you'll need
some strategy, configuring up to the first 3 stops of fuel (after that, it will default to repeatedly using the last
stop's amount of fuel repeatedly until the end of the race).



Now that you have a basic idea of how to set your starting fuel, go ahead and save this setup by clicking the
Save button at the bottom. The game will ask for a setup name. We might suggest a format for the setup
name such as "Rhez Race 10 laps" with the car name, what session the setup is for and how many laps of fuel
you have.



If you want a little bit more setup control but don't want to get into the nuts and bolts, try the Basic tab. By
clicking on one of the sliders, you can choose your basic downforce level, gearing bias, balance between
understeer and oversteer, and how stiff or soft you want the ride to be. These will NOT affect your fuel level
(or tire compound, for that matter), so make those choices separately.



If you do want to get into the nuts & bolts, there are many setup guides on the Internet, but we will cover
some of the basics here:



PLEASE NOTE that options that are grayed-out in the garage indicate that they are either not applicable to the
given vehicle, or there is only one available choice. Many of our base vehicles do not allow a lot of tweaking,
because you rarely buy a set of springs with a new car off the dealer lot. Those options are left for upgrades,
which are discussed under Race Season in this readme.



Under the General tab, there are gearing choices. Higher ratios mean better acceleration but lower top speed.
If first gear says "3.45 (13.82)", the first number is the actual gear ratio, and the second number is the ratio
after being multiplied by the final differential ratio. The final differential ratio affects all gears at once. The
graph in the upper-right will help you see how this affects the speeds in each gear. In 1st gear, the engine

                                                                                                                      1
2
RPM rises quickly with speed, and then drops as you shift into 2nd gear. It then rises at a slightly slower rate
until dropping for the shift into 3rd, etc.



A good start is to make sure that 1st gear accelerates you satisfactorily off the line. The second step is to get
the car to get close to peak revs in the highest gear right at the end of the longest straight. After that, the gears
should be fairly evenly spread (you can use the graph to visualize this), with the 1st->2nd shift causing a
somewhat bigger rev drop than the 4th->5th shift. To really optimize the gearing from there, you need to
think about acceleration out of important corners on the track, which is a bit beyond the scope of this
document.



Under Engine, you can adjust the Rev Limit. Higher rev limits sometimes boost your car's acceleration
slightly but cause the engine to be less reliable. The Radiator Size will affect engine cooling - a bigger
radiator will keep the engine cool and reliable, but will hurt your aerodynamics. Boost Mapping can again
increase engine power but be less reliable. Engine Brake Mapping will affect how much the engine helps
slow down the car - lower numbers result in MORE engine braking, which also uses less fuel. The downside
is that the engine only slows down the driven wheels, which can cause a braking imbalance between high and
low speed.



Under Weight, the main thing to note is the Lateral weight adjustment. If it is available, and you are on an
oval, you will want to move the weight as far as possible to the inside tire, generally the left side.
Front-to-rear weight distribution and wedge are more complex and beyond the scope of this document.



Under Aerodynamics, you can adjust the front and rear downforce (if available). More downforce in general
will help you go around corners faster, but will result in more drag and less speed on the straightaways. The
balance between front and rear downforce will directly affect your car's understeer/oversteer balance,
especially in high-speed corners. More front downforce and less rear downforce will tend towards oversteer,
and vice versa.



Steering Lock is mostly intended to allow users another way to configure their wheel's sensitivity. The
maximum angle that your front tires will turn at any one point, though, is dependent on several factors, of
which this is only one. Speed Sensitive Steering (in the Controller options) will reduce steering lock at higher
speeds, unless set to 0%. There is also a feature that gives full steering lock at low speeds to help navigate the
pitlane without hitting walls or other vehicles.



Under Brakes, the Brake Bias affects how much the front wheels are braking vs. how much the rear wheels
are braking. If you are locking up the front tires a lot or get too much understeer when applying the brakes,
you will want to shift the braking to the rear, and vice versa. Brake Duct Size will affect the brake cooling.
Hot brakes wear faster and you can even lose your brakes completely if they get too hot. The downsize to
bigger brake ducts is that they hurt the car's aerodynamics. Brake Pressure allows you to configure the brake
sensitivity. If you find you are locking up wheel too much, you should either go easier on the brake pedal or
reduce the Brake Pressure setting. Reducing the Brake Pressure setting can result in less braking, though, so
the best overall solution is to learn how to modulate the brake pedal to maximum effect. The Handbrake


2
                                                                                                                3

Pressure applies similarly to vehicles that are equipped with handbrakes.



Under Differential Lock, there are different ways of configuring how much the differential tries to lock the
driven wheels together. This is a complex subject and is beyond the scope of this document.



Under the Suspension tab, you will find many different options for controlling the suspension at each wheel of
the car. The first thing to note is the Symmetrical option. For ovals, you will definitely want to set this to No.



In general, softer suspensions have more instantaneous grip. You can apply this rule to help balance the car
through turns. If you want less understeer (or more oversteer), you can either soften up the front suspension
or stiffen up the rear, and vice versa. The downside to soft suspensions is that they are generally slower to
react and harder to control. Furthermore, soft suspensions can mess up today's finely tuned aerodynamics.



How do you soften up the suspension? Smaller anti-roll bars, lower spring rates, and less damping (which
comes under the names Slow/Fast Bump/Rebound). Need more grip on the rear tires coming out of the
turns? Try a smaller rear anti-roll bar.



For packers and ride height, you generally want to have the car as low as possible without hitting the ground
much. Packers are used to stiffen up the suspension ONLY when the car is close to bottoming out, so they
can be used to prevent hitting the ground even using low ride heights. The downside is that handling can
change radically when the suspension hits the packers.



Setting tire pressures and camber is very important to optimize your setup. For setting tire pressures and
cambers, you will mostly want to rely on the tire temperatures. You should drive for several laps to get the
tires up to operating temperature, and then come back to the garage. On the suspension page, each tire shows
the left-side, middle, and right-side temperatures when you left the track. If the temperature in the middle is
hotter than the sides, then you want to lower the pressure, and vice versa. If the left side is hotter than the
right side, then you will GENERALLY want to adjust camber to even them out. Negative camber means the
tire tilts inwards at the top. For normal road racing, all the tires usually use negative camber, which means the
left-hand tires tilt to the right and the right-hand tires tilt to the left. You should note that tires produce
slightly more cornering force when cambered, so you will actually want the inside edges of your tires a few
degrees hotter than the outside edges. For oval racing, you will generally want all the tires to tilt in the
direction of the turn. That generally means the left-side tires get positive camber, and the right-side tires get
negative camber.



The Advanced tab in the garage is beyond the scope of this document.




                                                                                                                3
4




4
                                                                                                                1




Replay Fridge:



rFactor features a brand new replay system, where you can create your own videos. You will find the Replay
Fridge under the Control icon in the main options. On that page, you will find some replay options at the top
of the screen. And assuming you have already run at least one race, you will find a list of replays to choose
from in the left pane and the bottom of the screen.



Clicking on a replay will bring up information about it in the right pane. If you have found a replay you want
to watch or edit, click the Play Replay. You also have the option of manually deleting or renaming replays.
By default, the replay system stores the last 5 replays at each track. If you don't want rFactor to ever delete a
specific replay, you must rename it to something without the full track name.



Once you have started up a replay, you can play it using the standard VCR controls. Maximize the screen for
a better view. If you want to toggle the onscreen graphics off, hit the Enter key.



To edit a replay:

•     Click in the middle of the long bottom window. Then use the Split button.

•     You now have two clips. You can continue to create more.

•     Clips can be moved, copied or deleted.

•     Each clip is like a piece of an editor's film, but much more powerful as the image on it is not fixed.

•      In each clip you can specify a vehicle to focus on and a camera to switch to (please note, however, that
free-look cameras are not currently supported).

•      Specifying and arranging these clips, you can create dramatic films switching to the right car at the
right moment using the right camera.

•     When complete save your creation to a movie format to share with your friends.

•     Experiment, it's fun.



If you want to create a video, first check the Output Settings. When you are ready, press the Export button.
Note that exporting a video takes a long time - a 30-second clip may take a half-hour or more to create. The

                                                                                                                1
2
quality and amount of time taken depends on the video codec used. You can change the video codec by
opening your player file (found by default at UserData/<your name>/<your name>.PLR) and changing the
setting for "AVI compressor fourcc". It must be a fourcc video codec - you can find out more information
about this standard (and available codecs) at fourcc.org. Note that very few of the codecs seems to be affected
much by the Quality setting in the Output Settings.




2
                                                                                                                 1




Multiplayer Client Setup:



To simply join an Internet game for the first time, you should first set up your connection. Go to Settings
under the Connect icon on the main page. Pick the Connection Type that is equal to or less than the real
connection you have. For example, if you have a Cable or DSL line with 192kbits upload capacity, we
recommend choosing the Cable/DSL 128K Up selection.



If you have tested your connection and know that your precise upload and download capacity is not
comparable to one of the existing Connection Types, then choose Custom and specify those capacities directly
in Upload Rating and Download Rating.



Warning: picking a connection type faster than what you actually have will likely lead to a unsatisfactory
multiplayer experience.



After you have set up your connection, click Join under the Connect icon. A list of games should appear
showing the Game Name, the Circuit, the number of Players out of the maximum allowed, and finally the
Ping. Just to clarify, the Ping is not your ping to the server. Rather, it is the average ping of the players that
are currently connected (and 0 if nobody is connected). Lower pings (under 150 or so) indicate that the server
has a good connection to its existing clients.



To get more information about a particular game, simply click on it. At the bottom of the screen, there are
three tabs, each of which has information about the game you have clicked on. A lock beside the name of the
game indicates there is a password (meaning that the server has probably invited specific people to join).
Another important piece of information is which Race Series (rFm) is being run. The two series that ship with
the game are SR Grand Prix Season and the Open Wheel Challenge, which were described earlier in this
document. If you may want to race a particular type of car, also check under the News/Info tab for the
Allowable Vehicles.



Back under the Settings tab, you will see which driving aids are allowed. A green box indicates that you are
allowed to use the given driving aid. If you depend on Traction Control to get around the tracks, it is
recommended that you not join games that disallow Traction Control.




                                                                                                                 1
2
You should also check the current Session that the game is in. You cannot currently join a game that is
already in the Race session. The Laps Remaining and Time Remaining show you how much longer the
current session will last (unless the participants or server choose to change sessions before it ends). The Flag
Rules are described elsewhere in this document, and the Damage Multiplier tells you how realistic the damage
is. 100% is realistic, 50% is pretty forgiving, and 0% causes no damage at all.



Under the Advanced tab, the only current important piece of information is the Data Rate of the server.
Higher data rates (1000+ kbps) indicate that the server can handle many cars with good quality. Finally, other
miscellaneous information can be found under the News/Info tab.



If you have decided on which game to join, go ahead and click it and then click Load Game at the
bottom-right hand corner of your screen. At that point you will need to choose a vehicle that matches the
server's Allowed Vehicles. When you are done, click Load Circuit and you will be in the game.



More information about participating in multiplayer games, including voting, is covered above in the Monitor
section.




2
                                                                                                                1




More Multiplayer Features:



On the Join page (found under the Connect icon in the main options), you will find three tabs at the top -
Server List, Friends List, and Chat. The Server List is where you are taken to by default and lists the games
you can join.



Under Friends List, you can specify friends by their profile name and clicking the Plus icon to add them.
Later on, you will be able to see which of your friends are racing right now. In the right pane you will see
games you have bookmarked. Once you are in a race, you can bookmark the server by pressing the call-vote
button in the bottom-left portion of the monitor and then pressing the "Bookmark" button. From then on, just
go to the Friends List, pick the bookmarked server and hit Join Race.



Under Chat, you can participate in rFactor chats using IRC. Simply hit Connect, and assuming your
nickname is not already taken (it defaults to your profile name) you will be able to chat with anybody listed in
the lower pane.



On the multiplayer Settings Page (found under the Connect icon in the main options), you will see RaceCast
settings in the lower part of the screen. RaceCast is an exciting new feature that allows you to watch live
timing, find games, and view results and rankings. To enable RaceCast to keep your statistics, you must first
register with RaceCast by typing in an e-mail address and password, then clicking the "RC Register" button.
If Registration succeeds, you can then press the "Sign on Racecast" button to sign on. When RaceCast is
activated, the Racecast Status indicator will light up green. From then on, the game will attempt to log in
automatically whenever you start up. To view results and so forth, open up your web browser and go to
racecast.rfactor.net. You will need to log in using your profile name (not the e-mail address) and password
that you registered with.




                                                                                                                1
2




2
                                                                                                                1




Multiplayer Server Setup:



There are two types of servers - dedicated and non-dedicated. Dedicated servers are run using the rFactor
Dedicated executable. This type of server does not have any graphics or sound and can run on a fairly
low-end machine (because of low CPU and memory usage). It can respond to and transmit networking
messages much quicker than a non-dedicated server. On the other hand, non-dedicated servers are set up
through the normal game, by clicking on the "Create" button under the Connect icon in the main options. On
non-dedicated servers, the host can race with the clients. The host of a non-dedicated server is also in
complete control of the game flow - the clients cannot vote to change sessions or add AI.



To run a server, you may first have to make sure it works with your firewall. With a non-dedicated server,
there is actually a Firewall Test button that you can use. In fact, in order to Announce your non-dedicated
server to the Internet, you MUST pass this Firewall Test first. It is on the multiplayer Settings page (under the
Connect icon in the main options). For further help with firewall issues and setting up ports, please consult
the FirewallGuide in the Support directory where rFactor was installed. If you still do not see your game on
the Internet, make sure the "Matchmaker Announce" option is enabled.



It is very important to set up the bandwidth options for a server. You can find information about Connection
Types and Upload/Download Speeds at the top of the Multiplayer Client Setup section. However, the server
has more considerations than the clients when setting these options up. For one thing, the upload capacity is
much more important for a server than the download capacity.



Note that by default, rFactor will use as much bandwidth as allowed to create the highest quality multiplayer
experience possible given the connection. The bandwidth allowance is determined by a combination of the
server and client's connection options. More to the point, just because your connection can support 1000
kbits/sec (1Mbit) doesn't mean you should configure rFactor to use 1000 kbits/sec. If you plan on running
several rFactor servers, or want some extra bandwidth available for other uses (web-browsing and other
networking applications), you should reduce the connection type and/or "share" the upload/download speeds.
For example, if you want to run 4 rFactor servers sharing a 5000 kbits/sec (5Mbit) upload connection, then
each server should be configured to use no more than (5000/4) = 1250 kbits/sec. While we are talking about
multiple rFactor servers running on the same machine, it should be noted that each one should use a separate
profile (or "player file"), otherwise options may get mixed up between them.



Another way of limiting bandwidth is only available through editing the multiplayer configuration file (found
by default at UserData/<your name>/multiplayer.ini). You can limit bandwidth on a per-client basis by
changing the Max Data Per Client setting. For example, say you have some clients joining with cable
connections (let's say 256kbit connections) and others joining using ISDN (64kbit). You may want everyone

                                                                                                                1
2
to experience the same connection type to your server, so you could change the Max Data Per Client to 64,
which will limit even the cable clients' connection to be the same as the ISDN clients. Clearly, you can then
easily calculate the maximum upload bandwidth you will be using. With 15 clients, you will be using no
more than 15 * 64 = 960 kbits/sec. You might note that if this exceeds the Upload Speed you configured,
bandwidth will be limited to the Upload Speed instead.



Servers have many options available to them. One of the first and most important is what Race Series (or
"game database") to use, which will partially dictate what vehicles and tracks can be used. After that, you will
want to set up the vehicle filters to allow only the vehicles you want. Vehicle filters were discussed above in
the "Gameplay Summary" section.



Selecting "RaceCast" (dedicated server) or "Post On RaceCast" (non-dedicated server) will have the timing
and other information sent to RaceCast so others can view the race results on your server.



There are many other options, such as which driving aids to allow, various race options and so forth that you
will encounter, and most are discussed elsewhere in this document. We would also like to point out some
options in the multiplayer configuration file. For dedicated servers only, you can configure the voting so it is
not too easy or too hard to change sessions, add AI, restart races, etc. For these and other options, please look
under the "External Options" section later in this document.



Finally, once the server is set up and clients have joined, you have the option of booting or banning people for
poor behavior. Booting people is temporary - the player could simply choose to re-join the server
immediately assuming the race session hasn't started. Banning people puts their IP in a list and prevents them
from re-joining. The full list of banned IPs is stored by default in UserData/<your name>/bans.xml, so you
can share it with friends or edit/delete it at a later time.




2
                                                                                                                 1




Command Line Options:



Some people may find a need to use one of our command-line options. To use command-line options, create
a shortcut to the executable (rFactor.exe for the normal game and rFactor Dedicated.exe for running a
dedicated server). Right-click on the shortcut and select Properties. Add one or more of the following
command line switches at the end of the Target:



trace=<1-3>              // this generates a file whose default location is UserData/Log/trace.txt that may be
helpful in diagnosing problems with running the game.

config=<file>              // run game using a config file different than the default config.ini

perfhud                  // testing/debugging graphics

+profile "<name>"           // this will run the game with the given player file name.

+oneclick                 // this allows a dedicated server to start up and load a track without user
intervention.

+host                    // auto-host (unsupported?)

+gamename "<name>"           // set auto-hosted game name

+password "<pswd>"          // set auto-hosted game password

+maxplayers <num>           // set auto-hosted maximum number of players

+connect <address:port> // auto-join at given address & port. If port given is 0, will use multiplayer.ini
value "Query Port Start".

+fullproc               // use dual processors if available (should only be used with Microsoft s dual
processor fix for Windows XP SP2)

+nosound                  // completely disable sound to diagnose problems




                                                                                                                 1
2




2
                                                                                                                 1




Modding:



While rFactor is very open to modding, there is some basic information that you should know before doing
so. First off, it's done completely at your own risk, as is downloading mods from other people.



Second, if you wish to modify existing tracks and vehicles, you should NOT touch any information that can
affect physics in any way. Doing so will prevent you from joining multiplayer races. This includes GDB
files, RFM files, much of the SCN and MAS files (any geometry that affects physics), HDV files, parts of the
VEH (such as the HDVehicle and Upgrades entries), TBC files, PM files, *gears.INI, *engine.INI, and parts
of the *upgrades.INI (any HDV= line, for example).



If you absolutely must change one of the above (for participation in a league for example), we would
recommend that everybody that you will be racing against save off the original and then get a copy of the
changed file. If anybody's version doesn't match the server's version, then that person can't join.



The basic structure of rFactor starts with the rFm files in the RFM directory, which define separate race
series. In it you will find filters for which tracks and vehicles to allow. The special * symbol is a wildcard
which will allow everything. These filters are used to compare against entries in the track GDB files ("Filter
Properties") and vehicle VEH files ("Classes"). When you pick or change the Race Series in game, it will
load only the tracks and vehicles appropriate for the new Race Series.



The rFm file also contains scoring info and seasons that you can race. While the original release version of
rFactor doesn't include any examples, you can create your own seasons without editing the rFm file. You do
this by creating a file ending in .AOS (for Add-On Season). Its contents should look something like this:



RFM = SR Grand Prix Season // this must match the name of an existing race series

Season = MySeason // must be 19 character or less

{

    FullSeasonName = Super Multi-Class Racing Challenge // name override

    SceneOrder    // order of events in the season



                                                                                                                 1
2

    {

        Mills_Long   // name from the top of an existing track GDB

    }

}



You can also add other information to the above (new points systems, different credit earnings, etc.) - just
look for examples from the existing rFm files to see what can be done.



More extensive modding (new skins, 3d models, physics) is unfortunately beyond the scope of this document.




2
                                                                                                            1




Performance Tuning in v1.250:



CPU / System Memory:

rFactor is designed to run on a wide range of intel and AMD CPUs. Using the minimum CPU requirements
of 1.0 GHz Pentium III (or AMD equivalent), with 256 MB free system memory, will just get you running at
the lowest settings. For the best racing in large fields with decent visuals, we recommend at least a 2.8 GHz
Pentium 4 (or AMD equivalent), and at least 1.0 GB system memory. This would be a mid-range machine by
today s HW standards.



Hyperthreading:

Based on our testing, running with Hyperthreading enabled offers little performance advantage.



Multi Core CPUs:

rFactor can take advantage of multiple core CPUs with the +fullproc command line option.



To avoid possible erratic timing problems, due to automatic CPU frequency adjustments made by the
operating systems, you can try the following solutions:



1.  For single-core CPUs (including those running with Hyperthreading), do not use the +fullproc
command-line option.

2.   For multi-core CPUs, make sure you have the very latest service packs for your operating system.

3.   For those using WinXP, add the /usepmtimer option to your Windows startup options, as follows:




                                                                                                            1
2




2
                                                                                                                   3



Video Card:

rFactor will run on a large range of video cards, from older DX7-level cards to the latest DX9 models. Using
the minimum video card requirement of a 64 MB DX7 card will seriously restrict your graphical details, and
the number of cars you can run. We recommend a mid-range DX9-level card with at least 128 MB video
memory, which are commonly available for under $100. While graphics performance has been significantly
enhanced in the latest version of rFactor, there are numerous settings and techniques for further optimizing
your graphics performance. This information may not apply to previous versions of rFactor, and is applicable
only to the content supplied with rFactor. Third-party mods may require different (often more conservative)
settings.



Video Card Memory:

The most common cause of low graphics performance is too little video card memory. We recommend a
video card with at least 128 MB of video memory. Both AGP and PCI-E interfaces will allow some
additional system memory to contribute to the total video memory available, which is reported on the main
dialog of the rF Config program.



For the AGP interface, you can usually specify the maximum amount of additional memory through the AGP
Aperture setting in your system BIOS. Optimal aperture settings are 64 or 128 MB. Settings below 64 MB
are too low to add much memory, and even on cards with large amounts of onboard RAM, can actually cause
performance problems. Settings above 128 MB may also cause performance to actually be lower. The ideal
AGP aperture setting is 128 MB.



For the PCI-E interface, the maximum amount of additional memory is usually determined automatically, and
in most cases this value is sufficient.



rFactor manages texture memory usage with an auto-reducing mechanism, which lowers the resolution of
most textures in an attempt to free up additional video memory. This auto-reducing mechanism is only
activated in critical situations to keep frame rates from dropping to unplayable levels, and is not meant to be
used as an automatic detail setting. When this mechanism is first activated, most textures are reduced in size
by one power of two in each dimension, and the free memory indicator changes from green to yellow. If it is
necessary to reduce textures a second time, the free memory indicator changes from yellow to red. If your
free memory indicator is always yellow or red, this is an indication that your display settings are too high for
your video hardware. You should either reduce your detail settings, or get a new video card with more
memory.



When using the highest texture and object settings (Full), you may experience very slow loading. This is
usually a sign of insufficient memory, either video or system. The usual solution is to reduce one or more
detail settings. To run all settings on Full, you should have a minimum of 1.5 GB of system memory, and at
least 256 MB of video memory.



                                                                                                                   3
4



It is important to base your display detail settings on actual video card memory, not on the total reported
amount. PCI Express video cards, in particular, often reserve extra memory of two to three times the actual
onboard video memory. Using substantial amounts of off-card memory will allow lots of resources to be
loaded, but can cause serious performance problems. Based on the actual amount of onboard video memory,
some common-sense guidelines are appropriate:



•     Above 256 MB: All display settings can be run at Full.

•     256 MB:          Track and texture settings can be run at Full, Player and Opponent detail should be
High.

•     128 MB:          All settings should be set to High.

•     64 MB:         Most setting should be set to Medium.

•     Below 64 MB:      Not supported by rFactor



The following graphics detail settings have the most impact on memory usage, in order of most to least
impact:



1.   Opponent Detail

2.   Texture Detail (applies to non-vehicle textures)

3.   Track Detail

4.   Player Detail

5.   Special Effects Detail



Graphics Shader Level:

rFactor supports three shader levels, DX7, DX8, and DX9, each providing improved visuals at the expense of
performance. The available detail levels, as reported in the rF Config program, are dependent on you video
card. For most newer video cards (those produced within the last year), the DX9 shader level will run at
nearly the same performance as the lower levels, while offering the best visuals.



Full Screen Anti-Aliasing (FSAA):

There are two ways to set FSAA in rFactor. The first method is through the Display Control Panel, usually
accessed by a right-click on the desktop. The other method is with the rF Config program (the preferred
method), which gives the best performance, since this will use FSAA only on the frame buffer, and not on any


4
                                                                                                                5

other surfaces such as rear view mirror, shadows, or HUD displays. When set from the control panel, FSAA
is applied to all of the previously mentioned surfaces, resulting in more smoothed features at the expense of
lower performance. Using FSAA can consume large amounts of video memory, contributing in another way
to lower performance on older video cards.



Anisotropic Filtering (AF):

Anisotropic filtering can also be set from either the Display Control Panel, or from inside the rFactor in game
Display Settings. Again, the preferred method is to set AF inside the game, as it is applied to all textures that
do not have a per-texture AF setting. Set from the control panel, the AF setting overrides per-texture AF
levels, and is applied to all textures, including shadows and HUD displays.



MIP Map LOD Bias:

Many track textures use a small negative MIP Map LOD bias to avoid overly blurred textures, particularly
road and road line textures. Using the setting Clamp Negative MIP Map LOD Bias will disable these bias
settings, resulting in excessive texture blurring, but slight additional performance.



SLI / Crossfire:

Several performance enhancements have been added to rFactor v1.250 to improve SLI / Crossfire
performance. The recommended SLI mode for rFactor is Alternate Frame Rendering (AFR) mode, although
it should also run properly in Split Frame Rendering (SFR) or AFR2 modes.



Dual-head gaming:

Running rFactor in dual-head mode is possible on both ATI and nVidia video cards with dual outputs, either
15-pin VGA or DVI. No additional hardware is required. In both cases, you must have an extra monitor
already plugged in to the second output. To enable dual-head mode from Windows XP:



ATI: From the Catalyst Control Center, select Displays Manager, right-click on the second monitor (whether
it is disabled or extended) and select Stretch Main horizontally onto monitor. This will extend your desktop to
the second monitor. Several new double-wide resolutions (such as 2048 x 768) will now be available for both
the desktop, and rFactor.



NVidia: From the nVidia control panel, go to the nView Display Settings page, set the nView Display Mode
to Horizontal Span. This will span your desktop across both monitors. Several new double-wide resolutions
(such as 2048 x 768) will now be available for both the desktop, and rFactor.



All dual-head modes are treated as widescreen (not multi-head) modes. Therefore, you may use either


                                                                                                                5
6
widescreen or standard (4:3) overlays. Multiple viewports are not available. The UI and HUD overlays were
designed for standard (4:3) resolutions, so it is recommended to not use Widescreen overlays, as this will
stretch (and distort) the UI and HUD overlay graphics to fill the entire screen.



Display spanning/stretching is not yet available in Windows Vista. This capability may be offered in a future
driver update.



Triple-head gaming:

Running rFactor in triple-head mode is possible on both ATI and nVidia video cards with the TripleHead2Go
(TH2G) adapter from Matrox Graphics. Visit the Matrox TripleHead2Go Website for compatibility and
operational information. The TH2G sits between your video card and your monitor(s), and presents a limited
range of new triple-wide screen resolutions to your video card via the Surround Gaming Utility. Additional
resolutions are available with the add-on Mode Expander Tool. Your video card, your monitor, and the TH2G
determine the available resolutions for triple-head gaming. rFactor will support any screen resolution
presented by the hardware.



In triple-head mode, rFactor can operate in either single-view or MultiView mode. In either case, the UI and
HUD overlays are always presented in standard (4:3) mode in the center screen only.



Single View: a single viewport with a very wide field-of-view (FOV) is used for higher performance. The
FOV is set from the UI display options, and the actual FOV used is 3 times the displayed setting (i.e., for a
display setting of 52°, the actual FOV used is 156°). Avoid FOV settings beyond about 58° (174° actual) as
this will cause a severe fisheye distortion effect.



MultiView: three viewports with standard field-of-view are used. This mode is preferred for multi-monitor
setups, but does require more powerful hardware to achieve playable framerates. Each viewport uses the FOV
settings from the UI display options, so you can easily achieve a total FOV of well over 200° and higher with
no fisheye distortion. When using this mode, it is best if your monitors are angled in proportion to the FOV,
at an angle of (FOV / 2).



MultiView mode now operates properly from any camera, including trackside cameras. The Replay Fridge
will only operate in the center screen, even in full screen mode. AVI export does not yet support double- or
triple-wide output.




6
7




7
8




8
                                                                                                                1




Known Issues:



•     Some software products may interfere with the normal startup procedure or multiplayer capabilities.

•       In some cases VET anti-virus software will cause the rFactor startup procedure to take an exceptionally
long time. If rFactor seems to be stuck on the rFactor logo screen and you have VET anti-virus installed, at
this time the only known work around is to uninstall VET.

•      Setting Force Feedback Effects to anything higher than Low on a Microsoft wheel may result in a loss
of forces after going over curbs. There are now two possible workarounds, both of which reset the force
feedback effects on the fly. The first is a Controller Mapping "Reset FFB" that you can use to manually reset
the force feedback. The second is a controller.ini option which can be used to reset the force feedback
automatically every X seconds. To enable it, open the file UserData//controller.ini and change the value of
"Reset FFB Time".




                                                                                                                1
